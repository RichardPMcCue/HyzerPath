from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional

class RoundCreate(BaseModel):
    course_id: int
    tracking_mode: str = "lies"  # discs | lies | detail | score
    layout: str = "full"         # full | front9 | back9

class RoundUpdate(BaseModel):
    tracking_mode: Optional[str] = None
    layout: Optional[str] = None

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
    tracking_mode: str = "lies"
    layout: str = "full"
    round_holes: list[RoundHoleResponse] = []

class RoundThrowCreate(BaseModel):
    throw_number: int
    disc_id: Optional[int] = None
    throw_style: Optional[str] = None  # 'backhand' | 'forehand'
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
    throw_style: Optional[str] = None
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


class LifetimeStatsResponse(BaseModel):
    """Aggregated career stats across all of the player's recorded rounds."""
    rounds_played: int
    holes_with_throws: int
    c1_putts_made: int
    c1_putts_attempted: int
    c1x_putts_made: int
    c1x_putts_attempted: int
    c2_putts_made: int
    c2_putts_attempted: int
    fairway_hits: int
    fairway_attempts: int
    parked: int
    gir_c1: int
    gir_c2: int
    gir_attempts: int
