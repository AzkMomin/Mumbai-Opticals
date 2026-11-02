"""Login checks, roles and password handling."""
import secrets
from functools import wraps

from flask import flash, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .settings import ADMIN_ROLES

PASSWORD_HASH_METHOD = 'pbkdf2:sha256'
_password_column_length = None


def current_user():
    return {
        'id': session.get('user_id'),
        'username': session.get('username'),
        'user_type': session.get('user_type'),
        'name': session.get('name'),
    }


def is_logged_in():
    return 'user_id' in session


def is_admin():
    return session.get('user_type') in ADMIN_ROLES


def wants_json():
    return request.accept_mimetypes.best == 'application/json' or request.blueprint == 'api'


def require_login():
    """before_request hook for staff-only blueprints."""
    if not is_logged_in():
        if wants_json():
            return jsonify({'error': 'Not logged in'}), 401
        flash("Please login to access this page.", "error")
        return redirect(url_for('auth.user_login'))
    return None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        return require_login() or view(*args, **kwargs)
    return wrapped


def admin_required(message, redirect_endpoint):
    """Only super-admins and admins may use the view."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not is_admin():
                flash(message, "error")
                return redirect(url_for(redirect_endpoint))
            return view(*args, **kwargs)
        return wrapped
    return decorator


# ---------------- passwords ----------------

def is_password_hash(value):
    return bool(value) and str(value).startswith(('pbkdf2:', 'scrypt:'))


def hash_password(password):
    return generate_password_hash(password, method=PASSWORD_HASH_METHOD)


def password_column_fits_hash():
    """True if users.password is wide enough for a hash (checked once per process)."""
    global _password_column_length
    if _password_column_length is None:
        length = db.query_value("""
            SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'password'
        """)
        _password_column_length = length or 0
    return _password_column_length >= 120


def verify_password(stored, given):
    if not stored or not given:
        return False
    if is_password_hash(stored):
        return check_password_hash(stored, given)
    # Old plain-text password (upgraded to a hash after a successful login)
    return secrets.compare_digest(str(stored).encode(), str(given).encode())


def password_for_storage(password):
    """Hash the password if the column can hold it, else keep it as-is."""
    return hash_password(password) if password_column_fits_hash() else password
