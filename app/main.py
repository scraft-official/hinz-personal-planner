from datetime import datetime, date, timedelta
from typing import Annotated
import csv
import io
import json

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Query, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from .db import get_session, init_db, seed_defaults, ensure_quick_block
from .models import BlockType, ScheduleEntry, RecurringTask, RecurringException

app = FastAPI(title="Planner")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_START_MINUTE = 7 * 60  # 07:00
DAY_END_MINUTE = 22 * 60 + 30  # 22:30
SLOT_MINUTES = 15
SLOT_HEIGHT_PX = 12
PRODUCTION_END = 15 * 60  # 15:00
ACTIVITY_END = 20 * 60    # 20:00

DURATION_OPTIONS = [30, 45, 60, 90, 120, 180, 270, 360]
ICON_CHOICES = [
    {"name": "calendar", "label": "Calendar"},
    {"name": "users", "label": "People"},
    {"name": "heart", "label": "Heart"},
    {"name": "home", "label": "Home"},
    {"name": "briefcase", "label": "Briefcase"},
    {"name": "dumbbell", "label": "Workout"},
    {"name": "book-open", "label": "Books"},
    {"name": "lightbulb", "label": "Ideas"},
    {"name": "clipboard", "label": "Checklist"},
    {"name": "phone", "label": "Calls"},
    {"name": "document", "label": "Docs"},
    {"name": "star", "label": "Priority"},
    {"name": "clock", "label": "Time"},
    {"name": "coffee", "label": "Coffee"},
    {"name": "music", "label": "Music"},
    {"name": "plane", "label": "Travel"},
    {"name": "shopping-bag", "label": "Shopping"},
    {"name": "camera", "label": "Camera"},
    {"name": "target", "label": "Goals"},
    {"name": "medal", "label": "Medal"},
    {"name": "shield", "label": "Shield"},
    {"name": "code", "label": "Code"},
]


def get_week_start(d: date) -> date:
    """Return the Monday of the week containing date d."""
    return d - timedelta(days=d.weekday())


def get_week_dates(week_start: date) -> list[dict]:
    """Return list of {day_name, date, is_today} for the week."""
    today = date.today()
    return [
        {
            "name": DAY_ORDER[i],
            "date": week_start + timedelta(days=i),
            "is_today": (week_start + timedelta(days=i)) == today,
        }
        for i in range(7)
    ]


def get_quick_block_type(session: Session) -> BlockType:
    quick = session.exec(select(BlockType).where(BlockType.is_quick_template == True)).first()
    if quick:
        return quick
    return ensure_quick_block(session)


def get_recurring_instances_for_week(session: Session, week_start: date) -> list[dict]:
    """Generate virtual entries for recurring tasks that fall within the given week."""
    week_end = week_start + timedelta(days=6)
    
    # Get all active recurring tasks
    recurring_tasks = session.exec(
        select(RecurringTask).where(
            RecurringTask.start_date <= week_end,
            (RecurringTask.end_date == None) | (RecurringTask.end_date >= week_start)
        )
    ).all()
    
    instances = []
    
    for task in recurring_tasks:
        # Get exceptions for this task in this week
        exceptions = session.exec(
            select(RecurringException).where(
                RecurringException.recurring_task_id == task.id,
                RecurringException.exception_date >= week_start,
                RecurringException.exception_date <= week_end,
            )
        ).all()
        exception_map = {ex.exception_date: ex for ex in exceptions}
        
        # Generate instances for each day in the week
        for day_offset in range(7):
            current_date = week_start + timedelta(days=day_offset)
            
            # Skip if before task start date
            if current_date < task.start_date:
                continue
            # Skip if after task end date
            if task.end_date and current_date > task.end_date:
                continue
            
            # Check if this date matches the recurrence pattern
            matches = False
            if task.pattern == "daily":
                days_since_start = (current_date - task.start_date).days
                matches = (days_since_start % task.interval) == 0
            elif task.pattern == "weekly":
                if task.day_of_week is not None and current_date.weekday() == task.day_of_week:
                    weeks_since_start = (current_date - task.start_date).days // 7
                    matches = (weeks_since_start % task.interval) == 0
            elif task.pattern == "monthly":
                if task.day_of_month is not None and current_date.day == task.day_of_month:
                    months_since_start = (current_date.year - task.start_date.year) * 12 + (current_date.month - task.start_date.month)
                    matches = (months_since_start % task.interval) == 0
            
            if not matches:
                continue
            
            # Check for exceptions
            exception = exception_map.get(current_date)
            if exception and exception.exception_type == "deleted":
                continue  # This instance was deleted
            
            # Get the day name
            day_name = DAY_ORDER[current_date.weekday()]
            start_minute = task.start_minute
            duration = task.duration_minutes
            
            # Apply modifications if this instance was modified
            if exception and exception.exception_type == "modified":
                if exception.new_day:
                    day_name = exception.new_day
                if exception.new_start_minute is not None:
                    start_minute = exception.new_start_minute
                if exception.new_duration_minutes is not None:
                    duration = exception.new_duration_minutes
            
            instances.append({
                "recurring_task_id": task.id,
                "instance_date": current_date,
                "title": task.title,
                "note": task.note,
                "day": day_name,
                "start_minute": start_minute,
                "duration_minutes": duration,
                "block_type": task.block_type,
                "is_recurring": True,
            })
    
    return instances


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_defaults()


