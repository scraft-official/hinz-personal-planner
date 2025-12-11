from datetime import datetime, date
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class Plan(SQLModel, table=True):
    """A plan represents a separate schedule (e.g., Work, Family, Personal)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50)
    color: str = Field(default="#0ea5e9", max_length=16)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    entries: List["ScheduleEntry"] = Relationship(back_populates="plan")
    recurring_tasks: List["RecurringTask"] = Relationship(back_populates="plan")


class BlockType(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    color: str = Field(default="#0ea5e9", max_length=16)
    icon: str = Field(default="calendar", max_length=32)
    duration_minutes: int = Field(default=60, ge=15, le=24 * 60)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_quick_template: bool = Field(default=False)

    entries: List["ScheduleEntry"] = Relationship(back_populates="block_type")
    recurring_tasks: List["RecurringTask"] = Relationship(back_populates="block_type")


class ScheduleEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    week_start: date = Field(index=True)  # Monday of the week
    day: str = Field(index=True)
    start_minute: int = Field(index=True, ge=0, le=24 * 60)
    duration_minutes: int = Field(default=60, ge=15, le=24 * 60)
    note: Optional[str] = Field(default=None, max_length=255)
    block_type_id: int = Field(foreign_key="blocktype.id")
    plan_id: Optional[int] = Field(default=None, foreign_key="plan.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    custom_title: Optional[str] = Field(default=None, max_length=80)
    is_quick: bool = Field(default=False)

    block_type: Optional[BlockType] = Relationship(back_populates="entries")
    plan: Optional[Plan] = Relationship(back_populates="entries")


class RecurringTask(SQLModel, table=True):
    """A recurring task template that generates instances on matching days."""
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=80)
    note: Optional[str] = Field(default=None, max_length=255)
    block_type_id: int = Field(foreign_key="blocktype.id")
    plan_id: Optional[int] = Field(default=None, foreign_key="plan.id", index=True)
    
    # Recurrence pattern: "daily", "weekly", "monthly"
    pattern: str = Field(default="weekly", max_length=16)
    # Interval: every X days/weeks/months
    interval: int = Field(default=1, ge=1)
    # Day of week for weekly (0=Monday..6=Sunday), or day of month for monthly (1-31)
    day_of_week: Optional[int] = Field(default=None)
    day_of_month: Optional[int] = Field(default=None)
    
    start_minute: int = Field(ge=0, le=24 * 60)
    duration_minutes: int = Field(default=60, ge=15, le=24 * 60)
    
    # Start date for the recurrence (first occurrence)
    start_date: date = Field(index=True)
    # Optional end date
    end_date: Optional[date] = Field(default=None)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    block_type: Optional[BlockType] = Relationship(back_populates="recurring_tasks")
    plan: Optional[Plan] = Relationship(back_populates="recurring_tasks")
    exceptions: List["RecurringException"] = Relationship(back_populates="recurring_task")


class RecurringException(SQLModel, table=True):
    """Tracks exceptions (deletions or modifications) to recurring task instances."""
    id: Optional[int] = Field(default=None, primary_key=True)
    recurring_task_id: int = Field(foreign_key="recurringtask.id", index=True)
    
    # The specific date this exception applies to
    exception_date: date = Field(index=True)
    
    # Type: "deleted" = instance removed, "modified" = instance moved/changed
    exception_type: str = Field(default="deleted", max_length=16)
    
    # For modified instances, store the new values (null = use original)
    new_day: Optional[str] = Field(default=None, max_length=16)
    new_start_minute: Optional[int] = Field(default=None)
    new_duration_minutes: Optional[int] = Field(default=None)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    recurring_task: Optional[RecurringTask] = Relationship(back_populates="exceptions")