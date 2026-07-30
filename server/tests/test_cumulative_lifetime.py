from datetime import datetime, timedelta, timezone

from achievements.cumulative_lifetime import TimeWellSpent, FullWorkDay, Dedicated, VeteranDevice
from models import Firmware


class TestTimeWellSpent:
    def test_over_1h_total_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        events = []
        # 120 puffs of 30s each = 3600s = 1h
        for i in range(120):
            start = base + timedelta(minutes=i)
            stop = start + timedelta(seconds=30)
            events.append(("test_device", "coil_a", "started", start))
            events.append(("test_device", "coil_a", "stopped", stop))
        add_events(events)
        last_stop = base + timedelta(minutes=119) + timedelta(seconds=30)
        ctx = make_ctx(event="stopped", timestamp=last_stop)
        assert TimeWellSpent().check(ctx) is True

    def test_under_1h_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        events = []
        # 10 puffs of 30s = 300s
        for i in range(10):
            start = base + timedelta(minutes=i)
            stop = start + timedelta(seconds=30)
            events.append(("test_device", "coil_a", "started", start))
            events.append(("test_device", "coil_a", "stopped", stop))
        add_events(events)
        last_stop = base + timedelta(minutes=9) + timedelta(seconds=30)
        ctx = make_ctx(event="stopped", timestamp=last_stop)
        assert TimeWellSpent().check(ctx) is False

    def test_started_event_ignored(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(120):
            start = base + timedelta(minutes=i)
            stop = start + timedelta(seconds=30)
            events.append(("test_device", "coil_a", "started", start))
            events.append(("test_device", "coil_a", "stopped", stop))
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base + timedelta(minutes=119))
        assert TimeWellSpent().check(ctx) is False


class TestFullWorkDay:
    def test_over_8h_total_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
        events = []
        # 960 puffs of 30s each = 28800s = 8h
        for i in range(960):
            start = base + timedelta(seconds=i * 35)
            stop = start + timedelta(seconds=30)
            events.append(("test_device", "coil_a", "started", start))
            events.append(("test_device", "coil_a", "stopped", stop))
        add_events(events)
        last_stop = base + timedelta(seconds=959 * 35 + 30)
        ctx = make_ctx(event="stopped", timestamp=last_stop)
        assert FullWorkDay().check(ctx) is True

    def test_under_8h_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
        events = []
        # 100 puffs of 30s = 3000s ~50min
        for i in range(100):
            start = base + timedelta(minutes=i)
            stop = start + timedelta(seconds=30)
            events.append(("test_device", "coil_a", "started", start))
            events.append(("test_device", "coil_a", "stopped", stop))
        add_events(events)
        last_stop = base + timedelta(minutes=99) + timedelta(seconds=30)
        ctx = make_ctx(event="stopped", timestamp=last_stop)
        assert FullWorkDay().check(ctx) is False


class TestDedicated:
    def test_3_firmware_versions_triggers(self, make_ctx, db_session):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        for v in ["1.0.0", "1.1.0", "2.0.0"]:
            db_session.add(Firmware(version=v, variant="nrf52840", size=1000))
        db_session.commit()
        ctx = make_ctx(event="started", timestamp=ts)
        assert Dedicated().check(ctx) is True

    def test_2_firmware_versions_does_not_trigger(self, make_ctx, db_session):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        for v in ["1.0.0", "1.1.0"]:
            db_session.add(Firmware(version=v, variant="nrf52840", size=1000))
        db_session.commit()
        ctx = make_ctx(event="started", timestamp=ts)
        assert Dedicated().check(ctx) is False

    def test_stopped_event_ignored(self, make_ctx, db_session):
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        for v in ["1.0.0", "1.1.0", "2.0.0"]:
            db_session.add(Firmware(version=v, variant="nrf52840", size=1000))
        db_session.commit()
        ctx = make_ctx(event="stopped", timestamp=ts)
        assert Dedicated().check(ctx) is False


class TestVeteranDevice:
    def test_365_days_since_first_puff_triggers(self, make_ctx, add_events):
        first = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        now = datetime(2025, 6, 16, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "started", first),
            ("test_device", "coil_a", "started", now),
        ])
        ctx = make_ctx(event="started", timestamp=now)
        assert VeteranDevice().check(ctx) is True

    def test_less_than_365_days_does_not_trigger(self, make_ctx, add_events):
        first = datetime(2025, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "started", first),
            ("test_device", "coil_a", "started", now),
        ])
        ctx = make_ctx(event="started", timestamp=now)
        assert VeteranDevice().check(ctx) is False

    def test_no_previous_puff(self, make_ctx):
        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=now)
        assert VeteranDevice().check(ctx) is False