def _schedule_data(session: Session, week_start: date):
    blocks = session.exec(
        select(BlockType)
        .where(BlockType.is_quick_template == False)
        .order_by(BlockType.name)
    ).all()
    entries = session.exec(
        select(ScheduleEntry).where(ScheduleEntry.week_start == week_start)
    ).all()
    entries_by_day: dict[str, list] = {d: [] for d in DAY_ORDER}
    for entry in entries:
        entries_by_day.setdefault(entry.day, []).append(entry)
    
    # Add recurring task instances
    recurring_instances = get_recurring_instances_for_week(session, week_start)
    for instance in recurring_instances:
        entries_by_day.setdefault(instance["day"], []).append(instance)
    
    # Sort all entries by start_minute
    for day_entries in entries_by_day.values():
        day_entries.sort(key=lambda e: e.start_minute if hasattr(e, 'start_minute') else e["start_minute"])
    
    week_dates = get_week_dates(week_start)
    
    # Check if this is current week and compute current time line position
    today = date.today()
    is_current_week = get_week_start(today) == week_start
    current_time_top = -1
    if is_current_week:
        now = datetime.now()
        current_minute = now.hour * 60 + now.minute
        if DAY_START_MINUTE <= current_minute <= DAY_END_MINUTE:
            current_time_top = ((current_minute - DAY_START_MINUTE) / SLOT_MINUTES) * SLOT_HEIGHT_PX
    
    return {
        "blocks": blocks,
        "entries_by_day": entries_by_day,
        "day_order": DAY_ORDER,
        "day_start": DAY_START_MINUTE,
        "day_end": DAY_END_MINUTE,
        "slot_minutes": SLOT_MINUTES,
        "slot_height": SLOT_HEIGHT_PX,
        "periods": [
            {"name": "Production", "start": DAY_START_MINUTE, "end": PRODUCTION_END, "class": "prod"},
            {"name": "Activity", "start": PRODUCTION_END, "end": ACTIVITY_END, "class": "act"},
            {"name": "Night", "start": ACTIVITY_END, "end": DAY_END_MINUTE, "class": "night"},
        ],
        "week_start": week_start,
        "week_dates": week_dates,
        "prev_week": week_start - timedelta(days=7),
        "next_week": week_start + timedelta(days=7),
        "duration_options": DURATION_OPTIONS,
        "icon_choices": ICON_CHOICES,
        "is_current_week": is_current_week,
        "current_time_top": current_time_top,
    }


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    week: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    if week:
        try:
            week_start = date.fromisoformat(week)
            week_start = get_week_start(week_start)
        except ValueError:
            week_start = get_week_start(date.today())
    else:
        week_start = get_week_start(date.today())
    
    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    return templates.TemplateResponse("index.html", ctx)


