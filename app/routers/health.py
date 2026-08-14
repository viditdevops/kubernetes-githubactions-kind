"""
routers/health.py - Liveness and readiness endpoints.

Kept deliberately dependency-light: liveness must never depend on the
database, or a DB outage would cause Kubernetes to kill and restart pods
that are actually fine - turning one problem (DB down) into two (app down too).
"""
from fastapi import APIRouter, HTTPException
import db

router = APIRouter()


@router.get("/health")
def liveness():
    """Process is alive. No external dependency checked here on purpose."""
    return {"status": "ok"}


@router.get("/ready")
def readiness():
    """Can this pod actually serve real traffic right now?"""
    try:
        db.check_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unreachable: {exc}")
    return {"status": "ready"}
