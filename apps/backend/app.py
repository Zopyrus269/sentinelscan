"""
Flask entrypoint for the SentinelScan backend.
"""

import os

from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

load_dotenv()

from apps.backend.routes.scan_routes import scan_bp
from apps.backend.routes.auth_routes import auth_bp


FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


def create_app() -> Flask:
    """Application factory -- builds and configures the Flask app."""
    app = Flask(__name__, static_folder=os.path.join(FRONTEND_DIR, "static"), static_url_path="/static")
    CORS(app)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
    app.register_blueprint(scan_bp)
    app.register_blueprint(auth_bp)

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

    @app.route("/privacy")
    def serve_privacy():
        return send_from_directory(FRONTEND_DIR, "privacy.html")

    @app.route("/status")
    def serve_status():
        return send_from_directory(FRONTEND_DIR, "status.html")

    @app.route("/terms")
    def serve_terms():
        return send_from_directory(FRONTEND_DIR, "terms.html")

    @app.route("/<path:filename>")
    def serve_static(filename):
        return send_from_directory(FRONTEND_DIR, filename)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
