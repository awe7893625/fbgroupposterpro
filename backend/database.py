from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

DB_PATH = Path.home() / ".fbgroupposter" / "data.sqlite"

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Apply incremental schema migrations for SQLite (no Alembic needed for dev)."""
    with engine.connect() as conn:
        # v1: add group_ids_json to posts
        try:
            conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE posts ADD COLUMN group_ids_json TEXT"
                )
            )
            conn.commit()
        except Exception:
            pass  # Column already exists

        # v2: platform column in groups
        try:
            conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE groups ADD COLUMN platform TEXT NOT NULL DEFAULT 'fb'"
                )
            )
            conn.commit()
        except Exception:
            pass  # Column already exists

        # v2b: platform_entity_id column in groups (Ray M4)
        try:
            conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE groups ADD COLUMN platform_entity_id TEXT"
                )
            )
            conn.commit()
        except Exception:
            pass  # Column already exists

        # v3: post_url column in post_records
        try:
            conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE post_records ADD COLUMN post_url TEXT"
                )
            )
            conn.commit()
        except Exception:
            pass  # Column already exists

        # v4: app_state table for license/vault metadata (created via Base.metadata above)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
