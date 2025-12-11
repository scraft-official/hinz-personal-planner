import os
from pathlib import Path
from typing import Iterator

from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine, select

DB_PATH = Path("data") / "planner.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def init_db() -> None:
    from .models import BlockType, ScheduleEntry, RecurringTask, RecurringException, Plan  # noqa: F401

    SQLModel.metadata.create_all(engine)
    apply_schema_patches()


def seed_defaults() -> None:
    """Create a minimal default palette if none exists and ensure quick task template."""
    from .models import BlockType, Plan

    with Session(engine) as session:
        existing = session.query(BlockType).count()
        if not existing:
            defaults = [
                {"name": "Friends", "color": "#0ea5e9", "icon": "users", "duration_minutes": 360},
                {"name": "Babe", "color": "#d946ef", "icon": "heart", "duration_minutes": 360},
                {"name": "Family", "color": "#22c55e", "icon": "home", "duration_minutes": 360},
                {"name": "Work", "color": "#38bdf8", "icon": "briefcase", "duration_minutes": 195},
                {"name": "Work Out", "color": "#f97316", "icon": "dumbbell", "duration_minutes": 195},
                {"name": "Studies", "color": "#ef4444", "icon": "book-open", "duration_minutes": 120},
                {"name": "Self Dev", "color": "#f59e0b", "icon": "lightbulb", "duration_minutes": 120},
                {"name": "Duties", "color": "#22c55e", "icon": "clipboard", "duration_minutes": 60},
                {"name": "Calls", "color": "#0ea5e9", "icon": "phone", "duration_minutes": 60},
                {"name": "Report", "color": "#9ca3af", "icon": "document", "duration_minutes": 60},
            ]
            for payload in defaults:
                session.add(BlockType(**payload))
            session.commit()
        ensure_quick_block(session)
        ensure_default_plan(session)


def get_session() -> Iterator[Session]:
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def apply_schema_patches() -> None:
    """Apply simple additive schema changes when running without migrations."""

    def column_exists(table: str, column: str) -> bool:
        with engine.connect() as conn:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(row[1] == column for row in rows)

    def ensure_column(table: str, column: str, ddl: str) -> None:
        if column_exists(table, column):
            return
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

    ensure_column("blocktype", "is_quick_template", "INTEGER NOT NULL DEFAULT 0")
    ensure_column("scheduleentry", "custom_title", "TEXT")
    ensure_column("scheduleentry", "is_quick", "INTEGER NOT NULL DEFAULT 0")
    ensure_column("scheduleentry", "plan_id", "INTEGER REFERENCES plan(id)")
    ensure_column("recurringtask", "plan_id", "INTEGER REFERENCES plan(id)")


def ensure_quick_block(session: Session):
    from .models import BlockType

    quick = session.exec(select(BlockType).where(BlockType.is_quick_template == True)).first()
    if quick:
        return quick
    quick_block = BlockType(
        name="Quick Task",
        color="#6b7280",
        icon="clipboard",
        duration_minutes=60,
        is_quick_template=True,
    )
    session.add(quick_block)
    session.commit()
    session.refresh(quick_block)
    return quick_block


def ensure_default_plan(session: Session):
    """Ensure at least one default plan exists."""
    from .models import Plan
    
    existing = session.exec(select(Plan)).first()
    if existing:
        return existing
    default_plan = Plan(
        name="My Plan",
        color="#0ea5e9",
    )
    session.add(default_plan)
    session.commit()
    session.refresh(default_plan)
    return default_plan
