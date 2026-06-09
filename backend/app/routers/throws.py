from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Disc, ThrowMeasurement, ThrowSession, User, UserDiscStat
from app.schemas import (
    ThrowCreate,
    ThrowResponse,
    ThrowSessionCreate,
    ThrowSessionResponse,
    ThrowSessionUpdate,
)
from app.utils import haversine_feet

router = APIRouter(prefix="/throws", tags=["throws"])


def _get_session(session_id: int, db: Session, user: User) -> ThrowSession:
    session = db.query(ThrowSession).filter(
        ThrowSession.session_id == session_id,
        ThrowSession.user_id == user.user_id
    ).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _sync_disc_stat(disc_id: int, db: Session, user: User) -> None:
    """Recompute UserDiscStat from all measured throws with this disc, so the
    recommendation engine learns from field work automatically."""
    avg_dist, max_dist, count = db.query(
        func.avg(ThrowMeasurement.distance_ft),
        func.max(ThrowMeasurement.distance_ft),
        func.count(ThrowMeasurement.throw_id),
    ).join(ThrowSession).filter(
        ThrowSession.user_id == user.user_id,
        ThrowMeasurement.disc_id == disc_id
    ).one()

    stat = db.query(UserDiscStat).filter(
        UserDiscStat.user_id == user.user_id,
        UserDiscStat.disc_id == disc_id
    ).first()

    if count == 0:
        if stat is not None:
            db.delete(stat)
        return

    if stat is None:
        stat = UserDiscStat(user_id=user.user_id, disc_id=disc_id)
        db.add(stat)
    stat.avg_distance = round(avg_dist)
    stat.max_distance = round(max_dist)
    stat.sample_size = count


@router.post("/sessions", response_model=ThrowSessionResponse)
async def create_session(
    session_in: ThrowSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = ThrowSession(user_id=current_user.user_id, **session_in.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions", response_model=list[ThrowSessionResponse])
async def list_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(ThrowSession).options(joinedload(ThrowSession.throws)).filter(
        ThrowSession.user_id == current_user.user_id
    ).order_by(ThrowSession.created_at.desc()).all()


@router.get("/sessions/{session_id}", response_model=ThrowSessionResponse)
async def get_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_session(session_id, db, current_user)


@router.patch("/sessions/{session_id}", response_model=ThrowSessionResponse)
async def update_session(
    session_id: int,
    session_in: ThrowSessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = _get_session(session_id, db, current_user)
    for key, value in session_in.model_dump().items():
        if value is not None:
            setattr(session, key, value)
    db.commit()
    db.refresh(session)
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = _get_session(session_id, db, current_user)
    disc_ids = {t.disc_id for t in session.throws if t.disc_id is not None}
    db.delete(session)
    for disc_id in disc_ids:
        _sync_disc_stat(disc_id, db, current_user)
    db.commit()
    return {"message": "Session deleted"}


@router.post("/sessions/{session_id}/throws", response_model=ThrowResponse)
async def record_throw(
    session_id: int,
    throw_in: ThrowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = _get_session(session_id, db, current_user)

    if throw_in.disc_id is not None:
        disc = db.query(Disc).filter(
            Disc.disc_id == throw_in.disc_id,
            Disc.user_id == current_user.user_id
        ).first()
        if disc is None:
            raise HTTPException(status_code=404, detail="Disc not found")

    distance = haversine_feet(
        session.start_latitude, session.start_longitude,
        throw_in.end_latitude, throw_in.end_longitude,
    )

    throw = ThrowMeasurement(
        session_id=session.session_id,
        disc_id=throw_in.disc_id,
        end_latitude=throw_in.end_latitude,
        end_longitude=throw_in.end_longitude,
        distance_ft=round(distance, 1),
    )
    db.add(throw)
    db.flush()

    if throw_in.disc_id is not None:
        _sync_disc_stat(throw_in.disc_id, db, current_user)

    db.commit()
    db.refresh(throw)
    return throw


@router.delete("/sessions/{session_id}/throws/{throw_id}")
async def delete_throw(
    session_id: int,
    throw_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = _get_session(session_id, db, current_user)
    throw = db.query(ThrowMeasurement).filter(
        ThrowMeasurement.throw_id == throw_id,
        ThrowMeasurement.session_id == session.session_id
    ).first()
    if throw is None:
        raise HTTPException(status_code=404, detail="Throw not found")

    disc_id = throw.disc_id
    db.delete(throw)
    db.flush()
    if disc_id is not None:
        _sync_disc_stat(disc_id, db, current_user)
    db.commit()
    return {"message": "Throw deleted"}