@app.get("/schedule", response_class=HTMLResponse)
def get_schedule(
    request: Request,
    week: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    if week:
        try:
            week_start = date.fromisoformat(week)
            week_start = get_week_start(week_start)
        except ValueError:
            week_start = get_week_start(date.today())
    else:
        week_start = get_week_start(date.today())
    
    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    return templates.TemplateResponse("partials/schedule.html", ctx)


@app.post("/blocks", response_class=HTMLResponse)
def create_block(
    request: Request,
    name: Annotated[str, Form(...)],
    color: Annotated[str, Form(...)],
    icon: Annotated[str, Form(...)],
    session: Session = Depends(get_session),
):
    block = BlockType(
        name=name.strip() or "Untitled",
        color=color,
        icon=icon,
        duration_minutes=60,  # Default, will be overridden by UI selector
    )
    session.add(block)
    session.commit()
    session.refresh(block)
    
    week_start = get_week_start(date.today())
    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    return templates.TemplateResponse("partials/palette.html", ctx)


@app.delete("/blocks/{block_id}", response_class=HTMLResponse)
def delete_block(
    request: Request,
    block_id: int,
    session: Session = Depends(get_session),
):
    block = session.get(BlockType, block_id)
    if block:
        # Don't allow deleting the quick task template
        if block.is_quick_template:
            raise HTTPException(status_code=400, detail="Cannot delete quick task template")
        # Delete all entries using this block first
        entries = session.exec(
            select(ScheduleEntry).where(ScheduleEntry.block_type_id == block_id)
        ).all()
        for entry in entries:
            session.delete(entry)
        session.delete(block)
        session.commit()
    
    week_start = get_week_start(date.today())
    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    return templates.TemplateResponse("partials/palette.html", ctx)


@app.post("/entries", response_class=HTMLResponse)
def create_entry(
    request: Request,
    day: Annotated[str, Form(...)],
    start_time: Annotated[str, Form(...)],
    duration_minutes: Annotated[int, Form(...)],
    block_type_id: Annotated[int, Form(...)],
    week: Annotated[str, Form(...)],
    note: Annotated[str | None, Form(...)] = "",
    session: Session = Depends(get_session),
):
    if day not in DAY_ORDER:
        raise HTTPException(status_code=400, detail="Invalid day")
    try:
        t = datetime.strptime(start_time, "%H:%M").time()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid time") from exc

    try:
        week_start = date.fromisoformat(week)
        week_start = get_week_start(week_start)
    except ValueError:
        week_start = get_week_start(date.today())

    start_minute = t.hour * 60 + t.minute
    if start_minute < DAY_START_MINUTE or start_minute > DAY_END_MINUTE:
        raise HTTPException(status_code=400, detail="Time outside day bounds")

    block = session.get(BlockType, block_type_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    entry = ScheduleEntry(
        week_start=week_start,
        day=day,
        start_minute=start_minute,
        duration_minutes=duration_minutes,
        block_type_id=block_type_id,
        note=note.strip() or None,
    )
    session.add(entry)
    session.commit()

    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/schedule.html", ctx)
    return templates.TemplateResponse("index.html", ctx)


@app.post("/quick-task", response_class=HTMLResponse)
def create_quick_task(
    request: Request,
    title: Annotated[str, Form(...)],
    day: Annotated[str, Form(...)],
    start_time: Annotated[str, Form(...)],
    week: Annotated[str | None, Form(...)] = None,
    session: Session = Depends(get_session),
):
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Title required")
    if day not in DAY_ORDER:
        raise HTTPException(status_code=400, detail="Invalid day")
    try:
        t = datetime.strptime(start_time, "%H:%M").time()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid time") from exc

    try:
        week_start = date.fromisoformat(week) if week else get_week_start(date.today())
        week_start = get_week_start(week_start)
    except ValueError:
        week_start = get_week_start(date.today())

    start_minute = t.hour * 60 + t.minute
    if start_minute < DAY_START_MINUTE or start_minute > DAY_END_MINUTE:
        raise HTTPException(status_code=400, detail="Time outside day bounds")

    duration = 60
    end_minute = start_minute + duration

    # Check for collision with existing entries
    existing = session.exec(
        select(ScheduleEntry).where(
            ScheduleEntry.week_start == week_start,
            ScheduleEntry.day == day,
        )
    ).all()
    for e in existing:
        e_end = e.start_minute + e.duration_minutes
        # Check overlap: not (end <= e.start or start >= e.end)
        if not (end_minute <= e.start_minute or start_minute >= e_end):
            raise HTTPException(status_code=409, detail="Time slot already occupied")

    quick_block = get_quick_block_type(session)

    entry = ScheduleEntry(
        week_start=week_start,
        day=day,
        start_minute=start_minute,
        duration_minutes=duration,
        block_type_id=quick_block.id,
        custom_title=clean_title,
        is_quick=True,
    )
    session.add(entry)
    session.commit()

    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/schedule.html", ctx)
    return templates.TemplateResponse("index.html", ctx)


@app.get("/entries/{entry_id}/note", response_class=HTMLResponse)
def get_entry_note(
    request: Request,
    entry_id: int,
    session: Session = Depends(get_session),
):
    entry = session.get(ScheduleEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    ctx = {"request": request, "entry": entry}
    return templates.TemplateResponse("partials/note_form.html", ctx)


@app.post("/entries/{entry_id}/note", response_class=HTMLResponse)
def save_entry_note(
    request: Request,
    entry_id: int,
    note: str | None = Form(default=""),
    session: Session = Depends(get_session),
):
    entry = session.get(ScheduleEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    clean_note = (note or "").strip() or None
    entry.note = clean_note
    session.add(entry)
    session.commit()

    week_start = entry.week_start
    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    response = templates.TemplateResponse("partials/schedule.html", ctx)
    response.headers["HX-Trigger"] = "entry-note-saved"
    return response


@app.post("/entries/{entry_id}/move", response_class=HTMLResponse)
def move_entry(
    request: Request,
    entry_id: int,
    day: Annotated[str, Form(...)],
    start_minute: Annotated[int, Form(...)],
    duration_minutes: Annotated[int, Form(...)],
    session: Session = Depends(get_session),
):
    if day not in DAY_ORDER:
        raise HTTPException(status_code=400, detail="Invalid day")
    entry = session.get(ScheduleEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # clamp inside day window
    start_clamped = max(DAY_START_MINUTE, min(start_minute, DAY_END_MINUTE))
    duration_clamped = max(SLOT_MINUTES, min(duration_minutes, (DAY_END_MINUTE - DAY_START_MINUTE)))
    if start_clamped + duration_clamped > DAY_END_MINUTE:
        start_clamped = DAY_END_MINUTE - duration_clamped

    entry.day = day
    entry.start_minute = start_clamped
    entry.duration_minutes = duration_clamped
    session.add(entry)
    session.commit()

    ctx = _schedule_data(session, entry.week_start)
    ctx["request"] = request
    return templates.TemplateResponse("partials/schedule.html", ctx)


@app.delete("/entries/{entry_id}", response_class=HTMLResponse)
def delete_entry(
    request: Request,
    entry_id: int,
    session: Session = Depends(get_session),
):
    entry = session.get(ScheduleEntry, entry_id)
    week_start = entry.week_start if entry else get_week_start(date.today())
    if entry:
        session.delete(entry)
        session.commit()
    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/schedule.html", ctx)
    return templates.TemplateResponse("index.html", ctx)


# ============== RECURRING TASKS ==============

@app.post("/recurring-tasks", response_class=HTMLResponse)
def create_recurring_task(
    request: Request,
    title: Annotated[str, Form(...)],
    block_type_id: Annotated[int, Form(...)],
    pattern: Annotated[str, Form(...)],
    interval: Annotated[int, Form(...)],
    start_time: Annotated[str, Form(...)],
    duration_minutes: Annotated[int, Form(...)],
    day_of_week: Annotated[int | None, Form(...)] = None,
    day_of_month: Annotated[int | None, Form(...)] = None,
    start_date: Annotated[str | None, Form(...)] = None,
    end_date: Annotated[str | None, Form(...)] = None,
    note: Annotated[str | None, Form(...)] = None,
    week: Annotated[str | None, Form(...)] = None,
    session: Session = Depends(get_session),
):
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Title required")
    if pattern not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="Invalid pattern")
    if interval < 1:
        raise HTTPException(status_code=400, detail="Interval must be >= 1")
    
    try:
        t = datetime.strptime(start_time, "%H:%M").time()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid time") from exc
    
    start_minute = t.hour * 60 + t.minute
    if start_minute < DAY_START_MINUTE or start_minute > DAY_END_MINUTE:
        raise HTTPException(status_code=400, detail="Time outside day bounds")
    
    block = session.get(BlockType, block_type_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block type not found")
    
    try:
        task_start_date = date.fromisoformat(start_date) if start_date else date.today()
    except ValueError:
        task_start_date = date.today()
    
    task_end_date = None
    if end_date:
        try:
            task_end_date = date.fromisoformat(end_date)
        except ValueError:
            pass
    
    task = RecurringTask(
        title=clean_title,
        note=(note or "").strip() or None,
        block_type_id=block_type_id,
        pattern=pattern,
        interval=interval,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        start_minute=start_minute,
        duration_minutes=duration_minutes,
        start_date=task_start_date,
        end_date=task_end_date,
    )
    session.add(task)
    session.commit()
    
    try:
        week_start = date.fromisoformat(week) if week else get_week_start(date.today())
        week_start = get_week_start(week_start)
    except ValueError:
        week_start = get_week_start(date.today())
    
    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/schedule.html", ctx)
    return templates.TemplateResponse("index.html", ctx)


@app.delete("/recurring-tasks/{task_id}", response_class=HTMLResponse)
def delete_recurring_task(
    request: Request,
    task_id: int,
    week: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    """Delete entire recurring task and all its exceptions."""
    task = session.get(RecurringTask, task_id)
    if task:
        # Delete all exceptions first
        exceptions = session.exec(
            select(RecurringException).where(RecurringException.recurring_task_id == task_id)
        ).all()
        for ex in exceptions:
            session.delete(ex)
        session.delete(task)
        session.commit()
    
    try:
        week_start = date.fromisoformat(week) if week else get_week_start(date.today())
        week_start = get_week_start(week_start)
    except ValueError:
        week_start = get_week_start(date.today())
    
    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/schedule.html", ctx)
    return templates.TemplateResponse("index.html", ctx)


@app.post("/recurring-tasks/{task_id}/exception", response_class=HTMLResponse)
def create_recurring_exception(
    request: Request,
    task_id: int,
    exception_date: Annotated[str, Form(...)],
    exception_type: Annotated[str, Form(...)],
    new_day: Annotated[str | None, Form(...)] = None,
    new_start_minute: Annotated[int | None, Form(...)] = None,
    new_duration_minutes: Annotated[int | None, Form(...)] = None,
    week: Annotated[str | None, Form(...)] = None,
    session: Session = Depends(get_session),
):
    """Create an exception for a specific instance of a recurring task."""
    task = session.get(RecurringTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Recurring task not found")
    
    if exception_type not in ("deleted", "modified"):
        raise HTTPException(status_code=400, detail="Invalid exception type")
    
    try:
        exc_date = date.fromisoformat(exception_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date") from exc
    
    # Check if exception already exists
    existing = session.exec(
        select(RecurringException).where(
            RecurringException.recurring_task_id == task_id,
            RecurringException.exception_date == exc_date,
        )
    ).first()
    
    if existing:
        # Update existing exception
        existing.exception_type = exception_type
        existing.new_day = new_day
        existing.new_start_minute = new_start_minute
        existing.new_duration_minutes = new_duration_minutes
        session.add(existing)
    else:
        # Create new exception
        exception = RecurringException(
            recurring_task_id=task_id,
            exception_date=exc_date,
            exception_type=exception_type,
            new_day=new_day,
            new_start_minute=new_start_minute,
            new_duration_minutes=new_duration_minutes,
        )
        session.add(exception)
    
    session.commit()
    
    try:
        week_start = date.fromisoformat(week) if week else get_week_start(date.today())
        week_start = get_week_start(week_start)
    except ValueError:
        week_start = get_week_start(date.today())
    
    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/schedule.html", ctx)
    return templates.TemplateResponse("index.html", ctx)


@app.patch("/recurring-tasks/{task_id}/move-all", response_class=HTMLResponse)
def move_all_recurring_instances(
    request: Request,
    task_id: int,
    day_of_week: Annotated[int, Form(...)],
    start_minute: Annotated[int, Form(...)],
    duration_minutes: Annotated[int, Form(...)],
    week: Annotated[str | None, Form(...)] = None,
    clear_exception_date: Annotated[str | None, Form(...)] = None,
    session: Session = Depends(get_session),
):
    """Move all instances of a recurring task to a new day/time."""
    task = session.get(RecurringTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Recurring task not found")
    
    # Clamp values
    start_clamped = max(DAY_START_MINUTE, min(start_minute, DAY_END_MINUTE))
    duration_clamped = max(SLOT_MINUTES, min(duration_minutes, (DAY_END_MINUTE - DAY_START_MINUTE)))
    if start_clamped + duration_clamped > DAY_END_MINUTE:
        start_clamped = DAY_END_MINUTE - duration_clamped
    
    task.day_of_week = day_of_week
    task.start_minute = start_clamped
    task.duration_minutes = duration_clamped
    session.add(task)
    
    # Clear any modified exception for the specific instance that triggered this change
    # This ensures the dragged instance also reflects the new base values
    if clear_exception_date:
        try:
            exc_date = date.fromisoformat(clear_exception_date)
            existing_exc = session.exec(
                select(RecurringException).where(
                    RecurringException.recurring_task_id == task_id,
                    RecurringException.exception_date == exc_date,
                    RecurringException.exception_type == "modified"
                )
            ).first()
            if existing_exc:
                session.delete(existing_exc)
        except ValueError:
            pass
    
    session.commit()
    
    try:
        week_start = date.fromisoformat(week) if week else get_week_start(date.today())
        week_start = get_week_start(week_start)
    except ValueError:
        week_start = get_week_start(date.today())
    
    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/schedule.html", ctx)
    return templates.TemplateResponse("index.html", ctx)


@app.get("/recurring-tasks/{task_id}/note", response_class=HTMLResponse)
def get_recurring_task_note(
    request: Request,
    task_id: int,
    instance_date: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    """Get note form for recurring task."""
    task = session.get(RecurringTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Recurring task not found")
    ctx = {"request": request, "task": task, "instance_date": instance_date, "is_recurring": True}
    return templates.TemplateResponse("partials/recurring_note_form.html", ctx)


@app.post("/recurring-tasks/{task_id}/note", response_class=HTMLResponse)
def save_recurring_task_note(
    request: Request,
    task_id: int,
    note: str | None = Form(default=""),
    week: str | None = Form(default=None),
    session: Session = Depends(get_session),
):
    """Save note for recurring task (affects all instances)."""
    task = session.get(RecurringTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Recurring task not found")
    
    task.note = (note or "").strip() or None
    session.add(task)
    session.commit()
    
    try:
        week_start = date.fromisoformat(week) if week else get_week_start(date.today())
        week_start = get_week_start(week_start)
    except ValueError:
        week_start = get_week_start(date.today())
    
    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    response = templates.TemplateResponse("partials/schedule.html", ctx)
    response.headers["HX-Trigger"] = "entry-note-saved"
    return response


# ─────────────────────────── EXPORT / IMPORT ─────────────────────────────────

@app.get("/export/csv")
def export_csv(session: Session = Depends(get_session)):
    """Export all data to a ZIP containing multiple CSV files."""
    import zipfile
    
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        # Block Types
        block_csv = io.StringIO()
        writer = csv.writer(block_csv)
        writer.writerow(["id", "name", "color", "icon", "duration_minutes", "is_quick_template", "created_at"])
        for bt in session.exec(select(BlockType)).all():
            writer.writerow([bt.id, bt.name, bt.color, bt.icon, bt.duration_minutes, bt.is_quick_template, bt.created_at.isoformat()])
        zf.writestr("block_types.csv", block_csv.getvalue())
        
        # Schedule Entries
        entry_csv = io.StringIO()
        writer = csv.writer(entry_csv)
        writer.writerow(["id", "week_start", "day", "start_minute", "duration_minutes", "note", "block_type_id", "custom_title", "is_quick", "created_at"])
        for e in session.exec(select(ScheduleEntry)).all():
            writer.writerow([e.id, e.week_start.isoformat(), e.day, e.start_minute, e.duration_minutes, e.note or "", e.block_type_id, e.custom_title or "", e.is_quick, e.created_at.isoformat()])
        zf.writestr("schedule_entries.csv", entry_csv.getvalue())
        
        # Recurring Tasks
        rec_csv = io.StringIO()
        writer = csv.writer(rec_csv)
        writer.writerow(["id", "title", "note", "block_type_id", "pattern", "interval", "day_of_week", "day_of_month", "start_minute", "duration_minutes", "start_date", "end_date", "created_at"])
        for rt in session.exec(select(RecurringTask)).all():
            writer.writerow([rt.id, rt.title, rt.note or "", rt.block_type_id, rt.pattern, rt.interval, rt.day_of_week, rt.day_of_month, rt.start_minute, rt.duration_minutes, rt.start_date.isoformat(), rt.end_date.isoformat() if rt.end_date else "", rt.created_at.isoformat()])
        zf.writestr("recurring_tasks.csv", rec_csv.getvalue())
        
        # Recurring Exceptions
        exc_csv = io.StringIO()
        writer = csv.writer(exc_csv)
        writer.writerow(["id", "recurring_task_id", "exception_date", "exception_type", "new_day", "new_start_minute", "new_duration_minutes", "created_at"])
        for ex in session.exec(select(RecurringException)).all():
            writer.writerow([ex.id, ex.recurring_task_id, ex.exception_date.isoformat(), ex.exception_type, ex.new_day or "", ex.new_start_minute or "", ex.new_duration_minutes or "", ex.created_at.isoformat()])
        zf.writestr("recurring_exceptions.csv", exc_csv.getvalue())
    
    output.seek(0)
    filename = f"planner_export_{date.today().isoformat()}.zip"
    return StreamingResponse(
        output,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/import/csv")
async def import_csv(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """Import data from a ZIP file containing CSV files. Replaces all existing data."""
    import zipfile
    
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a .zip file")
    
    contents = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(contents))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")
    
    # Delete all existing data (order matters due to foreign keys)
    session.exec(select(RecurringException)).all()
    for ex in session.exec(select(RecurringException)).all():
        session.delete(ex)
    for rt in session.exec(select(RecurringTask)).all():
        session.delete(rt)
    for e in session.exec(select(ScheduleEntry)).all():
        session.delete(e)
    for bt in session.exec(select(BlockType)).all():
        session.delete(bt)
    session.commit()
    
    # Import Block Types first
    if "block_types.csv" in zf.namelist():
        reader = csv.DictReader(io.StringIO(zf.read("block_types.csv").decode("utf-8")))
        for row in reader:
            bt = BlockType(
                id=int(row["id"]),
                name=row["name"],
                color=row["color"],
                icon=row["icon"],
                duration_minutes=int(row["duration_minutes"]),
                is_quick_template=row["is_quick_template"].lower() == "true",
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            session.add(bt)
        session.commit()
    
    # Import Schedule Entries
    if "schedule_entries.csv" in zf.namelist():
        reader = csv.DictReader(io.StringIO(zf.read("schedule_entries.csv").decode("utf-8")))
        for row in reader:
            entry = ScheduleEntry(
                id=int(row["id"]),
                week_start=date.fromisoformat(row["week_start"]),
                day=row["day"],
                start_minute=int(row["start_minute"]),
                duration_minutes=int(row["duration_minutes"]),
                note=row["note"] or None,
                block_type_id=int(row["block_type_id"]),
                custom_title=row["custom_title"] or None,
                is_quick=row["is_quick"].lower() == "true",
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            session.add(entry)
        session.commit()
    
    # Import Recurring Tasks
    if "recurring_tasks.csv" in zf.namelist():
        reader = csv.DictReader(io.StringIO(zf.read("recurring_tasks.csv").decode("utf-8")))
        for row in reader:
            rt = RecurringTask(
                id=int(row["id"]),
                title=row["title"],
                note=row["note"] or None,
                block_type_id=int(row["block_type_id"]),
                pattern=row["pattern"],
                interval=int(row["interval"]),
                day_of_week=int(row["day_of_week"]) if row["day_of_week"] else None,
                day_of_month=int(row["day_of_month"]) if row["day_of_month"] else None,
                start_minute=int(row["start_minute"]),
                duration_minutes=int(row["duration_minutes"]),
                start_date=date.fromisoformat(row["start_date"]),
                end_date=date.fromisoformat(row["end_date"]) if row["end_date"] else None,
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            session.add(rt)
        session.commit()
    
    # Import Recurring Exceptions
    if "recurring_exceptions.csv" in zf.namelist():
        reader = csv.DictReader(io.StringIO(zf.read("recurring_exceptions.csv").decode("utf-8")))
        for row in reader:
            ex = RecurringException(
                id=int(row["id"]),
                recurring_task_id=int(row["recurring_task_id"]),
                exception_date=date.fromisoformat(row["exception_date"]),
                exception_type=row["exception_type"],
                new_day=row["new_day"] or None,
                new_start_minute=int(row["new_start_minute"]) if row["new_start_minute"] else None,
                new_duration_minutes=int(row["new_duration_minutes"]) if row["new_duration_minutes"] else None,
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            session.add(ex)
        session.commit()
    
    # Ensure quick block exists
    ensure_quick_block(session)
    
    # Redirect to home
    week_start = get_week_start(date.today())
    ctx = _schedule_data(session, week_start)
    ctx["request"] = request
    ctx.update({
        "duration_options": DURATION_OPTIONS,
        "icon_choices": ICON_CHOICES,
    })
    # Return full page refresh notice
    return HTMLResponse(
        content='<html><head><meta http-equiv="refresh" content="0;url=/"></head><body>Import successful! Redirecting...</body></html>',
        status_code=200
    )

