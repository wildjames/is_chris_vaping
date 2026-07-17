import json
import logging
import secrets
import os

from flask import Flask, jsonify, send_from_directory

from extensions import DEV_MODE, SITE_DIR
from routes.admin import admin_bp
from routes.firmware import firmware_bp
from routes.vape import vape_bp

app = Flask(__name__, static_folder=str(SITE_DIR), static_url_path="")
_secret_key = os.environ.get("FLASK_SECRET_KEY")
if not _secret_key and not DEV_MODE:
    raise RuntimeError("FLASK_SECRET_KEY must be set in non-dev mode")
app.secret_key = _secret_key or secrets.token_hex(32)
logging.basicConfig(level=logging.INFO)

# Update gifs manifest on startup
GIFS_DIR = SITE_DIR / "gifs"
GIFS_DIR.mkdir(parents=True, exist_ok=True)
_gif_extensions = {".gif", ".png", ".jpg", ".jpeg", ".webp"}
_gif_manifest = [f.name for f in GIFS_DIR.iterdir() if f.suffix.lower() in _gif_extensions]
(GIFS_DIR / "manifest.json").write_text(json.dumps(_gif_manifest))

# Register blueprints
app.register_blueprint(vape_bp)
app.register_blueprint(firmware_bp)
app.register_blueprint(admin_bp)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/dev-config", methods=["GET"])
def dev_config():
    return jsonify({"dev_mode": DEV_MODE})


@app.route("/admin", methods=["GET"])
def serve_admin():
    return send_from_directory(SITE_DIR, "admin.html")


@app.route("/", methods=["GET"])
def serve_index():
    return send_from_directory(SITE_DIR, "index.html")


@app.route("/<path:filename>", methods=["GET"])
def serve_site(filename):
    return send_from_directory(SITE_DIR, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
