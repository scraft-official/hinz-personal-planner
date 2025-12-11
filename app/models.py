from datetime import datetime, date
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship


class BlockType(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    color: str = Field(default="#0ea5e9", max_length=16)
    icon: str = Field(default="calendar", max_length=32)
    duration_minutes: int = Field(default=60, ge=15, le=24 * 60)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_quick_template: bool = Field(default=False)

    entries: list["ScheduleEntry"] = Relationship(back_populates="block_type")


class ScheduleEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    week_start: date = Field(index=True)  # Monday of the week
    day: str = Field(index=True)
    start_minute: int = Field(index=True, ge=0, le=24 * 60)
    duration_minutes: int = Field(default=60, ge=15, le=24 * 60)
    note: Optional[str] = Field(default=None, max_length=255)
    block_type_id: int = Field(foreign_key="blocktype.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    custom_title: Optional[str] = Field(default=None, max_length=80)
    is_quick: bool = Field(default=False)

    block_type: Optional[BlockType] = Relationship(back_populates="entries")
