from datetime import datetime, timedelta, timezone

from achievements.patterns_oddities import (
    MorseCode, Metronome, Crescendo, Decrescendo,
    WitchingHour, NewYearsRip, PowerNap, PhantomPuff,
)


class TestMorseCode:
    def test_short_long_short_pattern_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base),
            ("test_device", "coil_a", "stopped", base + timedelta(seconds=0.5)),
            ("test_device", "coil_a", "started", base + timedelta(seconds=2)),
            ("test_device", "coil_a", "stopped", base + timedelta(seconds=8)),
            ("test_device", "coil_a", "started", base + timedelta(seconds=10)),
            ("test_device", "coil_a", "stopped", base + timedelta(seconds=10.5)),
        ]
        add_events(events)
        ctx = make_ctx(event="stopped", timestamp=base + timedelta(seconds=10.5))
        assert MorseCode().check(ctx) is True

    def test_all_short_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base),
            ("test_device", "coil_a", "stopped", base + timedelta(seconds=0.5)),
            ("test_device", "coil_a", "started", base + timedelta(seconds=2)),
            ("test_device", "coil_a", "stopped", base + timedelta(seconds=2.5)),
            ("test_device", "coil_a", "started", base + timedelta(seconds=4)),
            ("test_device", "coil_a", "stopped", base + timedelta(seconds=4.5)),
        ]
        add_events(events)
        ctx = make_ctx(event="stopped", timestamp=base + timedelta(seconds=4.5))
        assert MorseCode().check(ctx) is False

    def test_over_30s_window_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base),
            ("test_device", "coil_a", "stopped", base + timedelta(seconds=0.5)),
            ("test_device", "coil_a", "started", base + timedelta(seconds=10)),
            ("test_device", "coil_a", "stopped", base + timedelta(seconds=16)),
            ("test_device", "coil_a", "started", base + timedelta(seconds=31)),
            ("test_device", "coil_a", "stopped", base + timedelta(seconds=31.5)),
        ]
        add_events(events)
        ctx = make_ctx(event="stopped", timestamp=base + timedelta(seconds=31.5))
        assert MorseCode().check(ctx) is False


class TestMetronome:
    def test_5_evenly_spaced_puffs_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i * 10))
            for i in range(5)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=40))
        assert Metronome().check(ctx) is True

    def test_uneven_spacing_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        offsets = [0, 10, 25, 35, 50]
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=o))
            for o in offsets
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=50))
        assert Metronome().check(ctx) is False

    def test_within_tolerance_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        offsets = [0, 10.2, 20.1, 29.8, 40.0]
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=o))
            for o in offsets
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=40.0))
        assert Metronome().check(ctx) is True

    def test_fewer_than_5_puffs(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base + timedelta(seconds=i * 10))
            for i in range(3)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(seconds=20))
        assert Metronome().check(ctx) is False


class TestCrescendo:
    def test_increasing_durations_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        offset = 0
        for i in range(5):
            duration = 1 + i  # 1s, 2s, 3s, 4s, 5s
            events.append(("test_device", "coil_a", "started", base + timedelta(seconds=offset)))
            events.append(("test_device", "coil_a", "stopped", base + timedelta(seconds=offset + duration)))
            offset += duration + 2
        add_events(events)
        last_stop = base + timedelta(seconds=offset - 2)
        ctx = make_ctx(event="stopped", timestamp=last_stop)
        assert Crescendo().check(ctx) is True

    def test_decreasing_durations_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        offset = 0
        for i in range(5):
            duration = 5 - i  # 5s, 4s, 3s, 2s, 1s
            events.append(("test_device", "coil_a", "started", base + timedelta(seconds=offset)))
            events.append(("test_device", "coil_a", "stopped", base + timedelta(seconds=offset + duration)))
            offset += duration + 2
        add_events(events)
        last_stop = base + timedelta(seconds=offset - 2)
        ctx = make_ctx(event="stopped", timestamp=last_stop)
        assert Crescendo().check(ctx) is False

    def test_fewer_than_5_puffs(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base),
            ("test_device", "coil_a", "stopped", base + timedelta(seconds=1)),
            ("test_device", "coil_a", "started", base + timedelta(seconds=3)),
            ("test_device", "coil_a", "stopped", base + timedelta(seconds=5)),
        ]
        add_events(events)
        ctx = make_ctx(event="stopped", timestamp=base + timedelta(seconds=5))
        assert Crescendo().check(ctx) is False


