"""Staff logins: list, add/edit, delete."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .. import db
from ..auth import current_user, password_for_storage, require_login, verify_password
from ..helpers import DELETE_METHODS, page_args, pagination

bp = Blueprint('users', __name__)
bp.before_request(require_login)


def _visibility_filter(user):
    """Admins can't see super-admins; employees only see themselves."""
    if user['user_type'] == 'admin':
        return " AND user_type IN ('admin', 'employee')", []
    if user['user_type'] == 'employee':
        return " AND login_id = %s", [user['id']]
    return "", []


@bp.route('/login/logins')
def manage_logins():
    user = current_user()
    page, per_page, offset = page_args(request)
    filter_type = request.args.get('filter', 'all')
    search_name = request.args.get('search', '')

    where, params = _visibility_filter(user)
    if filter_type != 'all' and not (user['user_type'] == 'admin' and filter_type == 'super-admin'):
        where += " AND user_type = %s"
        params.append(filter_type)
    if search_name:
        where += " AND (name LIKE %s OR username LIKE %s)"
        params.extend([f'%{search_name}%', f'%{search_name}%'])

    total_records = db.query_value("SELECT COUNT(*) FROM users WHERE 1=1" + where, params)
    users = db.query_all("""
        SELECT login_id, user_type, username, name, gender, mobile_no, status,
               DATE_FORMAT(created_at, '%d/%m/%Y %h:%i %p') AS last_login,
               DATE_FORMAT(updated_at, '%d/%m/%Y %h:%i %p') AS updated_at_formatted,
               CASE user_type WHEN 'super-admin' THEN 'Super Admin' WHEN 'admin' THEN 'Admin'
                              WHEN 'employee' THEN 'Employee' ELSE user_type END AS user_type_display,
               CASE WHEN status = 'active' THEN 'Active' ELSE 'Inactive' END AS status_display,
               UPPER(LEFT(name, 2)) AS initials,
               'System' AS created_by
        FROM users WHERE 1=1""" + where + " ORDER BY created_at DESC LIMIT %s OFFSET %s",
        params + [per_page, offset])

    counts = db.query_one("""
        SELECT COUNT(*) AS total,
               SUM(user_type = 'super-admin') AS super_admin,
               SUM(user_type = 'admin') AS admin,
               SUM(user_type = 'employee') AS employee,
               SUM(status = 'active') AS active
        FROM users
    """)
    counts = {k: int(v or 0) for k, v in counts.items()}

    return render_template('users/logins.html', users=users, current_user=user, counts=counts,
                           pagination=pagination(page, per_page, total_records),
                           current_filter=filter_type, current_search=search_name)


@bp.route('/login/add', methods=['GET', 'POST'])
def add_login():
    user = current_user()
    user['user_type'] = user['user_type'] or 'employee'
    login_id = request.args.get('id', type=int)
    edit_mode = login_id is not None

    def form_page(user_data):
        return render_template('users/add_login.html', edit_mode=edit_mode, user_data=user_data, current_user=user)

    user_data = None
    if edit_mode:
        user_data = db.query_one("SELECT * FROM users WHERE login_id = %s", (login_id,))
        if not user_data:
            flash("User not found.", "error")
            return redirect(url_for('users.manage_logins'))
        if user['user_type'] == 'admin' and user_data['user_type'] == 'super-admin':
            flash("You cannot edit Super Admin accounts.", "error")
            return redirect(url_for('users.manage_logins'))
        user_data = {k: v for k, v in user_data.items() if k != 'password'}

    if request.method == 'GET':
        return form_page(user_data)

    form = request.form
    full_name, username, password = form.get('fullName'), form.get('username'), form.get('password')
    login_type, status, phone = form.get('loginType'), form.get('status'), form.get('phone')
    gender = (form.get('gender') or '').capitalize() or None  # stored as Male / Female / Other

    if user['user_type'] == 'admin' and login_type == 'super-admin':
        flash("You cannot create or promote Super Admin accounts.", "error")
        return form_page(user_data)

    if not edit_mode:
        if not all([full_name, username, password, login_type, status, phone, gender]):
            flash("All fields are required for new login.", "error")
            return form_page(user_data)
        if db.query_one("SELECT login_id FROM users WHERE username = %s", (username,)):
            flash("Username already exists. Please choose another.", "error")
            return form_page(None)
        db.execute("""
            INSERT INTO users (user_type, username, name, password, gender, mobile_no, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (login_type, username, full_name, password_for_storage(password), gender, phone, status))
        db.commit()
        flash("New login added successfully!", "success")
        return redirect(url_for('users.manage_logins'))

    # Edit: only update the fields that changed
    if username and username != user_data['username'] and \
            db.query_one("SELECT login_id FROM users WHERE username = %s AND login_id != %s", (username, login_id)):
        flash("Username already exists. Please choose another.", "error")
        return form_page(user_data)

    stored_password = db.query_value("SELECT password FROM users WHERE login_id = %s", (login_id,))
    changes = {}
    for column, value in [('name', full_name), ('username', username), ('user_type', login_type),
                          ('status', status), ('mobile_no', phone), ('gender', gender)]:
        if value and value != user_data[column]:
            changes[column] = value
    if password and not verify_password(stored_password, password):
        changes['password'] = password_for_storage(password)

    if not changes:
        flash("No changes were made to the login.", "info")
        return redirect(url_for('users.manage_logins'))

    sets = ', '.join(f"{column} = %s" for column in changes) + ", updated_at = NOW()"
    db.execute(f"UPDATE users SET {sets} WHERE login_id = %s", list(changes.values()) + [login_id])
    db.commit()
    flash("Login updated successfully!", "success")
    return redirect(url_for('users.manage_logins'))


@bp.route('/login/delete', methods=DELETE_METHODS)
def delete_login():
    login_id = request.values.get('id', type=int)
    if session.get('user_type') != 'super-admin':
        flash("Only Super Admin can delete logins.", "error")
        return redirect(url_for('users.manage_logins'))
    if not login_id:
        flash("No login ID provided.", "error")
        return redirect(url_for('users.manage_logins'))

    target = db.query_one("SELECT user_type FROM users WHERE login_id = %s", (login_id,))
    if not target:
        flash("User not found.", "error")
    elif target['user_type'] == 'super-admin':
        flash("Super Admin accounts cannot be deleted.", "error")
    else:
        db.execute("DELETE FROM users WHERE login_id = %s", (login_id,))
        db.commit()
        flash("Login deleted successfully.", "success")
    return redirect(url_for('users.manage_logins'))
