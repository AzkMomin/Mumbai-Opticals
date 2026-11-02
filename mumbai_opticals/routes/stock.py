"""Stock: add stock, low stock, stock movement history (edit/delete)."""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from .. import db
from ..auth import require_login
from ..helpers import DELETE_METHODS, change_stock, stock_effect

bp = Blueprint('stock', __name__)
bp.before_request(require_login)

TRANSACTION_TYPES = ('PURCHASE', 'SALE', 'RETURN', 'ADJUSTMENT')


@bp.route('/products/add_stock', methods=['GET', 'POST'])
def add_stock():
    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        quantity = request.form.get('quantity', type=int)
        if not product_id or not quantity or quantity <= 0:
            flash('Please choose a product and a quantity greater than 0.', 'error')
            return redirect(url_for('stock.add_stock'))
        if not db.query_one("SELECT product_id FROM stock WHERE product_id = %s", (product_id,)):
            db.execute("INSERT INTO stock (product_id, quantity) VALUES (%s, 0)", (product_id,))
        change_stock(product_id, 'PURCHASE', quantity, product_id, 'MANUAL_STOCK',
                     f'Added {quantity} units. Previous: {{previous}}, New: {{new}}')
        db.commit()
        flash('Stock updated successfully!', 'success')
        return redirect(url_for('products.products'))

    products = db.query_all("""
        SELECT p.product_id, p.product_name, p.product_image, p.selling_price,
               pt.type_name, pc.category_name, COALESCE(s.quantity, 0) AS quantity
        FROM products p
        JOIN product_types pt ON p.product_type_id = pt.type_id
        JOIN product_categories pc ON pt.category_id = pc.category_id
        LEFT JOIN stock s ON p.product_id = s.product_id
        ORDER BY p.created_at DESC
    """)
    return render_template('stock/add_stock.html', products=products)


@bp.route('/products/low_stock')
def low_stock():
    products = db.query_all("""
        SELECT p.*, pt.type_name, pc.category_name, s.quantity, s.reorder_level
        FROM products p
        JOIN product_types pt ON p.product_type_id = pt.type_id
        JOIN product_categories pc ON pt.category_id = pc.category_id
        JOIN stock s ON p.product_id = s.product_id
        WHERE s.quantity <= s.reorder_level
        ORDER BY s.quantity ASC
    """)
    return render_template('stock/low_stock.html', products=products)


@bp.route('/products/stock_transactions')
def stock_transactions():
    filter_type = request.args.get('type', 'all')
    sql = """
        SELECT st.*, p.product_name, p.model_code, p.product_id, pt.type_name, pc.category_name,
               DATE_FORMAT(st.created_at, '%d/%m/%Y %h:%i %p') AS formatted_date
        FROM stock_transactions st
        JOIN products p ON st.product_id = p.product_id
        JOIN product_types pt ON p.product_type_id = pt.type_id
        JOIN product_categories pc ON pt.category_id = pc.category_id
    """
    params = []
    if filter_type != 'all':
        sql += " WHERE st.transaction_type = %s"
        params.append(filter_type.upper())
    sql += " ORDER BY st.created_at DESC, st.transaction_id DESC LIMIT 100"

    all_products = db.query_all("""
        SELECT p.product_id, p.product_name, pt.type_name
        FROM products p JOIN product_types pt ON p.product_type_id = pt.type_id
        ORDER BY p.product_name
    """)
    return render_template('stock/stock_transactions.html', transactions=db.query_all(sql, params),
                           all_products=all_products, current_filter=filter_type)


@bp.route('/get_stock_transaction/<int:transaction_id>')
def get_stock_transaction(transaction_id):
    transaction = db.query_one("""
        SELECT st.*, p.product_name FROM stock_transactions st
        JOIN products p ON st.product_id = p.product_id
        WHERE st.transaction_id = %s
    """, (transaction_id,))
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    return jsonify(transaction)


@bp.route('/products/edit_stock_transaction', methods=['POST'])
def edit_stock_transaction():
    transaction_id = request.form.get('transaction_id', type=int)
    product_id = request.form.get('product_id', type=int)
    transaction_type = (request.form.get('transaction_type') or '').upper()
    quantity = request.form.get('quantity', type=int)
    notes = request.form.get('notes', '')

    original = db.query_one("SELECT * FROM stock_transactions WHERE transaction_id = %s", (transaction_id,))
    if not original:
        flash('Transaction not found', 'error')
        return redirect(url_for('stock.stock_transactions'))
    if not product_id or quantity is None or quantity < 0 or transaction_type not in TRANSACTION_TYPES:
        flash('Please enter a valid product, type and quantity.', 'error')
        return redirect(url_for('stock.stock_transactions'))

    # Undo the original movement
    db.execute("UPDATE stock SET quantity = quantity - %s WHERE product_id = %s",
               (stock_effect(original), original['product_id']))

    current_quantity = db.query_value("SELECT quantity FROM stock WHERE product_id = %s", (product_id,)) or 0
    if transaction_type in ('PURCHASE', 'RETURN'):
        new_quantity = current_quantity + quantity
    elif transaction_type == 'SALE':
        new_quantity = current_quantity - quantity
    else:  # ADJUSTMENT sets the stock to the given quantity
        new_quantity = quantity

    db.execute("""
        UPDATE stock_transactions SET product_id = %s, transaction_type = %s, quantity = %s,
               previous_quantity = %s, new_quantity = %s, notes = %s
        WHERE transaction_id = %s
    """, (product_id, transaction_type, quantity, current_quantity, new_quantity, notes, transaction_id))
    db.execute("UPDATE stock SET quantity = %s WHERE product_id = %s", (new_quantity, product_id))
    db.commit()

    flash('Stock transaction updated successfully!', 'success')
    return redirect(url_for('stock.stock_transactions'))


@bp.route('/products/delete_stock_transaction/<int:transaction_id>', methods=DELETE_METHODS)
def delete_stock_transaction(transaction_id):
    transaction = db.query_one("SELECT * FROM stock_transactions WHERE transaction_id = %s", (transaction_id,))
    if not transaction:
        flash('Transaction not found', 'error')
        return redirect(url_for('stock.stock_transactions'))

    db.execute("UPDATE stock SET quantity = quantity - %s WHERE product_id = %s",
               (stock_effect(transaction), transaction['product_id']))
    db.execute("DELETE FROM stock_transactions WHERE transaction_id = %s", (transaction_id,))
    db.commit()
    flash('Stock transaction deleted successfully! Stock has been reverted.', 'success')
    return redirect(url_for('stock.stock_transactions'))
