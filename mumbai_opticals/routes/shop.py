"""Public shop: product catalogue on the home page, product pages, reviews, questions
and WhatsApp ordering."""
import re
import time
from urllib.parse import quote

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

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
           COALESCE(s.quantity, 0) AS quantity,
           COALESCE(rv.avg_rating, 0) AS avg_rating, COALESCE(rv.review_count, 0) AS review_count
    FROM products p
    JOIN product_types pt ON pt.type_id = p.product_type_id
    JOIN product_categories pc ON pc.category_id = pt.category_id
    LEFT JOIN stock s ON s.product_id = p.product_id
    LEFT JOIN (
        SELECT product_id, AVG(rating) AS avg_rating, COUNT(*) AS review_count
        FROM product_reviews WHERE status = 'published' GROUP BY product_id
    ) rv ON rv.product_id = p.product_id
"""
IN_STOCK_FIRST = "(COALESCE(s.quantity, 0) > 0) DESC"

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

REVIEWS_PER_HOUR = 5
RECENTLY_VIEWED = 8


# ---------------------------------------------------------------- helpers

def order_number():
    """Manager's WhatsApp number: config.ORDER_WHATSAPP, else the shop phone."""
    number = current_app.config.get('ORDER_WHATSAPP') or get_company().get('phone') or ''
    digits = re.sub(r'\D', '', str(number))
    if len(digits) == 10:  # Indian mobile without country code
        digits = '91' + digits
    return digits


def contact_link():
    message = quote(f"Hello {get_company()['name']}! I have a question about your products.")
    return f"https://wa.me/{order_number()}?text={message}"


def _price(value):
    amount = float(value or 0)
    return f"₹{amount:,.0f}" if amount == int(amount) else f"₹{amount:,.2f}"


def _photos_for(product_ids):
    """{product_id: [static paths]} in display order."""
    if not product_ids:
        return {}
    marks = ', '.join(['%s'] * len(product_ids))
    rows = db.query_all(f"""
        SELECT product_id, path FROM product_images WHERE product_id IN ({marks})
        ORDER BY product_id, sort_order, image_id
    """, list(product_ids))
    photos = {}
    for row in rows:
        photos.setdefault(row['product_id'], []).append(row['path'])
    return photos


def _prepare(product, photos=None):
    product['price_text'] = _price(product['selling_price'])
    product['in_stock'] = int(product['quantity'] or 0) > 0
    product['icon'] = TYPE_ICONS.get(product['type_name'], 'fa-box')
    product['details'] = [(label, product[key]) for key, label in DETAIL_LABELS if product.get(key)]
    product['summary'] = ' · '.join(str(v) for _, v in product['details'][:3])
    paths = (photos or {}).get(product['product_id']) or ([product['product_image']] if product.get('product_image') else [])
    product['images'] = [url_for('static', filename=p) for p in paths]
    product['image_url'] = product['images'][0] if product['images'] else None
    product['rating'] = round(float(product.get('avg_rating') or 0), 1)
    product['review_count'] = int(product.get('review_count') or 0)
    product['order_url'] = order_link(product)
    return product


def _prepare_all(rows):
    photos = _photos_for([r['product_id'] for r in rows])
    return [_prepare(r, photos) for r in rows]


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


# ---------------------------------------------------------------- pages

def shop_page():
    products = _prepare_all(db.query_all(
        PUBLIC_SELECT + f" ORDER BY {IN_STOCK_FIRST}, p.created_at DESC, p.product_id DESC"))
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


