"""
Authentication Blueprint Routes
Handles user registration, login, logout, and credential validation.
"""

import os
from flask import Flask, redirect, url_for, flash, request, jsonify, session, render_template
from flask_wtf.csrf import CSRFError
from config import Config
from extensions import db, login_manager, csrf
from routes.auth import auth_bp
from routes.main import main_bp
from rate_limiter import limiter
from datetime import datetime, timedelta


def create_app():
    """Create and configure the Flask application."""

    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)

    # 10-Minute Idle Timeout Configuration
    flask_app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)

    @flask_app.context_processor
    def inject_template_globals():
        return {'current_year': datetime.now().year}

    # Ensure upload directories exist
    os.makedirs(flask_app.config['UPLOAD_FOLDER_FACES'], exist_ok=True)
    os.makedirs(flask_app.config['UPLOAD_FOLDER_ENCODINGS'], exist_ok=True)

    # Initialize extensions
    db.init_app(flask_app)
    login_manager.init_app(flask_app)
    csrf.init_app(flask_app)
    limiter.init_app(flask_app)

    # Register blueprints
    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(main_bp)

    # Automatically initialize SQLite tables
    with flask_app.app_context():
        db.create_all()

    # ==============================================================================
    # SESSION TIMEOUT HOOK
    # ==============================================================================
    @flask_app.before_request
    def refresh_session_timeout():
        # Make the session permanent to respect the PERMANENT_SESSION_LIFETIME
        session.permanent = True
        # Mark it as modified so the timer resets on every request
        session.modified = True

    # ==============================================================================
    # GLOBAL CSRF ERROR HANDLER
    # ==============================================================================
    @flask_app.errorhandler(CSRFError)
    def handle_csrf_error(_e):
        if request.path.endswith(('.ico', '.png', '.jpg', '.css', '.js')):
            return '', 204

        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'valid': False,
                'errors': {'csrf': 'Session expired or invalid CSRF token. Please refresh.'}
            }), 400

        flashed = session.get('_flashes', [])
        warning_msg = 'Session security token expired or missing. Please sign in again.'
        if not any(msg == warning_msg for _, msg in flashed):
            flash(warning_msg, 'warning')

        return redirect(url_for('auth.login'))

    # ===========================================================================
    # BROWSER NAVIGATION ERROR HANDLERS
    # ===========================================================================
    def redirect_browser_error(_error, status_code):
        """Keep invalid browser URLs inside the authentication flow."""
        if request.path.startswith('/static/') or request.path.startswith('/favicon'):
            return '', status_code

        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': 'The requested resource was not found.' if status_code == 404
                else 'You are not authorized to access this resource.'
            }), status_code

        # If the failing path is already the login page, render it instead of
        # redirecting back to it — this prevents a redirect loop when the
        # browser is navigating between a protected page and the login URL.
        try:
            login_path = url_for('auth.login')
        except Exception:
            login_path = '/login'

        if request.path == login_path or request.path.startswith(login_path):
            # Render the login page with the requested status code so the
            # browser receives a normal response instead of a redirect.
            return render_template('login.html'), status_code

        if status_code == 404:
            flash('The page you requested was not found. Please sign in to continue.', 'warning')
        else:
            flash('Please sign in with an authorized account to continue.', 'warning')
        return redirect(url_for('auth.login'))

    @flask_app.errorhandler(404)
    def handle_not_found(error):
        return redirect_browser_error(error, 404)

    @flask_app.errorhandler(403)
    def handle_forbidden(error):
        return redirect_browser_error(error, 403)

    # ==============================================================================
    # GLOBAL RATE LIMIT ERROR HANDLER (429)
    # ==============================================================================
    @flask_app.errorhandler(429)
    def ratelimit_handler(_e):
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'valid': False, 'errors': {'rate_limit': 'Too many requests. Please try again later.'}}), 429

        if request.path.startswith('/static/') or request.path.startswith('/favicon'):
            return '', 429

        message = 'Too many requests. Please wait a moment before trying again.'
        flash(message, 'warning')

        if request.referrer:
            return redirect(request.referrer)
        return redirect(url_for('main.attendance'))

    return flask_app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=8080)
