from datetime import timedelta

from sqlalchemy import func, select

from achievements.base import Achievement, register
from models import VapeEvent


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
class SunriseRip(Achievement):
    id = "sunrise_rip"
    name = "Sunrise Rip"
    description = "Puff between 5:00–5:15 AM"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        return ctx.timestamp.hour == 5 and ctx.timestamp.minute < 15


@register
class LunchBreak(Achievement):
    id = "lunch_break"
    name = "Lunch Break"
    description = "Puff between 12:00–12:05 PM every day for a week"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        if not (ctx.timestamp.hour == 12 and ctx.timestamp.minute < 5):
            return False

        # Check past 7 days each had a puff in 12:00-12:05
        for days_ago in range(1, 7):
            day = ctx.timestamp - timedelta(days=days_ago)
            day_start = day.replace(hour=12, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=12, minute=5, second=0, microsecond=0)
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
class AroundTheClock(Achievement):
    id = "around_the_clock"
    name = "Around the Clock"
    description = "At least one puff in every hour of a 24-hour period"

    def device_scope(self, ctx):
        return ctx.device_name

    def check(self, ctx):
        if ctx.event != "started":
            return False
        window_start = ctx.timestamp - timedelta(hours=24)
        events = ctx.db_session.execute(
            select(VapeEvent.timestamp).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp <= ctx.timestamp,
            )
        ).scalars().all()

        hours_covered = set()
        for ts in events:
            hours_covered.add(ts.hour)
        return len(hours_covered) == 24
