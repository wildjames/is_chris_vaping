import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

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