@bp.route('/shop/<int:product_id>')
def product(product_id):
    row = db.query_one(PUBLIC_SELECT + " WHERE p.product_id = %s", (product_id,))
    if not row:
        return redirect(url_for('main.index'))
    item = _prepare_all([row])[0]

    # Ratings breakdown and reviews
    counts = {star: 0 for star in range(5, 0, -1)}
    for r in db.query_all("""
        SELECT rating, COUNT(*) AS n FROM product_reviews
        WHERE product_id = %s AND status = 'published' GROUP BY rating
    """, (product_id,)):
        counts[int(r['rating'])] = int(r['n'])
    total = sum(counts.values())
    histogram = [{'star': s, 'count': n, 'percent': round(n * 100 / total) if total else 0} for s, n in counts.items()]

    sort = request.args.get('sort', 'top')
    order = "r.created_at DESC" if sort == 'recent' else "r.helpful DESC, r.verified DESC, r.created_at DESC"
    reviews = db.query_all(f"""
        SELECT r.review_id, r.name, r.rating, r.title, r.body, r.verified, r.helpful,
               DATE_FORMAT(r.created_at, '%d %M %Y') AS created
        FROM product_reviews r WHERE r.product_id = %s AND r.status = 'published'
        ORDER BY {order}
    """, (product_id,))
    questions = db.query_all("""
        SELECT name, question, answer, DATE_FORMAT(answered_at, '%d %M %Y') AS answered
        FROM product_questions WHERE product_id = %s AND status = 'published'
        ORDER BY answered_at DESC
    """, (product_id,))

    # Recommendations
    together_ids = [r['product_id'] for r in db.query_all("""
        SELECT bi2.product_id, COUNT(DISTINCT bi2.bill_id) AS times
        FROM bill_items bi1
        JOIN bill_items bi2 ON bi2.bill_id = bi1.bill_id AND bi2.product_id != bi1.product_id
        JOIN bills b ON b.bill_id = bi1.bill_id AND b.status != 'CANCELLED'
        WHERE bi1.product_id = %s
        GROUP BY bi2.product_id ORDER BY times DESC LIMIT 6
    """, (product_id,))]
    together = _products_by_ids(together_ids)
    similar = _prepare_all(db.query_all(PUBLIC_SELECT + f"""
        WHERE pt.type_id = %s AND p.product_id != %s
        ORDER BY {IN_STOCK_FIRST}, COALESCE(rv.avg_rating, 0) DESC, ABS(p.selling_price - %s) LIMIT 10
    """, (row['type_id'], product_id, row['selling_price'] or 0)))
    shown = {product_id} | {p['product_id'] for p in together + similar}
    popular = [p for p in _prepare_all(db.query_all(PUBLIC_SELECT + """
        LEFT JOIN (SELECT bi.product_id, SUM(bi.quantity) AS sold FROM bill_items bi
                   JOIN bills b ON b.bill_id = bi.bill_id AND b.status != 'CANCELLED'
                   GROUP BY bi.product_id) sales ON sales.product_id = p.product_id
        WHERE COALESCE(s.quantity, 0) > 0
        ORDER BY COALESCE(sales.sold, 0) DESC, COALESCE(rv.review_count, 0) DESC, p.created_at DESC LIMIT 16
    """)) if p['product_id'] not in shown][:10]

    # Recently viewed (kept in the visitor's session)
    viewed = [pid for pid in session.get('recently_viewed', []) if pid != product_id]
    recent = _products_by_ids(viewed[:RECENTLY_VIEWED])
    session['recently_viewed'] = ([product_id] + viewed)[:RECENTLY_VIEWED]

    return render_template('public/product.html', product=item, contact_url=contact_link(),
                           histogram=histogram, reviews=reviews, questions=questions, sort=sort,
                           together=together, similar=similar, popular=popular, recent=recent,
                           helpful_votes=set(session.get('helpful_votes', [])),
                           already_reviewed=product_id in session.get('reviewed', []))


def _products_by_ids(ids):
    if not ids:
        return []
    marks = ', '.join(['%s'] * len(ids))
    rows = {r['product_id']: r for r in db.query_all(PUBLIC_SELECT + f" WHERE p.product_id IN ({marks})", ids)}
    return _prepare_all([rows[i] for i in ids if i in rows])


# ---------------------------------------------------------------- customer input

def _clean(text, limit):
    return re.sub(r'\s+\n', '\n', (text or '').strip())[:limit]


