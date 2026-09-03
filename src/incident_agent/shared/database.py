"""SQLAlchemy engine and session construction."""

from collections.abc import Callable, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .health import ProbeResult


def create_engine_and_session(
    database_url: str,
) -> tuple[Engine, sessionmaker[Session]]:
    """Create an engine and typed session factory for the configured URL."""

    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    engine = create_engine(database_url, connect_args=connect_args, future=True)
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
