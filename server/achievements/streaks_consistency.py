from datetime import timedelta

from sqlalchemy import func, select

from achievements.base import Achievement, register
from models import AchievementAward, VapeEvent


@register
class DailyDriver(Achievement):
    id = "daily_driver"
    name = "Daily Driver"
    description = "Puff on 7 consecutive days"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        for days_ago in range(7):
            day = ctx.timestamp - timedelta(days=days_ago)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            count = ctx.db_session.execute(
                select(func.count(VapeEvent.id)).where(
                    VapeEvent.device_name == ctx.device_name,
                    VapeEvent.event == "started",
                    VapeEvent.timestamp >= day_start,
                    VapeEvent.timestamp < day_end,
                )
            ).scalar()
            if count == 0:
                return False
        return True


@register
class MonthlyPass(Achievement):
    id = "monthly_pass"
    name = "Monthly Pass"
    description = "Puff on 30 consecutive days"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        for days_ago in range(30):
            day = ctx.timestamp - timedelta(days=days_ago)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            count = ctx.db_session.execute(
                select(func.count(VapeEvent.id)).where(
                    VapeEvent.device_name == ctx.device_name,
                    VapeEvent.event == "started",
                    VapeEvent.timestamp >= day_start,
                    VapeEvent.timestamp < day_end,
                )
            ).scalar()
            if count == 0:
                return False
        return True


@register
class CleanStreak(Achievement):
    id = "clean_streak"
    name = "Clean Streak"
    description = "No puffs for 24 hours"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        # Check that there were no puffs in the 24h before this one
        window_start = ctx.timestamp - timedelta(hours=24)
        prev = ctx.db_session.execute(
            select(VapeEvent.timestamp).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp < ctx.timestamp,
            ).limit(1)
        ).scalar()
        return prev is None


@register
class DetoxWeek(Achievement):
    id = "detox_week"
    name = "Detox Week"
    description = "No puffs for 7 consecutive days"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        window_start = ctx.timestamp - timedelta(days=7)
        prev = ctx.db_session.execute(
            select(VapeEvent.timestamp).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp < ctx.timestamp,
            ).limit(1)
        ).scalar()
        return prev is None


@register
class Relapse(Achievement):
    id = "relapse"
    name = "Relapse"
    description = "First puff after a Clean Streak"
    repeatable = True

    def check(self, ctx):
        if ctx.event != "started":
            return False
        # Check if device has a clean_streak achievement
        has_clean = ctx.db_session.execute(
            select(AchievementAward.id).where(
                AchievementAward.achievement_id == "clean_streak",
                AchievementAward.device_name == ctx.device_name,
            ).limit(1)
        ).first()
        if not has_clean:
            return False
        # This IS the first puff after the streak (clean_streak triggers on same event)
        window_start = ctx.timestamp - timedelta(hours=24)
        prev = ctx.db_session.execute(
            select(VapeEvent.timestamp).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp < ctx.timestamp,
            ).limit(1)
        ).scalar()
        return prev is None
