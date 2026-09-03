"""SQLAlchemy engine and session construction."""

from collections.abc import Callable, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .health import ProbeResult


def create_engine_and_session(
    database_url: str,
) -> tuple[Engine, sessionmaker[Session]]:
    """Create an engine and typed session factory for the configured URL."""

    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    poolclass = (
        StaticPool if database_url in {"sqlite://", "sqlite:///:memory:"} else None
    )
    engine_kwargs = {"connect_args": connect_args, "future": True}
    if poolclass is not None:
        engine_kwargs["poolclass"] = poolclass
    engine = create_engine(database_url, **engine_kwargs)
    return engine, sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def database_probe(engine: Engine) -> Callable[[], ProbeResult]:
    """Return a probe that checks a cheap database round trip."""

    def probe() -> ProbeResult:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return ProbeResult.ok()

    return probe


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a transaction-scoped session for service and repository code."""

    with factory() as session:
        yield session
