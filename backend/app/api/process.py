"""Processing driven by the open web page (see pipeline/tick.py). Thin router."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.config import get_settings
from app.db import get_session
from app.pipeline.tick import tick

router = APIRouter(tags=["process"])


@router.post("/process/tick")
async def process_tick(session: Session = Depends(get_session)) -> dict:
    """Run one processing step, if any is due. `enabled: false` tells the page to stop asking."""
    if not get_settings().process_in_requests:
        return {"enabled": False}
    return {"enabled": True, **(await tick(session))}
