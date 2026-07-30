from datetime import datetime, timedelta, timezone

from achievements.streaks_consistency import (
    CleanStreak,
    DailyDriver,
    DetoxWeek,
    MonthlyPass,
    Relapse,
)

from models import AchievementAward


class TestDailyDriver:
    def test_7_consecutive_days_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base - timedelta(days=i, hours=i % 3))
            for i in range(7)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base)
        assert DailyDriver().check(ctx) is True

    def test_missing_day_in_streak(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(7):
            if i == 3:
                continue
            events.append(("test_device", "coil_a", "started", base - timedelta(days=i)))
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base)
        assert DailyDriver().check(ctx) is False

    def test_stopped_event_ignored(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base - timedelta(days=i))
            for i in range(7)
        ]
        add_events(events)
        ctx = make_ctx(event="stopped", timestamp=base)
        assert DailyDriver().check(ctx) is False


class TestMonthlyPass:
    def test_30_consecutive_days_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            ("test_device", "coil_a", "started", base - timedelta(days=i))
            for i in range(30)
        ]
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base)
        assert MonthlyPass().check(ctx) is True

    def test_missing_day_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(30):
            if i == 15:
                continue
            events.append(("test_device", "coil_a", "started", base - timedelta(days=i)))
        add_events(events)
        ctx = make_ctx(event="started", timestamp=base)
        assert MonthlyPass().check(ctx) is False


class TestCleanStreak:
    def test_no_puffs_for_24h_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        # Last puff was 25 hours ago
        add_events([
            ("test_device", "coil_a", "started", base - timedelta(hours=25)),
        ])
        ctx = make_ctx(event="started", timestamp=base)
        assert CleanStreak().check(ctx) is True

    def test_recent_puff_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "started", base - timedelta(hours=10)),
        ])
        ctx = make_ctx(event="started", timestamp=base)
        assert CleanStreak().check(ctx) is False

    def test_stopped_event_ignored(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="stopped", timestamp=base)
        assert CleanStreak().check(ctx) is False


class TestDetoxWeek:
    def test_no_puffs_for_7_days_triggers(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "started", base - timedelta(days=8)),
        ])
        ctx = make_ctx(event="started", timestamp=base)
        assert DetoxWeek().check(ctx) is True

    def test_puff_within_7_days_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        add_events([
            ("test_device", "coil_a", "started", base - timedelta(days=5)),
        ])
        ctx = make_ctx(event="started", timestamp=base)
        assert DetoxWeek().check(ctx) is False


class TestRelapse:
    def test_first_puff_after_clean_streak_triggers(self, make_ctx, add_events, db_session):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        # Add a clean_streak achievement award
        db_session.add(AchievementAward(
            achievement_id="clean_streak",
            device_name="test_device",
            awarded_at=base - timedelta(hours=1),
        ))
        db_session.commit()
        # No puffs in last 24h
        add_events([
            ("test_device", "coil_a", "started", base - timedelta(hours=25)),
        ])
        ctx = make_ctx(event="started", timestamp=base)
        assert Relapse().check(ctx) is True

    def test_no_clean_streak_does_not_trigger(self, make_ctx, add_events):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        ctx = make_ctx(event="started", timestamp=base)
        assert Relapse().check(ctx) is False

    def test_recent_puff_does_not_trigger(self, make_ctx, add_events, db_session):
        base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        db_session.add(AchievementAward(
            achievement_id="clean_streak",
            device_name="test_device",
            awarded_at=base - timedelta(hours=30),
        ))
        db_session.commit()
        add_events([
            ("test_device", "coil_a", "started", base - timedelta(hours=5)),
        ])
        ctx = make_ctx(event="started", timestamp=base)
        assert Relapse().check(ctx) is False
