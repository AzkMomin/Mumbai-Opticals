"""Home page and dashboard."""
from datetime import date, timedelta

from flask import Blueprint, render_template, request

from .. import db
from ..auth import login_required

bp = Blueprint('main', __name__)

PERIODS = {'today': 'Today', 'week': 'This Week', 'month': 'This Month', 'year': 'This Year'}
PREVIOUS_LABEL = {'today': 'yesterday', 'week': 'last week', 'month': 'last month', 'year': 'last year'}


@bp.route('/')
def index():
    from .shop import shop_page
    return shop_page()


def _month_start(d, months_back=0):
    year, month = d.year, d.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def _period_range(period, today):
    """(start, end, previous_start) for the chosen period; end is exclusive."""
    if period == 'today':
        return today, today + timedelta(days=1), today - timedelta(days=1)
    if period == 'week':
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=7), start - timedelta(days=7)
    if period == 'year':
        start = date(today.year, 1, 1)
        return start, date(today.year + 1, 1, 1), date(today.year - 1, 1, 1)
    start = _month_start(today)
    return start, _month_start(today, -1), _month_start(today, 1)


def _change(current, previous):
    if not previous:
        return None
    return round((current - previous) / previous * 100)


def _sales(start, end):
    row = db.query_one("""
        SELECT COALESCE(SUM(total_amount), 0) AS sales, COUNT(*) AS orders
        FROM bills WHERE status != 'CANCELLED' AND bill_date >= %s AND bill_date < %s
    """, (start, end))
    return db.to_float(row['sales']), int(row['orders'])


@bp.route('/login/dashboard')
@login_required
def dashboard():
    period = request.args.get('period', 'month')
    if period not in PERIODS:
        period = 'month'
    today = date.today()
    start, end, prev_start = _period_range(period, today)

    sales_now, orders_now = _sales(start, end)
    sales_prev, orders_prev = _sales(prev_start, start)
    customers_new = db.query_value("SELECT COUNT(*) FROM customers WHERE created_at >= %s AND created_at < %s",
                                   (start, end))
    customers_prev = db.query_value("SELECT COUNT(*) FROM customers WHERE created_at >= %s AND created_at < %s",
                                    (prev_start, start))
    stats = {
        'sales': sales_now, 'sales_change': _change(sales_now, sales_prev),
        'orders': orders_now, 'orders_change': _change(orders_now, orders_prev),
        'customers': db.query_value("SELECT COUNT(*) FROM customers"),
        'customers_new': customers_new, 'customers_change': _change(customers_new, customers_prev),
        'low_stock': db.query_value("SELECT COUNT(*) FROM stock WHERE quantity <= reorder_level"),
        'outstanding': db.to_float(db.query_value("""
            SELECT COALESCE(SUM(total_amount - total_paid), 0) FROM bills
            WHERE status != 'CANCELLED' AND payment_status IN ('PENDING', 'PARTIALLY_PAID')
        """)),
    }

    # Sales for the last 6 months (chart)
    chart = []
    for back in range(5, -1, -1):
        month_start = _month_start(today, back)
        sales, _ = _sales(month_start, _month_start(today, back - 1))
        chart.append({'label': month_start.strftime('%b %Y'), 'sales': sales})

    top_products = db.query_all("""
        SELECT p.product_name, SUM(bi.quantity) AS qty
        FROM bill_items bi
        JOIN bills b ON b.bill_id = bi.bill_id
        JOIN products p ON p.product_id = bi.product_id
        WHERE b.status != 'CANCELLED' AND b.bill_date >= %s AND b.bill_date < %s
        GROUP BY p.product_id, p.product_name
        ORDER BY qty DESC LIMIT 5
    """, (start, end))
    for row in top_products:
        row['qty'] = int(row['qty'] or 0)

    brand_stock = db.query_all("""
        SELECT pc.category_name, pt.type_name, COUNT(*) AS products,
               SUM(COALESCE(s.quantity, 0)) AS total_stock,
               SUM(COALESCE(s.reorder_level, 5)) AS reorder_total,
               SUM(COALESCE(s.quantity, 0) <= COALESCE(s.reorder_level, 5)) AS low_items,
               COALESCE(SUM(sold.qty), 0) AS sold
        FROM products p
        JOIN product_types pt ON pt.type_id = p.product_type_id
        JOIN product_categories pc ON pc.category_id = pt.category_id
        LEFT JOIN stock s ON s.product_id = p.product_id
        LEFT JOIN (
            SELECT bi.product_id, SUM(bi.quantity) AS qty
            FROM bill_items bi JOIN bills b ON b.bill_id = bi.bill_id
            WHERE b.status != 'CANCELLED' AND b.bill_date >= %s AND b.bill_date < %s
            GROUP BY bi.product_id
        ) sold ON sold.product_id = p.product_id
        GROUP BY pc.category_name, pt.type_name
        ORDER BY pc.category_name, pt.type_name
    """, (start, end))
    for row in brand_stock:
        for key in ('products', 'total_stock', 'low_items', 'sold'):
            row[key] = int(row[key] or 0)

    return render_template('dashboard/dashboard.html', stats=stats, chart=chart, top_products=top_products,
                           brand_stock=brand_stock, period=period, periods=PERIODS,
                           previous_label=PREVIOUS_LABEL[period])
