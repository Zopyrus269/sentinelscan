"""
Flask entrypoint for the SentinelScan Log Site service.

Serves the developer-only log monitoring dashboard, telemetry APIs, and uptime probe.
"""
import os
from flask import Flask, jsonify, send_from_directory

from apps.logsite.api import api_bp
from apps.logsite.probe import probe_bp

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")


def create_app() -> Flask:
    """Builds and configures the developer-only log site Flask app."""
    app = Flask(
        __name__,
        static_folder=os.path.join(FRONTEND_DIR, "static"),
        static_url_path="/static"
    )

    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-logsite-secret-key")

    app.register_blueprint(api_bp)
    app.register_blueprint(probe_bp)

    @app.after_request
    def add_security_headers(response):
        """Enforces security headers and Content Security Policy on all responses."""
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
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

    @app.route("/healthz")
    def healthz():
        """Public health check endpoint for deployment monitoring."""
        return jsonify({"status": "ok"})

    @app.route("/")
    def serve_index():
        """Serves the status board (index.html)."""
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/<path:filename>")
    def serve_frontend_file(filename: str):
        """Serves HTML pages and frontend assets."""
        file_path = os.path.join(FRONTEND_DIR, filename)
        if os.path.exists(file_path) and not os.path.isdir(file_path):
            return send_from_directory(FRONTEND_DIR, filename)
        # Fallback to index.html if file not found
        return send_from_directory(FRONTEND_DIR, "index.html")

    return app


app = create_app()

if __name__ == "__main__":
    is_debug = os.environ.get("FLASK_DEBUG", "False").lower() in ["true", "1", "t"]
    app.run(debug=is_debug, port=5001)
