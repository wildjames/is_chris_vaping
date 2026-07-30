from datetime import datetime, timedelta, timezone

from achievements.time_of_day import EarlyBird, NightOwl, SunriseRip, LunchBreak, AroundTheClock


class TestEarlyBird:
    def test_puff_at_5am_triggers(self, make_ctx):
        ts = datetime(2025, 6, 15, 5, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert EarlyBird().check(ctx) is True

    def test_puff_at_3am_triggers(self, make_ctx):
        ts = datetime(2025, 6, 15, 3, 30, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert EarlyBird().check(ctx) is True

    def test_puff_at_6am_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 6, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert EarlyBird().check(ctx) is False

    def test_puff_at_noon_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert EarlyBird().check(ctx) is False

    def test_stopped_event_ignored(self, make_ctx):
        ts = datetime(2025, 6, 15, 3, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="stopped", timestamp=ts)
        assert EarlyBird().check(ctx) is False


class TestNightOwl:
    def test_puff_at_2am_triggers(self, make_ctx):
        ts = datetime(2025, 6, 15, 2, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert NightOwl().check(ctx) is True

    def test_puff_at_3am_triggers(self, make_ctx):
        ts = datetime(2025, 6, 15, 3, 30, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert NightOwl().check(ctx) is True

    def test_puff_at_4am_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 4, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert NightOwl().check(ctx) is False

    def test_puff_at_1am_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 1, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert NightOwl().check(ctx) is False


class TestSunriseRip:
    def test_puff_at_505am_triggers(self, make_ctx):
        ts = datetime(2025, 6, 15, 5, 5, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert SunriseRip().check(ctx) is True

    def test_puff_at_500am_triggers(self, make_ctx):
        ts = datetime(2025, 6, 15, 5, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert SunriseRip().check(ctx) is True

    def test_puff_at_515am_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 5, 15, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert SunriseRip().check(ctx) is False

    def test_puff_at_6am_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 6, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert SunriseRip().check(ctx) is False


class TestLunchBreak:
    def test_7_consecutive_days_at_lunch_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 2, 0, tzinfo=timezone.utc)
        events = []
        for days_ago in range(7):
            ts = base - timedelta(days=days_ago)
            events.append(("test_device", "coil_a", "started", ts))
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base)
        assert LunchBreak().check(ctx) is True

    def test_missing_one_day_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 2, 0, tzinfo=timezone.utc)
        events = []
        for days_ago in range(7):
            if days_ago == 3:  # Skip one day
                continue
            ts = base - timedelta(days=days_ago)
            events.append(("test_device", "coil_a", "started", ts))
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base)
        assert LunchBreak().check(ctx) is False

    def test_puff_outside_lunch_window_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 2, 0, tzinfo=timezone.utc)
        events = []
        for days_ago in range(1, 7):
            ts = base - timedelta(days=days_ago)
            events.append(("test_device", "coil_a", "started", ts))
        add_events(events)
        # Current puff is at 12:06 (outside window)
        ctx = make_ctx(event="started", timestamp=datetime(2025, 6, 15, 12, 6, 0, tzinfo=timezone.utc))
        assert LunchBreak().check(ctx) is False


class TestAroundTheClock:
    def test_all_24_hours_covered_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(hours=h, minutes=30))
            for h in range(24)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(hours=23, minutes=30))
        assert AroundTheClock().check(ctx) is True

    def test_missing_one_hour_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(hours=h, minutes=30))
            for h in range(23)  # Missing hour 23
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(hours=22, minutes=30))
        assert AroundTheClock().check(ctx) is False

    def test_stopped_event_ignored(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(hours=h, minutes=30))
            for h in range(24)
        ]
        add_events(events)
        ctx = make_ctx(event="stopped", timestamp=base + timedelta(hours=23, minutes=30))
        assert AroundTheClock().check(ctx) is False
