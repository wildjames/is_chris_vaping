import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure server dir is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Mock extensions module before any achievements imports
_mock_extensions = MagicMock()
_mock_extensions.ACHIEVEMENT_CHANNEL = "test:achievements"
_mock_extensions.Session = MagicMock()
_mock_extensions.cache_get_all_devices = MagicMock(return_value={})
_mock_extensions.redis_client = MagicMock()
_mock_extensions.send_achievement_push = MagicMock()
sys.modules["extensions"] = _mock_extensions

from models import Base, VapeEvent, AchievementAward, Device, Firmware
from achievements.base import AchievementContext, _registry


@pytest.fixture
def db_session():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _strip_tz(dt):
    """Strip timezone info to match SQLite behavior."""
    if dt and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


@pytest.fixture
def make_ctx(db_session):
    """Factory to build AchievementContext with sensible defaults."""
    def _make(
        device_name="test_device",
        coil="coil_a",
        event="started",
        timestamp=None,
        all_devices=None,
    ):
        if timestamp is None:
            timestamp = datetime(2025, 6, 15, 12, 0, 0)
        else:
            timestamp = _strip_tz(timestamp)
        if all_devices is None:
            all_devices = {
                device_name: {"coil_a": event == "started", "coil_b": False, "last_event": event, "last_updated": timestamp.isoformat()}
            }
        return AchievementContext(
            device_name=device_name,
            coil=coil,
            event=event,
            timestamp=timestamp,
            db_session=db_session,
            all_devices=all_devices,
        )
    return _make


@pytest.fixture
def add_events(db_session):
    """Helper to bulk-add VapeEvents."""
    def _add(events):
        """events: list of (device_name, coil, event_type, timestamp)"""
        for device_name, coil, event_type, ts in events:
            db_session.add(VapeEvent(
                device_name=device_name,
                coil=coil,
                event=event_type,
                timestamp=_strip_tz(ts),
            ))
        db_session.commit()
    return _add


@pytest.fixture
def add_puffs(db_session):
    """Helper to add N start events for a device."""
    def _add(device_name="test_device", coil="coil_a", count=1, start_time=None, interval_seconds=60):
        if start_time is None:
            start_time = datetime(2025, 6, 15, 10, 0, 0)
        else:
            start_time = _strip_tz(start_time)
        for i in range(count):
            ts = start_time + timedelta(seconds=i * interval_seconds)
            db_session.add(VapeEvent(
                device_name=device_name,
                coil=coil,
                event="started",
                timestamp=ts,
            ))
        db_session.commit()
    return _add
