from sqlalchemy import func, select

from achievements.base import Achievement, AchievementContext, register
from models import VapeEvent


def _puff_count(ctx: AchievementContext) -> int:
    return ctx.db_session.execute(
        select(func.count(VapeEvent.id)).where(
            VapeEvent.device_name == ctx.device_name,
            VapeEvent.event == "started",
        )
    ).scalar()


@register
class FirstBlood(Achievement):
    id = "first_blood"
    name = "First Blood"
    description = "Record your first puff"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        return _puff_count(ctx) == 1


@register
class Century(Achievement):
    id = "century"
    name = "Century"
    description = "100 total puffs"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        return _puff_count(ctx) >= 100


@register
class KiloChuffer(Achievement):
    id = "kilo_chuffer"
    name = "Kilo Chuffer"
    description = "1,000 total puffs"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        return _puff_count(ctx) >= 1000


@register
class TenGrand(Achievement):
    id = "ten_grand"
    name = "Ten Grand"
    description = "10,000 total puffs"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        return _puff_count(ctx) >= 10000


@register
class Chronic(Achievement):
    id = "chronic"
    name = "Chronic"
    description = "100,000 total puffs"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        return _puff_count(ctx) >= 100000
