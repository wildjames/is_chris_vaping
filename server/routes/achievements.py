import json

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import select

from achievements import get_achievement_meta
from achievements.base import _registry
from extensions import ACHIEVEMENT_CHANNEL, Session, redis_client
from models import AchievementAward

achievements_bp = Blueprint("achievements", __name__)


@achievements_bp.route("/achievements/all", methods=["GET"])
def all_achievements():
    """Return all possible achievements and their award status, optionally filtered by device."""
    device_filter = request.args.get("device")
    db_session = Session()
    try:
        query = select(AchievementAward)
        if device_filter:
            query = query.where(AchievementAward.device_name == device_filter)
        awards = db_session.execute(query).scalars().all()

        awarded_map = {}
        for award in awards:
            key = award.achievement_id
            if key not in awarded_map:
                awarded_map[key] = []
            awarded_map[key].append({
                "device_name": award.device_name,
                "awarded_at": award.awarded_at.isoformat(),
            })

        result = []
        for ach in _registry:
            result.append({
                "id": ach.id,
                "name": ach.name,
                "description": ach.description,
                "awarded": awarded_map.get(ach.id, []),
            })
        return jsonify(result), 200
    finally:
        db_session.close()


@achievements_bp.route("/achievements/recent", methods=["GET"])
def recent_achievements():
    db_session = Session()
    try:
        awards = (
            db_session.execute(
                select(AchievementAward)
                .order_by(AchievementAward.awarded_at.desc())
                .limit(3)
            )
            .scalars()
            .all()
        )
        result = []
        for award in awards:
            meta = get_achievement_meta(award.achievement_id)
            result.append({
                "achievement_id": award.achievement_id,
                "name": meta["name"],
                "description": meta["description"],
                "device_name": award.device_name,
                "awarded_at": award.awarded_at.isoformat(),
            })
        return jsonify(result), 200
    finally:
        db_session.close()


@achievements_bp.route("/achievements/stream", methods=["GET"])
def achievements_stream():
    def generate():
        pubsub = redis_client.pubsub()
        pubsub.subscribe(ACHIEVEMENT_CHANNEL)
        try:
            while True:
                message = pubsub.get_message(timeout=30)
                if message and message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
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
