"""Small shared helpers: uploads, pagination, stock movements, errors."""
import os
import uuid
from datetime import datetime

from flask import current_app, render_template
from werkzeug.utils import secure_filename

from . import db
from .settings import ALLOWED_IMAGE_EXTENSIONS, PER_PAGE, STATIC_DIR

# Delete/cancel actions. GET is still accepted until every page sends these as forms.
DELETE_METHODS = ['GET', 'POST']

GENERIC_ERROR = "Something went wrong. Please try again, or contact the administrator if it keeps happening."


def error_page(e=None, status=500):
    """Log the real error for the server log and show staff a generic message."""
    if e is not None:
        current_app.logger.exception("Request failed: %s", e)
    return render_template('errors/error.html', error=GENERIC_ERROR), status


# ---------------- uploads ----------------

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_image(file, folder, prefix=None):
    """Save an uploaded image under static/<folder>. Returns the path relative to static/,
    '' if no file was sent, or None if the file type isn't allowed."""
    if not file or not file.filename:
        return ''
    if not allowed_file(file.filename):
        return None
    filename = secure_filename(file.filename)
    if prefix:
        name = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    else:
        name = f"{uuid.uuid4().hex}_{filename}"
    target_dir = os.path.join(STATIC_DIR, folder)
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, name)
    file.save(path)
    os.chmod(path, 0o644)
    return f"{folder}/{name}".replace(os.sep, '/')


# ---------------- pagination ----------------

def page_args(request):
    page = max(request.args.get('page', 1, type=int), 1)
    return page, PER_PAGE, (page - 1) * PER_PAGE


def pagination(page, per_page, total_records):
    total_pages = (total_records + per_page - 1) // per_page if total_records > 0 else 1
    return {
        'current_page': page,
        'total_pages': total_pages,
        'total_records': total_records,
        'per_page': per_page,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1,
        'next_page': page + 1,
    }


# ---------------- stock ----------------

def change_stock(product_id, transaction_type, quantity, reference_id, reference_type, notes=''):
    """Change a product's stock and record the movement in stock_transactions.

    SALE subtracts; PURCHASE/RETURN add. Part of the current request's database
    transaction, so it is committed (or rolled back) together with the caller's work.
    `notes` may contain {previous} and {new} placeholders.
    """
    row = db.query_one("SELECT quantity FROM stock WHERE product_id = %s FOR UPDATE", (product_id,))
    previous_quantity = row['quantity'] if row else 0
    if transaction_type == 'SALE':
        new_quantity = previous_quantity - quantity
    else:
        new_quantity = previous_quantity + quantity
    db.execute("UPDATE stock SET quantity = %s WHERE product_id = %s", (new_quantity, product_id))
    notes = notes.replace('{previous}', str(previous_quantity)).replace('{new}', str(new_quantity))
    db.execute("""
        INSERT INTO stock_transactions
        (product_id, transaction_type, quantity, previous_quantity, new_quantity, reference_id, reference_type, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (product_id, transaction_type, quantity, previous_quantity, new_quantity, reference_id, reference_type, notes))
    return previous_quantity, new_quantity


def stock_effect(transaction):
    """How much a recorded stock transaction changed the stock (to undo it)."""
    if transaction['transaction_type'] in ('PURCHASE', 'RETURN'):
        return transaction['quantity']
    if transaction['transaction_type'] == 'SALE':
        return -transaction['quantity']
    return transaction['new_quantity'] - transaction['previous_quantity']  # ADJUSTMENT


def payment_status_for(bill_total, total_paid):
    """Return (payment_status, balance_due) for a bill."""
    balance_due = bill_total - total_paid
    if balance_due <= 0.01:
        return 'PAID', 0
    if total_paid > 0:
        return 'PARTIALLY_PAID', balance_due
    return 'PENDING', balance_due
