from datetime import datetime, timezone

from sqlalchemy import create_engine, event, types
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from pinterest_automation.config.settings import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UTCDateTime(types.TypeDecorator):
    impl = types.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


def make_session_factory(db_url: str) -> sessionmaker:
    from pinterest_automation.database import models  # noqa: F401 register tables
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


_factory = None


def get_session_factory() -> sessionmaker:
    global _factory
    if _factory is None:
        _factory = make_session_factory(settings.db_url)
    return _factory


def init_db() -> None:
    get_session_factory()
