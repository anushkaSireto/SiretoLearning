from collections.abc import Generator
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.config import get_settings

class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency: provide a database session to path operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def run_migrations() -> None:
    """Apply Alembic migrations before serving API requests."""
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")
