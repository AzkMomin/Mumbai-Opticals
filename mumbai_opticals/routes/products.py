"""Products: list, add, edit, view, delete, and the type-specific form fields."""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from markupsafe import escape

from .. import db
from ..auth import require_login
from ..helpers import DELETE_METHODS, save_image
from ..settings import PRODUCT_DETAIL_COLUMNS, PRODUCT_TYPE_FIELDS

bp = Blueprint('products', __name__)
bp.before_request(require_login)

PRODUCT_SELECT = """
    SELECT p.*, pt.type_name, pc.category_name,
           COALESCE(s.quantity, 0) AS quantity, s.purchase_price AS stock_purchase_price,
           s.selling_price AS stock_selling_price, s.reorder_level
    FROM products p
    JOIN product_types pt ON p.product_type_id = pt.type_id
    JOIN product_categories pc ON pt.category_id = pc.category_id
    LEFT JOIN stock s ON p.product_id = s.product_id
"""


def _with_prices(product):
    """Stock prices win over the product's own prices when set (matches the old pages)."""
    if product:
        for key in ('purchase_price', 'selling_price'):
            stock_value = product.pop(f'stock_{key}', None)
            if stock_value is not None:
                product[key] = stock_value
    return product


def _money(name):
    try:
        return float(request.form.get(name) or 0)
    except ValueError:
        return None


@bp.route('/products')
def products():
    stock_filter = request.args.get('stock_filter', 'all')
    search = request.args.get('search', '')

    where, params = [], []
    if search:
        where.append("(p.product_name LIKE %s OR p.model_code LIKE %s)")
        params += [f'%{search}%', f'%{search}%']
    if stock_filter == 'low':
        where.append("COALESCE(s.quantity, 0) < 5")
    elif stock_filter == 'medium':
        where.append("COALESCE(s.quantity, 0) BETWEEN 5 AND 10")
    elif stock_filter == 'high':
        where.append("COALESCE(s.quantity, 0) > 10")

    sql = PRODUCT_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY p.created_at DESC"
    rows = [_with_prices(p) for p in db.query_all(sql, params)]

    counts = db.query_one("""
        SELECT COUNT(*) AS total,
               SUM(COALESCE(s.quantity, 0) < 5) AS low_stock,
               SUM(COALESCE(s.quantity, 0) BETWEEN 5 AND 10) AS medium_stock,
               SUM(COALESCE(s.quantity, 0) > 10) AS high_stock
        FROM products p LEFT JOIN stock s ON p.product_id = s.product_id
    """)
    counts = {k: int(v or 0) for k, v in counts.items()}

    return render_template('products/products.html', products=rows, counts=counts,
                           current_stock_filter=stock_filter, current_search=search)


def _product_types():
    return db.query_all("""
        SELECT pt.*, pc.category_name FROM product_types pt
        JOIN product_categories pc ON pt.category_id = pc.category_id
        ORDER BY pc.category_name, pt.type_name
    """)


