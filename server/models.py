from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    coil_a: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    coil_b: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_event: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VapeEvent(Base):
    __tablename__ = "vape_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    coil: Mapped[str] = mapped_column(String(10), nullable=False)
    event: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class Firmware(Base):
    __tablename__ = "firmware"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


def init_db(db_url: str):
    engine = create_engine(db_url, pool_pre_ping=True, pool_recycle=3600)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session
