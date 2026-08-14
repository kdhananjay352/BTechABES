"""
Authentication Blueprint Routes
Handles user registration, login, logout, and credential validation.
"""

import os
from flask import Flask, redirect, url_for, flash, request, jsonify, session
from flask_wtf.csrf import CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from extensions import db, login_manager, csrf
from routes.auth import auth_bp
from routes.main import main_bp
from datetime import timedelta

limiter = Limiter(key_func=get_remote_address, default_limits=[
    "200 per day", "50 per hour"], storage_uri="memory://")


def create_app():
    """Create and configure the Flask application."""

    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)
    
    # 10-Minute Idle Timeout Configuration
    flask_app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)

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

    # ==============================================================================
    # GLOBAL RATE LIMIT ERROR HANDLER (429)
    # ==============================================================================
    @flask_app.errorhandler(429)
    def ratelimit_handler(_e):
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'valid': False, 'errors': {'rate_limit': 'Too many requests. Please try again later.'}}), 429

        flash('Too many requests. Please wait 60 seconds before trying again.', 'danger')
        return redirect(url_for('auth.login'))

    return flask_app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=8080)