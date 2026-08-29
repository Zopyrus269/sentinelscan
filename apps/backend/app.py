"""
Flask entrypoint for the SentinelScan backend.
"""

import os

from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from apps.backend.extensions import limiter

load_dotenv()

from apps.backend.routes.scan_routes import scan_bp
from apps.backend.routes.auth_routes import auth_bp
from apps.backend.routes.history_routes import history_bp
from apps.backend.routes.dev_routes import dev_bp
from apps.backend.routes.telemetry_routes import telemetry_bp
from apps.backend.logstore import pipeline

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


def create_app() -> Flask:
    """Application factory -- builds and configures the Flask app."""
    app = Flask(__name__, static_folder=os.path.join(FRONTEND_DIR, "static"), static_url_path="/static")
    
    # Harden CORS
    allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    CORS(app, origins=allowed_origins)
    
    # Render terminates TLS at its own proxy, so without this every request looks like it
    # came from that proxy's address -- and flask-limiter's per-IP buckets collapse into a
    # single shared one for the entire internet. Telemetry is the first high-frequency
    # endpoint here, so it is the first that would notice.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    limiter.init_app(app)

    # Installs the request/error hooks and logging bridge that record backend-originated
    # events (http, error, agent, worker, llm). Must come before pipeline.ensure_started()
    # below: observability.emit's queue is the same queue the sink thread drains (see
    # apps/backend/observability/emit.py), so the sink should be ready to drain by the
    # time the app starts accepting requests that could emit into it.
    from apps.backend.observability import init_app as init_observability
    init_observability(app)

    # Only stand up the sink thread when telemetry is actually switched on. Otherwise this
    # is a polling background thread and a hijacked SIGTERM handler serving a feature that
    # is off -- and off is the production default (see render.yaml).
    if pipeline.is_enabled():
        pipeline.ensure_started()

    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
    app.register_blueprint(scan_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(dev_bp)
    app.register_blueprint(telemetry_bp)

    @app.after_request
    def add_security_headers(response):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://www.gstatic.com https://apis.google.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self' https://*.googleapis.com; "
            "img-src 'self' data: https://*.googleusercontent.com; "
            "frame-src https://sentinelscan-3f82d.firebaseapp.com https://apis.google.com https://accounts.google.com; "
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
