"""Staff login and logout."""
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from .. import db
from ..auth import hash_password, is_password_hash, password_column_fits_hash, verify_password
from ..settings import ADMIN_ROLES

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'GET':
        if 'user_id' in session:
            return redirect(url_for('main.dashboard'))
        return render_template('auth/login.html')

    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    if not email or not password:
        return render_template('auth/login.html', error="Please fill in both email and password fields.")

    try:
        user = db.query_one("SELECT * FROM users WHERE username = %s", (email,))
        if not user or not verify_password(user['password'], password):
            return render_template('auth/login.html', error="Invalid email or password. Please try again.")

        if str(user.get('status') or '').lower() == 'inactive':
            return render_template('auth/login.html',
                                   error="This account is inactive. Please contact the administrator.")

        if user['user_type'] not in ADMIN_ROLES:
            return render_template('auth/login.html', error="Invalid user type. Please contact administrator.")

        # Upgrade an old plain-text password to a secure hash
        if not is_password_hash(user['password']) and password_column_fits_hash():
            db.execute("UPDATE users SET password = %s WHERE login_id = %s",
                       (hash_password(password), user['login_id']))
            db.commit()
    except Exception as e:
        current_app.logger.exception("Login failed: %s", e)
        return render_template('auth/login.html', error="A server error occurred. Please try again later.")

    session.clear()
    session['logged_in'] = True
    session['user_id'] = user['login_id']
    session['username'] = user.get('username') or email
    session['name'] = user.get('name') or session['username']
    session['user_type'] = user['user_type']
    session['admin_id'] = user['login_id']
    session['admin_name'] = session['username']
    return redirect(url_for('main.dashboard'))


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.user_login'))
