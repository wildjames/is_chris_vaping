from datetime import datetime, timedelta, timezone

from achievements.milestone_counts import FirstBlood, Century, KiloChuffer, TenGrand, Chronic


class TestFirstBlood:
    def test_first_puff_triggers(self, make_ctx, add_puffs):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_puffs(count=1, start_time=ts)
        ctx = make_ctx(event="started", timestamp=ts)
        assert FirstBlood().check(ctx) is True

    def test_second_puff_does_not_trigger(self, make_ctx, add_puffs):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_puffs(count=2, start_time=ts)
        ctx = make_ctx(event="started", timestamp=ts + timedelta(seconds=60))
        assert FirstBlood().check(ctx) is False

    def test_stopped_event_does_not_trigger(self, make_ctx, add_puffs):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_puffs(count=1, start_time=ts)
        ctx = make_ctx(event="stopped", timestamp=ts)
        assert FirstBlood().check(ctx) is False


class TestCentury:
    def test_at_100_puffs(self, make_ctx, add_puffs):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_puffs(count=100, start_time=ts)
        ctx = make_ctx(event="started", timestamp=ts + timedelta(seconds=99 * 60))
        assert Century().check(ctx) is True

    def test_at_99_puffs(self, make_ctx, add_puffs):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_puffs(count=99, start_time=ts)
        ctx = make_ctx(event="started", timestamp=ts + timedelta(seconds=98 * 60))
        assert Century().check(ctx) is False

    def test_stopped_event_ignored(self, make_ctx, add_puffs):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_puffs(count=100, start_time=ts)
        ctx = make_ctx(event="stopped", timestamp=ts + timedelta(seconds=99 * 60))
        assert Century().check(ctx) is False


class TestKiloChuffer:
    def test_at_1000_puffs(self, make_ctx, add_puffs):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_puffs(count=1000, start_time=ts, interval_seconds=10)
        ctx = make_ctx(event="started", timestamp=ts + timedelta(seconds=999 * 10))
        assert KiloChuffer().check(ctx) is True

    def test_below_1000(self, make_ctx, add_puffs):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_puffs(count=999, start_time=ts, interval_seconds=10)
        ctx = make_ctx(event="started", timestamp=ts + timedelta(seconds=998 * 10))
        assert KiloChuffer().check(ctx) is False


class TestTenGrand:
    def test_at_10000(self, make_ctx, add_puffs):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_puffs(count=10000, start_time=ts, interval_seconds=1)
        ctx = make_ctx(event="started", timestamp=ts + timedelta(seconds=9999))
        assert TenGrand().check(ctx) is True

    def test_below_10000(self, make_ctx, add_puffs):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_puffs(count=9999, start_time=ts, interval_seconds=1)
        ctx = make_ctx(event="started", timestamp=ts + timedelta(seconds=9998))
        assert TenGrand().check(ctx) is False


class TestChronic:
    def test_at_100000(self, make_ctx, add_puffs):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_puffs(count=100000, start_time=ts, interval_seconds=1)
        ctx = make_ctx(event="started", timestamp=ts + timedelta(seconds=99999))
        assert Chronic().check(ctx) is True

    def test_below_100000(self, make_ctx, add_puffs):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_puffs(count=99999, start_time=ts, interval_seconds=1)
        ctx = make_ctx(event="started", timestamp=ts + timedelta(seconds=99998))
        assert Chronic().check(ctx) is False