class TestDecrescendo:
    def test_decreasing_durations_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        offset = 0
        for i in range(5):
            duration = 5 - i  # 5s, 4s, 3s, 2s, 1s
            events.append(("test_device", "coil_a", "started", base + timedelta(seconds=offset)))
            events.append(("test_device", "coil_a", "stopped", base + timedelta(seconds=offset + duration)))
            offset += duration + 2
        add_events(events)
        last_stop = base + timedelta(seconds=offset - 2)
        ctx = make_ctx(event="stopped", timestamp=last_stop)
        assert Decrescendo().check(ctx) is True

    def test_increasing_durations_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        offset = 0
        for i in range(5):
            duration = 1 + i
            events.append(("test_device", "coil_a", "started", base + timedelta(seconds=offset)))
            events.append(("test_device", "coil_a", "stopped", base + timedelta(seconds=offset + duration)))
            offset += duration + 2
        add_events(events)
        last_stop = base + timedelta(seconds=offset - 2)
        ctx = make_ctx(event="stopped", timestamp=last_stop)
        assert Decrescendo().check(ctx) is False


class TestWitchingHour:
    def test_puff_at_midnight_triggers(self, make_ctx):
        ts = datetime(2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert WitchingHour().check(ctx) is True

    def test_puff_3s_after_midnight_triggers(self, make_ctx):
        ts = datetime(2025, 6, 15, 0, 0, 3, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert WitchingHour().check(ctx) is True

    def test_puff_4s_before_midnight_triggers(self, make_ctx):
        ts = datetime(2025, 6, 14, 23, 59, 56, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert WitchingHour().check(ctx) is True

    def test_puff_at_1am_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 1, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert WitchingHour().check(ctx) is False

    def test_puff_10s_after_midnight_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 0, 0, 10, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert WitchingHour().check(ctx) is False


class TestNewYearsRip:
    def test_puff_at_new_years_triggers(self, make_ctx):
        ts = datetime(2025, 1, 1, 0, 0, 30, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert NewYearsRip().check(ctx) is True

    def test_puff_at_1201_jan1_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 1, 1, 0, 1, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert NewYearsRip().check(ctx) is False

    def test_puff_on_another_day_does_not_trigger(self, make_ctx):
        ts = datetime(2025, 6, 15, 0, 0, 30, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=ts)
        assert NewYearsRip().check(ctx) is False


class TestPowerNap:
    def test_gap_of_1h_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "stopped", base - timedelta(hours=1)),
        ])
        ctx = make_ctx(event="started", timestamp=base)
        assert PowerNap().check(ctx) is True

    def test_gap_of_3h_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "stopped", base - timedelta(hours=3)),
        ])
        ctx = make_ctx(event="started", timestamp=base)
        assert PowerNap().check(ctx) is False

    def test_gap_of_10min_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "stopped", base - timedelta(minutes=10)),
        ])
        ctx = make_ctx(event="started", timestamp=base)
        assert PowerNap().check(ctx) is False

    def test_no_previous_event_does_not_trigger(self, make_ctx):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=base)
        assert PowerNap().check(ctx) is False


class TestPhantomPuff:
    def test_puff_exactly_0_5s_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "started", base),
            ("test_device", "coil_a", "stopped", base + timedelta(milliseconds=500)),
        ])
        ctx = make_ctx(event="stopped", timestamp=base + timedelta(milliseconds=500))
        assert PhantomPuff().check(ctx) is True

    def test_puff_0_48s_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "started", base),
            ("test_device", "coil_a", "stopped", base + timedelta(milliseconds=480)),
        ])
        ctx = make_ctx(event="stopped", timestamp=base + timedelta(milliseconds=480))
        assert PhantomPuff().check(ctx) is True

    def test_puff_1s_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "started", base),
            ("test_device", "coil_a", "stopped", base + timedelta(seconds=1)),
        ])
        ctx = make_ctx(event="stopped", timestamp=base + timedelta(seconds=1))
        assert PhantomPuff().check(ctx) is False

    def test_puff_0_3s_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "started", base),
            ("test_device", "coil_a", "stopped", base + timedelta(milliseconds=300)),
        ])
        ctx = make_ctx(event="stopped", timestamp=base + timedelta(milliseconds=300))
        assert PhantomPuff().check(ctx) is False
