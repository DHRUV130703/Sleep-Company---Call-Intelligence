"""Record progress: update the call row and append a JobEvent (the live Batch page reads these)."""

from sqlmodel import Session

from app.db import utcnow
from app.models import Call, CallStage, CallStatus, JobEvent


def emit(
    session: Session,
    call: Call,
    *,
    stage: CallStage,
    status: CallStatus,
    message: str = "",
    progress: int = 0,
    commit: bool = True,
) -> None:
    call.stage = stage
    call.status = status
    call.updated_at = utcnow()
    session.add(call)
    assert call.id is not None
    session.add(
        JobEvent(
            batch_id=call.batch_id,
            call_id=call.id,
            stage=stage,
            status=status,
            message=message,
            progress=progress,
        )
    )
    if commit:
        session.commit()
