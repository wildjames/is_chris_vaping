from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy import delete, func, select

from extensions import ADMIN_PASSWORD_HASH, Session, cache_delete_device
from models import Device, VapeEvent
from werkzeug.security import check_password_hash

admin_bp = Blueprint("admin", __name__)


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/admin/login", methods=["POST"])
def admin_login():
    if not ADMIN_PASSWORD_HASH:
        return jsonify({"error": "Admin login not configured"}), 503

    data = request.get_json(silent=True)
    if not data or not data.get("password"):
        return jsonify({"error": "Password required"}), 400

    if check_password_hash(ADMIN_PASSWORD_HASH, data["password"]):
        session["admin"] = True
        return jsonify({"status": "ok"}), 200
    return jsonify({"error": "Invalid password"}), 401


@admin_bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return jsonify({"status": "ok"}), 200


@admin_bp.route("/admin/check", methods=["GET"])
def admin_check():
    if session.get("admin"):
        return jsonify({"authenticated": True}), 200
    return jsonify({"authenticated": False}), 200


@admin_bp.route("/admin/devices", methods=["GET"])
@require_admin
def admin_devices():
    db_session = Session()
    try:
        devices = []
        for device in db_session.execute(select(Device).order_by(Device.name)).scalars():
            event_count = db_session.execute(
                select(func.count(VapeEvent.id)).where(VapeEvent.device_name == device.name)
            ).scalar()
            devices.append({
                "id": device.id,
                "name": device.name,
                "coil_a": device.coil_a,
                "coil_b": device.coil_b,
                "last_event": device.last_event,
                "last_updated": device.last_updated.isoformat() if device.last_updated else None,
                "event_count": event_count,
            })
        return jsonify({"devices": devices}), 200
    finally:
        db_session.close()


@admin_bp.route("/admin/devices/<int:device_id>", methods=["DELETE"])
@require_admin
def admin_delete_device(device_id):
    db_session = Session()
    try:
        device = db_session.execute(
            select(Device).where(Device.id == device_id)
        ).scalar_one_or_none()
        if not device:
            return jsonify({"error": "Device not found"}), 404

        device_name = device.name
        db_session.execute(
            delete(VapeEvent).where(VapeEvent.device_name == device_name)
        )
        db_session.delete(device)
        db_session.commit()

        cache_delete_device(device_name)

        current_app.logger.info("Admin deleted device: %s (id=%d)", device_name, device_id)
        return jsonify({"status": "ok", "deleted": device_name}), 200
    finally:
        db_session.close()


@admin_bp.route("/admin/devices/<int:device_id>/events", methods=["GET"])
@require_admin
def admin_device_events(device_id):
    db_session = Session()
    try:
        device = db_session.execute(
            select(Device).where(Device.id == device_id)
        ).scalar_one_or_none()
        if not device:
            return jsonify({"error": "Device not found"}), 404

        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)

        events = db_session.execute(
            select(VapeEvent)
            .where(VapeEvent.device_name == device.name)
            .order_by(VapeEvent.timestamp.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()

        return jsonify({
            "device": device.name,
            "events": [{
                "id": e.id,
                "coil": e.coil,
                "event": e.event,
                "timestamp": e.timestamp.isoformat(),
            } for e in events],
        }), 200
    finally:
        db_session.close()


@admin_bp.route("/admin/activity", methods=["GET"])
@require_admin
def admin_activity():
    """Get aggregated vape activity data for charts.

    Query params:
      - days: number of days to look back (default 7)
      - device: optional device name filter
    """
    days = request.args.get("days", 7, type=int)
    days = min(max(days, 1), 365)
    device_filter = request.args.get("device")

    since = datetime.now(timezone.utc) - timedelta(days=days)

    db_session = Session()
    try:
        query = select(VapeEvent).where(VapeEvent.timestamp >= since)
        if device_filter:
            query = query.where(VapeEvent.device_name == device_filter)
        query = query.order_by(VapeEvent.timestamp.asc())

        events = db_session.execute(query).scalars().all()

        # Aggregate by hour
        hourly = {}
        for e in events:
            hour_key = e.timestamp.strftime("%Y-%m-%d %H:00")
            if hour_key not in hourly:
                hourly[hour_key] = {"started": 0, "stopped": 0}
            hourly[hour_key][e.event] = hourly[hour_key].get(e.event, 0) + 1

        # Aggregate by day
        daily = {}
        for e in events:
            day_key = e.timestamp.strftime("%Y-%m-%d")
            if day_key not in daily:
                daily[day_key] = {"started": 0, "stopped": 0}
            daily[day_key][e.event] = daily[day_key].get(e.event, 0) + 1

        # Per-device totals
        per_device = {}
        for e in events:
            if e.device_name not in per_device:
                per_device[e.device_name] = {"started": 0, "stopped": 0}
            per_device[e.device_name][e.event] = per_device[e.device_name].get(e.event, 0) + 1

        return jsonify({
            "days": days,
            "since": since.isoformat(),
            "hourly": hourly,
            "daily": daily,
            "per_device": per_device,
            "total_events": len(events),
        }), 200
    finally:
        db_session.close()
