"""Protection against forged form submissions (CSRF).

Every staff form and data-changing fetch() sends a per-session token, added
automatically by static/js/app.js. Requests without the right token are refused.
"""
import secrets

from flask import abort, flash, jsonify, redirect, request, session

SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}
# Public endpoints that can't carry a token (GitHub webhook) or don't need one
EXEMPT_ENDPOINTS = {'webhook.git_webhook', 'auth.user_login', 'portal.customer_view_bill'}


def csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = session['_csrf_token'] = secrets.token_urlsafe(32)
    return token


def check_csrf():
    if request.method in SAFE_METHODS or request.endpoint in EXEMPT_ENDPOINTS or request.endpoint is None:
        return None
    sent = request.form.get('csrf_token') or request.headers.get('X-CSRFToken', '')
    expected = session.get('_csrf_token', '')
    if expected and sent and secrets.compare_digest(sent, expected):
        return None
    if request.accept_mimetypes.best == 'application/json':
        return jsonify(error='Session expired, please reload the page.'), 400
    flash("Your session expired or the form was out of date. Please try again.", "error")
    target = request.referrer if request.referrer and request.referrer.startswith(request.host_url) else None
    return redirect(target) if target else abort(400)
