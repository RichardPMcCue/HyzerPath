from pydantic import BaseModel, ConfigDict
from typing import Optional
from enum import Enum
from app.recommendation import SegmentRecommendation

class NodeType(str, Enum):
    tee = "tee"
    landing_zone = "landing_zone"
    mando = "mando"
    dogleg = "dogleg"
    basket = "basket"

class HoleCreate(BaseModel):
    hole_number: int
    par: int
    distance: int
    elevation: int

class HoleNodeCreate(BaseModel):
    node_type: NodeType
    sequence: int
    label: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    centerline_distance: Optional[float] = None
    is_fairway: bool = True

class HoleEdgeCreate(BaseModel):
    from_node_id: int
    to_node_id: int
    distance: int
    fairway_width: Optional[int] = None

class HoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    hole_id: int
    course_id: int
    hole_number: int
    par: int
    distance: int
    elevation: int
    is_approved: bool

class HoleUpdate(BaseModel):
    hole_number: Optional[int] = None
    par: Optional[int] = None
    distance: Optional[int] = None
    elevation: Optional[int] = None
    is_approved: Optional[bool] = None # needs admin protection

class HoleNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hole_node_id: int
    hole_id: int
    node_type: NodeType
    sequence: int
    label: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    centerline_distance: Optional[float] = None
    is_fairway: bool = True

class HoleEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hole_edge_id: int
    from_node_id: int
    to_node_id: int
    distance: int
    fairway_width: Optional[int] = None

class HolePathResponse(BaseModel):
    nodes: list[HoleNodeResponse]
    edges: list[HoleEdgeResponse]
    total_distance: float
    node_count: int
    recommendations: list[SegmentRecommendation] = []

class CourseCreate(BaseModel):
    name: str
    city: str
    state: str
    address: str
    total_par: int

class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    course_id: int
    name: str
    city: str
    state: str
    address: str
    total_par: int
    is_approved: bool
    holes: list[HoleResponse] = []

class CourseUpdate(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    address: Optional[str] = None
    total_par: Optional[int] = None
    is_approved: Optional[bool] = None # needs admin protection