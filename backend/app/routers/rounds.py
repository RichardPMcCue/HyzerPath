from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Bag, Course, Hole, Round, RoundHole, User
from app.schemas import RoundCreate, RoundHoleResponse, RoundHoleScore, RoundResponse

router = APIRouter(prefix="/rounds", tags=["rounds"])


def _get_round(round_id: int, db: Session, user: User) -> Round:
    round_ = db.query(Round).options(joinedload(Round.round_holes)).filter(
        Round.round_id == round_id,
        Round.user_id == user.user_id
    ).first()
    if round_ is None:
        raise HTTPException(status_code=404, detail="Round not found")
    return round_


def _get_or_create_bag(db: Session, user: User) -> Bag:
    bag = db.query(Bag).filter(Bag.user_id == user.user_id, Bag.is_active == True).first()
    if bag is None:
        bag = db.query(Bag).filter(Bag.user_id == user.user_id).first()
    if bag is None:
        bag = Bag(user_id=user.user_id, name="My Bag", is_active=True)
        db.add(bag)
        db.flush()
    return bag


@router.post("", response_model=RoundResponse)
async def start_round(round_in: RoundCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = db.query(Course).filter(Course.course_id == round_in.course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    bag = _get_or_create_bag(db, current_user)
    round_ = Round(user_id=current_user.user_id, course_id=round_in.course_id, bag_id=bag.bag_id)
    db.add(round_)
    db.commit()
    db.refresh(round_)
    return round_


@router.get("", response_model=list[RoundResponse])
async def list_rounds(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Round).options(joinedload(Round.round_holes)).filter(
        Round.user_id == current_user.user_id
    ).order_by(Round.played_at.desc()).all()


@router.get("/{round_id}", response_model=RoundResponse)
async def get_round(round_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_round(round_id, db, current_user)


@router.put("/{round_id}/holes/{hole_id}", response_model=RoundHoleResponse)
async def set_hole_score(
    round_id: int,
    hole_id: int,
    score_in: RoundHoleScore,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    round_ = _get_round(round_id, db, current_user)

    hole = db.query(Hole).filter(
        Hole.hole_id == hole_id,
        Hole.course_id == round_.course_id
    ).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found on this round's course")

    round_hole = db.query(RoundHole).filter(
        RoundHole.round_id == round_id,
        RoundHole.hole_id == hole_id
    ).first()
    if round_hole is None:
        round_hole = RoundHole(round_id=round_id, hole_id=hole_id)
        db.add(round_hole)
    round_hole.score = score_in.score

    db.commit()
    db.refresh(round_hole)
    return round_hole


@router.post("/{round_id}/finish", response_model=RoundResponse)
async def finish_round(round_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    round_ = _get_round(round_id, db, current_user)
    round_.total_score = sum(rh.score for rh in round_.round_holes)
    db.commit()
    db.refresh(round_)
    return round_


@router.delete("/{round_id}")
async def delete_round(round_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    round_ = _get_round(round_id, db, current_user)
    for rh in round_.round_holes:
        db.delete(rh)
    db.delete(round_)
    db.commit()
    return {"message": "Round deleted"}
