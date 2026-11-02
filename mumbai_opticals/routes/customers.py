"""Customers: list, add/edit, view, delete, search."""
import re

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from .. import db
from ..auth import admin_required, current_user, require_login
from ..helpers import DELETE_METHODS, page_args, pagination

bp = Blueprint('customers', __name__)
bp.before_request(require_login)

PHONE_PATTERN = re.compile(r'^\+\d{1,3}\d{6,14}$')
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


@bp.route('/customers')
def customers():
    page, per_page, offset = page_args(request)
    search = request.args.get('search', '')

    where, params = "", []
    if search:
        where = " AND (name LIKE %s OR email LIKE %s OR phone LIKE %s)"
        params = [f'%{search}%'] * 3

    total_records = db.query_value("SELECT COUNT(*) FROM customers WHERE 1=1" + where, params)
    rows = db.query_all("""
        SELECT customer_id, name, phone, email,
               DATE_FORMAT(created_at, '%d/%m/%Y %h:%i %p') AS created_at
        FROM customers WHERE 1=1""" + where + " ORDER BY customers.created_at DESC LIMIT %s OFFSET %s",
        params + [per_page, offset])

    return render_template('customers/customers.html', customers=rows, current_user=current_user(),
                           pagination=pagination(page, per_page, total_records), current_search=search)


@bp.route('/customers/add', methods=['GET', 'POST'])
def add_customer():
    customer_id = request.args.get('id', type=int)
    edit_mode = customer_id is not None

    customer_data = None
    if edit_mode:
        customer_data = db.query_one("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
        if not customer_data:
            flash("Customer not found.", "error")
            return redirect(url_for('customers.customers'))

    def form_page():
        return render_template('customers/add_customer.html', edit_mode=edit_mode,
                               customer_data=customer_data, current_user=current_user())

    if request.method == 'GET':
        return form_page()

    name = (request.form.get('name') or '').strip()
    # fullPhone comes from the international phone picker
    phone = (request.form.get('fullPhone') or request.form.get('phone') or '').strip()
    email = (request.form.get('email') or '').strip()

    if not all([name, phone, email]):
        flash("All fields are required.", "error")
        return form_page()
    if not phone.startswith('+'):
        phone = '+' + phone
    if not PHONE_PATTERN.match(phone):
        flash("Please enter a valid international phone number with country code (e.g., +919876543210).", "error")
        return form_page()
    if not EMAIL_PATTERN.match(email):
        flash("Please enter a valid email address.", "error")
        return form_page()

    exclude = customer_id or 0
    if db.query_one("SELECT customer_id FROM customers WHERE email = %s AND customer_id != %s", (email, exclude)):
        flash("Email already exists. Please use another email.", "error")
        return form_page()
    if db.query_one("SELECT customer_id FROM customers WHERE phone = %s AND customer_id != %s", (phone, exclude)):
        flash("Phone number already exists. Please use another number.", "error")
        return form_page()

    if edit_mode:
        db.execute("UPDATE customers SET name = %s, phone = %s, email = %s WHERE customer_id = %s",
                   (name, phone, email, customer_id))
        flash("Customer updated successfully!", "success")
    else:
        db.execute("INSERT INTO customers (name, phone, email, created_at) VALUES (%s, %s, %s, NOW())",
                   (name, phone, email))
        flash("Customer added successfully!", "success")
    db.commit()
    return redirect(url_for('customers.customers'))


@bp.route('/customers/delete', methods=DELETE_METHODS)
@admin_required("You don't have permission to delete customers.", 'customers.customers')
def delete_customer():
    customer_id = request.values.get('id', type=int)
    if not customer_id:
        flash("No customer ID provided.", "error")
        return redirect(url_for('customers.customers'))

    if db.query_value("SELECT COUNT(*) FROM bills WHERE customer_id = %s", (customer_id,)):
        flash("This customer has bills, so they can't be deleted.", "error")
        return redirect(url_for('customers.customers'))

    db.execute("DELETE FROM customers WHERE customer_id = %s", (customer_id,))
    db.commit()
    flash("Customer deleted successfully!", "success")
    return redirect(url_for('customers.customers'))


@bp.route('/customers/view')
def view_customer():
    customer_id = request.args.get('id', type=int)
    if not customer_id:
        flash("No customer ID provided.", "error")
        return redirect(url_for('customers.customers'))

    customer = db.query_one("""
        SELECT customer_id, name, phone, email,
               DATE_FORMAT(created_at, '%d/%m/%Y %h:%i %p') AS created_at
        FROM customers WHERE customer_id = %s
    """, (customer_id,))
    if not customer:
        flash("Customer not found.", "error")
        return redirect(url_for('customers.customers'))
    return render_template('customers/view_customer.html', customer=customer)


@bp.route('/search_customers')
def search_customers():
    term = request.args.get('term', '')
    if term:
        rows = db.query_all("""
            SELECT customer_id, name, phone, email FROM customers
            WHERE name LIKE %s OR phone LIKE %s ORDER BY name LIMIT 10
        """, (f'%{term}%', f'%{term}%'))
    else:
        rows = db.query_all("SELECT customer_id, name, phone, email FROM customers ORDER BY name LIMIT 10")
    return jsonify(rows)
