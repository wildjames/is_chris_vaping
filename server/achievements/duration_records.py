from typing import Optional

from sqlalchemy import select

from achievements.base import Achievement, AchievementContext, register
from models import VapeEvent


def _last_puff_duration(ctx: AchievementContext) -> Optional[float]:
    """Get duration of the puff that just ended (seconds)."""
    if ctx.event != "stopped":
        return None
    start = ctx.db_session.execute(
        select(VapeEvent.timestamp).where(
            VapeEvent.device_name == ctx.device_name,
            VapeEvent.coil == ctx.coil,
            VapeEvent.event == "started",
            VapeEvent.timestamp < ctx.timestamp,
        ).order_by(VapeEvent.timestamp.desc()).limit(1)
    ).scalar()
    if start is None:
        return None
    return (ctx.timestamp - start).total_seconds()


def _recent_puff_durations(ctx: AchievementContext, n: int) -> list[float]:
    """Get the last N puff durations for this device (most recent first)."""
    stops = ctx.db_session.execute(
        select(VapeEvent.timestamp).where(
            VapeEvent.device_name == ctx.device_name,
            VapeEvent.event == "stopped",
            VapeEvent.timestamp <= ctx.timestamp,
        ).order_by(VapeEvent.timestamp.desc()).limit(n)
    ).scalars().all()

    durations = []
    for stop_ts in stops:
        start_ts = ctx.db_session.execute(
            select(VapeEvent.timestamp).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.timestamp < stop_ts,
            ).order_by(VapeEvent.timestamp.desc()).limit(1)
        ).scalar()
        if start_ts is not None:
            durations.append((stop_ts - start_ts).total_seconds())
    return durations


@register
class QuickDraw(Achievement):
    id = "quick_draw"
    name = "Quick Draw"
    description = "A puff under 0.5 seconds"

    def check(self, ctx):
        duration = _last_puff_duration(ctx)
        if duration is None:
            return False
        return duration < 0.5


@register
class SavourIt(Achievement):
    id = "savour_it"
    name = "Savour It"
    description = "A single puff lasting over 10 seconds"

    def check(self, ctx):
        duration = _last_puff_duration(ctx)
        if duration is None:
            return False
        return duration > 10


@register
class IronLungs(Achievement):
    id = "iron_lungs"
    name = "Iron Lungs"
    description = "A single puff lasting over 20 seconds"

    def check(self, ctx):
        duration = _last_puff_duration(ctx)
        if duration is None:
            return False
        return duration > 20


@register
class AreYouOkay(Achievement):
    id = "are_you_okay"
    name = "Are You Okay?"
    description = "A single puff lasting over 30 seconds"

    def check(self, ctx):
        duration = _last_puff_duration(ctx)
        if duration is None:
            return False
        return duration > 30


@register
class MicroHit(Achievement):
    id = "micro_hit"
    name = "Micro-Hit"
    description = "10 puffs under 1 second in a row"

    def check(self, ctx):
        if ctx.event != "stopped":
            return False
        durations = _recent_puff_durations(ctx, 10)
        if len(durations) < 10:
            return False
        return all(d < 1.0 for d in durations)
