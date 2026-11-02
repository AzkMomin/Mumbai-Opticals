"""Payments: receive against a bill, list, view, edit, delete."""
import uuid
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .. import db
from ..auth import admin_required, require_login
from ..helpers import DELETE_METHODS, payment_status_for

bp = Blueprint('payments', __name__)
bp.before_request(require_login)

PAYMENT_METHODS = ('CASH', 'CARD', 'UPI', 'CREDIT', 'BANK_TRANSFER', 'CHEQUE')


def _amount(name='amount'):
    try:
        return float(request.form.get(name) or 0)
    except ValueError:
        return None


def _update_bill_totals(bill_id):
    """Recalculate a bill's paid/balance/status from its payments."""
    bill_total = db.to_float(db.query_value("SELECT total_amount FROM bills WHERE bill_id = %s", (bill_id,)))
    total_paid = db.to_float(db.query_value("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE bill_id = %s",
                                            (bill_id,)))
    payment_status, balance_due = payment_status_for(bill_total, total_paid)
    db.execute("UPDATE bills SET total_paid = %s, balance_due = %s, payment_status = %s WHERE bill_id = %s",
               (total_paid, balance_due, payment_status, bill_id))


@bp.route('/bills/receive_payment/<int:bill_id>', methods=['GET', 'POST'])
def receive_payment(bill_id):
    bill = db.query_one("""
        SELECT b.*, c.name AS customer_name, c.phone AS customer_phone,
               (SELECT COUNT(*) FROM bill_items bi WHERE bi.bill_id = b.bill_id) AS item_count
        FROM bills b LEFT JOIN customers c ON b.customer_id = c.customer_id
        WHERE b.bill_id = %s
    """, (bill_id,))
    if not bill:
        flash('Bill not found', 'error')
        return redirect(url_for('bills.bills'))

    db.floatify(bill, 'total_amount', 'total_paid')
    bill['balance_due'] = db.to_float(bill.get('balance_due')) or bill['total_amount'] - bill['total_paid']

    if bill['status'] == 'CANCELLED':
        flash('This bill is cancelled.', 'warning')
        return redirect(url_for('bills.view_bill', bill_id=bill_id))
    if bill['payment_status'] == 'PAID':
        flash('This bill is already fully paid.', 'warning')
        return redirect(url_for('bills.view_bill', bill_id=bill_id))

    if request.method == 'GET':
        return render_template('payments/receive_payment.html', bill=bill)

    amount = _amount()
    if amount is None or amount <= 0:
        flash('Payment amount must be greater than 0.', 'error')
        return render_template('payments/receive_payment.html', bill=bill)
    if amount > bill['balance_due'] + 0.001:
        flash(f"Payment amount cannot exceed balance due of ₹{bill['balance_due']:.2f}", 'error')
        return render_template('payments/receive_payment.html', bill=bill)

    payment_number = f"PAY-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    db.execute("""
        INSERT INTO payments (bill_id, payment_number, amount, payment_method, payment_date,
                              reference_number, notes, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (bill_id, payment_number, amount, request.form.get('payment_method', 'CASH'), datetime.now().date(),
          request.form.get('reference_number', ''), request.form.get('notes', ''), session.get('user_id')))
    _update_bill_totals(bill_id)
    db.commit()

    flash(f'Payment of ₹{amount:.2f} received successfully! Payment Number: {payment_number}', 'success')
    return redirect(url_for('bills.view_bill', bill_id=bill_id))


