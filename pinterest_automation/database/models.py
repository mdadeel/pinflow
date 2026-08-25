from datetime import datetime

from sqlalchemy import ForeignKey, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pinterest_automation.database.db import Base, UTCDateTime, utcnow


class Pin(Base):
    __tablename__ = "pins"
    __table_args__ = (UniqueConstraint("image_hash", name="uq_image_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    image_path: Mapped[str] = mapped_column(String(500))
    image_hash: Mapped[str] = mapped_column(String(64))

    title: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    alt_text: Mapped[str | None] = mapped_column(Text)
    primary_keyword: Mapped[str | None] = mapped_column(String(100))
    secondary_keywords: Mapped[str | None] = mapped_column(Text)   # JSON array string
    tags: Mapped[str | None] = mapped_column(Text)                 # JSON array string
    board_name: Mapped[str | None] = mapped_column(String(100))
    board_id: Mapped[str | None] = mapped_column(String(50))
    content_category: Mapped[str | None] = mapped_column(String(50))

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    ai_called_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    scheduled_time: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    published_time: Mapped[datetime | None] = mapped_column(UTCDateTime)
    pin_id_str: Mapped[str | None] = mapped_column(String(50))      # Pinterest pin id
    pin_url: Mapped[str | None] = mapped_column(String(500))

    file_size: Mapped[int | None] = mapped_column(Integer)   # bytes
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class AnalyticsRow(Base):
    __tablename__ = "analytics"
    __table_args__ = (UniqueConstraint("pin_id", name="uq_analytics_pin"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pin_id: Mapped[int] = mapped_column(ForeignKey("pins.id"))
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    outbound_clicks: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
