from datetime import datetime, timedelta, timezone

from achievements.frequency_rate import ChainSmoker, GatlingGun, OneAndDone, MarathonSession, PaceYourself


class TestChainSmoker:
    def test_10_puffs_in_2_minutes_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i * 10))
            for i in range(10)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=90))
        assert ChainSmoker().check(ctx) is True

    def test_9_puffs_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i * 10))
            for i in range(9)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=80))
        assert ChainSmoker().check(ctx) is False

    def test_puffs_spread_too_far_apart(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i * 30))
            for i in range(10)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=270))
        assert ChainSmoker().check(ctx) is False

    def test_stopped_event_ignored(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i * 10))
            for i in range(10)
        ]
        add_events(events)
        ctx = make_ctx(event="stopped", timestamp=base + timedelta(seconds=90))
        assert ChainSmoker().check(ctx) is False


class TestGatlingGun:
    def test_20_puffs_in_5_minutes_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i * 14))
            for i in range(20)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=19 * 14))
        assert GatlingGun().check(ctx) is True

    def test_19_puffs_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i * 14))
            for i in range(19)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=18 * 14))
        assert GatlingGun().check(ctx) is False


class TestOneAndDone:
    def test_single_puff_yesterday_triggers(self, make_ctx, add_events):
        today = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        yesterday = datetime(2025, 6, 14, 15, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "started", yesterday),
            ("test_device", "coil_a", "started", today),
        ])
        ctx = make_ctx(event="started", timestamp=today)
        assert OneAndDone().check(ctx) is True

    def test_multiple_puffs_yesterday_does_not_trigger(self, make_ctx, add_events):
        today = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        yesterday1 = datetime(2025, 6, 14, 10, 0, 0, tzinfo=timezone.utc)
        yesterday2 = datetime(2025, 6, 14, 15, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "started", yesterday1),
            ("test_device", "coil_a", "started", yesterday2),
            ("test_device", "coil_a", "started", today),
        ])
        ctx = make_ctx(event="started", timestamp=today)
        assert OneAndDone().check(ctx) is False


class TestMarathonSession:
    def test_consistent_puffs_every_5_min_for_hour(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 11, 0, 0, tzinfo=timezone.utc)
        # One puff per 4 minutes for 60 minutes (15 puffs)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(minutes=i * 4))
            for i in range(16)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(minutes=60))
        assert MarathonSession().check(ctx) is True

    def test_gap_in_session_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 11, 0, 0, tzinfo=timezone.utc)
        # Puffs in first 30min and last 10min, gap in middle
        events = []
        for i in range(7):
            events.append(("test_device", "coil_a", "started", base + timedelta(minutes=i * 4)))
        for i in range(3):
            events.append(("test_device", "coil_a", "started", base + timedelta(minutes=50 + i * 3)))
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(minutes=60))
        assert MarathonSession().check(ctx) is False

    def test_too_few_puffs(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 11, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(minutes=i * 10))
            for i in range(5)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(minutes=60))
        assert MarathonSession().check(ctx) is False


class TestPaceYourself:
    def test_10_puffs_exactly_60s_apart(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i * 60))
            for i in range(10)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=9 * 60))
        assert PaceYourself().check(ctx) is True

    def test_puffs_with_tolerance(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i * 60 + (i % 2) * 3))
            for i in range(10)
        ]
        add_events(events)
        last_ts = base + timedelta(seconds=9 * 60 + 3)
        ctx = make_ctx(event="started", timestamp=last_ts)
        assert PaceYourself().check(ctx) is True

    def test_irregular_puffs_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        # Irregular intervals
        offsets = [0, 30, 90, 120, 200, 260, 350, 400, 500, 570]
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=o))
            for o in offsets
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=570))
        assert PaceYourself().check(ctx) is False

    def test_fewer_than_10_puffs(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i * 60))
            for i in range(5)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=4 * 60))
        assert PaceYourself().check(ctx) is False
