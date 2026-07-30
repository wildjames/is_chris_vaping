from datetime import timedelta

from sqlalchemy import func, select

from achievements.base import Achievement, register
from models import VapeEvent


@register
class SynchronisedVaping(Achievement):
    id = "synchronised_vaping"
    name = "Synchronised Vaping"
    description = "Two devices puff within 1 second of each other"

    def device_scope(self, ctx):
        return None

    def check(self, ctx):
        if ctx.event != "started":
            return False
        window_start = ctx.timestamp - timedelta(seconds=1)
        window_end = ctx.timestamp + timedelta(seconds=1)
        other = ctx.db_session.execute(
            select(VapeEvent.id).where(
                VapeEvent.device_name != ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp <= window_end,
            ).limit(1)
        ).first()
        return other is not None


@register
class Duet(Achievement):
    id = "duet"
    name = "Duet"
    description = "Two devices actively puffing at the exact same moment"

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


@register
class MexicanWave(Achievement):
    id = "mexican_wave"
    name = "Mexican Wave"
    description = "3+ devices puff within 10 seconds"

    def device_scope(self, ctx):
        return None

    def check(self, ctx):
        if ctx.event != "started":
            return False
        window_start = ctx.timestamp - timedelta(seconds=10)
        devices = ctx.db_session.execute(
            select(VapeEvent.device_name).where(
                VapeEvent.event == "started",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp <= ctx.timestamp,
            ).distinct()
        ).scalars().all()
        return len(set(devices)) >= 3


@register
class Copycat(Achievement):
    id = "copycat"
    name = "Copycat"
    description = "Device starts a puff within 3 seconds of another device stopping"

    def device_scope(self, ctx):
        return None

    def check(self, ctx):
        if ctx.event != "started":
            return False
        window_start = ctx.timestamp - timedelta(seconds=3)
        other_stop = ctx.db_session.execute(
            select(VapeEvent.id).where(
                VapeEvent.device_name != ctx.device_name,
                VapeEvent.event == "stopped",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp <= ctx.timestamp,
            ).limit(1)
        ).first()
        return other_stop is not None


@register
class Rivalry(Achievement):
    id = "rivalry"
    name = "Rivalry"
    description = "Two devices each exceed 50 puffs in the same hour"

    def device_scope(self, ctx):
        return None

    def check(self, ctx):
        if ctx.event != "started":
            return False
        hour_start = ctx.timestamp.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)

        # Get per-device puff counts this hour
        rows = ctx.db_session.execute(
            select(VapeEvent.device_name, func.count(VapeEvent.id)).where(
                VapeEvent.event == "started",
                VapeEvent.timestamp >= hour_start,
                VapeEvent.timestamp < hour_end,
            ).group_by(VapeEvent.device_name)
        ).all()

        over_50 = sum(1 for _, count in rows if count >= 50)
        return over_50 >= 2


@register
class TheFavourite(Achievement):
    id = "the_favourite"
    name = "The Favourite"
    description = "One device has more puffs than all others combined"

    def device_scope(self, ctx):
        return None

    def check(self, ctx):
        if ctx.event != "started":
            return False
        rows = ctx.db_session.execute(
            select(VapeEvent.device_name, func.count(VapeEvent.id)).where(
                VapeEvent.event == "started",
            ).group_by(VapeEvent.device_name)
        ).all()

        if len(rows) < 2:
            return False

        counts = {name: count for name, count in rows}
        total = sum(counts.values())
        return any(c > total - c for c in counts.values())


@register
class PassingTheTorch(Achievement):
    id = "passing_the_torch"
    name = "Passing the Torch"
    description = "A new device's first puff happens within 1 minute of another device's last-ever puff"

    def device_scope(self, ctx):
        return None

    def check(self, ctx):
        if ctx.event != "started":
            return False
        # Check this is the device's first puff
        device_count = ctx.db_session.execute(
            select(func.count(VapeEvent.id)).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
            )
        ).scalar()
        if device_count != 1:
            return False

        # Check if any other device had its last puff within 1 minute
        window_start = ctx.timestamp - timedelta(minutes=1)
        other_devices = ctx.db_session.execute(
            select(VapeEvent.device_name).where(
                VapeEvent.device_name != ctx.device_name,
                VapeEvent.event == "started",
            ).distinct()
        ).scalars().all()

        for other_name in other_devices:
            last_puff = ctx.db_session.execute(
                select(VapeEvent.timestamp).where(
                    VapeEvent.device_name == other_name,
                    VapeEvent.event == "started",
                ).order_by(VapeEvent.timestamp.desc()).limit(1)
            ).scalar()
            if last_puff and window_start <= last_puff <= ctx.timestamp:
                return True
        return False


@register
class FleetAdmiral(Achievement):
    id = "fleet_admiral"
    name = "Fleet Admiral"
    description = "5+ devices registered simultaneously"

    def device_scope(self, ctx):
        return None

    def check(self, ctx):
        if ctx.event != "started":
            return False
        return len(ctx.all_devices) >= 5


@register
class LoneWolf(Achievement):
    id = "lone_wolf"
    name = "Lone Wolf"
    description = "Only one device active for 30 consecutive days"

    def device_scope(self, ctx):
        return None

    def check(self, ctx):
        if ctx.event != "started":
            return False
        window_start = ctx.timestamp - timedelta(days=30)
        devices = ctx.db_session.execute(
            select(VapeEvent.device_name).where(
                VapeEvent.event == "started",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp <= ctx.timestamp,
            ).distinct()
        ).scalars().all()
        return len(set(devices)) == 1


@register
class SocialVaping(Achievement):
    id = "social_vaping"
    name = "Social Vaping"
    description = "3+ devices all active within a 5-minute window"

    def device_scope(self, ctx):
        return None

    def check(self, ctx):
        if ctx.event != "started":
            return False
        window_start = ctx.timestamp - timedelta(minutes=5)
        devices = ctx.db_session.execute(
            select(VapeEvent.device_name).where(
                VapeEvent.event == "started",
                VapeEvent.timestamp >= window_start,
                VapeEvent.timestamp <= ctx.timestamp,
            ).distinct()
        ).scalars().all()
        return len(set(devices)) >= 3