def _too_many(key, per_hour):
    now = time.time()
    recent = [t for t in session.get(key, []) if now - t < 3600]
    session[key] = recent
    return len(recent) >= per_hour


def _note(key):
    session[key] = session.get(key, []) + [time.time()]


@bp.route('/shop/<int:product_id>/review', methods=['POST'])
def add_review(product_id):
    back = redirect(url_for('shop.product', product_id=product_id) + '#reviews')
    if request.form.get('website'):  # hidden field only bots fill in
        return back
    if not db.query_value("SELECT COUNT(*) FROM products WHERE product_id = %s", (product_id,)):
        return redirect(url_for('main.index'))

    name = _clean(request.form.get('name'), 80)
    title = _clean(request.form.get('title'), 150)
    body = _clean(request.form.get('body'), 3000)
    phone = re.sub(r'\D', '', request.form.get('phone') or '')[-10:]
    try:
        rating = int(request.form.get('rating') or 0)
    except ValueError:
        rating = 0

    if not 1 <= rating <= 5:
        flash("Please choose a star rating.", "error")
        return back
    if not name:
        flash("Please add your name.", "error")
        return back
    if product_id in session.get('reviewed', []):
        flash("You've already reviewed this product.", "error")
        return back
    if _too_many('review_times', REVIEWS_PER_HOUR):
        flash("You've written several reviews in the last hour. Please try again later.", "error")
        return back

    # "Verified purchase" when the phone number belongs to a customer who bought this product
    verified = 0
    if len(phone) == 10:
        verified = 1 if db.query_value("""
            SELECT COUNT(*) FROM bills b
            JOIN customers c ON c.customer_id = b.customer_id
            JOIN bill_items bi ON bi.bill_id = b.bill_id
            WHERE bi.product_id = %s AND b.status != 'CANCELLED'
              AND RIGHT(REGEXP_REPLACE(c.phone, '[^0-9]', ''), 10) = %s
        """, (product_id, phone)) else 0

    db.execute("""
        INSERT INTO product_reviews (product_id, name, phone, rating, title, body, verified)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (product_id, name, phone or None, rating, title or None, body or None, verified))
    db.commit()
    session['reviewed'] = session.get('reviewed', []) + [product_id]
    _note('review_times')
    flash("Thank you! Your review is now on this page.", "success")
    return back


@bp.route('/shop/<int:product_id>/question', methods=['POST'])
def ask_question(product_id):
    back = redirect(url_for('shop.product', product_id=product_id) + '#questions')
    if request.form.get('website'):
        return back
    name = _clean(request.form.get('name'), 80)
    question = _clean(request.form.get('question'), 1000)
    if not name or len(question) < 5:
        flash("Please add your name and a question.", "error")
        return back
    if _too_many('question_times', REVIEWS_PER_HOUR):
        flash("You've asked several questions in the last hour. Please try again later.", "error")
        return back
    if not db.query_value("SELECT COUNT(*) FROM products WHERE product_id = %s", (product_id,)):
        return redirect(url_for('main.index'))
    db.execute("INSERT INTO product_questions (product_id, name, question) VALUES (%s, %s, %s)",
               (product_id, name, question))
    db.commit()
    _note('question_times')
    flash("Thanks! We'll answer here soon. For a quick reply, message us on WhatsApp.", "success")
    return back


@bp.route('/shop/review/<int:review_id>/helpful', methods=['POST'])
def helpful(review_id):
    votes = session.get('helpful_votes', [])
    product_id = db.query_value("SELECT product_id FROM product_reviews WHERE review_id = %s", (review_id,))
    if product_id is None:
        return redirect(url_for('main.index'))
    if review_id not in votes:
        db.execute("UPDATE product_reviews SET helpful = helpful + 1 WHERE review_id = %s", (review_id,))
        db.commit()
        session['helpful_votes'] = (votes + [review_id])[-200:]
    return redirect(url_for('shop.product', product_id=product_id, sort=request.args.get('sort', 'top'))
                    + f'#review-{review_id}')
