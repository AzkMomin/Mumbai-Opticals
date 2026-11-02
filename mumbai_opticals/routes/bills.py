"""Bills: list, generate, view, edit, print, cancel, delete, WhatsApp link, product search."""
import json
import uuid
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from .. import db
from ..auth import require_login
from ..helpers import DELETE_METHODS, change_stock, payment_status_for
from ..settings import COMPANY

bp = Blueprint('bills', __name__)
bp.before_request(require_login)

ITEM_MONEY_FIELDS = ('price_per_unit', 'discount_percent', 'discount_amount', 'total_price')


def _bill_money(bill):
    db.floatify(bill, 'subtotal', 'discount', 'tax', 'total_amount', 'total_paid')
    bill['balance_due'] = db.to_float(bill.get('balance_due')) or bill['total_amount'] - bill['total_paid']
    return bill


@bp.route('/bills')
def bills():
    status = request.args.get('status', 'all')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search = request.args.get('search', '')

    # Date and search filters apply to the list and the summary cards; status only to the list
    common, params = "", []
    if date_from:
        common += " AND b.bill_date >= %s"
        params.append(date_from)
    if date_to:
        common += " AND b.bill_date <= %s"
        params.append(date_to)
    if search:
        common += " AND (b.bill_number LIKE %s OR c.name LIKE %s OR c.phone LIKE %s)"
        params += [f'%{search}%'] * 3
    status_filters = {
        'paid': " AND b.payment_status = 'PAID'",
        'pending': " AND b.payment_status = 'PENDING'",
        'partially_paid': " AND b.payment_status = 'PARTIALLY_PAID'",
        'cancelled': " AND b.status = 'CANCELLED'",
    }
    where = common + status_filters.get(status, "")

    rows = db.query_all("""
        SELECT b.*, c.name AS customer_name, c.phone AS customer_phone,
               (SELECT COUNT(*) FROM bill_items bi WHERE bi.bill_id = b.bill_id) AS item_count,
               DATE_FORMAT(b.bill_date, '%d/%m/%Y') AS formatted_date,
               DATE_FORMAT(b.created_at, '%d/%m/%Y %H:%i') AS formatted_created
        FROM bills b LEFT JOIN customers c ON b.customer_id = c.customer_id
        WHERE 1=1""" + where + " ORDER BY b.created_at DESC", params)
    rows = [_bill_money(b) for b in rows]

    s = db.query_one("""
        SELECT COUNT(*) AS total_bills,
               SUM(b.payment_status = 'PAID') AS paid_count,
               SUM(b.payment_status = 'PENDING') AS pending_count,
               SUM(b.payment_status = 'PARTIALLY_PAID') AS partially_paid_count,
               SUM(b.status = 'CANCELLED') AS cancelled_count,
               SUM(CASE WHEN b.payment_status = 'PAID' THEN b.total_amount ELSE 0 END) AS total_revenue,
               SUM(CASE WHEN b.payment_status IN ('PENDING', 'PARTIALLY_PAID') AND b.status != 'CANCELLED'
                        THEN b.total_amount - b.total_paid ELSE 0 END) AS total_outstanding
        FROM bills b LEFT JOIN customers c ON b.customer_id = c.customer_id
        WHERE 1=1""" + common, params)
    summary = {k: (db.to_float(v) if k.startswith('total_') and k != 'total_bills' else int(v or 0))
               for k, v in s.items()}

    t = db.query_one("""
        SELECT COUNT(*) AS `all`, SUM(payment_status = 'PAID') AS paid, SUM(payment_status = 'PENDING') AS pending,
               SUM(payment_status = 'PARTIALLY_PAID') AS partially_paid, SUM(status = 'CANCELLED') AS cancelled
        FROM bills
    """)
    filter_counts = {k: int(v or 0) for k, v in t.items()}

    return render_template('bills/bills.html', bills=rows, summary=summary, filter_counts=filter_counts,
                           current_status=status, date_from=date_from, date_to=date_to, current_search=search)


