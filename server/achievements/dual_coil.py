from sqlalchemy import func, select

from achievements.base import Achievement, register
from models import VapeEvent


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
class CoilLoyalist(Achievement):
    id = "coil_loyalist"
    name = "Coil Loyalist"
    description = "100 consecutive puffs on the same coil"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        recent_coils = ctx.db_session.execute(
            select(VapeEvent.coil).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
            ).order_by(VapeEvent.timestamp.desc()).limit(100)
        ).scalars().all()
        if len(recent_coils) < 100:
            return False
        return len(set(recent_coils)) == 1


@register
class Ambidextrous(Achievement):
    id = "ambidextrous"
    name = "Ambidextrous"
    description = "Equal puffs on both coils within a day (±5%)"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        from datetime import timedelta
        day_start = ctx.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        coil_a_count = ctx.db_session.execute(
            select(func.count(VapeEvent.id)).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.coil == "coil_a",
                VapeEvent.timestamp >= day_start,
                VapeEvent.timestamp < day_end,
            )
        ).scalar()

        coil_b_count = ctx.db_session.execute(
            select(func.count(VapeEvent.id)).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.coil == "coil_b",
                VapeEvent.timestamp >= day_start,
                VapeEvent.timestamp < day_end,
            )
        ).scalar()

        total = coil_a_count + coil_b_count
        if total < 10:  # Need a meaningful sample
            return False
        diff = abs(coil_a_count - coil_b_count)
        return diff <= total * 0.05


@register
class CoilSwap(Achievement):
    id = "coil_swap"
    name = "Coil Swap"
    description = "Alternate between coil A and coil B 10 times in a row"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        recent_coils = ctx.db_session.execute(
            select(VapeEvent.coil).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
            ).order_by(VapeEvent.timestamp.desc()).limit(10)
        ).scalars().all()
        if len(recent_coils) < 10:
            return False
        for i in range(1, len(recent_coils)):
            if recent_coils[i] == recent_coils[i - 1]:
                return False
        return True


@register
class FavouriteChild(Achievement):
    id = "favourite_child"
    name = "Favourite Child"
    description = "One coil has 10x the lifetime puffs of the other"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        coil_a_count = ctx.db_session.execute(
            select(func.count(VapeEvent.id)).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.coil == "coil_a",
            )
        ).scalar()

        coil_b_count = ctx.db_session.execute(
            select(func.count(VapeEvent.id)).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.coil == "coil_b",
            )
        ).scalar()

        if coil_a_count == 0 or coil_b_count == 0:
            return False
        return coil_a_count >= 10 * coil_b_count or coil_b_count >= 10 * coil_a_count
