import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_registry: list["Achievement"] = []


@dataclass
class AchievementContext:
    device_name: str
    coil: str
    event: str  # "started" or "stopped"
    timestamp: datetime = field(default=None)
    db_session: object = None  # SQLAlchemy Session
    all_devices: dict = None  # {name: {coil_a, coil_b, last_event, last_updated}}

    def __post_init__(self):
        # Normalize to naive UTC so comparisons with DB timestamps work
        if self.timestamp is not None and self.timestamp.tzinfo is not None:
            self.timestamp = self.timestamp.astimezone(timezone.utc).replace(tzinfo=None)


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
