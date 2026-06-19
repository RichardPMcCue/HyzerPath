from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Bag, Course, Disc, Hole, HoleNode, HoleEdge, Round, RoundHole, RoundThrow, User
from app.schemas import (
    RoundCreate, RoundUpdate, RoundHoleResponse, RoundHoleScore, RoundResponse,
    RoundThrowCreate, RoundThrowResponse, RoundStatsResponse, LifetimeStatsResponse,
)

VALID_TRACKING_MODES = ("discs", "lies", "detail", "score")
VALID_LAYOUTS = ("full", "front9", "back9")
from app.utils import haversine_feet, compute_fairway_polygon, point_in_polygon

C1_FT = 33.0   # circle 1: 10 meters
C2_FT = 66.0   # circle 2: 20 meters
C1X_FT = 11.0  # C1X excludes the gimme range inside ~3.3 m
PARKED_FT = 10.0
FAIRWAY_ZONES = ("fairway", "c1", "c2", "basket")

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
    if round_in.tracking_mode not in VALID_TRACKING_MODES:
        raise HTTPException(status_code=400, detail=f"tracking_mode must be one of {VALID_TRACKING_MODES}")
    if round_in.layout not in VALID_LAYOUTS:
        raise HTTPException(status_code=400, detail=f"layout must be one of {VALID_LAYOUTS}")

    bag = _get_or_create_bag(db, current_user)
    round_ = Round(
        user_id=current_user.user_id,
        course_id=round_in.course_id,
        bag_id=bag.bag_id,
        tracking_mode=round_in.tracking_mode,
        layout=round_in.layout,
    )
    db.add(round_)
    db.commit()
    db.refresh(round_)
    return round_