def _bill_products():
    products = db.query_all("""
        SELECT p.product_id, p.product_name, p.product_image, p.model_name, p.model_code,
               COALESCE(s.selling_price, p.selling_price) AS selling_price,
               pt.type_name, pc.category_name, s.quantity
        FROM products p
        JOIN product_types pt ON p.product_type_id = pt.type_id
        JOIN product_categories pc ON pt.category_id = pc.category_id
        JOIN stock s ON p.product_id = s.product_id
        WHERE s.quantity > 0
        ORDER BY pt.type_name, p.product_name
    """)
    for p in products:
        p['quantity'] = int(p['quantity'] or 0)
        p['selling_price'] = db.to_float(p['selling_price'])
        p['type_name'] = p['type_name'] or 'Misc'
    return products


def _parse_bill_items(form):
    """Read the item rows from the bill form. Discount per row is a rupee amount."""
    items = []
    product_ids = form.getlist('items[]')
    quantities = form.getlist('quantities[]')
    prices = form.getlist('prices[]')
    discounts = form.getlist('discounts[]')
    details = form.getlist('details[]')
    for i, product_id in enumerate(product_ids):
        try:
            item = {
                'product_id': int(product_id),
                'quantity': int(quantities[i]),
                'price': float(prices[i]),
                'discount': float(discounts[i]) if i < len(discounts) and discounts[i] else 0.0,
            }
        except (ValueError, IndexError):
            return None
        if item['quantity'] <= 0 or item['price'] < 0 or item['discount'] < 0:
            return None
        item['details'] = _clean_details(details[i] if i < len(details) else '')
        gross = item['price'] * item['quantity']
        item['discount'] = min(item['discount'], gross)
        item['total'] = round(gross - item['discount'], 2)
        item['discount_percent'] = round(item['discount'] / gross * 100, 2) if gross else 0
        items.append(item)
    return items


DETAIL_FIELDS = {
    'frame_type', 'material', 'model_name', 'model_code', 'model_color', 'model_size',
    'lens_for', 'lens_type', 'which_side', 'company', 'add_on', 'index_value', 'dia',
    'watch_type', 'watch_mechanism', 'strap_material', 'dial_color', 'brand', 'color', 'size',
}
DETAIL_LABELS = {
    'frame_type': 'Frame', 'material': 'Material', 'model_name': 'Model', 'model_code': 'Code',
    'model_color': 'Color', 'model_size': 'Size', 'lens_for': 'For', 'lens_type': 'Type', 'which_side': 'Side',
    'company': 'Company', 'add_on': 'Add-on', 'index_value': 'Index', 'dia': 'DIA', 'watch_type': 'Type',
    'watch_mechanism': 'Mechanism', 'strap_material': 'Strap', 'dial_color': 'Dial', 'brand': 'Brand',
    'color': 'Color', 'size': 'Size',
}
PRESCRIPTION_FIELDS = ('eye', 'sph', 'cyl', 'axis', 'add', 'vision', 'pd')


def _clean_details(raw):
    """Keep only known text fields from a row's details (JSON)."""
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    clean = {k: str(v)[:100] for k, v in data.items() if k in DETAIL_FIELDS and str(v).strip()}
    return json.dumps(clean) if clean else None


def _clean_prescription_rows(raw):
    try:
        rows = json.loads(raw) if raw else []
    except ValueError:
        return []
    if not isinstance(rows, list):
        return []
    clean = []
    for row in rows[:6]:
        if isinstance(row, dict):
            r = {k: str(row.get(k) or '').strip()[:20] for k in PRESCRIPTION_FIELDS}
            if any(r[k] for k in PRESCRIPTION_FIELDS if k != 'eye'):
                clean.append(r)
    return clean


def _number_or_none(value):
    try:
        return float(value) if value not in (None, '') else None
    except ValueError:
        return None


