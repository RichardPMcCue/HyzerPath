import json
from pydantic import BaseModel, ConfigDict, field_validator
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
    # Open ring of [lat, lng] pairs outlining the playable fairway
    fairway_polygon: Optional[list[tuple[float, float]]] = None

class HoleNodeCreate(BaseModel):
    node_type: NodeType
    sequence: int
    label: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    centerline_distance: Optional[float] = None
    is_fairway: bool = True

class HoleNodeUpdate(BaseModel):
    node_type: Optional[NodeType] = None
    sequence: Optional[int] = None
    label: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    centerline_distance: Optional[float] = None
    is_fairway: Optional[bool] = None

class HoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hole_id: int
    course_id: int
    hole_number: int
    par: int
    distance: int
    elevation: int
    is_approved: bool
    fairway_polygon: Optional[list[tuple[float, float]]] = None

    @field_validator("fairway_polygon", mode="before")
    @classmethod
    def _parse_ring(cls, v):
        # The model stores the ring as JSON text (like HoleHazard.polygon)
        return json.loads(v) if isinstance(v, str) else v

class HoleUpdate(BaseModel):
    hole_number: Optional[int] = None
    par: Optional[int] = None
    distance: Optional[int] = None
    elevation: Optional[int] = None
    is_approved: Optional[bool] = None # needs admin protection
    fairway_polygon: Optional[list[tuple[float, float]]] = None

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

class HazardCreate(BaseModel):
    hazard_type: str  # 'ob', 'water', 'trees', ...
    # Ring of [lat, lon] pairs (open — no need to repeat the first point)
    polygon: list[tuple[float, float]]

class HazardResponse(BaseModel):
    hazard_id: int
    hole_id: int
    hazard_type: str
    polygon: list[tuple[float, float]] = []

class HolePathResponse(BaseModel):
    nodes: list[HoleNodeResponse]
    total_distance: float
    node_count: int
    recommendations: list[SegmentRecommendation] = []
    # Closed ring of [lat, lon] pairs tracing the fairway corridor, for map display
    fairway_polygon: list[tuple[float, float]] = []
    # Hazard/OB areas drawn by course editors, for map display
    hazards: list[HazardResponse] = []

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