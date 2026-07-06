import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Course, User, Hole, HoleNode, HoleHazard, Disc, UserDiscStat, UserThrowStyle, Round, RoundHole
from app.schemas import CourseCreate, CourseResponse, CourseUpdate, HoleCreate, HoleResponse, HoleUpdate, HoleNodeResponse, HolePathResponse, HoleNodeCreate, HoleNodeUpdate, HazardCreate, HazardResponse
from app.dependencies import get_current_user, get_current_admin
from app.fairway import FairwayRegion, MODE_EROSION_FT, corridor_ring
from app.recommendation import recommend_route, player_reach, flatten_style_distances
from app.wind import get_wind

router = APIRouter(prefix="/courses", tags=["course"])


def recompute_total_par(course: Course):
    course.total_par = sum(h.par for h in course.holes) or course.total_par


def hole_ring(hole: Hole) -> Optional[list]:
    """The hole's fairway ring: stored polygon, or a straight 60ft corridor
    synthesized from tee→basket for holes with no drawn fairway."""
    if hole.fairway_polygon:
        return json.loads(hole.fairway_polygon)
    pts = [
        (n.latitude, n.longitude)
        for n in sorted(hole.nodes, key=lambda n: n.sequence)
        if n.node_type in ("tee", "basket") and n.latitude is not None
    ]
    if len(pts) >= 2:
        return corridor_ring(pts)
    return None


def recompute_hole_distance(hole: Hole):
    """Hole length = the derived playing line through the fairway polygon at
    the balanced safety margin (there is no stored centerline)."""
    ring = hole_ring(hole)
    tee = next((n for n in hole.nodes if n.node_type == "tee" and n.latitude is not None), None)
    basket = next((n for n in hole.nodes if n.node_type == "basket" and n.latitude is not None), None)
    if ring is None or tee is None or basket is None:
        return
    region = FairwayRegion(ring)
    route = region.route(
        (tee.latitude, tee.longitude), (basket.latitude, basket.longitude),
        MODE_EROSION_FT["balanced"],
    )
    hole.distance = round(region.route_length_ft(route))


def hazard_polygon(h: HoleHazard) -> list:
    return json.loads(h.polygon) if h.polygon else []


def hazard_response(h: HoleHazard) -> HazardResponse:
    return HazardResponse(
        hazard_id=h.hazard_id, hole_id=h.hole_id,
        hazard_type=h.hazard_type, polygon=hazard_polygon(h),
    )


