from datetime import datetime, timedelta, timezone

from achievements.duration_records import QuickDraw, SavourIt, IronLungs, AreYouOkay, MicroHit


class TestQuickDraw:
    def test_short_puff_triggers(self, make_ctx, add_events):
        start = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stop = start + timedelta(seconds=0.3)
        add_events([
            ("test_device", "coil_a", "started", start),
            ("test_device", "coil_a", "stopped", stop),
        ])
        ctx = make_ctx(event="stopped", timestamp=stop)
        assert QuickDraw().check(ctx) is True

    def test_long_puff_does_not_trigger(self, make_ctx, add_events):
        start = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stop = start + timedelta(seconds=1.0)
        add_events([
            ("test_device", "coil_a", "started", start),
            ("test_device", "coil_a", "stopped", stop),
        ])
        ctx = make_ctx(event="stopped", timestamp=stop)
        assert QuickDraw().check(ctx) is False

    def test_started_event_ignored(self, make_ctx, add_events):
        start = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([("test_device", "coil_a", "started", start)])
        ctx = make_ctx(event="started", timestamp=start)
        assert QuickDraw().check(ctx) is False

    def test_exactly_half_second_does_not_trigger(self, make_ctx, add_events):
        start = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stop = start + timedelta(seconds=0.5)
        add_events([
            ("test_device", "coil_a", "started", start),
            ("test_device", "coil_a", "stopped", stop),
        ])
        ctx = make_ctx(event="stopped", timestamp=stop)
        assert QuickDraw().check(ctx) is False


class TestSavourIt:
    def test_over_10s_triggers(self, make_ctx, add_events):
        start = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stop = start + timedelta(seconds=11)
        add_events([
            ("test_device", "coil_a", "started", start),
            ("test_device", "coil_a", "stopped", stop),
        ])
        ctx = make_ctx(event="stopped", timestamp=stop)
        assert SavourIt().check(ctx) is True

    def test_under_10s_does_not_trigger(self, make_ctx, add_events):
        start = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stop = start + timedelta(seconds=9)
        add_events([
            ("test_device", "coil_a", "started", start),
            ("test_device", "coil_a", "stopped", stop),
        ])
        ctx = make_ctx(event="stopped", timestamp=stop)
        assert SavourIt().check(ctx) is False


class TestIronLungs:
    def test_over_20s_triggers(self, make_ctx, add_events):
        start = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stop = start + timedelta(seconds=21)
        add_events([
            ("test_device", "coil_a", "started", start),
            ("test_device", "coil_a", "stopped", stop),
        ])
        ctx = make_ctx(event="stopped", timestamp=stop)
        assert IronLungs().check(ctx) is True

    def test_under_20s_does_not_trigger(self, make_ctx, add_events):
        start = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stop = start + timedelta(seconds=15)
        add_events([
            ("test_device", "coil_a", "started", start),
            ("test_device", "coil_a", "stopped", stop),
        ])
        ctx = make_ctx(event="stopped", timestamp=stop)
        assert IronLungs().check(ctx) is False


class TestAreYouOkay:
    def test_over_30s_triggers(self, make_ctx, add_events):
        start = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stop = start + timedelta(seconds=31)
        add_events([
            ("test_device", "coil_a", "started", start),
            ("test_device", "coil_a", "stopped", stop),
        ])
        ctx = make_ctx(event="stopped", timestamp=stop)
        assert AreYouOkay().check(ctx) is True

    def test_under_30s_does_not_trigger(self, make_ctx, add_events):
        start = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        stop = start + timedelta(seconds=25)
        add_events([
            ("test_device", "coil_a", "started", start),
            ("test_device", "coil_a", "stopped", stop),
        ])
        ctx = make_ctx(event="stopped", timestamp=stop)
        assert AreYouOkay().check(ctx) is False


class TestMicroHit:
    def test_10_short_puffs_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(10):
            start = base + timedelta(seconds=i * 3)
            stop = start + timedelta(seconds=0.8)
            events.append(("test_device", "coil_a", "started", start))
            events.append(("test_device", "coil_a", "stopped", stop))
        add_events(events)
        last_stop = base + timedelta(seconds=9 * 3) + timedelta(seconds=0.8)
        ctx = make_ctx(event="stopped", timestamp=last_stop)
        assert MicroHit().check(ctx) is True

    def test_one_long_puff_breaks_streak(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(9):
            start = base + timedelta(seconds=i * 3)
            stop = start + timedelta(seconds=0.8)
            events.append(("test_device", "coil_a", "started", start))
            events.append(("test_device", "coil_a", "stopped", stop))
        # Last puff is too long
        start = base + timedelta(seconds=9 * 3)
        stop = start + timedelta(seconds=1.5)
        events.append(("test_device", "coil_a", "started", start))
        events.append(("test_device", "coil_a", "stopped", stop))
        add_events(events)
        ctx = make_ctx(event="stopped", timestamp=stop)
        assert MicroHit().check(ctx) is False

    def test_fewer_than_10_puffs(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(5):
            start = base + timedelta(seconds=i * 3)
            stop = start + timedelta(seconds=0.5)
            events.append(("test_device", "coil_a", "started", start))
            events.append(("test_device", "coil_a", "stopped", stop))
        add_events(events)
        last_stop = base + timedelta(seconds=4 * 3) + timedelta(seconds=0.5)
        ctx = make_ctx(event="stopped", timestamp=last_stop)
        assert MicroHit().check(ctx) is False

    def test_started_event_ignored(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(10):
            start = base + timedelta(seconds=i * 3)
            stop = start + timedelta(seconds=0.5)
            events.append(("test_device", "coil_a", "started", start))
            events.append(("test_device", "coil_a", "stopped", stop))
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=9 * 3))
        assert MicroHit().check(ctx) is False
