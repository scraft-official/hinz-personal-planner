import os
import importlib
from fastapi.testclient import TestClient
from sqlmodel import Session, select


def make_client():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    import app.db as db
    import app.main as main

    importlib.reload(db)
    importlib.reload(main)
    client = TestClient(main.app)
    return client, db


def test_index_renders():
    client, _ = make_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "This Week Schedule" in resp.text


def test_create_entry():
    client, db = make_client()
    from app.models import BlockType

    with Session(db.engine) as session:
        block_id = session.exec(select(BlockType.id)).first()
        assert block_id is not None

    payload = {
        "day": "Monday",
        "start_time": "09:00",
        "duration_minutes": 60,
        "block_type_id": block_id,
        "note": "Test entry",
    }
    resp = client.post("/entries", data=payload)
    assert resp.status_code == 200
    with Session(db.engine) as session:
        count = session.exec(select(BlockType)).count()
        assert count >= 1
