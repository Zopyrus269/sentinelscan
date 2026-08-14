"""
Flask entrypoint for the SentinelScan backend.
"""

import os

from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from apps.backend.extensions import limiter

load_dotenv()

from apps.backend.routes.scan_routes import scan_bp
from apps.backend.routes.auth_routes import auth_bp
from apps.backend.routes.history_routes import history_bp
from apps.backend.routes.dev_routes import dev_bp

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


def create_app() -> Flask:
    """Application factory -- builds and configures the Flask app."""
    app = Flask(__name__, static_folder=os.path.join(FRONTEND_DIR, "static"), static_url_path="/static")
    
    # Harden CORS
    allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    CORS(app, origins=allowed_origins)
    
    limiter.init_app(app)
    
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
    app.register_blueprint(scan_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(dev_bp)

    @app.after_request
    def add_security_headers(response):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://www.gstatic.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self' https://*.googleapis.com; "
            "img-src 'self' data: https://*.googleusercontent.com; "
            "frame-ancestors 'none'; "
            "object-src 'none';"
        )
        response.headers['Content-Security-Policy'] = csp
        response.headers.pop('Server', None)
        response.headers.pop('X-Powered-By', None)
        return response

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/")
    def serve_index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/dashboard")
    def serve_dashboard():
        return send_from_directory(FRONTEND_DIR, "dashboard.html")

    @app.route("/report")
    def serve_report():
        return send_from_directory(FRONTEND_DIR, "report.html")

    @app.route("/documentation")
    def serve_documentation():
        return send_from_directory(FRONTEND_DIR, "documentation.html")

    # privacy.html, terms.html, api-reference.html, responsible-disclosure.html,
    # and status.html (and their /privacy, /terms, /api-reference,
    # /responsible-disclosure, /status routes) were removed -- their content
    # now lives entirely in the documentation page's own sections (see
    # DocsExplorer.jsx). The site-wide footer's Privacy Policy/Terms links
    # point at /documentation#privacy and /documentation#terms instead.

    @app.route("/<path:filename>")
    def serve_static(filename):
        return send_from_directory(FRONTEND_DIR, filename)

    return app


app = create_app()

if __name__ == "__main__":
    is_debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']
    app.run(debug=is_debug, port=5000)
