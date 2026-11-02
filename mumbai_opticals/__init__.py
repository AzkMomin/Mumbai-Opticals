"""Mumbai Opticals shop management app."""
import os
import secrets
from datetime import datetime

from flask import Flask, jsonify, render_template, request, url_for
from werkzeug.exceptions import HTTPException

from . import db
from .helpers import error_page, get_company
from .schema import ensure_schema
from .security import check_csrf, csrf_token
from .settings import BASE_DIR, CDN, MAX_UPLOAD_BYTES, STATIC_DIR, load_local_config

# Endpoints that answer with JSON (used by page scripts)
JSON_ENDPOINTS = {
    'customers.search_customers', 'products.get_product_fields', 'bills.search_products',
    'prescriptions.get_customer_prescriptions', 'stock.get_stock_transaction', 'webhook.git_webhook',
}


def _secret_key(configured):
    """Use SECRET_KEY from config.py, else a key file created once (not in git), so
    staff stay logged in across reloads and deploys."""
    if configured:
        return configured
    key_file = os.path.join(BASE_DIR, '.secret_key')
    try:
        with open(key_file) as f:
            key = f.read().strip()
        if key:
            return key
    except FileNotFoundError:
        pass
    key = secrets.token_hex(32)
    with open(key_file, 'w') as f:
        f.write(key)
    os.chmod(key_file, 0o600)
    return key


def create_app():
    app = Flask(__name__,
                template_folder=os.path.join(BASE_DIR, 'templates'),
                static_folder=os.path.join(BASE_DIR, 'static'),
                static_url_path='/static')

    app.config.update(load_local_config())
    app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_BYTES
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.secret_key = _secret_key(app.config.get('SECRET_KEY'))

    from .routes import BLUEPRINTS
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    app.teardown_appcontext(db.close_db)
    app.before_request(check_csrf)
    app.before_request(ensure_schema)

    @app.after_request
    def security_headers(response):
        if request.endpoint == 'static':
            # Files are versioned with ?v=..., so browsers may keep them for a long time
            if request.args.get('v'):
                response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        else:
            # Don't let the browser show staff pages from cache after logout
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        return response

    @app.errorhandler(Exception)
    def handle_error(e):
        if isinstance(e, HTTPException):
            if request.endpoint in JSON_ENDPOINTS:
                return jsonify(error=e.name), e.code
            if e.code == 404:
                return render_template('errors/error.html', error="Page not found."), 404
            return e
        if request.endpoint in JSON_ENDPOINTS:
            app.logger.exception("Request failed: %s", e)
            return jsonify(error='Server error'), 500
        return error_page(e)

    asset_versions = {}

    def asset(path):
        """URL for a file in static/, with a version so browsers fetch it again after a deploy."""
        if path not in asset_versions:
            try:
                asset_versions[path] = int(os.path.getmtime(os.path.join(STATIC_DIR, path)))
            except OSError:
                asset_versions[path] = 0
        return url_for('static', filename=path, v=asset_versions[path])

    @app.context_processor
    def template_helpers():
        return {'now': datetime.now, 'asset': asset, 'cdn': CDN, 'csrf_token': csrf_token, 'company': get_company()}

    return app
