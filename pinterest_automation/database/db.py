from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from pinterest_automation.config.settings import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


def make_session_factory(db_url: str) -> sessionmaker:
    from pinterest_automation.database import models  # noqa: F401 register tables
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


_factory = None


def get_session_factory() -> sessionmaker:
    global _factory
    if _factory is None:
        _factory = make_session_factory(settings.db_url)
    return _factory


def init_db() -> None:
    from pinterest_automation.database import models  # noqa: F401 register tables
    get_session_factory()
