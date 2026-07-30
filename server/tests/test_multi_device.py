from datetime import datetime, timedelta, timezone

from achievements.multi_device import (
    SynchronisedVaping, Duet, MexicanWave, Copycat, Rivalry,
    TheFavourite, PassingTheTorch, FleetAdmiral, LoneWolf, SocialVaping,
)


class TestSynchronisedVaping:
    def test_two_devices_within_1s_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("other_device", "coil_a", "started", base + timedelta(seconds=0.5)),
        ])
        ctx = make_ctx(device_name="test_device", event="started", timestamp=base)
        assert SynchronisedVaping().check(ctx) is True

    def test_devices_far_apart_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("other_device", "coil_a", "started", base - timedelta(seconds=5)),
        ])
        ctx = make_ctx(device_name="test_device", event="started", timestamp=base)
        assert SynchronisedVaping().check(ctx) is False

    def test_same_device_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_b", "started", base + timedelta(seconds=0.5)),
        ])
        ctx = make_ctx(device_name="test_device", event="started", timestamp=base)
        assert SynchronisedVaping().check(ctx) is False

    def test_global_scope(self):
        assert SynchronisedVaping().device_scope(None) is None


class TestDuet:
    def test_two_devices_active_triggers(self, make_ctx):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        all_devices = {
            "device1": {"coil_a": True, "coil_b": False},
            "device2": {"coil_a": True, "coil_b": False},
        }
        ctx = make_ctx(device_name="device1", event="started", timestamp=ts, all_devices=all_devices)
        assert Duet().check(ctx) is True

    def test_one_device_active_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        all_devices = {
            "device1": {"coil_a": True, "coil_b": False},
            "device2": {"coil_a": False, "coil_b": False},
        }
        ctx = make_ctx(device_name="device1", event="started", timestamp=ts, all_devices=all_devices)
        assert Duet().check(ctx) is False


class TestMexicanWave:
    def test_3_devices_in_10s_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("device1", "coil_a", "started", base - timedelta(seconds=8)),
            ("device2", "coil_a", "started", base - timedelta(seconds=4)),
            ("device3", "coil_a", "started", base),
        ])
        ctx = make_ctx(device_name="device3", event="started", timestamp=base)
        assert MexicanWave().check(ctx) is True

    def test_2_devices_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("device1", "coil_a", "started", base - timedelta(seconds=5)),
            ("device2", "coil_a", "started", base),
        ])
        ctx = make_ctx(device_name="device2", event="started", timestamp=base)
        assert MexicanWave().check(ctx) is False


class TestCopycat:
    def test_start_within_3s_of_another_stop_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("other_device", "coil_a", "stopped", base - timedelta(seconds=2)),
        ])
        ctx = make_ctx(device_name="test_device", event="started", timestamp=base)
        assert Copycat().check(ctx) is True

    def test_start_after_3s_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("other_device", "coil_a", "stopped", base - timedelta(seconds=5)),
        ])
        ctx = make_ctx(device_name="test_device", event="started", timestamp=base)
        assert Copycat().check(ctx) is False

    def test_same_device_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "stopped", base - timedelta(seconds=1)),
        ])
        ctx = make_ctx(device_name="test_device", event="started", timestamp=base)
        assert Copycat().check(ctx) is False


class TestRivalry:
    def test_two_devices_over_50_puffs_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(50):
            events.append(("device1", "coil_a", "started", base + timedelta(seconds=i)))
            events.append(("device2", "coil_a", "started", base + timedelta(seconds=i + 0.5)))
        add_events(events)
        ctx = make_ctx(device_name="device1", event="started", timestamp=base + timedelta(seconds=49))
        assert Rivalry().check(ctx) is True

    def test_one_device_under_50_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("device1", "coil_a", "started", base + timedelta(seconds=i))
            for i in range(50)
        ]
        events.extend([
            ("device2", "coil_a", "started", base + timedelta(seconds=i))
            for i in range(10)
        ])
        add_events(events)
        ctx = make_ctx(device_name="device1", event="started", timestamp=base + timedelta(seconds=49))
        assert Rivalry().check(ctx) is False


class TestTheFavourite:
    def test_one_device_dominates_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("device1", "coil_a", "started", base + timedelta(seconds=i))
            for i in range(100)
        ]
        events.extend([
            ("device2", "coil_a", "started", base + timedelta(seconds=200 + i))
            for i in range(10)
        ])
        add_events(events)
        ctx = make_ctx(device_name="device1", event="started", timestamp=base + timedelta(seconds=99))
        assert TheFavourite().check(ctx) is True

    def test_even_split_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("device1", "coil_a", "started", base + timedelta(seconds=i))
            for i in range(50)
        ]
        events.extend([
            ("device2", "coil_a", "started", base + timedelta(seconds=100 + i))
            for i in range(50)
        ])
        add_events(events)
        ctx = make_ctx(device_name="device1", event="started", timestamp=base + timedelta(seconds=49))
        assert TheFavourite().check(ctx) is False


class TestPassingTheTorch:
    def test_new_device_first_puff_within_1min_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("old_device", "coil_a", "started", base - timedelta(seconds=30)),
            ("new_device", "coil_a", "started", base),
        ])
        ctx = make_ctx(device_name="new_device", event="started", timestamp=base)
        assert PassingTheTorch().check(ctx) is True

    def test_not_first_puff_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("old_device", "coil_a", "started", base - timedelta(seconds=30)),
            ("new_device", "coil_a", "started", base - timedelta(hours=1)),
            ("new_device", "coil_a", "started", base),
        ])
        ctx = make_ctx(device_name="new_device", event="started", timestamp=base)
        assert PassingTheTorch().check(ctx) is False


class TestFleetAdmiral:
    def test_5_devices_triggers(self, make_ctx):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        all_devices = {f"device{i}": {"coil_a": False, "coil_b": False} for i in range(5)}
        ctx = make_ctx(event="started", timestamp=ts, all_devices=all_devices)
        assert FleetAdmiral().check(ctx) is True

    def test_4_devices_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        all_devices = {f"device{i}": {"coil_a": False, "coil_b": False} for i in range(4)}
        ctx = make_ctx(event="started", timestamp=ts, all_devices=all_devices)
        assert FleetAdmiral().check(ctx) is False


class TestLoneWolf:
    def test_single_device_30_days_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base - timedelta(days=i))
            for i in range(30)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base)
        assert LoneWolf().check(ctx) is True

    def test_multiple_devices_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base - timedelta(days=i))
            for i in range(30)
        ]
        events.append(("other_device", "coil_a", "started", base - timedelta(days=5)))
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base)
        assert LoneWolf().check(ctx) is False


class TestSocialVaping:
    def test_3_devices_in_5min_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("device1", "coil_a", "started", base - timedelta(minutes=3)),
            ("device2", "coil_a", "started", base - timedelta(minutes=1)),
            ("device3", "coil_a", "started", base),
        ])
        ctx = make_ctx(device_name="device3", event="started", timestamp=base)
        assert SocialVaping().check(ctx) is True

    def test_2_devices_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("device1", "coil_a", "started", base - timedelta(minutes=2)),
            ("device2", "coil_a", "started", base),
        ])
        ctx = make_ctx(device_name="device2", event="started", timestamp=base)
        assert SocialVaping().check(ctx) is False
