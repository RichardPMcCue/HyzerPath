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
