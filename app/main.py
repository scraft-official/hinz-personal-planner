from datetime import datetime, date, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from .db import get_session, init_db, seed_defaults, ensure_quick_block
from .models import BlockType, ScheduleEntry

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
    entries_by_day: dict[str, list[ScheduleEntry]] = {d: [] for d in DAY_ORDER}
    for entry in entries:
        entries_by_day.setdefault(entry.day, []).append(entry)
    for day_entries in entries_by_day.values():
        day_entries.sort(key=lambda e: e.start_minute)
    
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
