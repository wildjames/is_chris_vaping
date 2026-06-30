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

app = Flask(__name__, static_folder=str(SITE_DIR), static_url_path="")
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

# Redis key that holds a set of all known device names
DEVICE_LIST_KEY = "devices"
# Per-device state stored at "device:{name}"
DEVICE_KEY_PREFIX = "device:"

REDIS_FIRMWARE_VERSION_KEY = "firmware:version"
REDIS_FIRMWARE_SIZE_KEY = "firmware:size"
REDIS_FIRMWARE_UPLOADED_AT_KEY = "firmware:uploaded_at"


def device_key(name):
    return f"{DEVICE_KEY_PREFIX}{name}"


def get_device_state(name):
    raw = redis_client.get(device_key(name))
    if raw:
        return json.loads(raw)
    return {"coil_a": False, "coil_b": False, "last_event": None, "last_updated": None}


def set_device_state(name, state):
    redis_client.set(device_key(name), json.dumps(state))
    redis_client.sadd(DEVICE_LIST_KEY, name)


def get_all_device_names():
    return redis_client.smembers(DEVICE_LIST_KEY)


def get_all_devices():
    names = get_all_device_names()
    devices = {}
    for name in names:
        devices[name] = get_device_state(name)
    return devices


def rename_device(old_name, new_name):
    """Rename a device: move its state to a new key and update the device list."""
    state = get_device_state(old_name)
    redis_client.delete(device_key(old_name))
    redis_client.srem(DEVICE_LIST_KEY, old_name)
    set_device_state(new_name, state)


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
    vape_name = data.get("vape_name", "default")

    if coil not in ("coil_a", "coil_b"):
        return jsonify({"error": "Invalid coil, must be coil_a or coil_b"}), 400
    if event not in ("started", "stopped"):
        return jsonify({"error": "Invalid event, must be started or stopped"}), 400

    # Update per-device state
    state = get_device_state(vape_name)
    state[coil] = event == "started"
    state["last_event"] = f"{coil}:{event}"
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    set_device_state(vape_name, state)

    devices = get_all_devices()
    is_vaping = any(d.get("coil_a", False) or d.get("coil_b", False) for d in devices.values())
    app.logger.info(
        "Vape update: %s %s %s | vaping=%s", vape_name, coil, event, is_vaping
    )

    return jsonify({"status": "ok", "is_vaping": is_vaping, "device": state, "devices": devices}), 200


@app.route("/device/rename", methods=["POST"])
@require_token
def device_rename():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    old_name = data.get("old_name")
    new_name = data.get("new_name")

    if not old_name or not new_name:
        return jsonify({"error": "old_name and new_name are required"}), 400

    if old_name not in get_all_device_names():
        return jsonify({"error": f"Device '{old_name}' not found"}), 404

    if new_name in get_all_device_names():
        return jsonify({"error": f"Device '{new_name}' already exists"}), 409

    rename_device(old_name, new_name)
    app.logger.info("Device renamed: %s -> %s", old_name, new_name)
    return jsonify({"status": "ok", "old_name": old_name, "new_name": new_name}), 200


@app.route("/vape-status", methods=["GET"])
def vape_status():
    try:
        devices = get_all_devices()
        is_vaping = any(d.get("coil_a", False) or d.get("coil_b", False) for d in devices.values())
        return jsonify({"is_vaping": is_vaping, "devices": devices}), 200
    except Exception as e:
        app.logger.exception("Error retrieving vape status: %s", e)
        return jsonify({"is_vaping": False, "devices": {}}), 200

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
