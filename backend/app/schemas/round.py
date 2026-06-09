from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional

class RoundCreate(BaseModel):
    course_id: int

class RoundHoleScore(BaseModel):
    score: int

class RoundHoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hole_id: int
    score: int

class RoundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    round_id: int
    course_id: int
    bag_id: int
    played_at: datetime
    total_score: Optional[int] = None
    round_holes: list[RoundHoleResponse] = []

class RoundThrowCreate(BaseModel):
    throw_number: int
    disc_id: Optional[int] = None
    start_latitude: Optional[float] = None
    start_longitude: Optional[float] = None
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None
    landing_zone: Optional[str] = None  # basket | c1 | c2 | fairway | off_fairway | ob
    drop_zone: Optional[str] = None     # after OB: c1 | c2 | fairway | off_fairway | tee_pad
    putt_distance_ft: Optional[float] = None  # band midpoint from the putt-distance picker
    is_holed: bool = False

class RoundThrowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    round_throw_id: int
    round_id: int
    hole_id: int
    throw_number: int
    disc_id: Optional[int] = None
    distance_ft: Optional[float] = None
    landing_zone: Optional[str] = None
    drop_zone: Optional[str] = None
    is_holed: bool

class RoundStatsResponse(BaseModel):
    holes_with_throws: int
    c1_putts_made: int
    c1_putts_attempted: int
    c2_putts_made: int
    c2_putts_attempted: int
    fairway_hits: int
    fairway_attempts: int
    parked: int
