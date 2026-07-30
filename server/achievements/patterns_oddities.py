from datetime import timedelta

from sqlalchemy import select

from achievements.base import Achievement, register
from models import VapeEvent


def _recent_puff_pairs(ctx, n):
    """Get the last N (start, stop) timestamp pairs for this device."""
    stops = ctx.db_session.execute(
        select(VapeEvent.timestamp).where(
            VapeEvent.device_name == ctx.device_name,
            VapeEvent.event == "stopped",
            VapeEvent.timestamp <= ctx.timestamp,
        ).order_by(VapeEvent.timestamp.desc()).limit(n)
    ).scalars().all()

    pairs = []
    for stop_ts in reversed(stops):
        start_ts = ctx.db_session.execute(
            select(VapeEvent.timestamp).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
                VapeEvent.timestamp < stop_ts,
            ).order_by(VapeEvent.timestamp.desc()).limit(1)
        ).scalar()
        if start_ts is not None:
            pairs.append((start_ts, stop_ts))
    return pairs


@register
class MorseCode(Achievement):
    id = "morse_code"
    name = "Morse Code"
    description = "A sequence of short-long-short puffs (<1s, >5s, <1s) within 30 seconds"

    def check(self, ctx):
        if ctx.event != "stopped":
            return False
        pairs = _recent_puff_pairs(ctx, 3)
        if len(pairs) < 3:
            return False

        # Check all 3 happened within 30 seconds
        if (pairs[-1][1] - pairs[0][0]).total_seconds() > 30:
            return False

        durations = [(stop - start).total_seconds() for start, stop in pairs]
        return durations[0] < 1.0 and durations[1] > 5.0 and durations[2] < 1.0


@register
class Metronome(Achievement):
    id = "metronome"
    name = "Metronome"
    description = "5 puffs with identical intervals (±0.5s)"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        starts = ctx.db_session.execute(
            select(VapeEvent.timestamp).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.event == "started",
            ).order_by(VapeEvent.timestamp.desc()).limit(5)
        ).scalars().all()

        if len(starts) < 5:
            return False

        starts = list(reversed(starts))
        intervals = [(starts[i] - starts[i - 1]).total_seconds() for i in range(1, len(starts))]
        avg = sum(intervals) / len(intervals)
        return all(abs(iv - avg) <= 0.5 for iv in intervals)


@register
class Crescendo(Achievement):
    id = "crescendo"
    name = "Crescendo"
    description = "5 consecutive puffs each longer than the last"

    def check(self, ctx):
        if ctx.event != "stopped":
            return False
        pairs = _recent_puff_pairs(ctx, 5)
        if len(pairs) < 5:
            return False

        durations = [(stop - start).total_seconds() for start, stop in pairs]
        for i in range(1, len(durations)):
            if durations[i] <= durations[i - 1]:
                return False
        return True


@register
class Decrescendo(Achievement):
    id = "decrescendo"
    name = "Decrescendo"
    description = "5 consecutive puffs each shorter than the last"

    def check(self, ctx):
        if ctx.event != "stopped":
            return False
        pairs = _recent_puff_pairs(ctx, 5)
        if len(pairs) < 5:
            return False

        durations = [(stop - start).total_seconds() for start, stop in pairs]
        for i in range(1, len(durations)):
            if durations[i] >= durations[i - 1]:
                return False
        return True


@register
class WitchingHour(Achievement):
    id = "witching_hour"
    name = "Witching Hour"
    description = "Puff at exactly midnight (00:00:00 ±5s)"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        midnight = ctx.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        diff = abs((ctx.timestamp - midnight).total_seconds())
        # Also check just before midnight (23:59:55+)
        next_midnight = midnight + timedelta(days=1)
        diff_next = abs((next_midnight - ctx.timestamp).total_seconds())
        return diff <= 5 or diff_next <= 5


@register
class NewYearsRip(Achievement):
    id = "new_years_rip"
    name = "New Year's Rip"
    description = "Puff in the first minute of January 1st"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        return ctx.timestamp.month == 1 and ctx.timestamp.day == 1 and ctx.timestamp.hour == 0 and ctx.timestamp.minute == 0


@register
class PowerNap(Achievement):
    id = "power_nap"
    name = "Power Nap"
    description = "Device goes to deep sleep and wakes back up within 2 hours"

    def check(self, ctx):
        if ctx.event != "started":
            return False
        # Look for a gap of at least 30 minutes but less than 2 hours
        prev_event = ctx.db_session.execute(
            select(VapeEvent.timestamp).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.timestamp < ctx.timestamp,
            ).order_by(VapeEvent.timestamp.desc()).limit(1)
        ).scalar()
        if prev_event is None:
            return False
        gap = (ctx.timestamp - prev_event).total_seconds()
        return 1800 <= gap <= 7200  # 30min to 2h


@register
class PhantomPuff(Achievement):
    id = "phantom_puff"
    name = "Phantom Puff"
    description = "A puff so short the firmware debounce almost caught it (~0.5s ±50ms)"

    def check(self, ctx):
        if ctx.event != "stopped":
            return False
        start = ctx.db_session.execute(
            select(VapeEvent.timestamp).where(
                VapeEvent.device_name == ctx.device_name,
                VapeEvent.coil == ctx.coil,
                VapeEvent.event == "started",
                VapeEvent.timestamp < ctx.timestamp,
            ).order_by(VapeEvent.timestamp.desc()).limit(1)
        ).scalar()
        if start is None:
            return False
        duration = (ctx.timestamp - start).total_seconds()
        return abs(duration - 0.5) < 0.05  # within 50ms of exactly 0.5s
