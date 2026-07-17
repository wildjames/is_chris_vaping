import atexit
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

import redis
from flask import jsonify, request
from sqlalchemy import select
from sqlalchemy.engine import URL
from werkzeug.security import generate_password_hash

from models import Device, VapeEvent, init_db

logger = logging.getLogger(__name__)

# --- Configuration ---

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_USERNAME = os.environ.get("REDIS_USERNAME", "")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
REDIS_KEY = os.environ.get("REDIS_KEY", "WhoIsVaping")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_USER = os.environ.get("DB_USER", "vape")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "vape")

FIRMWARE_DIR = Path(os.environ.get("FIRMWARE_DIR", "/firmware"))
AUTH_TOKEN = os.environ.get("VAPE_API_TOKEN")
DEV_MODE = os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes")

ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

VAPE_TIMEOUT_SECONDS = int(os.environ.get("VAPE_TIMEOUT_SECONDS", "120"))
WATCHDOG_INTERVAL_SECONDS = int(os.environ.get("WATCHDOG_INTERVAL_SECONDS", "5"))

SITE_DIR = Path(__file__).resolve().parent / "site"

# Generate password hash at startup if raw password is provided
if ADMIN_PASSWORD and not ADMIN_PASSWORD_HASH:
    ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD)

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

# --- Background worker pool ---

_db_executor = ThreadPoolExecutor(max_workers=2)
atexit.register(_db_executor.shutdown, wait=True)


# --- Auth decorator ---

def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != AUTH_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# --- Redis cache helpers ---

def device_key(name):
    return f"{DEVICE_KEY_PREFIX}{name}"


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
        return db_get_all_devices_and_warm_cache()
    devices = {}
    for name in names:
        state = cache_get_device(name)
        if state:
            devices[name] = state
        else:
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


# --- DB persistence ---

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
        logger.exception("Failed to persist vape update to DB")


# --- Watchdog ---

def check_stale_devices():
    """Synthesize stopped events when a device is marked active but hasn't updated recently."""
    now = datetime.now(timezone.utc)
    try:
        devices = cache_get_all_devices()
    except Exception:
        logger.exception("Watchdog: failed to retrieve devices")
        return

    for name, state in devices.items():
        if not (state.get("coil_a") or state.get("coil_b")):
            continue

        last_updated_str = state.get("last_updated")
        if not last_updated_str:
            continue
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
        except (ValueError, TypeError):
            continue
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)

        age = (now - last_updated).total_seconds()
        if age <= VAPE_TIMEOUT_SECONDS:
            continue

        current_state = dict(state)
        for coil in ("coil_a", "coil_b"):
            if not current_state.get(coil):
                continue
            logger.warning(
                "Watchdog: %s %s active for %.0fs, synthesizing stopped event",
                name, coil, age,
            )
            current_state[coil] = False
            current_state["last_event"] = f"{coil}:stopped"
            current_state["last_updated"] = now.isoformat()
            cache_set_device(name, current_state)
            _db_executor.submit(
                db_persist_vape_update, name, coil, "stopped", current_state.copy(), now
            )


WATCHDOG_LOCK_KEY = f"{REDIS_KEY}:watchdog_lock"
WATCHDOG_LOCK_TTL_SECONDS = WATCHDOG_INTERVAL_SECONDS + 10


def _watchdog_loop(stop_event):
    while not stop_event.wait(WATCHDOG_INTERVAL_SECONDS):
        try:
            lock = redis_client.lock(WATCHDOG_LOCK_KEY, timeout=WATCHDOG_LOCK_TTL_SECONDS)
            acquired = lock.acquire(blocking=False)
            if not acquired:
                logger.debug("Watchdog: another worker holds the lock, skipping")
                continue
            try:
                check_stale_devices()
            finally:
                try:
                    lock.release()
                except Exception:
                    logger.exception("Watchdog: failed to release lock")
        except Exception:
            logger.exception("Watchdog loop error")


_watchdog_stop = threading.Event()
_watchdog_thread = threading.Thread(
    target=_watchdog_loop, args=(_watchdog_stop,), daemon=True, name="vape-watchdog"
)
_watchdog_thread.start()
atexit.register(_watchdog_stop.set)
