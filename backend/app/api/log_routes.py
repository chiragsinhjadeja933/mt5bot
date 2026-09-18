"""Log and event routes — Section 23 / 25."""
from fastapi import APIRouter, Depends, Query
from app.main import verify_token
from datetime import datetime, timezone

router = APIRouter(tags=["logs"], dependencies=[Depends(verify_token)])


@router.get("/logs")
async def get_logs(
    level: str | None = None,
    limit: int = Query(default=200, le=1000),
) -> list:
    from app.database.models import get_session, SystemEvent
    with get_session() as session:
        q = session.query(SystemEvent).order_by(SystemEvent.created_at.desc())
        if level:
            q = q.filter(SystemEvent.severity == level.upper())
        rows = q.limit(limit).all()
        return [
            {
                "id": r.id,
                "event_type": r.event_type,
                "severity": r.severity,
                "component": r.component,
                "message": r.message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


@router.get("/events")
async def get_events(limit: int = Query(default=100, le=500)) -> list:
    from app.database.models import get_session, SystemEvent
    with get_session() as session:
        rows = session.query(SystemEvent)\
            .order_by(SystemEvent.created_at.desc())\
            .limit(limit).all()
        return [{"id": r.id, "type": r.event_type, "message": r.message,
                 "time": r.created_at.isoformat() if r.created_at else None} for r in rows]


@router.get("/audit")
async def get_audit(limit: int = Query(default=100, le=500)) -> list:
    from app.database.models import get_session, SystemEvent
    with get_session() as session:
        rows = session.query(SystemEvent)\
            .filter(SystemEvent.event_type == "audit")\
            .order_by(SystemEvent.created_at.desc())\
            .limit(limit).all()
        return [{"id": r.id, "message": r.message,
                 "time": r.created_at.isoformat() if r.created_at else None} for r in rows]
