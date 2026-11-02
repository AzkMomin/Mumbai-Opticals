"""Home page and dashboard."""
from datetime import date

from flask import Blueprint, render_template

from .. import db
from ..auth import login_required

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    return render_template('public/index.html')


def _month_start(d, months_back=0):
    year, month = d.year, d.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _change(current, previous):
    if not previous:
        return None
    return round((current - previous) / previous * 100)


@bp.route('/login/dashboard')
@login_required
def dashboard():
    today = date.today()
    this_month, last_month = _month_start(today), _month_start(today, 1)

    def sales_between(start, end):
        row = db.query_one("""
            SELECT COALESCE(SUM(total_amount), 0) AS sales, COUNT(*) AS orders
            FROM bills WHERE status != 'CANCELLED' AND bill_date >= %s AND bill_date < %s
        """, (start, end))
        return db.to_float(row['sales']), int(row['orders'])

    next_month = _month_start(today, -1)
    sales_now, orders_now = sales_between(this_month, next_month)
    sales_prev, orders_prev = sales_between(last_month, this_month)

    customers_total = db.query_value("SELECT COUNT(*) FROM customers")
    customers_now = db.query_value("SELECT COUNT(*) FROM customers WHERE created_at >= %s", (this_month,))
    customers_prev = db.query_value("SELECT COUNT(*) FROM customers WHERE created_at >= %s AND created_at < %s",
                                    (last_month, this_month))
    low_stock = db.query_value("SELECT COUNT(*) FROM stock WHERE quantity <= reorder_level")
    outstanding = db.to_float(db.query_value("""
        SELECT COALESCE(SUM(total_amount - total_paid), 0) FROM bills
        WHERE status != 'CANCELLED' AND payment_status IN ('PENDING', 'PARTIALLY_PAID')
    """))

    # Last 6 months of sales for the chart
    chart = []
    for back in range(5, -1, -1):
        start, end = _month_start(today, back), _month_start(today, back - 1)
        sales, _ = sales_between(start, end)
        chart.append({'label': start.strftime('%b %Y'), 'sales': sales})

    top_products = db.query_all("""
        SELECT p.product_name, SUM(bi.quantity) AS qty
        FROM bill_items bi
        JOIN bills b ON b.bill_id = bi.bill_id AND b.status != 'CANCELLED'
        JOIN products p ON p.product_id = bi.product_id
        GROUP BY p.product_id, p.product_name
        ORDER BY qty DESC LIMIT 5
    """)
    recent_bills = db.query_all("""
        SELECT b.bill_id, b.bill_number, b.total_amount, b.payment_status, b.status, c.name AS customer_name,
               DATE_FORMAT(b.bill_date, '%d/%m/%Y') AS formatted_date
        FROM bills b LEFT JOIN customers c ON c.customer_id = b.customer_id
        ORDER BY b.created_at DESC LIMIT 5
    """)

    stats = {
        'sales': sales_now, 'sales_change': _change(sales_now, sales_prev),
        'orders': orders_now, 'orders_change': _change(orders_now, orders_prev),
        'customers': customers_total, 'customers_new': customers_now,
        'customers_change': _change(customers_now, customers_prev),
        'low_stock': low_stock, 'outstanding': outstanding,
    }
    return render_template('dashboard/dashboard.html', stats=stats, chart=chart,
                           top_products=top_products, recent_bills=recent_bills)