@router.patch("/{round_id}", response_model=RoundResponse)
async def update_round(
    round_id: int,
    round_in: RoundUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    round_ = _get_round(round_id, db, current_user)
    if round_in.tracking_mode is not None:
        if round_in.tracking_mode not in VALID_TRACKING_MODES:
            raise HTTPException(status_code=400, detail=f"tracking_mode must be one of {VALID_TRACKING_MODES}")
        round_.tracking_mode = round_in.tracking_mode
    if round_in.layout is not None:
        if round_in.layout not in VALID_LAYOUTS:
            raise HTTPException(status_code=400, detail=f"layout must be one of {VALID_LAYOUTS}")
        round_.layout = round_in.layout
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
    db.delete(round_)  # throws cascade via relationship
    db.commit()
    return {"message": "Round deleted"}


@router.post("/{round_id}/holes/{hole_id}/throws", response_model=RoundThrowResponse)
async def record_round_throw(
    round_id: int,
    hole_id: int,
    throw_in: RoundThrowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    round_ = _get_round(round_id, db, current_user)
    hole = db.query(Hole).filter(Hole.hole_id == hole_id, Hole.course_id == round_.course_id).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found on this round's course")

    if throw_in.disc_id is not None:
        disc = db.query(Disc).filter(
            Disc.disc_id == throw_in.disc_id,
            Disc.user_id == current_user.user_id
        ).first()
        if disc is None:
            raise HTTPException(status_code=404, detail="Disc not found")

    distance = None
    if None not in (throw_in.start_latitude, throw_in.start_longitude, throw_in.end_latitude, throw_in.end_longitude):
        distance = round(haversine_feet(
            throw_in.start_latitude, throw_in.start_longitude,
            throw_in.end_latitude, throw_in.end_longitude,
        ), 1)
    elif throw_in.putt_distance_ft is not None:
        distance = throw_in.putt_distance_ft  # zone mode: band midpoint estimate

    throw = RoundThrow(
        round_id=round_id,
        hole_id=hole_id,
        distance_ft=distance,
        **throw_in.model_dump(exclude={"putt_distance_ft"}),
    )
    db.add(throw)
    db.flush()

    if throw_in.disc_id is not None:
        from app.routers.throws import _sync_disc_stat
        _sync_disc_stat(throw_in.disc_id, db, current_user)

    db.commit()
    db.refresh(throw)
    return throw


@router.delete("/{round_id}/throws/{round_throw_id}")
async def delete_round_throw(
    round_id: int,
    round_throw_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Undo a misrecorded throw."""
    _get_round(round_id, db, current_user)
    throw = db.query(RoundThrow).filter(
        RoundThrow.round_throw_id == round_throw_id,
        RoundThrow.round_id == round_id
    ).first()
    if throw is None:
        raise HTTPException(status_code=404, detail="Throw not found")
    disc_id = throw.disc_id
    db.delete(throw)
    db.flush()
    if disc_id is not None:
        from app.routers.throws import _sync_disc_stat
        _sync_disc_stat(disc_id, db, current_user)
    db.commit()
    return {"message": "Throw deleted"}


def _compute_round_counts(round_id: int, db: Session) -> dict:
    """Raw stat counts for one round. Works from GPS coordinates when present,
    landing zones when not. Covers C1/C1X/C2 putting, fairway hits, parked, and
    greens in regulation (reaching the green within par - 2 throws)."""
    throws = db.query(RoundThrow).filter(RoundThrow.round_id == round_id).all()

    by_hole: dict = {}
    for t in throws:
        by_hole.setdefault(t.hole_id, []).append(t)

    c = dict(
        holes=0, c1_made=0, c1_att=0, c1x_made=0, c1x_att=0, c2_made=0, c2_att=0,
        fw_hits=0, fw_att=0, parked=0, gir_c1=0, gir_c2=0, gir_att=0,
    )

    for hole_id, hole_throws in by_hole.items():
        c["holes"] += 1
        nodes = db.query(HoleNode).filter(HoleNode.hole_id == hole_id).all()
        basket = next((n for n in nodes if n.node_type == "basket" and n.latitude is not None), None)
        edges = db.query(HoleEdge).filter(
            HoleEdge.from_node_id.in_([n.hole_node_id for n in nodes])
        ).all()
        fairway_ring = compute_fairway_polygon([n for n in nodes if n.is_fairway], edges)
        hole = db.query(Hole).filter(Hole.hole_id == hole_id).first()
        # Throws allowed to reach the green and still make par with two putts
        reg = max(1, (hole.par - 2)) if hole and hole.par else 1

        reached_c1_throw = None
        reached_c2_throw = None
        prev_landing_zone = None  # where the previous throw left the player
        for t in sorted(hole_throws, key=lambda x: x.throw_number):
            # Start circle: GPS distance to basket, or the previous landing zone
            from_basket = None
            start_circle = None
            if basket is not None and t.start_latitude is not None:
                from_basket = haversine_feet(t.start_latitude, t.start_longitude, basket.latitude, basket.longitude)
                if from_basket <= C1_FT:
                    start_circle = "c1"
                elif from_basket <= C2_FT:
                    start_circle = "c2"
            elif prev_landing_zone in ("c1", "c2"):
                start_circle = prev_landing_zone

            if start_circle == "c1":
                c["c1_att"] += 1
                if t.is_holed:
                    c["c1_made"] += 1
                # C1X excludes tap-ins inside the gimme range (GPS only)
                if from_basket is not None and from_basket > C1X_FT:
                    c["c1x_att"] += 1
                    if t.is_holed:
                        c["c1x_made"] += 1
            elif start_circle == "c2":
                c["c2_att"] += 1
                if t.is_holed:
                    c["c2_made"] += 1

            # Parked: landing within 10ft (GPS only)
            if basket is not None and t.end_latitude is not None and not t.is_holed:
                to_basket = haversine_feet(t.end_latitude, t.end_longitude, basket.latitude, basket.longitude)
                if to_basket <= PARKED_FT:
                    c["parked"] += 1

            # Fairway hit: the drive landed in the corridor (GPS) or a fairway zone
            if t.throw_number == 1 and not t.is_holed:
                if t.end_latitude is not None and len(fairway_ring) >= 3:
                    c["fw_att"] += 1
                    if point_in_polygon(t.end_latitude, t.end_longitude, fairway_ring):
                        c["fw_hits"] += 1
                elif t.landing_zone is not None:
                    c["fw_att"] += 1
                    if t.landing_zone in FAIRWAY_ZONES:
                        c["fw_hits"] += 1

            # Did this throw land on the green? (for GIR) — GPS or landing zone
            landed_c1 = landed_c2 = False
            if t.is_holed:
                landed_c1 = True
            elif basket is not None and t.end_latitude is not None:
                to_basket = haversine_feet(t.end_latitude, t.end_longitude, basket.latitude, basket.longitude)
                landed_c1 = to_basket <= C1_FT
                landed_c2 = to_basket <= C2_FT
            else:
                landed_c1 = t.landing_zone in ("basket", "c1")
                landed_c2 = t.landing_zone == "c2"
            if reached_c1_throw is None and landed_c1:
                reached_c1_throw = t.throw_number
            if reached_c2_throw is None and (landed_c1 or landed_c2):
                reached_c2_throw = t.throw_number

            # Next throw starts from the drop zone after an OB
            prev_landing_zone = t.drop_zone if t.landing_zone == "ob" else t.landing_zone

        # Green in regulation: reached the circle within regulation throws
        c["gir_att"] += 1
        if reached_c1_throw is not None and reached_c1_throw <= reg:
            c["gir_c1"] += 1
        if reached_c2_throw is not None and reached_c2_throw <= reg:
            c["gir_c2"] += 1

    return c


@router.get("/stats/lifetime", response_model=LifetimeStatsResponse)
async def lifetime_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Career stats aggregated across all of the player's recorded rounds."""
    rounds = db.query(Round).filter(Round.user_id == current_user.user_id).all()
    agg: dict = defaultdict(int)
    rounds_played = 0
    for r in rounds:
        counts = _compute_round_counts(r.round_id, db)
        if counts["holes"] > 0:
            rounds_played += 1
        for k, v in counts.items():
            agg[k] += v

    return LifetimeStatsResponse(
        rounds_played=rounds_played,
        holes_with_throws=agg["holes"],
        c1_putts_made=agg["c1_made"],
        c1_putts_attempted=agg["c1_att"],
        c1x_putts_made=agg["c1x_made"],
        c1x_putts_attempted=agg["c1x_att"],
        c2_putts_made=agg["c2_made"],
        c2_putts_attempted=agg["c2_att"],
        fairway_hits=agg["fw_hits"],
        fairway_attempts=agg["fw_att"],
        parked=agg["parked"],
        gir_c1=agg["gir_c1"],
        gir_c2=agg["gir_c2"],
        gir_attempts=agg["gir_att"],
    )


@router.get("/{round_id}/stats", response_model=RoundStatsResponse)
async def round_stats(round_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Computes C1/C2 putting, fairway hits, and parked shots. Works from GPS
    coordinates when present, landing zones when not."""
    _get_round(round_id, db, current_user)  # ownership check
    c = _compute_round_counts(round_id, db)
    return RoundStatsResponse(
        holes_with_throws=c["holes"],
        c1_putts_made=c["c1_made"],
        c1_putts_attempted=c["c1_att"],
        c2_putts_made=c["c2_made"],
        c2_putts_attempted=c["c2_att"],
        fairway_hits=c["fw_hits"],
        fairway_attempts=c["fw_att"],
        parked=c["parked"],
    )
