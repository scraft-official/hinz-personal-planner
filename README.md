# Planner (desktop-first prototype)

Python FastAPI + HTMX + SQLModel + SQLite. Desktop-first weekly planner that mirrors the magnetic block board.

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
