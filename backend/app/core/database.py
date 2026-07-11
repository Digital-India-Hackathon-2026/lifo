"""SQLite storage for Track 3 items (Campaign Graph — item 31, and upcoming
32/68/82/84).

Storage: backend/data/kavach.db (gitignored, same pattern as vault.json).
Table creation happens at app startup via init_db() in each owning router's
module (called from main.py's lifespan) — never at import time.
"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "kavach.db"

engine = create_engine(f"sqlite:///{_DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    """FastAPI dependency: yields a request-scoped DB session, always closed after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
