from sqlalchemy import func, select

from achievements.base import Achievement, AchievementContext, register
from models import VapeEvent


def _total_puff_duration_seconds(ctx: AchievementContext) -> float:
    """Sum of all puff durations for this device."""
    starts = ctx.db_session.execute(
        select(VapeEvent.timestamp).where(
            VapeEvent.device_name == ctx.device_name,
            VapeEvent.event == "started",
        ).order_by(VapeEvent.timestamp)
    ).scalars().all()

    stops = ctx.db_session.execute(
        select(VapeEvent.timestamp).where(
            VapeEvent.device_name == ctx.device_name,
            VapeEvent.event == "stopped",
        ).order_by(VapeEvent.timestamp)
    ).scalars().all()

    total = 0.0
    # Pair each stop with its nearest preceding start
    start_idx = 0
    for stop_ts in stops:
        while start_idx < len(starts) - 1 and starts[start_idx + 1] < stop_ts:
            start_idx += 1
        if start_idx < len(starts) and starts[start_idx] < stop_ts:
            total += (stop_ts - starts[start_idx]).total_seconds()
            start_idx += 1
    return total


@register
class TimeWellSpent(Achievement):
    id = "time_well_spent"
    name = "Time Well Spent"
    description = "Total puff duration exceeds 1 hour"

    def check(self, ctx):
        if ctx.event != "stopped":
            return False
        return _total_puff_duration_seconds(ctx) >= 3600


@register
class FullWorkDay(Achievement):
    id = "full_work_day"
    name = "Full Work Day"
    description = "Total puff duration exceeds 8 hours"

    def check(self, ctx):
        if ctx.event != "stopped":
            return False
        return _total_puff_duration_seconds(ctx) >= 28800


@register
class Dedicated(Achievement):
    id = "dedicated"
    name = "Dedicated"
    description = "Active across 3+ firmware versions"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        # Check firmware versions via OTA tracking
        # Firmware updates are tracked in the firmware table
        # We track by looking at distinct firmware events or device metadata
        try:
            from models import Firmware
            versions = ctx.db_session.execute(
                select(func.count(func.distinct(Firmware.version)))
            ).scalar()
            return versions >= 3
        except Exception:
            return False


@register
class VeteranDevice(Achievement):
    id = "veteran_device"
    name = "Veteran Device"
    description = "A single device active for 365 days since first puff"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        first_puff = ctx.db_session.execute(
            select(VapeEvent.timestamp).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
            ).order_by(VapeEvent.timestamp).limit(1)
        ).scalar()
        if first_puff is None:
            return False
        days_active = (ctx.timestamp - first_puff).days
        return days_active >= 365
