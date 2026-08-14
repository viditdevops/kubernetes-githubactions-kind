"""
routers/items.py - Minimal demo resource, proves the DB dependency works
end-to-end (write + read), not just that a connection can open.
"""
import time
from fastapi import APIRouter, HTTPException
import db

router = APIRouter()


@router.get("/items")
def list_items():
    try:
        return {"items": db.fetch_recent_items(limit=10)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/items")
def create_item():
    try:
        new_id = db.insert_item(name=f"item-{int(time.time())}")
        return {"created_id": new_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
