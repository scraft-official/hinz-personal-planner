# Hinz Personal Planner

>A lightweight, local-first weekly planner web app built with FastAPI, HTMX, and SQLModel.

This repository contains a small planner application that renders a week view schedule and provides quick block/recurring task creation, multi-plan support (color-coded plans), and an interactive, JavaScript-enhanced UI powered by HTMX.

---

## Tech stack

- Backend: FastAPI
- Templating: Jinja2
- Frontend interactivity: HTMX + vanilla JavaScript
- ORM: SQLModel (SQLite backend)
- Styling: CSS (custom)

## Key features

- Weekly schedule grid with draggable/resizable blocks
- Quick task capture and recurring tasks
- Multiple plans (named, colored) with per-plan filtering and management
- Overlap collision handling across plans
- Mobile-responsive layout with optimized controls

## Repository layout

- `app/main.py` — FastAPI application and route handlers
- `app/templates/` — Jinja2 templates (main page, partials like schedule and plans list)
- `app/static/js/app.js` — Client-side JavaScript (HTMX hooks, drag/drop, overlaps computation)
- `app/static/css/styles.css` — Application styles
- `app/models.py` — SQLModel models (Plan, ScheduleEntry, RecurringTask, etc.)

## Requirements

- Python 3.10+ (recommended)
- Recommended to run inside a virtual environment

## Setup (Windows PowerShell)

1. Create and activate a virtual environment

```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1
```

2. Install dependencies

```powershell
pip install -r requirements.txt
```

3. Run the app (development)

```powershell
# from project root
python -m uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000 in your browser.

## Notes on data

- This project uses SQLite via SQLModel. The database file is local to the project (check the config in `app/config.py`).
- There are no special migrations in this template; adjust as needed if you add Alembic.

## Developer notes

- HTMX endpoints: many UI actions use HTMX to partially update the DOM. Look for `hx-` attributes in templates.
- The schedule grid rendering is in `app/templates/partials/schedule.html` and entries are wired to the JavaScript in `app/static/js/app.js` (functions such as `setupEntries()`, `computeOverlaps()`, and `replaceScheduleHtml()`).
- Plan management UI is in `app/templates/partials/plans_list.html` and it's updated via HTMX triggers.
- CSS for the planner lives in `app/static/css/styles.css` and contains responsive rules for mobile breakpoints.

## Common tasks

- Rebuild frontend (no build step here — static files are plain JS/CSS): make edits and refresh the dev server.
- Running the server in production: use an ASGI server behind a reverse proxy (example: Gunicorn + Uvicorn workers or Hypercorn). Configure a proper production database and environment variables.

## Contributing

Contributions and bug reports are welcome. Please open issues describing the problem or feature request.

## Run locally

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Visit http://localhost:8000.

Env override (optional): set `DATABASE_URL` if you want to point to another SQLite path or Postgres; defaults to `sqlite:///data/planner.db`.

## Docker

```bash
docker compose up --build
```
Data lives in `./data/planner.db` (volume mounted in compose).

## Features
- Pre-seeded block palette matching your paper set; add custom blocks (color, icon, default duration).
- Weekly grid 07:00–22:30 with Production/Activity/Night backgrounds.
- Add/remove scheduled entries with HTMX; durations default from selected block.
- Drag to move entries between days/times; resize from the handle to change duration.
- Icons are monochrome inline SVGs for consistency.

## Next ideas
- Drag/drop placement and resizing.
- Mobile-friendly stacked view.
- Configurable day start/end and custom period bands.
- User accounts / sharing.