@bp.route('/payments')
def payments():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search = request.args.get('search', '')

    where, params = "", []
    if date_from:
        where += " AND p.payment_date >= %s"
        params.append(date_from)
    if date_to:
        where += " AND p.payment_date <= %s"
        params.append(date_to)
    summary_where, summary_params = where, list(params)
    if search:
        where += " AND (p.payment_number LIKE %s OR b.bill_number LIKE %s OR c.name LIKE %s OR c.phone LIKE %s)"
        params += [f'%{search}%'] * 4

    rows = db.query_all("""
        SELECT p.*, b.bill_number, b.total_amount AS bill_total, c.name AS customer_name,
               c.phone AS customer_phone, u.name AS received_by,
               DATE_FORMAT(p.payment_date, '%d/%m/%Y') AS formatted_date,
               DATE_FORMAT(p.created_at, '%d/%m/%Y %H:%i') AS formatted_created
        FROM payments p
        JOIN bills b ON p.bill_id = b.bill_id
        JOIN customers c ON b.customer_id = c.customer_id
        LEFT JOIN users u ON p.created_by = u.login_id
        WHERE 1=1""" + where + " ORDER BY p.payment_date DESC, p.created_at DESC", params)
    for row in rows:
        db.floatify(row, 'amount', 'bill_total')

    s = db.query_one("""
        SELECT COUNT(*) AS total_payments, SUM(p.amount) AS total_amount, AVG(p.amount) AS avg_payment
        FROM payments p WHERE 1=1""" + summary_where, summary_params)
    summary = {'total_payments': int(s['total_payments'] or 0), 'total_amount': db.to_float(s['total_amount']),
               'avg_payment': db.to_float(s['avg_payment'])}

    return render_template('payments/payments.html', payments=rows, summary=summary,
                           date_from=date_from, date_to=date_to, current_search=search)


@bp.route('/payments/view/<int:payment_id>')
def view_payment(payment_id):
    payment = db.query_one("""
        SELECT p.*, b.bill_number, b.total_amount AS bill_total, c.name AS customer_name,
               c.phone AS customer_phone, u.name AS created_by_name
        FROM payments p
        JOIN bills b ON p.bill_id = b.bill_id
        JOIN customers c ON b.customer_id = c.customer_id
        LEFT JOIN users u ON p.created_by = u.login_id
        WHERE p.payment_id = %s
    """, (payment_id,))
    if not payment:
        flash('Payment not found', 'error')
        return redirect(url_for('payments.payments'))
    return render_template('payments/view_payment.html', payment=payment)


@bp.route('/payments/edit/<int:payment_id>', methods=['GET', 'POST'])
@admin_required("You don't have permission to edit payments.", 'payments.payments')
def edit_payment(payment_id):
    payment = db.query_one("""
        SELECT p.*, b.bill_number, b.total_amount AS bill_total, b.total_paid, b.balance_due,
               c.name AS customer_name
        FROM payments p
        JOIN bills b ON p.bill_id = b.bill_id
        JOIN customers c ON b.customer_id = c.customer_id
        WHERE p.payment_id = %s
    """, (payment_id,))
    if not payment:
        flash('Payment not found', 'error')
        return redirect(url_for('payments.payments'))

    db.floatify(payment, 'amount', 'bill_total', 'total_paid', 'balance_due')
    payment['max_allowed'] = payment['balance_due'] + payment['amount']

    if request.method == 'GET':
        return render_template('payments/edit_payment.html', payment=payment)

    new_amount = _amount()
    if new_amount is None or new_amount <= 0:
        flash('Payment amount must be greater than 0.', 'error')
        return render_template('payments/edit_payment.html', payment=payment)
    if new_amount > payment['max_allowed'] + 0.001:
        flash(f"Payment amount cannot exceed ₹{payment['max_allowed']:.2f}", 'error')
        return render_template('payments/edit_payment.html', payment=payment)

    db.execute("""
        UPDATE payments SET amount = %s, payment_method = %s, reference_number = %s, notes = %s,
               payment_date = %s
        WHERE payment_id = %s
    """, (new_amount, request.form.get('payment_method') or payment['payment_method'],
          request.form.get('reference_number', ''), request.form.get('notes', ''),
          request.form.get('payment_date') or payment['payment_date'], payment_id))
    _update_bill_totals(payment['bill_id'])
    db.commit()

    flash('Payment updated successfully!', 'success')
    return redirect(url_for('payments.view_payment', payment_id=payment_id))


@bp.route('/payments/delete/<int:payment_id>', methods=DELETE_METHODS)
@admin_required("You don't have permission to delete payments.", 'payments.payments')
def delete_payment(payment_id):
    payment = db.query_one("SELECT bill_id, amount FROM payments WHERE payment_id = %s", (payment_id,))
    if not payment:
        flash('Payment not found', 'error')
        return redirect(url_for('payments.payments'))

    db.execute("DELETE FROM payments WHERE payment_id = %s", (payment_id,))
    _update_bill_totals(payment['bill_id'])
    db.commit()
    flash(f"Payment deleted successfully! Amount ₹{db.to_float(payment['amount']):.2f} removed from bill.", 'success')
    return redirect(url_for('payments.payments'))