@bp.route('/bills/generate', methods=['GET', 'POST'])
def generate_bill():
    if request.method == 'GET':
        return render_template('bills/generate_bill.html', products=_bill_products())

    customer_id = request.form.get('customer_id', type=int)
    if not customer_id or not db.query_one("SELECT customer_id FROM customers WHERE customer_id = %s",
                                           (customer_id,)):
        flash("Please select a customer.", "error")
        return redirect(url_for('bills.generate_bill'))

    items = _parse_bill_items(request.form)
    if items is None:
        flash("Some item rows have invalid quantities or prices.", "error")
        return redirect(url_for('bills.generate_bill'))
    if not items:
        flash("Please add at least one product to the bill.", "error")
        return redirect(url_for('bills.generate_bill'))

    # Check stock for the total quantity of each product
    needed = {}
    for item in items:
        needed[item['product_id']] = needed.get(item['product_id'], 0) + item['quantity']
    shortages = []
    for product_id, quantity in needed.items():
        stock = db.query_one("""
            SELECT s.quantity, p.product_name FROM stock s JOIN products p ON s.product_id = p.product_id
            WHERE s.product_id = %s FOR UPDATE
        """, (product_id,))
        if not stock:
            shortages.append("Product not found in stock")
        elif stock['quantity'] < quantity:
            shortages.append(f"{stock['product_name']}: Requested {quantity}, Available {stock['quantity']}")
    if shortages:
        flash("Cannot generate bill. Stock shortage:\n" + "\n".join(shortages), "error")
        return redirect(url_for('bills.generate_bill'))

    # Totals are worked out here, not trusted from the browser
    try:
        extra_discount = max(float(request.form.get('additional_discount') or 0), 0)
        tax_percent = max(float(request.form.get('tax') or 0), 0)
    except ValueError:
        flash("Discount and tax must be numbers.", "error")
        return redirect(url_for('bills.generate_bill'))
    subtotal = round(sum(i['price'] * i['quantity'] for i in items), 2)
    item_discount = round(sum(i['discount'] for i in items), 2)
    after_discount = max(subtotal - item_discount - extra_discount, 0)
    tax_amount = round(after_discount * tax_percent / 100, 2)
    total = round(after_discount + tax_amount, 2)
    discount_total = round(item_discount + extra_discount, 2)

    prescription_rows = _clean_prescription_rows(request.form.get('prescription_rows'))

    bill_number = f"BILL-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    bill_id = db.execute("""
        INSERT INTO bills (bill_number, customer_id, bill_date, subtotal, discount, tax, total_amount,
                           payment_method, notes, status, payment_status, total_paid, balance_due,
                           prescription_details)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE', 'PENDING', 0, %s, %s)
    """, (bill_number, customer_id, datetime.now().date(), subtotal, discount_total, tax_amount, total,
          request.form.get('payment_method', 'CASH'), request.form.get('notes', ''), total,
          json.dumps(prescription_rows) if prescription_rows else None))

    # Prescription rows typed in on the bill are also saved to the customer's prescriptions
    loaded = request.form.get('prescription_id', type=int)
    if prescription_rows and not loaded:
        for row in prescription_rows:
            db.execute("""
                INSERT INTO prescriptions (customer_id, prescription_date, eye, splt, cvl, axis, add_value,
                                           vision, pupillary_distance, photo_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '')
            """, (customer_id, datetime.now().date(), row['eye'], _number_or_none(row['sph']),
                  _number_or_none(row['cyl']), _number_or_none(row['axis']), _number_or_none(row['add']),
                  row['vision'], _number_or_none(row['pd'])))

    for item in items:
        db.execute("""
            INSERT INTO bill_items (bill_id, product_id, quantity, price_per_unit,
                                    discount_percent, discount_amount, total_price, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (bill_id, item['product_id'], item['quantity'], item['price'], item['discount_percent'],
              item['discount'], item['total'], item['details']))
        change_stock(item['product_id'], 'SALE', item['quantity'], bill_id, 'BILL',
                     f"Sold {item['quantity']} units in bill {bill_number}")
    db.commit()

    flash(f'Bill generated successfully! Bill Number: {bill_number}', 'success')
    return redirect(url_for('bills.view_bill', bill_id=bill_id))


def _get_bill(bill_id):
    return db.query_one("""
        SELECT b.*, c.name AS customer_name, c.phone AS customer_phone, c.email AS customer_email
        FROM bills b LEFT JOIN customers c ON b.customer_id = c.customer_id
        WHERE b.bill_id = %s
    """, (bill_id,))


