from datetime import timedelta

from sqlalchemy import func, select

from achievements.base import Achievement, register
from models import VapeEvent


@register
class ChainSmoker(Achievement):
    id = "chain_smoker"
    name = "Chain Smoker"
    description = "10 puffs within 2 minutes"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        window_start = ctx.timestamp - timedelta(minutes=2)
        count = ctx.db_session.execute(
            select(func.count(VapeEvent.id)).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp <= ctx.timestamp,
            )
        ).scalar()
        return count >= 10


@register
class GatlingGun(Achievement):
    id = "gatling_gun"
    name = "Gatling Gun"
    description = "20 puffs within 5 minutes"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        window_start = ctx.timestamp - timedelta(minutes=5)
        count = ctx.db_session.execute(
            select(func.count(VapeEvent.id)).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp <= ctx.timestamp,
            )
        ).scalar()
        return count >= 20


@register
class OneAndDone(Achievement):
    id = "one_and_done"
    name = "One and Done"
    description = "Only a single puff in an entire day"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        day_start = ctx.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        # Check the previous day (since the day must be complete)
        prev_day_start = day_start - timedelta(days=1)
        count = ctx.db_session.execute(
            select(func.count(VapeEvent.id)).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.timestamp >= prev_day_start,
                VapeEvent.timestamp < day_start,
            )
        ).scalar()
        return count == 1


@register
class MarathonSession(Achievement):
    id = "marathon_session"
    name = "Marathon Session"
    description = "At least one puff every 5 minutes for an hour straight"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        window_start = ctx.timestamp - timedelta(hours=1)
        starts = ctx.db_session.execute(
            select(VapeEvent.timestamp).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp <= ctx.timestamp,
            ).order_by(VapeEvent.timestamp)
        ).scalars().all()

        if len(starts) < 12:
            return False

        # Check that every 5-minute window in the hour has at least one puff
        for i in range(12):
            slot_start = window_start + timedelta(minutes=5 * i)
            slot_end = slot_start + timedelta(minutes=5)
            if not any(slot_start <= ts < slot_end for ts in starts):
                return False
        return True


@register
class PaceYourself(Achievement):
    id = "pace_yourself"
    name = "Pace Yourself"
    description = "Exactly 1 puff per minute for 10 consecutive minutes (±5s tolerance)"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        window_start = ctx.timestamp - timedelta(minutes=10)
        starts = ctx.db_session.execute(
            select(VapeEvent.timestamp).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp <= ctx.timestamp,
            ).order_by(VapeEvent.timestamp)
        ).scalars().all()

        if len(starts) < 10:
            return False

        # Take the last 10 puffs and check they're spaced ~60s apart
        recent = starts[-10:]
        for i in range(1, len(recent)):
            gap = (recent[i] - recent[i - 1]).total_seconds()
            if abs(gap - 60.0) > 5.0:
                return False
        return True
