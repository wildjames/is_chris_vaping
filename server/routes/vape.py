from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select, update

from extensions import (
    Session, cache_get_all_devices, cache_get_device, cache_set_device,
    cache_delete_device, db_persist_vape_update, require_token, _db_executor,
)
from models import Device, VapeEvent

vape_bp = Blueprint("vape", __name__)


@vape_bp.route("/vape-update", methods=["POST"])
@require_token
def vape_update():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    coil = data.get("coil")
    event = data.get("event")
    vape_name = data.get("vape_name", "default")
    if not isinstance(vape_name, str):
        return jsonify({"error": "vape_name must be a string"}), 400
    vape_name = vape_name.strip() or "default"
    if len(vape_name) > 64:
        return jsonify({"error": "vape_name too long (max 64)"}), 400
    if coil not in ("coil_a", "coil_b"):
        return jsonify({"error": "Invalid coil, must be coil_a or coil_b"}), 400
    if event not in ("started", "stopped"):
        return jsonify({"error": "Invalid event, must be started or stopped"}), 400

    ts_ms = data.get("timestamp")
    if ts_ms is not None:
        try:
            now = datetime.fromtimestamp(int(ts_ms) / 1000.0, tz=timezone.utc)
            if now > datetime.now(timezone.utc) + timedelta(seconds=60):
                return jsonify({"error": "timestamp is too far in the future"}), 400
        except (ValueError, OverflowError, OSError):
            return jsonify({"error": "Invalid timestamp"}), 400
    else:
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
    current_app.logger.info(
        "Vape update: %s %s %s | vaping=%s", vape_name, coil, event, is_vaping
    )

    return jsonify({"status": "ok", "is_vaping": is_vaping, "device": state, "devices": devices}), 200


@vape_bp.route("/device/rename", methods=["POST"])
@require_token
def device_rename():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    old_name = data.get("old_name")
    new_name = data.get("new_name")

    if not new_name:
        return jsonify({"error": "new_name is required"}), 400

    session = Session()
    try:
        device = None
        if old_name:
            device = session.execute(
                select(Device).where(Device.name == old_name)
            ).scalar_one_or_none()

        if device is None:
            existing = session.execute(
                select(Device).where(Device.name == new_name)
            ).scalar_one_or_none()
            if existing:
                current_app.logger.info("Device already exists with name: %s", new_name)
                return jsonify({"status": "ok", "old_name": old_name, "new_name": new_name}), 200

            device = Device(name=new_name)
            session.add(device)
            session.commit()

            cache_set_device(new_name, {
                "coil_a": False,
                "coil_b": False,
                "last_event": None,
                "last_updated": None,
            })

            current_app.logger.info("Device created via rename: %s", new_name)
            return jsonify({"status": "ok", "old_name": old_name, "new_name": new_name, "created": True}), 200

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
    if old_name:
        state = cache_get_device(old_name)
        cache_delete_device(old_name)
    else:
        state = None
    if state:
        cache_set_device(new_name, state)

    current_app.logger.info("Device renamed: %s -> %s", old_name, new_name)
    return jsonify({"status": "ok", "old_name": old_name, "new_name": new_name}), 200


@vape_bp.route("/vape-status", methods=["GET"])
def vape_status():
    try:
        devices = cache_get_all_devices()
        is_vaping = any(d.get("coil_a", False) or d.get("coil_b", False) for d in devices.values())
        return jsonify({"is_vaping": is_vaping, "devices": devices}), 200
    except Exception as e:
        current_app.logger.exception("Error retrieving vape status: %s", e)
        return jsonify({"is_vaping": False, "devices": {}}), 200
