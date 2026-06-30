import atexit
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

import redis
from flask import Flask, jsonify, request, send_file, send_from_directory
from models import Device, Firmware, VapeEvent, init_db
from sqlalchemy import select, update
from sqlalchemy.engine import URL

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_USERNAME = os.environ.get("REDIS_USERNAME", "")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
REDIS_KEY = os.environ.get("REDIS_KEY", "IsChrisVaping")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_USER = os.environ.get("DB_USER", "vape")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "vape")

FIRMWARE_DIR = Path(os.environ.get("FIRMWARE_DIR", "/firmware"))
AUTH_TOKEN = os.environ.get("VAPE_API_TOKEN")


SITE_DIR = Path(__file__).resolve().parent / "site"

app = Flask(__name__, static_folder=str(SITE_DIR), static_url_path="")
logging.basicConfig(level=logging.INFO)

_db_executor = ThreadPoolExecutor(max_workers=2)
atexit.register(_db_executor.shutdown, wait=True)

if not AUTH_TOKEN:
    raise RuntimeError("VAPE_API_TOKEN environment variable must be set")

# --- Redis (cache) ---
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    username=REDIS_USERNAME or None,
    password=REDIS_PASSWORD or None,
    decode_responses=True,
)

# Redis key prefixes
DEVICE_LIST_KEY = f"{REDIS_KEY}:devices"
DEVICE_KEY_PREFIX = f"{REDIS_KEY}:device:"

# --- MariaDB (persistent) ---
DB_URL = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)
engine, Session = init_db(DB_URL)


def device_key(name):
    return f"{DEVICE_KEY_PREFIX}{name}"


# --- Redis cache helpers ---

def cache_get_device(name):
    raw = redis_client.get(device_key(name))
    if raw:
        return json.loads(raw)
    return None


def cache_set_device(name, state):
    redis_client.set(device_key(name), json.dumps(state))
    redis_client.sadd(DEVICE_LIST_KEY, name)


def cache_get_all_devices():
    """Get all devices from cache. Falls back to DB on cache miss."""
    names = redis_client.smembers(DEVICE_LIST_KEY)
    if not names:
        # Cache miss - load from DB
        return db_get_all_devices_and_warm_cache()
    devices = {}
    for name in names:
        state = cache_get_device(name)
        if state:
            devices[name] = state
        else:
            # Per-device key evicted/missing - repopulate entire cache from DB
            return db_get_all_devices_and_warm_cache()
    return devices


def cache_delete_device(name):
    redis_client.delete(device_key(name))
    redis_client.srem(DEVICE_LIST_KEY, name)


def db_get_all_devices_and_warm_cache():
    """Load all devices from DB and populate Redis cache."""
    session = Session()
    try:
        devices = {}
        for device in session.execute(select(Device)).scalars():
            state = {
                "coil_a": device.coil_a,
                "coil_b": device.coil_b,
                "last_event": device.last_event,
                "last_updated": device.last_updated.isoformat() if device.last_updated else None,
            }
            devices[device.name] = state
            cache_set_device(device.name, state)
        return devices
    finally:
        session.close()


# --- DB persistence (runs in background for vape updates) ---

def db_persist_vape_update(vape_name, coil, event, state, timestamp):
    """Persist vape state and event to MariaDB."""
    try:
        session = Session()
        try:
            device = session.execute(
                select(Device).where(Device.name == vape_name)
            ).scalar_one_or_none()

            if device is None:
                device = Device(name=vape_name)
                session.add(device)

            device.coil_a = state["coil_a"]
            device.coil_b = state["coil_b"]
            device.last_event = state["last_event"]
            device.last_updated = timestamp

            session.add(VapeEvent(
                device_name=vape_name,
                coil=coil,
                event=event,
                timestamp=timestamp,
            ))
            session.commit()
        finally:
            session.close()
    except Exception:
        app.logger.exception("Failed to persist vape update to DB")


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

    now = datetime.now(timezone.utc)

    # Fast path: update Redis cache immediately
    state = cache_get_device(vape_name) or {
        "coil_a": False, "coil_b": False, "last_event": None, "last_updated": None
    }
    state[coil] = event == "started"
    state["last_event"] = f"{coil}:{event}"
    state["last_updated"] = now.isoformat()
    cache_set_device(vape_name, state)

    # Persist to MariaDB via bounded worker pool
    _db_executor.submit(db_persist_vape_update, vape_name, coil, event, state, now)

    devices = cache_get_all_devices()
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

    # Rename in MariaDB (source of truth)
    session = Session()
    try:
        device = session.execute(
            select(Device).where(Device.name == old_name)
        ).scalar_one_or_none()

        if device is None:
            return jsonify({"error": f"Device '{old_name}' not found"}), 404

        existing = session.execute(
            select(Device).where(Device.name == new_name)
        ).scalar_one_or_none()
        if existing is not None:
            return jsonify({"error": f"Device '{new_name}' already exists"}), 409

        device.name = new_name
        session.execute(
            update(VapeEvent)
            .where(VapeEvent.device_name == old_name)
            .values(device_name=new_name)
        )
        session.commit()
    finally:
        session.close()

    # Update Redis cache
    state = cache_get_device(old_name)
    cache_delete_device(old_name)
    if state:
        cache_set_device(new_name, state)

    app.logger.info("Device renamed: %s -> %s", old_name, new_name)
    return jsonify({"status": "ok", "old_name": old_name, "new_name": new_name}), 200


@app.route("/vape-status", methods=["GET"])
def vape_status():
    try:
        devices = cache_get_all_devices()
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
    """Returns metadata about the latest firmware version from MariaDB."""
    session = Session()
    try:
        fw = session.execute(
            select(Firmware).order_by(Firmware.id.desc())
        ).scalars().first()
        if not fw:
            return jsonify({"error": "No firmware available"}), 404
        return jsonify({
            "version": fw.version,
            "size": fw.size,
            "uploaded_at": fw.uploaded_at.isoformat() if fw.uploaded_at else None,
        }), 200
    finally:
        session.close()


@app.route("/firmware/download", methods=["GET"])
def firmware_download():
    """Download the latest firmware binary."""
    session = Session()
    try:
        fw = session.execute(
            select(Firmware).order_by(Firmware.id.desc())
        ).scalars().first()
        if not fw:
            return jsonify({"error": "No firmware available"}), 404
        version = fw.version
    finally:
        session.close()

    firmware_path = FIRMWARE_DIR / "firmware.bin"
    if not firmware_path.is_file():
        return jsonify({"error": "Firmware file missing"}), 404
    return send_file(firmware_path, mimetype="application/octet-stream",
                     download_name=f"firmware-{version}.bin")


@app.route("/firmware/upload", methods=["POST"])
@require_token
def firmware_upload():
    """Upload a new firmware binary. Persists metadata to MariaDB."""
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
    now = datetime.now(timezone.utc)

    session = Session()
    try:
        session.add(Firmware(version=version, size=file_size, uploaded_at=now))
        session.commit()
    finally:
        session.close()

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
