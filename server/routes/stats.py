from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, jsonify
from sqlalchemy import func, select

from extensions import Session, redis_client, STATS_NOTIFY_CHANNEL
from models import Device, VapeEvent

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/stats/data", methods=["GET"])
def stats_data():
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    six_hours_ago = now - timedelta(hours=6)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    twenty_four_hours_ago = now - timedelta(hours=24)

    db_session = Session()
    try:
        device_count = db_session.execute(select(func.count(Device.id))).scalar()

        chuff_filter = VapeEvent.event == "started"
        chuffs_last_hour = db_session.execute(
            select(func.count(VapeEvent.id)).where(chuff_filter, VapeEvent.timestamp >= one_hour_ago)
        ).scalar()
        chuffs_last_6_hours = db_session.execute(
            select(func.count(VapeEvent.id)).where(chuff_filter, VapeEvent.timestamp >= six_hours_ago)
        ).scalar()
        chuffs_since_midnight = db_session.execute(
            select(func.count(VapeEvent.id)).where(chuff_filter, VapeEvent.timestamp >= midnight)
        ).scalar()

        devices = []
        for device in db_session.execute(select(Device).order_by(Device.name)).scalars():
            dev_chuffs_1h = db_session.execute(
                select(func.count(VapeEvent.id))
                .where(VapeEvent.device_name == device.name, chuff_filter, VapeEvent.timestamp >= one_hour_ago)
            ).scalar()
            dev_chuffs_6h = db_session.execute(
                select(func.count(VapeEvent.id))
                .where(VapeEvent.device_name == device.name, chuff_filter, VapeEvent.timestamp >= six_hours_ago)
            ).scalar()
            dev_chuffs_midnight = db_session.execute(
                select(func.count(VapeEvent.id))
                .where(VapeEvent.device_name == device.name, chuff_filter, VapeEvent.timestamp >= midnight)
            ).scalar()

            raw_events = db_session.execute(
                select(VapeEvent)
                .where(VapeEvent.device_name == device.name, VapeEvent.timestamp >= twenty_four_hours_ago)
                .order_by(VapeEvent.timestamp.asc())
            ).scalars().all()

            devices.append({
                "name": device.name,
                "chuffs_last_hour": dev_chuffs_1h,
                "chuffs_last_6_hours": dev_chuffs_6h,
                "chuffs_since_midnight": dev_chuffs_midnight,
                "events_24h": [{
                    "coil": e.coil,
                    "event": e.event,
                    "timestamp": e.timestamp.isoformat(),
                } for e in raw_events],
            })

        return jsonify({
            "device_count": device_count,
            "chuffs_last_hour": chuffs_last_hour,
            "chuffs_last_6_hours": chuffs_last_6_hours,
            "chuffs_since_midnight": chuffs_since_midnight,
            "devices": devices,
        }), 200
    finally:
        db_session.close()


@stats_bp.route("/stats/stream", methods=["GET"])
def stats_stream():
    def generate():
        pubsub = redis_client.pubsub()
        pubsub.subscribe(STATS_NOTIFY_CHANNEL)
        try:
            while True:
                message = pubsub.get_message(timeout=30)
                if message and message["type"] == "message":
                    yield "data: update\n\n"
                elif message is None:
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            pubsub.unsubscribe()
            pubsub.close()

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
