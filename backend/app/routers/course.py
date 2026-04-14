from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Course, User, Hole, HoleNode, HoleEdge
from app.schemas import CourseCreate, CourseResponse, CourseUpdate, HoleCreate, HoleResponse, HoleUpdate, HoleNodeResponse, HoleEdgeResponse, HolePathResponse, HoleNodeCreate, HoleEdgeCreate
from app.dependencies import get_current_user
from app.graph import dijkstra

router = APIRouter(prefix="/courses", tags=["course"])

@router.post("/{course_id}/holes", response_model=HoleResponse)
async def create_hole(course_id: int, hole_in: HoleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    hole_dict = hole_in.model_dump()
    hole_dict["course_id"] = course_id
    hole_dict["is_approved"] = False
    db_hole = Hole(**hole_dict)
    db.add(db_hole)
    db.commit()
    db.refresh(db_hole)
    return db_hole

@router.get("/{course_id}/holes/{hole_id}/path", response_model=HolePathResponse)
async def get_path(
    course_id: int,
    hole_id: int,
    start_node_id: Optional[int] = None,
    end_node_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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

    if start is None or end is None:
        raise HTTPException(status_code=400, detail="Could not resolve start or end node")

    edge_tuples = [(e.from_node_id, e.to_node_id, e.distance) for e in edges]
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

    return HolePathResponse(
        nodes=path_nodes,
        edges=path_edges,
        total_distance=total_distance,
        node_count=len(path_nodes)
    )

@router.post("/{course_id}/holes/{hole_id}/nodes", response_model=HoleNodeResponse)
async def create_hole_node(
    course_id: int,
    hole_id: int,
    node_in: HoleNodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    db.commit()
    db.refresh(db_node)
    return db_node


@router.post("/{course_id}/holes/{hole_id}/edges", response_model=HoleEdgeResponse)
async def create_hole_edge(
    course_id: int,
    hole_id: int,
    edge_in: HoleEdgeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    courses = db.query(Course).filter(Course.is_approved == True).all()
    return courses


@router.post("", response_model=CourseResponse)
async def create_course(course_in: CourseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course_dict = course_in.model_dump()
    course_dict["is_approved"] = False
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
async def patch_courses(course_in: CourseUpdate, course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
async def delete_courses(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = db.query(Course).filter(Course.course_id == course_id).first()

    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    
    db.delete(course)
    db.commit()
    return {"message": "Course deleted"}