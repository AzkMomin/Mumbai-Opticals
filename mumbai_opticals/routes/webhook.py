"""GitHub -> PythonAnywhere auto-deploy.

GitHub calls this URL on every push. If the request is signed with WEBHOOK_SECRET
(set in config.py on the server), it pulls the latest code and reloads the site.
"""
import getpass
import hashlib
import hmac
import os
import subprocess

from flask import Blueprint, abort, current_app, jsonify, request

from ..settings import BASE_DIR

bp = Blueprint('webhook', __name__)

DEPLOY_BRANCH = 'main'


@bp.route('/git-webhook', methods=['POST'])
def git_webhook():
    secret = current_app.config.get('WEBHOOK_SECRET')
    if not secret:
        return jsonify(error='Webhook not configured'), 503

    signature = request.headers.get('X-Hub-Signature-256', '')
    expected = 'sha256=' + hmac.new(secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        abort(403)

    event = request.headers.get('X-GitHub-Event', '')
    if event == 'ping':
        return jsonify(status='pong'), 200
    if event != 'push':
        return jsonify(status=f'ignored event {event}'), 200

    payload = request.get_json(silent=True) or {}
    if payload.get('ref') != f'refs/heads/{DEPLOY_BRANCH}':
        return jsonify(status='ignored branch', ref=payload.get('ref')), 200

    try:
        result = subprocess.run(['git', 'pull', '--ff-only', 'origin', DEPLOY_BRANCH],
                                cwd=BASE_DIR, capture_output=True, text=True, timeout=120)
    except Exception as e:
        return jsonify(status='pull failed', error=str(e)), 500
    if result.returncode != 0:
        return jsonify(status='pull failed', output=result.stdout + result.stderr), 500

    # Touching the WSGI file makes PythonAnywhere reload the web app
    wsgi_file = current_app.config.get('WSGI_FILE') or \
        f"/var/www/{getpass.getuser()}_pythonanywhere_com_wsgi.py"
    try:
        os.utime(wsgi_file, None)
    except OSError as e:
        return jsonify(status='pulled, reload failed', error=str(e), output=result.stdout), 500

    return jsonify(status='deployed', output=result.stdout), 200
