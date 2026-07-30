import json
import logging

from sqlalchemy import select

from achievements.base import (  # noqa: F401
    Achievement,
    AchievementContext,
    _registry,
    register,
)
from extensions import (
    ACHIEVEMENT_CHANNEL,
    Session,
    cache_get_all_devices,
    redis_client,
    send_achievement_push,
)
from models import AchievementAward

logger = logging.getLogger(__name__)


def get_achievement_meta(achievement_id: str) -> dict:
    """Look up name/description for an achievement_id from the registry."""
    for ach in _registry:
        if ach.id == achievement_id:
            return {"name": ach.name, "description": ach.description}
    return {"name": achievement_id, "description": ""}


def _already_awarded(db_session, achievement_id, scope_device):
    query = select(AchievementAward.id).where(
        AchievementAward.achievement_id == achievement_id,
    )
    if scope_device is not None:
        query = query.where(AchievementAward.device_name == scope_device)
    else:
        query = query.where(AchievementAward.device_name.is_(None))
    return db_session.execute(query.limit(1)).first() is not None


def run_checks(device_name, coil, event, timestamp):
    """Check all registered achievements after a vape event. Runs in background."""
    db_session = Session()
    try:
        all_devices = cache_get_all_devices()
        ctx = AchievementContext(
            device_name=device_name,
            coil=coil,
            event=event,
            timestamp=timestamp,
            db_session=db_session,
            all_devices=all_devices,
        )

        for ach in _registry:
            try:
                scope_device = ach.device_scope(ctx)

                if not ach.repeatable and _already_awarded(db_session, ach.id, scope_device):
                    continue

                if not ach.check(ctx):
                    continue

                award = AchievementAward(
                    achievement_id=ach.id,
                    device_name=scope_device,
                    awarded_at=timestamp,
                )
                db_session.add(award)
                db_session.commit()

                redis_client.publish(
                    ACHIEVEMENT_CHANNEL,
                    json.dumps({
                        "achievement_id": ach.id,
                        "name": ach.name,
                        "description": ach.description,
                        "device_name": scope_device,
                        "awarded_at": timestamp.isoformat(),
                    }),
                )
                if scope_device:
                    send_achievement_push(scope_device, ach.name, ach.description)
                logger.info(
                    "Achievement unlocked: %s for %s",
                    ach.name,
                    scope_device or "global",
                )
            except Exception:
                logger.exception("Error checking achievement %s", ach.id)
                db_session.rollback()
    except Exception:
        logger.exception("Failed to run achievement checks")
    finally:
        db_session.close()


# ---------------------------------------------------------------------------
# Import all achievement modules to trigger @register decorators
# ---------------------------------------------------------------------------

from achievements import (  # noqa: F401
    milestone_counts,
    duration_records,
    frequency_rate,
    time_of_day,
    streaks_consistency,
    dual_coil,
    multi_device,
    patterns_oddities,
    cumulative_lifetime,
)
