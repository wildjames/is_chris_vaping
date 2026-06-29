import json
import logging
import os
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

import redis
from flask import Flask, jsonify, request, send_file, send_from_directory

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_USERNAME = os.environ.get("REDIS_USERNAME", "")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
FIRMWARE_DIR = Path(os.environ.get("FIRMWARE_DIR", "/firmware"))
AUTH_TOKEN = os.environ.get("VAPE_API_TOKEN")


SITE_DIR = Path(__file__).resolve().parent / "site"

app = Flask(__name__, static_folder=str(SITE_DIR), static_url_path="/static")
logging.basicConfig(level=logging.INFO)

if not AUTH_TOKEN:
    raise RuntimeError("VAPE_API_TOKEN environment variable must be set")

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    username=REDIS_USERNAME or None,
    password=REDIS_PASSWORD or None,
    decode_responses=True,
)

VAPE_STATE_KEY = "vape_state"
REDIS_FIRMWARE_VERSION_KEY = "firmware:version"
REDIS_FIRMWARE_SIZE_KEY = "firmware:size"
REDIS_FIRMWARE_UPLOADED_AT_KEY = "firmware:uploaded_at"


def get_vape_state():
    raw = redis_client.get(VAPE_STATE_KEY)
    if raw:
        return json.loads(raw)
    return {
        "coil_a": False,
        "coil_b": False,
        "last_event": None,
        "last_updated": None,
    }


def set_vape_state(state):
    redis_client.set(VAPE_STATE_KEY, json.dumps(state))


def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != AUTH_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/vape-update", methods=["POST"])
@require_token
def vape_update():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    coil = data.get("coil")
    event = data.get("event")

    if coil not in ("coil_a", "coil_b"):
        return jsonify({"error": "Invalid coil, must be coil_a or coil_b"}), 400
    if event not in ("started", "stopped"):
        return jsonify({"error": "Invalid event, must be started or stopped"}), 400

    vape_state = get_vape_state()
    vape_state[coil] = event == "started"
    vape_state["last_event"] = f"{coil}:{event}"
    vape_state["last_updated"] = datetime.now(timezone.utc).isoformat()
    set_vape_state(vape_state)

    is_vaping = vape_state["coil_a"] or vape_state["coil_b"]
    app.logger.info(
        "Vape update: %s %s | vaping=%s", coil, event, is_vaping
    )

    return jsonify({"status": "ok", "is_vaping": is_vaping, "state": vape_state}), 200


@app.route("/vape-status", methods=["GET"])
def vape_status():
    vape_state = get_vape_state()
    is_vaping = vape_state["coil_a"] or vape_state["coil_b"]
    return jsonify({"is_vaping": is_vaping, "state": vape_state}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/firmware/latest", methods=["GET"])
def firmware_latest():
    """Returns metadata about the latest firmware version."""
    version = redis_client.get(REDIS_FIRMWARE_VERSION_KEY)
    if not version:
        return jsonify({"error": "No firmware available"}), 404
    size = redis_client.get(REDIS_FIRMWARE_SIZE_KEY)
    uploaded_at = redis_client.get(REDIS_FIRMWARE_UPLOADED_AT_KEY)
    return jsonify({
        "version": version,
        "size": int(size) if size else 0,
        "uploaded_at": uploaded_at,
    }), 200


@app.route("/firmware/download", methods=["GET"])
def firmware_download():
    """Download the latest firmware binary."""
    version = redis_client.get(REDIS_FIRMWARE_VERSION_KEY)
    if not version:
        return jsonify({"error": "No firmware available"}), 404
    firmware_path = FIRMWARE_DIR / "firmware.bin"
    if not firmware_path.is_file():
        return jsonify({"error": "Firmware file missing"}), 404
    return send_file(firmware_path, mimetype="application/octet-stream",
                     download_name=f"firmware-{version}.bin")


@app.route("/firmware/upload", methods=["POST"])
@require_token
def firmware_upload():
    """Upload a new firmware binary. Requires version query param."""
    version = request.args.get("version")
    if not version:
        return jsonify({"error": "version query parameter required"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)
    firmware_path = FIRMWARE_DIR / "firmware.bin"
    file.save(firmware_path)

    file_size = firmware_path.stat().st_size
    redis_client.set(REDIS_FIRMWARE_VERSION_KEY, version)
    redis_client.set(REDIS_FIRMWARE_SIZE_KEY, str(file_size))
    redis_client.set(REDIS_FIRMWARE_UPLOADED_AT_KEY, datetime.now(timezone.utc).isoformat())

    app.logger.info("Firmware uploaded: version=%s size=%d", version, file_size)
    return jsonify({"status": "ok", "version": version, "size": file_size}), 200


@app.route("/", methods=["GET"])
def serve_index():
    return send_from_directory(SITE_DIR, "index.html")


@app.route("/<path:filename>", methods=["GET"])
def serve_site(filename):
    return send_from_directory(SITE_DIR, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