@router.get("/{course_id}/holes/{hole_id}/hazards", response_model=list[HazardResponse])
async def get_hole_hazards(course_id: int, hole_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    hole = db.query(Hole).filter(Hole.hole_id == hole_id, Hole.course_id == course_id).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found")
    return [hazard_response(h) for h in hole.hole_hazards]


@router.post("/{course_id}/holes/{hole_id}/hazards", response_model=HazardResponse)
async def create_hole_hazard(
    course_id: int,
    hole_id: int,
    hazard_in: HazardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    hole = db.query(Hole).filter(Hole.hole_id == hole_id, Hole.course_id == course_id).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found")
    if len(hazard_in.polygon) < 3:
        raise HTTPException(status_code=400, detail="Hazard polygon needs at least 3 points")

    hazard = HoleHazard(
        hole_id=hole_id,
        hazard_type=hazard_in.hazard_type,
        polygon=json.dumps([[lat, lng] for lat, lng in hazard_in.polygon]),
    )
    db.add(hazard)
    db.commit()
    db.refresh(hazard)
    return hazard_response(hazard)


@router.delete("/{course_id}/holes/{hole_id}/hazards/{hazard_id}")
async def delete_hole_hazard(
    course_id: int,
    hole_id: int,
    hazard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    hole = db.query(Hole).filter(Hole.hole_id == hole_id, Hole.course_id == course_id).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found")
    hazard = db.query(HoleHazard).filter(
        HoleHazard.hazard_id == hazard_id, HoleHazard.hole_id == hole_id
    ).first()
    if hazard is None:
        raise HTTPException(status_code=404, detail="Hazard not found")

    db.delete(hazard)
    db.commit()
    return {"message": "Hazard deleted"}


@router.post("/{course_id}/holes", response_model=HoleResponse)
async def create_hole(course_id: int, hole_in: HoleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    hole_dict = hole_in.model_dump()
    hole_dict["course_id"] = course_id
    hole_dict["is_approved"] = True
    if hole_dict.get("fairway_polygon") is not None:
        hole_dict["fairway_polygon"] = json.dumps([[lat, lng] for lat, lng in hole_dict["fairway_polygon"]])
    db_hole = Hole(**hole_dict)
    db.add(db_hole)
    db.flush()
    recompute_total_par(course)
    db.commit()
    db.refresh(db_hole)
    return db_hole


@router.patch("/{course_id}/holes/{hole_id}", response_model=HoleResponse)
async def patch_hole(course_id: int, hole_id: int, hole_in: HoleUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    hole = db.query(Hole).filter(Hole.hole_id == hole_id, Hole.course_id == course_id).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found")

    for key, value in hole_in.model_dump().items():
        if value is None:
            continue
        if key == "fairway_polygon":
            value = json.dumps([[lat, lng] for lat, lng in value])
        setattr(hole, key, value)

    if hole_in.fairway_polygon is not None:
        recompute_hole_distance(hole)
    recompute_total_par(hole.course)
    db.commit()
    db.refresh(hole)
    return hole


@router.delete("/{course_id}/holes/{hole_id}")
async def delete_hole(course_id: int, hole_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    hole = db.query(Hole).filter(Hole.hole_id == hole_id, Hole.course_id == course_id).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found")

    played = db.query(RoundHole).filter(RoundHole.hole_id == hole_id).first()
    if played is not None:
        raise HTTPException(status_code=409, detail="Hole has recorded rounds and cannot be deleted")

    course = hole.course
    db.delete(hole)
    db.flush()
    recompute_total_par(course)
    db.commit()
    return {"message": "Hole deleted"}


@router.get("/{course_id}/holes/{hole_id}/nodes", response_model=list[HoleNodeResponse])
async def get_hole_nodes(course_id: int, hole_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    hole = db.query(Hole).filter(Hole.hole_id == hole_id, Hole.course_id == course_id).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found")
    return db.query(HoleNode).filter(HoleNode.hole_id == hole_id).order_by(HoleNode.sequence).all()

@router.get("/{course_id}/holes/{hole_id}/path", response_model=HolePathResponse)
async def get_path(
    course_id: int,
    hole_id: int,
    lie_latitude: Optional[float] = None,
    lie_longitude: Optional[float] = None,
    mode: str = "balanced",
    use_wind: bool = False,
    wind_speed: Optional[float] = None,
    wind_direction: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if mode not in ("conservative", "balanced", "aggressive"):
        raise HTTPException(status_code=400, detail="mode must be conservative, balanced, or aggressive")

    hole = db.query(Hole).filter(Hole.hole_id == hole_id, Hole.course_id == course_id).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found")

    nodes = db.query(HoleNode).filter(HoleNode.hole_id == hole_id).order_by(HoleNode.sequence).all()
    tee = next((n for n in nodes if n.node_type == "tee" and n.latitude is not None), None)
    basket = next((n for n in nodes if n.node_type == "basket" and n.latitude is not None), None)
    if basket is None:
        raise HTTPException(status_code=400, detail="Hole has no GPS basket")

    # Live round: plan from wherever the last throw landed; otherwise the tee
    start_is_lie = lie_latitude is not None and lie_longitude is not None
    if start_is_lie:
        start = (lie_latitude, lie_longitude)
    elif tee is not None:
        start = (tee.latitude, tee.longitude)
    else:
        raise HTTPException(status_code=400, detail="Hole has no GPS tee")

    ring = hole_ring(hole)
    if ring is None:
        raise HTTPException(status_code=400, detail="Hole has no fairway mapped")

    hazards = [
        (h.hazard_type, hazard_polygon(h))
        for h in hole.hole_hazards
        if len(hazard_polygon(h)) >= 3
    ]

    # The playing line is derived from the fairway polygon: hazards are carved
    # out of the routable region (aggressive players route the raw fairway and
    # just get warned), then the region is eroded by the mode's safety margin.
    region = FairwayRegion(
        ring,
        [poly for _, poly in hazards],
        subtract_hazards=(mode != "aggressive"),
    )
    route = region.route(start, (basket.latitude, basket.longitude), MODE_EROSION_FT[mode])

    # Player reach + per-style distances (forehand and backhand carry differently)
    discs = db.query(Disc).filter(Disc.user_id == current_user.user_id).all()
    disc_stats = db.query(UserDiscStat).filter(
        UserDiscStat.user_id == current_user.user_id
    ).all()
    style_distances: dict = {}
    style_max: dict = {}
    for stat in disc_stats:
        style = stat.throw_style or "backhand"
        style_distances.setdefault(style, {})[stat.disc_id] = stat.avg_distance
        style_max.setdefault(style, {})[stat.disc_id] = stat.max_distance
    disc_distances = flatten_style_distances(style_distances)
    disc_max_distances = flatten_style_distances(style_max)

    style_rows = db.query(UserThrowStyle).filter(
        UserThrowStyle.user_id == current_user.user_id
    ).all()
    hand = style_rows[0].hand if style_rows else "right"
    style_priority = {r.throw_type: r.priority for r in style_rows}
    allowed_styles = [r.throw_type for r in style_rows] or None
    style_hands = {r.throw_type: r.hand for r in style_rows}

    # Wind: explicit params win; otherwise fetch live conditions at the start
    resolved_wind_speed = wind_speed or 0.0
    resolved_wind_direction = wind_direction
    if use_wind and wind_speed is None:
        wind = await get_wind(start[0], start[1])
        if wind:
            resolved_wind_speed = wind["speed"]
            resolved_wind_direction = wind["direction"]

    recommendations = recommend_route(
        region=region,
        route=route,
        discs=discs,
        disc_distances=disc_distances,
        disc_max_distances=disc_max_distances,
        wind_speed=resolved_wind_speed,
        wind_direction=resolved_wind_direction,
        mode=mode,
        style_distances=style_distances,
        style_max_distances=style_max,
        hand=hand,
        style_priority=style_priority,
        allowed_styles=allowed_styles,
        style_hands=style_hands,
        hazard_polygons=hazards,
        start_is_lie=start_is_lie,
    )

    # Only real physical points render on the map — legacy landing_zone chain
    # rows stay in the DB but are not part of the polygon model.
    gps_nodes = [
        n for n in nodes
        if n.latitude is not None and n.longitude is not None
        and n.node_type in ("tee", "basket", "mando")
    ]
    return HolePathResponse(
        nodes=gps_nodes,
        total_distance=region.route_length_ft(route),
        node_count=len(gps_nodes),
        recommendations=recommendations,
        # closed ring for map display, like the hazard rings
        fairway_polygon=ring + [ring[0]],
        hazards=[hazard_response(h) for h in hole.hole_hazards],
    )

@router.post("/{course_id}/holes/{hole_id}/nodes", response_model=HoleNodeResponse)
async def create_hole_node(
    course_id: int,
    hole_id: int,
    node_in: HoleNodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    hole = db.query(Hole).filter(Hole.hole_id == hole_id, Hole.course_id == course_id).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found")

    node_dict = node_in.model_dump()
    node_dict["hole_id"] = hole_id
    db_node = HoleNode(**node_dict)
    db.add(db_node)
    db.flush()
    recompute_hole_distance(hole)
    db.commit()
    db.refresh(db_node)
    return db_node


@router.delete("/{course_id}/holes/{hole_id}/nodes/{node_id}")
async def delete_hole_node(
    course_id: int,
    hole_id: int,
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    hole = db.query(Hole).filter(Hole.hole_id == hole_id, Hole.course_id == course_id).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found")

    node = db.query(HoleNode).filter(
        HoleNode.hole_node_id == node_id, HoleNode.hole_id == hole_id
    ).first()
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")

    db.delete(node)  # touching edges cascade via the node's edge relationships
    db.flush()
    recompute_hole_distance(hole)
    db.commit()
    return {"message": "Node deleted"}


@router.patch("/{course_id}/holes/{hole_id}/nodes/{node_id}", response_model=HoleNodeResponse)
async def patch_hole_node(
    course_id: int,
    hole_id: int,
    node_id: int,
    node_in: HoleNodeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    hole = db.query(Hole).filter(Hole.hole_id == hole_id, Hole.course_id == course_id).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found")

    node = db.query(HoleNode).filter(
        HoleNode.hole_node_id == node_id, HoleNode.hole_id == hole_id
    ).first()
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")

    for key, value in node_in.model_dump(exclude_unset=True).items():
        setattr(node, key, value)

    db.flush()
    recompute_hole_distance(hole)
    db.commit()
    db.refresh(node)
    return node


@router.get("", response_model=list[CourseResponse])
async def get_courses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Admins see everything, including unapproved courses they are still mapping
    query = db.query(Course)
    if not current_user.is_admin:
        query = query.filter(Course.is_approved == True)
    return query.all()


@router.post("", response_model=CourseResponse)
async def create_course(course_in: CourseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course_dict = course_in.model_dump()
    # Admin-created courses go live immediately; others wait for approval
    course_dict["is_approved"] = bool(current_user.is_admin)
    db_course = Course(
         **course_dict
    )
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course

@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    
    return course

@router.patch("/{course_id}", response_model=CourseResponse)
async def patch_courses(course_in: CourseUpdate, course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    
    for key, value in course_in.model_dump().items():
        if value is not None:
            setattr(course, key, value)

    db.commit()
    db.refresh(course)
    return course

@router.delete("/{course_id}")
async def delete_courses(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    course = db.query(Course).filter(Course.course_id == course_id).first()

    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    played = db.query(Round).filter(Round.course_id == course_id).first()
    if played is not None:
        raise HTTPException(status_code=409, detail="Course has recorded rounds and cannot be deleted")

    db.delete(course)
    db.commit()
    return {"message": "Course deleted"}