"""Public shop: product catalogue on the home page, product pages, WhatsApp ordering."""
import re
from urllib.parse import quote

from flask import Blueprint, current_app, redirect, render_template, url_for

from .. import db
from ..helpers import get_company

bp = Blueprint('shop', __name__)

# Only these columns are ever shown publicly (never purchase prices)
PUBLIC_SELECT = """
    SELECT p.product_id, p.product_name, p.product_description, p.product_image, p.selling_price,
           p.frame_type, p.material, p.model_name, p.model_code, p.model_color, p.model_size,
           p.lens_type, p.which_side, p.lens_for, p.company,
           p.watch_type, p.watch_mechanism, p.strap_material, p.water_resistance, p.dial_color,
           pt.type_id, pt.type_name, pc.category_id, pc.category_name,
           COALESCE(s.quantity, 0) AS quantity
    FROM products p
    JOIN product_types pt ON pt.type_id = p.product_type_id
    JOIN product_categories pc ON pc.category_id = pt.category_id
    LEFT JOIN stock s ON s.product_id = p.product_id
"""

# Details worth showing a customer, by field
DETAIL_LABELS = [
    ('model_name', 'Model'), ('model_code', 'Code'), ('frame_type', 'Frame'), ('material', 'Material'),
    ('model_color', 'Colour'), ('model_size', 'Size'), ('lens_type', 'Lens'), ('lens_for', 'For'),
    ('which_side', 'Side'), ('company', 'Brand'), ('watch_type', 'Type'), ('watch_mechanism', 'Movement'),
    ('strap_material', 'Strap'), ('dial_color', 'Dial'), ('water_resistance', 'Water resistance'),
]

TYPE_ICONS = {
    'Frames': 'fa-glasses', 'Goggles': 'fa-glasses', 'Lenses': 'fa-eye',
    'Wrist Watches': 'fa-clock', 'Hand Watches': 'fa-clock',
}


def order_number():
    """Manager's WhatsApp number: config.ORDER_WHATSAPP, else the shop phone."""
    number = current_app.config.get('ORDER_WHATSAPP') or get_company().get('phone') or ''
    digits = re.sub(r'\D', '', str(number))
    if len(digits) == 10:  # Indian mobile without country code
        digits = '91' + digits
    return digits


def _price(value):
    amount = float(value or 0)
    return f"₹{amount:,.0f}" if amount == int(amount) else f"₹{amount:,.2f}"


def _prepare(product):
    product['price_text'] = _price(product['selling_price'])
    product['in_stock'] = int(product['quantity'] or 0) > 0
    product['icon'] = TYPE_ICONS.get(product['type_name'], 'fa-box')
    product['details'] = [(label, product[key]) for key, label in DETAIL_LABELS if product.get(key)]
    product['summary'] = ' · '.join(str(v) for _, v in product['details'][:3])
    product['image_url'] = url_for('static', filename=product['product_image']) if product.get('product_image') else None
    product['order_url'] = order_link(product)
    return product


def order_link(product):
    """wa.me link with a ready-to-send message for this product."""
    company = get_company()
    link = url_for('shop.product', product_id=product['product_id'], _external=True)
    details = '\n'.join(f"• {label}: {value}" for label, value in product['details'][:5])
    if int(product['quantity'] or 0) > 0:
        message = (
            f"Hello {company['name']}! 👋\n\n"
            f"I'd like to order this from your website:\n\n"
            f"🛍️ *{product['product_name']}*\n"
            f"• Category: {product['type_name']}\n"
            + (details + "\n" if details else "")
            + f"• Price: {_price(product['selling_price'])}\n"
            f"• Quantity: 1\n\n"
            f"🔗 {link}\n\n"
            f"My name: \n"
            f"Pickup from shop / delivery address: \n\n"
            f"Please confirm availability and the total. Thank you!"
        )
    else:
        message = (
            f"Hello {company['name']}! 👋\n\n"
            f"I saw *{product['product_name']}* ({product['type_name']}, {_price(product['selling_price'])}) "
            f"on your website and it shows out of stock.\n\n"
            f"🔗 {link}\n\n"
            f"Could you let me know when it will be available, or suggest something similar?\n\n"
            f"My name: \n\nThank you!"
        )
    return f"https://wa.me/{order_number()}?text={quote(message)}"


def shop_page():
    products = [_prepare(p) for p in db.query_all(
        PUBLIC_SELECT + " ORDER BY (COALESCE(s.quantity, 0) > 0) DESC, p.created_at DESC, p.product_id DESC")]
    categories = []
    for p in products:
        cat = next((c for c in categories if c['id'] == p['category_id']), None)
        if not cat:
            cat = {'id': p['category_id'], 'name': p['category_name'], 'types': [], 'count': 0}
            categories.append(cat)
        cat['count'] += 1
        if not any(t['id'] == p['type_id'] for t in cat['types']):
            cat['types'].append({'id': p['type_id'], 'name': p['type_name']})
    # Biggest categories first, "Misc"-style catch-alls last
    categories.sort(key=lambda c: (c['name'].lower() in ('misc', 'other', 'others'), -c['count'], c['name']))
    return render_template('public/index.html', products=products, categories=categories,
                           contact_url=contact_link())


def contact_link():
    message = quote(f"Hello {get_company()['name']}! I have a question about your products.")
    return f"https://wa.me/{order_number()}?text={message}"


@bp.route('/shop/<int:product_id>')
def product(product_id):
    row = db.query_one(PUBLIC_SELECT + " WHERE p.product_id = %s", (product_id,))
    if not row:
        return redirect(url_for('main.index'))
    item = _prepare(row)
    related = [_prepare(p) for p in db.query_all(
        PUBLIC_SELECT + " WHERE pt.type_id = %s AND p.product_id != %s ORDER BY (COALESCE(s.quantity, 0) > 0) DESC, "
                        "p.created_at DESC LIMIT 4", (row['type_id'], product_id))]
    return render_template('public/product.html', product=item, related=related, contact_url=contact_link())