def bill_items(bill_id):
    """Items of a bill, with the details typed on the bill taking priority over the product's own."""
    items = db.query_all("""
        SELECT bi.*, p.product_name, p.product_image, p.model_code, p.model_name, p.model_color, p.model_size,
               p.frame_type, p.material, p.lens_for, p.lens_type, p.which_side, p.company,
               p.watch_type, p.watch_mechanism, p.strap_material, p.dial_color, p.brand, p.color, p.size,
               pt.type_name, pc.category_name
        FROM bill_items bi
        JOIN products p ON bi.product_id = p.product_id
        JOIN product_types pt ON p.product_type_id = pt.type_id
        JOIN product_categories pc ON pt.category_id = pc.category_id
        WHERE bi.bill_id = %s
        ORDER BY bi.item_id
    """, (bill_id,))
    for item in items:
        db.floatify(item, *ITEM_MONEY_FIELDS)
        try:
            details = json.loads(item.get('details') or '{}')
        except ValueError:
            details = {}
        if isinstance(details, dict):
            item.update({k: v for k, v in details.items() if v})
            item['details_text'] = ' · '.join(f"{DETAIL_LABELS.get(k, k)}: {v}" for k, v in details.items() if v)
        item['group'] = _item_group(item['type_name'])
    return items


def _item_group(type_name):
    if type_name in ('Frames', 'Goggles'):
        return 'frames'
    if type_name == 'Lenses':
        return 'lenses'
    if type_name in ('Wrist Watches', 'Hand Watches'):
        return 'watches'
    return 'misc'


def bill_prescription(bill):
    """Prescription rows saved with the bill, shaped as {right: {...}, left: {...}} for the templates."""
    try:
        rows = json.loads(bill.get('prescription_details') or '[]')
    except ValueError:
        rows = []
    if not rows:
        return None
    result = {'rows': rows}
    for row in rows:
        for side in ('right', 'left'):
            if row.get('eye', '').lower() in (side, 'both'):
                for key in ('sph', 'cyl', 'axis', 'add', 'vision'):
                    result[f'{side}_{key}'] = row.get(key, '')
        result['pupillary_distance'] = result.get('pupillary_distance') or row.get('pd', '')
    return result


@bp.route('/bills/view/<int:bill_id>')
def view_bill(bill_id):
    bill = _get_bill(bill_id)
    if not bill:
        flash('Bill not found', 'error')
        return redirect(url_for('bills.bills'))
    payments = db.query_all("""
        SELECT p.*, u.name AS received_by FROM payments p
        LEFT JOIN users u ON p.created_by = u.login_id
        WHERE p.bill_id = %s ORDER BY p.payment_date DESC, p.payment_id DESC
    """, (bill_id,))
    for p in payments:
        db.floatify(p, 'amount')
    return render_template('bills/view_bill.html', bill=_bill_money(bill), items=bill_items(bill_id),
                           payments=payments, prescription=bill_prescription(bill))


@bp.route('/bills/print/<int:bill_id>')
def print_bill(bill_id):
    bill = _get_bill(bill_id)
    if not bill:
        flash('Bill not found', 'error')
        return redirect(url_for('bills.bills'))
    return render_template('bills/print_bill.html', bill=_bill_money(bill), items=bill_items(bill_id),
                           company=COMPANY, prescription=bill_prescription(bill))


@bp.route('/bills/edit/<int:bill_id>', methods=['GET', 'POST'])
def edit_bill(bill_id):
    bill = _get_bill(bill_id)
    if not bill:
        flash('Bill not found', 'error')
        return redirect(url_for('bills.bills'))

    if request.method == 'POST':
        if bill['status'] == 'CANCELLED':
            flash('A cancelled bill cannot be edited.', 'error')
            return redirect(url_for('bills.view_bill', bill_id=bill_id))
        try:
            discount = max(float(request.form.get('discount') or 0), 0)
            tax = max(float(request.form.get('tax') or 0), 0)
        except ValueError:
            flash('Discount and tax must be numbers.', 'error')
            return redirect(url_for('bills.edit_bill', bill_id=bill_id))
        customer_id = request.form.get('customer_id', type=int) or bill['customer_id']

        # Keep the total, balance and payment status consistent with the new discount/tax
        subtotal = db.to_float(bill['subtotal'])
        total = round(max(subtotal - discount, 0) + tax, 2)
        total_paid = db.to_float(bill['total_paid'])
        payment_status, balance_due = payment_status_for(total, total_paid)
        db.execute("""
            UPDATE bills SET customer_id = %s, bill_date = %s, discount = %s, tax = %s, total_amount = %s,
                   balance_due = %s, payment_status = %s, payment_method = %s, notes = %s
            WHERE bill_id = %s
        """, (customer_id, request.form.get('bill_date') or bill['bill_date'], discount, tax, total,
              balance_due, payment_status, request.form.get('payment_method') or bill['payment_method'],
              request.form.get('notes', ''), bill_id))
        db.commit()
        flash('Bill updated successfully!', 'success')
        return redirect(url_for('bills.view_bill', bill_id=bill_id))

    return render_template('bills/edit_bill.html', bill=_bill_money(bill), items=bill_items(bill_id),
                           products=_bill_products())


