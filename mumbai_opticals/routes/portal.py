"""Customer-facing bill page (link sent on WhatsApp), protected by phone-number check."""
import re

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .. import db
from ..helpers import get_company
from .bills import bill_items

bp = Blueprint('portal', __name__)

MAX_ATTEMPTS = 5


def _digits(value):
    return re.sub(r'\D', '', value or '')


@bp.route('/customer/bill/<int:bill_id>', methods=['GET', 'POST'])
def customer_view_bill(bill_id):
    bill = db.query_one("""
        SELECT b.*, c.name AS customer_name, c.phone AS customer_phone, c.email AS customer_email
        FROM bills b JOIN customers c ON b.customer_id = c.customer_id
        WHERE b.bill_id = %s
    """, (bill_id,))
    if not bill:
        return render_template('portal/customer_verify.html', bill_id=bill_id, not_found=True), 404

    verified_key, attempts_key = f'bill_verified_{bill_id}', f'bill_attempts_{bill_id}'

    if request.method == 'POST':
        attempts = session.get(attempts_key, 0)
        if attempts >= MAX_ATTEMPTS:
            flash("Too many incorrect attempts. Please contact the shop.", "error")
            return render_template('portal/customer_verify.html', bill_id=bill_id)

        entered, stored = _digits(request.form.get('phone')), _digits(bill['customer_phone'])
        # Accept the number with or without the country code
        if entered and stored and len(entered) >= 10 and (entered == stored or stored.endswith(entered)):
            session[verified_key] = True
            session.pop(attempts_key, None)
            return redirect(url_for('portal.customer_view_bill', bill_id=bill_id))

        session[attempts_key] = attempts + 1
        flash("Incorrect phone number. Please try again.", "error")
        return render_template('portal/customer_verify.html', bill_id=bill_id)

    if session.get(verified_key):
        company = get_company()
        company = dict(company, logo=url_for('static', filename=company['logo'], _external=True))
        return render_template('portal/customer_bill.html', bill=bill, items=bill_items(bill_id), company=company)

    return render_template('portal/customer_verify.html', bill_id=bill_id)
