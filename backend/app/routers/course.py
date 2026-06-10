from collections import namedtuple
from types import SimpleNamespace
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Course, User, Hole, HoleNode, HoleEdge, Disc, UserDiscStat, Round, RoundHole
from app.schemas import CourseCreate, CourseResponse, CourseUpdate, HoleCreate, HoleResponse, HoleUpdate, HoleNodeResponse, HoleEdgeResponse, HolePathResponse, HoleNodeCreate, HoleNodeUpdate, HoleEdgeCreate
from app.dependencies import get_current_user, get_current_admin
from app.graph import dijkstra, compute_edge_weight
from app.recommendation import SegmentRecommendation, recommend_path, player_reach
from app.utils import compute_dynamic_centerline, compute_centerline_distance, compute_fairway_width_at_sequence, compute_fairway_polygon, haversine_feet
from app.wind import get_wind

CenterlinePoint = namedtuple("CenterlinePoint", ["latitude", "longitude"])

router = APIRouter(prefix="/courses", tags=["course"])


def recompute_total_par(course: Course):
    course.total_par = sum(h.par for h in course.holes) or course.total_par


def recompute_hole_geometry(db: Session, hole: Hole):
    """After a node moves: refresh edge distances and the hole's tee→basket length."""
    nodes = {n.hole_node_id: n for n in hole.nodes}
    edges = db.query(HoleEdge).filter(HoleEdge.from_node_id.in_(nodes.keys())).all()
    for e in edges:
        a, b = nodes.get(e.from_node_id), nodes.get(e.to_node_id)
        if a and b and None not in (a.latitude, a.longitude, b.latitude, b.longitude):
            e.distance = round(haversine_feet(a.latitude, a.longitude, b.latitude, b.longitude))
    tee = next((n for n in hole.nodes if n.node_type == "tee"), None)
    basket = next((n for n in hole.nodes if n.node_type == "basket"), None)
    if tee and basket and None not in (tee.latitude, tee.longitude, basket.latitude, basket.longitude):
        hole.distance = round(haversine_feet(tee.latitude, tee.longitude, basket.latitude, basket.longitude))


