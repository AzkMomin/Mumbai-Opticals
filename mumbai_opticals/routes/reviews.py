"""Staff: moderate customer reviews and answer product questions."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .. import db
from ..auth import require_login

bp = Blueprint('reviews', __name__)
bp.before_request(require_login)


@bp.app_context_processor
def pending_count():
    """Number of unanswered questions, for the sidebar badge (staff pages only)."""
    if 'user_id' not in session:
        return {}
    try:
        return {'pending_questions': db.query_value(
            "SELECT COUNT(*) FROM product_questions WHERE status = 'pending'")}
    except Exception:
        return {}


@bp.route('/reviews')
def manage():
    product_id = request.args.get('product_id', type=int)
    tab = request.args.get('tab', 'questions' if not product_id else 'reviews')
    where, params = "", []
    if product_id:
        where, params = " AND r.product_id = %s", [product_id]

    reviews = db.query_all("""
        SELECT r.*, p.product_name, DATE_FORMAT(r.created_at, '%d/%m/%Y') AS created
        FROM product_reviews r JOIN products p ON p.product_id = r.product_id
        WHERE 1=1""" + where + " ORDER BY r.created_at DESC LIMIT 200", params)
    questions = db.query_all("""
        SELECT q.*, p.product_name, DATE_FORMAT(q.created_at, '%d/%m/%Y') AS created
        FROM product_questions q JOIN products p ON p.product_id = q.product_id
        WHERE 1=1""" + where.replace('r.', 'q.') + """
        ORDER BY q.status = 'pending' DESC, q.created_at DESC LIMIT 200""", params)
    summary = db.query_one("""
        SELECT COUNT(*) AS reviews, ROUND(AVG(rating), 1) AS average,
               SUM(status = 'hidden') AS hidden FROM product_reviews
    """)
    product = db.query_one("SELECT product_id, product_name FROM products WHERE product_id = %s",
                           (product_id,)) if product_id else None
    return render_template('reviews/manage.html', reviews=reviews, questions=questions, summary=summary,
                           tab=tab, product=product)


def _back():
    return redirect(request.referrer or url_for('reviews.manage'))


@bp.route('/reviews/<int:review_id>/toggle', methods=['POST'])
def toggle_review(review_id):
    db.execute("""
        UPDATE product_reviews SET status = IF(status = 'published', 'hidden', 'published') WHERE review_id = %s
    """, (review_id,))
    db.commit()
    flash("Review updated.", "success")
    return _back()


@bp.route('/reviews/<int:review_id>/delete', methods=['POST'])
def delete_review(review_id):
    db.execute("DELETE FROM product_reviews WHERE review_id = %s", (review_id,))
    db.commit()
    flash("Review deleted.", "success")
    return _back()


@bp.route('/questions/<int:question_id>/answer', methods=['POST'])
def answer_question(question_id):
    answer = (request.form.get('answer') or '').strip()[:2000]
    if not answer:
        flash("Write an answer before publishing.", "error")
        return _back()
    db.execute("""
        UPDATE product_questions SET answer = %s, answered_by = %s, answered_at = NOW(), status = 'published'
        WHERE question_id = %s
    """, (answer, session.get('user_id'), question_id))
    db.commit()
    flash("Answer published on the product page.", "success")
    return _back()


@bp.route('/questions/<int:question_id>/toggle', methods=['POST'])
def toggle_question(question_id):
    db.execute("""
        UPDATE product_questions SET status = CASE
            WHEN status = 'hidden' THEN IF(answer IS NULL OR answer = '', 'pending', 'published')
            ELSE 'hidden' END
        WHERE question_id = %s
    """, (question_id,))
    db.commit()
    flash("Question updated.", "success")
    return _back()


@bp.route('/questions/<int:question_id>/delete', methods=['POST'])
def delete_question(question_id):
    db.execute("DELETE FROM product_questions WHERE question_id = %s", (question_id,))
    db.commit()
    flash("Question deleted.", "success")
    return _back()
