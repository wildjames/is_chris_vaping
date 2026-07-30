from datetime import datetime, timedelta, timezone

from achievements.dual_coil import DoubleBarrel, CoilLoyalist, Ambidextrous, CoilSwap, FavouriteChild


class TestDoubleBarrel:
    def test_both_coils_active_triggers(self, make_ctx):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        all_devices = {"test_device": {"coil_a": True, "coil_b": True, "last_event": "started"}}
        ctx = make_ctx(event="started", timestamp=ts, all_devices=all_devices)
        assert DoubleBarrel().check(ctx) is True

    def test_one_coil_active_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        all_devices = {"test_device": {"coil_a": True, "coil_b": False, "last_event": "started"}}
        ctx = make_ctx(event="started", timestamp=ts, all_devices=all_devices)
        assert DoubleBarrel().check(ctx) is False

    def test_no_coils_active_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        all_devices = {"test_device": {"coil_a": False, "coil_b": False, "last_event": "stopped"}}
        ctx = make_ctx(event="started", timestamp=ts, all_devices=all_devices)
        assert DoubleBarrel().check(ctx) is False

    def test_stopped_event_ignored(self, make_ctx):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        all_devices = {"test_device": {"coil_a": True, "coil_b": True, "last_event": "started"}}
        ctx = make_ctx(event="stopped", timestamp=ts, all_devices=all_devices)
        assert DoubleBarrel().check(ctx) is False


class TestCoilLoyalist:
    def test_100_same_coil_puffs_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i))
            for i in range(100)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=99))
        assert CoilLoyalist().check(ctx) is True

    def test_mixed_coils_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i))
            for i in range(99)
        ]
        events.append(("test_device", "coil_b", "started", base + timedelta(seconds=99)))
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=99))
        assert CoilLoyalist().check(ctx) is False

    def test_fewer_than_100_puffs(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i))
            for i in range(50)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=49))
        assert CoilLoyalist().check(ctx) is False


class TestAmbidextrous:
    def test_equal_puffs_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(10):
            events.append(("test_device", "coil_a", "started", base + timedelta(minutes=i * 2)))
            events.append(("test_device", "coil_b", "started", base + timedelta(minutes=i * 2 + 1)))
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(minutes=19))
        assert Ambidextrous().check(ctx) is True

    def test_unequal_puffs_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(minutes=i))
            for i in range(15)
        ]
        events.extend([
            ("test_device", "coil_b", "started", base + timedelta(minutes=20 + i))
            for i in range(5)
        ])
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(minutes=24))
        assert Ambidextrous().check(ctx) is False

    def test_too_few_puffs(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(minutes=1)),
            ("test_device", "coil_b", "started", base + timedelta(minutes=2)),
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(minutes=2))
        assert Ambidextrous().check(ctx) is False


class TestCoilSwap:
    def test_alternating_coils_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(10):
            coil = "coil_a" if i % 2 == 0 else "coil_b"
            events.append(("test_device", coil, "started", base + timedelta(seconds=i)))
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=9))
        assert CoilSwap().check(ctx) is True

    def test_consecutive_same_coil_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(8):
            coil = "coil_a" if i % 2 == 0 else "coil_b"
            events.append(("test_device", coil, "started", base + timedelta(seconds=i)))
        # Two consecutive same coil
        events.append(("test_device", "coil_a", "started", base + timedelta(seconds=8)))
        events.append(("test_device", "coil_a", "started", base + timedelta(seconds=9)))
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=9))
        assert CoilSwap().check(ctx) is False


class TestFavouriteChild:
    def test_10x_ratio_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i))
            for i in range(100)
        ]
        events.extend([
            ("test_device", "coil_b", "started", base + timedelta(seconds=200 + i))
            for i in range(10)
        ])
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=209))
        assert FavouriteChild().check(ctx) is True

    def test_less_than_10x_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i))
            for i in range(50)
        ]
        events.extend([
            ("test_device", "coil_b", "started", base + timedelta(seconds=100 + i))
            for i in range(10)
        ])
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=109))
        assert FavouriteChild().check(ctx) is False

    def test_one_coil_zero_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i))
            for i in range(100)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=99))
        assert FavouriteChild().check(ctx) is False