@bp.route('/bills/delete/<int:bill_id>', methods=DELETE_METHODS)
def delete_bill(bill_id):
    bill = db.query_one("SELECT status FROM bills WHERE bill_id = %s", (bill_id,))
    if not bill:
        flash('Bill not found', 'error')
        return redirect(url_for('bills.bills'))

    # A cancelled bill already had its stock put back
    if bill['status'] != 'CANCELLED':
        for item in db.query_all("SELECT product_id, quantity FROM bill_items WHERE bill_id = %s", (bill_id,)):
            change_stock(item['product_id'], 'RETURN', item['quantity'], bill_id, 'BILL_DELETED',
                         f'Stock restored from deleted bill #{bill_id}')
    db.execute("DELETE FROM payments WHERE bill_id = %s", (bill_id,))
    db.execute("DELETE FROM bill_items WHERE bill_id = %s", (bill_id,))
    db.execute("DELETE FROM bills WHERE bill_id = %s", (bill_id,))
    db.commit()
    flash('Bill deleted successfully and stock restored!', 'success')
    return redirect(url_for('bills.bills'))


@bp.route('/bills/cancel/<int:bill_id>', methods=DELETE_METHODS)
def cancel_bill(bill_id):
    bill = db.query_one("SELECT status FROM bills WHERE bill_id = %s", (bill_id,))
    if not bill:
        flash('Bill not found', 'error')
        return redirect(url_for('bills.bills'))
    if bill['status'] == 'CANCELLED':
        flash('This bill is already cancelled.', 'warning')
        return redirect(url_for('bills.view_bill', bill_id=bill_id))

    db.execute("UPDATE bills SET status = 'CANCELLED' WHERE bill_id = %s", (bill_id,))
    for item in db.query_all("SELECT product_id, quantity FROM bill_items WHERE bill_id = %s", (bill_id,)):
        change_stock(item['product_id'], 'RETURN', item['quantity'], bill_id, 'BILL_CANCELLED',
                     f'Stock restored from cancelled bill #{bill_id}')
    db.commit()
    flash('Bill cancelled successfully and stock restored!', 'success')
    return redirect(url_for('bills.view_bill', bill_id=bill_id))


@bp.route('/bills/send_whatsapp/<int:bill_id>')
def send_bill_whatsapp(bill_id):
    bill = db.query_one("""
        SELECT c.phone, b.bill_number FROM bills b JOIN customers c ON b.customer_id = c.customer_id
        WHERE b.bill_id = %s
    """, (bill_id,))
    if not bill or not bill['phone']:
        flash("Customer phone number not found.", "error")
        return redirect(url_for('bills.view_bill', bill_id=bill_id))

    bill_link = url_for('portal.customer_view_bill', bill_id=bill_id, _external=True)
    message = (f"Dear Customer,\n\nYour bill has been generated. Click the link below to view your bill:\n\n"
               f"{bill_link}\n\nThank you for shopping with {COMPANY['name']}!")
    phone = ''.join(ch for ch in bill['phone'] if ch.isdigit())
    return redirect(f"https://wa.me/{phone}?text={quote(message)}")


@bp.route('/search_products')
def search_products():
    term = f"%{request.args.get('term', '')}%"
    rows = db.query_all("""
        SELECT p.product_id, p.product_name, p.product_image, pt.type_name, pc.category_name,
               s.quantity, COALESCE(s.selling_price, p.selling_price) AS selling_price
        FROM products p
        JOIN product_types pt ON p.product_type_id = pt.type_id
        JOIN product_categories pc ON pt.category_id = pc.category_id
        JOIN stock s ON p.product_id = s.product_id
        WHERE s.quantity > 0 AND (p.product_name LIKE %s OR p.model_code LIKE %s OR p.model_name LIKE %s)
        ORDER BY p.product_name LIMIT 20
    """, (term, term, term))
    return jsonify(db.jsonable(rows))
