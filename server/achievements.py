import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select

from extensions import (
    ACHIEVEMENT_CHANNEL,
    Session,
    cache_get_all_devices,
    redis_client,
)
from models import AchievementAward, VapeEvent

logger = logging.getLogger(__name__)

_registry: list["Achievement"] = []


@dataclass
class AchievementContext:
    device_name: str
    coil: str
    event: str  # "started" or "stopped"
    timestamp: datetime
    db_session: object  # SQLAlchemy Session
    all_devices: dict  # {name: {coil_a, coil_b, last_event, last_updated}}


class Achievement:
    """Base class for all achievements. Subclass and decorate with @register."""

    id: str = ""
    name: str = ""
    description: str = ""
    repeatable: bool = False

    def check(self, ctx: AchievementContext) -> bool:
        """Return True if this achievement should be awarded right now."""
        raise NotImplementedError

    def device_scope(self, ctx: AchievementContext) -> Optional[str]:
        """Return device_name for per-device achievements, None for global."""
        return ctx.device_name


def register(cls):
    """Class decorator — registers an achievement in the global registry."""
    _registry.append(cls())
    return cls


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
# Achievement definitions — add new @register classes below
# ---------------------------------------------------------------------------


@register
class FirstBlood(Achievement):
    id = "first_blood"
    name = "First Blood"
    description = "Record your first puff"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        count = ctx.db_session.execute(
            select(func.count(VapeEvent.id)).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
            )
        ).scalar()
        return count == 1


@register
class Century(Achievement):
    id = "century"
    name = "Century"
    description = "100 total puffs"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        count = ctx.db_session.execute(
            select(func.count(VapeEvent.id)).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
            )
        ).scalar()
        return count >= 100


@register
class DoubleBarrel(Achievement):
    id = "double_barrel"
    name = "Double Barrel"
    description = "Both coils active simultaneously"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        state = ctx.all_devices.get(ctx.device_name, {})
        return state.get("coil_a") and state.get("coil_b")


@register
class EarlyBird(Achievement):
    id = "early_bird"
    name = "Early Bird"
    description = "Puff before 6:00 AM"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        return ctx.timestamp.hour < 6


@register
class NightOwl(Achievement):
    id = "night_owl"
    name = "Night Owl"
    description = "Puff after 2:00 AM"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        return 2 <= ctx.timestamp.hour < 4


@register
class Duet(Achievement):
    id = "duet"
    name = "Duet"
    description = "Two devices puffing at the same time"

    def device_scope(self, ctx):
        return None

    def check(self, ctx):
        if ctx.event != "started":
            return False
        active = sum(
            1 for d in ctx.all_devices.values()
            if d.get("coil_a") or d.get("coil_b")
        )
        return active >= 2