@bp.route('/products/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'GET':
        return render_template('products/add_product.html', product_types=_product_types())

    product_type = db.query_one("""
        SELECT pt.*, pc.category_name FROM product_types pt
        JOIN product_categories pc ON pt.category_id = pc.category_id
        WHERE pt.type_id = %s
    """, (request.form.get('product_type_id'),))
    if not product_type:
        flash("Invalid product type selected.", "error")
        return redirect(url_for('products.add_product'))

    product_name = request.form.get('product_name', '').strip()
    if not product_name:
        flash("Product name is required.", "error")
        return redirect(url_for('products.add_product'))

    selling_price, purchase_price = _money('selling_price'), _money('purchase_price')
    if selling_price is None or purchase_price is None or selling_price < 0 or purchase_price < 0:
        flash("Prices must be valid numbers and cannot be negative.", "error")
        return redirect(url_for('products.add_product'))

    product_image = save_image(request.files.get('product_image'),
                               f"uploads/products/{product_type['category_name']}")
    if product_image is None:
        flash("Product image must be a PNG, JPG or GIF.", "error")
        return redirect(url_for('products.add_product'))

    columns = ['product_type_id', 'product_name', 'product_image', 'product_description',
               'selling_price', 'purchase_price'] + PRODUCT_DETAIL_COLUMNS + ['warranty']
    values = [product_type['type_id'], product_name, product_image, request.form.get('product_description', ''),
              selling_price, purchase_price] + \
             [request.form.get(c, '') for c in PRODUCT_DETAIL_COLUMNS] + [request.form.get('warranty', '')]
    product_id = db.execute(
        f"INSERT INTO products ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})", values)

    # Stock starts at 0; it is added from the "Add Stock" page
    db.execute("""
        INSERT INTO stock (product_id, quantity, purchase_price, selling_price, reorder_level)
        VALUES (%s, 0, %s, %s, %s)
    """, (product_id, purchase_price, selling_price, request.form.get('reorder_level') or 5))
    db.commit()

    flash('Product added successfully! Stock can be added later from the "Add Stock" section.', 'success')
    return redirect(url_for('products.products'))


@bp.route('/get_product_fields/<int:type_id>')
def get_product_fields(type_id):
    product_type = db.query_one("SELECT * FROM product_types WHERE type_id = %s", (type_id,))
    if not product_type:
        return jsonify({'error': 'Product type not found'}), 404

    fields = []
    for type_names, type_fields in PRODUCT_TYPE_FIELDS.items():
        if product_type['type_name'] in type_names:
            fields = type_fields
            break

    html = ''
    for field in fields:
        label, name = escape(field['label']), escape(field['name'])
        if field['type'] == 'select':
            options = ''.join(f'<option value="{escape(o)}">{escape(o)}</option>' for o in field['options'])
            html += f'''
                <div class="col-md-4 mb-2">
                    <label class="form-label">{label}</label>
                    <select class="form-control form-control-sm" name="{name}">
                        <option value="">Select {label}</option>
                        {options}
                    </select>
                </div>'''
        else:
            placeholder = f' placeholder="{escape(field["placeholder"])}"' if field.get('placeholder') else ''
            html += f'''
                <div class="col-md-4 mb-2">
                    <label class="form-label">{label}</label>
                    <input type="text" class="form-control form-control-sm" name="{name}"{placeholder}>
                </div>'''

    return jsonify({'type_name': product_type['type_name'], 'fields': fields, 'html': html})


@bp.route('/products/view/<int:product_id>')
def view_product(product_id):
    product = _with_prices(db.query_one(PRODUCT_SELECT + " WHERE p.product_id = %s", (product_id,)))
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for('products.products'))
    transactions = db.query_all(
        "SELECT * FROM stock_transactions WHERE product_id = %s ORDER BY created_at DESC", (product_id,))
    return render_template('products/view_product.html', product=product, transactions=transactions)


@bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    product = _with_prices(db.query_one(PRODUCT_SELECT + " WHERE p.product_id = %s", (product_id,)))
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for('products.products'))

    if request.method == 'GET':
        # The Add Product page has an edit mode
        return render_template('products/add_product.html', edit_mode=True, product=product)

    back = redirect(url_for('products.edit_product', product_id=product_id))
    product_name = request.form.get('product_name', '').strip()
    if not product_name:
        flash("Product name is required.", "error")
        return back

    selling_price, purchase_price = _money('selling_price'), _money('purchase_price')
    if selling_price is None or purchase_price is None or selling_price < 0 or purchase_price < 0:
        flash("Prices must be valid numbers and cannot be negative.", "error")
        return back
    try:
        reorder_level = int(request.form.get('reorder_level') or product.get('reorder_level') or 5)
    except ValueError:
        reorder_level = 5

    product_image = save_image(request.files.get('product_image'),
                               f"uploads/products/{product['category_name']}")
    if product_image is None:
        flash("Product image must be a PNG, JPG or GIF.", "error")
        return back
    product_image = product_image or product.get('product_image') or ''

    detail_columns = PRODUCT_DETAIL_COLUMNS + ['warranty']
    sets = ', '.join(f"{c} = %s" for c in ['product_name', 'product_image', 'product_description',
                                            'selling_price', 'purchase_price'] + detail_columns)
    values = [product_name, product_image, request.form.get('product_description', ''), selling_price,
              purchase_price] + [request.form.get(c, product.get(c) or '') for c in detail_columns]
    db.execute(f"UPDATE products SET {sets} WHERE product_id = %s", values + [product_id])

    # Quantity is changed through stock transactions so the history stays correct
    db.execute("""
        UPDATE stock SET purchase_price = %s, selling_price = %s, reorder_level = %s WHERE product_id = %s
    """, (purchase_price, selling_price, reorder_level, product_id))
    db.commit()
    flash('Product updated successfully!', 'success')
    return redirect(url_for('products.view_product', product_id=product_id))


@bp.route('/products/delete/<int:product_id>', methods=DELETE_METHODS)
def delete_product(product_id):
    if db.query_value("SELECT COUNT(*) FROM bill_items WHERE product_id = %s", (product_id,)):
        flash('Cannot delete product as it has been sold in bills', 'error')
    else:
        db.execute("DELETE FROM stock_transactions WHERE product_id = %s", (product_id,))
        db.execute("DELETE FROM stock WHERE product_id = %s", (product_id,))
        db.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
        db.commit()
        flash('Product deleted successfully!', 'success')
    return redirect(url_for('products.products'))