@router.post("/{course_id}/holes", response_model=HoleResponse)
async def create_hole(course_id: int, hole_in: HoleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    hole_dict = hole_in.model_dump()
    hole_dict["course_id"] = course_id
    hole_dict["is_approved"] = True
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
        if value is not None:
            setattr(hole, key, value)

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
    start_node_id: Optional[int] = None,
    end_node_id: Optional[int] = None,
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

    nodes = db.query(HoleNode).filter(HoleNode.hole_id == hole_id).all()
    edges = db.query(HoleEdge).filter(
        HoleEdge.from_node_id.in_([n.hole_node_id for n in nodes])
    ).all()

    node_map = {n.hole_node_id: n for n in nodes}

    tee = next((n for n in nodes if n.node_type == "tee"), None)
    basket = next((n for n in nodes if n.node_type == "basket"), None)

    start = node_map.get(start_node_id) if start_node_id else tee
    end = node_map.get(end_node_id) if end_node_id else basket

    # Live round mode: the player's lie becomes a virtual start node wired
    # into the graph, so the plan adapts to wherever the last throw landed.
    if lie_latitude is not None and lie_longitude is not None:
        lie = SimpleNamespace(
            hole_node_id=0, hole_id=hole_id, node_type="tee", sequence=-1,
            label="Your lie", latitude=lie_latitude, longitude=lie_longitude,
            centerline_distance=None, is_fairway=False,
        )
        node_map[0] = lie
        for n in nodes:
            if n.latitude is None or n.longitude is None or n.node_type == "tee":
                continue
            dist = haversine_feet(lie_latitude, lie_longitude, n.latitude, n.longitude)
            edges.append(SimpleNamespace(
                hole_edge_id=0, from_node_id=0, to_node_id=n.hole_node_id,
                distance=round(dist), fairway_width=None, edge_hazards=[],
            ))
        start = lie

    if start is None or end is None:
        raise HTTPException(status_code=400, detail="Could not resolve start or end node")

    # Dynamic centerline/width from fairway nodes, falling back to stored values
    fairway_nodes = [n for n in nodes if n.is_fairway]
    centerline_points = [
        CenterlinePoint(lat, lon) for lat, lon in compute_dynamic_centerline(fairway_nodes)
    ]

    def effective_centerline_distance(node):
        if node is None:
            return None
        if node.centerline_distance is not None:
            return node.centerline_distance
        if len(centerline_points) >= 2 and node.latitude is not None and node.longitude is not None:
            return compute_centerline_distance(node.latitude, node.longitude, centerline_points)
        return None

    def effective_fairway_width(edge):
        if edge.fairway_width:
            return edge.fairway_width
        to_node = node_map.get(edge.to_node_id)
        if to_node is not None:
            return compute_fairway_width_at_sequence(fairway_nodes, to_node.sequence)
        return None

    # Player reach informs routing: edges beyond a single throw cost more,
    # and hazard tolerance scales with mode.
    discs = db.query(Disc).filter(Disc.user_id == current_user.user_id).all()
    disc_stats = db.query(UserDiscStat).filter(
        UserDiscStat.user_id == current_user.user_id
    ).all()
    disc_distances = {stat.disc_id: stat.avg_distance for stat in disc_stats}
    disc_max_distances = {stat.disc_id: stat.max_distance for stat in disc_stats}
    reach = player_reach(discs, disc_distances, disc_max_distances, mode)

    edge_tuples = [
        (
            e.from_node_id,
            e.to_node_id,
            compute_edge_weight(
                e,
                node_map.get(e.to_node_id),
                centerline_distance=effective_centerline_distance(node_map.get(e.to_node_id)),
                fairway_width=effective_fairway_width(e),
                mode=mode,
                reach=reach,
            ),
        )
        for e in edges
    ]
    path_ids = dijkstra(edge_tuples, start.hole_node_id, end.hole_node_id)

    if not path_ids:
        raise HTTPException(status_code=400, detail="No path found between start and end node")

    path_nodes = [node_map[node_id] for node_id in path_ids]

    edge_lookup = {(e.from_node_id, e.to_node_id): e for e in edges}

    path_edges = []
    total_distance = 0
    for i in range(len(path_ids) - 1):
        edge = edge_lookup.get((path_ids[i], path_ids[i + 1]))
        if edge:
            path_edges.append(edge)
            total_distance += edge.distance

    # Wind: explicit params win; otherwise fetch live conditions at the tee
    resolved_wind_speed = wind_speed or 0.0
    resolved_wind_direction = wind_direction
    if use_wind and wind_speed is None and start.latitude is not None and start.longitude is not None:
        wind = await get_wind(start.latitude, start.longitude)
        if wind:
            resolved_wind_speed = wind["speed"]
            resolved_wind_direction = wind["direction"]

    recommendations = recommend_path(
        path_nodes=path_nodes,
        edge_lookup=edge_lookup,
        discs=discs,
        disc_distances=disc_distances,
        disc_max_distances=disc_max_distances,
        wind_speed=resolved_wind_speed,
        wind_direction=resolved_wind_direction,
        mode=mode,
    )

    return HolePathResponse(
        nodes=path_nodes,
        edges=path_edges,
        total_distance=total_distance,
        node_count=len(path_nodes),
        recommendations=recommendations,
        fairway_polygon=compute_fairway_polygon(fairway_nodes, edges)
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
    recompute_hole_geometry(db, hole)
    db.commit()
    db.refresh(db_node)
    return db_node


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
    recompute_hole_geometry(db, hole)
    db.commit()
    db.refresh(node)
    return node


@router.post("/{course_id}/holes/{hole_id}/edges", response_model=HoleEdgeResponse)
async def create_hole_edge(
    course_id: int,
    hole_id: int,
    edge_in: HoleEdgeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    hole = db.query(Hole).filter(Hole.hole_id == hole_id, Hole.course_id == course_id).first()
    if hole is None:
        raise HTTPException(status_code=404, detail="Hole not found")

    from_node = db.query(HoleNode).filter(
        HoleNode.hole_node_id == edge_in.from_node_id,
        HoleNode.hole_id == hole_id
    ).first()
    if from_node is None:
        raise HTTPException(status_code=404, detail="from_node not found on this hole")

    to_node = db.query(HoleNode).filter(
        HoleNode.hole_node_id == edge_in.to_node_id,
        HoleNode.hole_id == hole_id
    ).first()
    if to_node is None:
        raise HTTPException(status_code=404, detail="to_node not found on this hole")

    edge_dict = edge_in.model_dump()
    db_edge = HoleEdge(**edge_dict)
    db.add(db_edge)
    db.commit()
    db.refresh(db_edge)
    return db_edge

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