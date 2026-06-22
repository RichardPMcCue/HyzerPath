from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional

class ThrowSessionCreate(BaseModel):
    start_latitude: float
    start_longitude: float

class ThrowCreate(BaseModel):
    end_latitude: float
    end_longitude: float
    disc_id: Optional[int] = None
    throw_style: Optional[str] = None  # 'backhand' | 'forehand'

class ThrowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    throw_id: int
    session_id: int
    disc_id: Optional[int] = None
    throw_style: Optional[str] = None
    end_latitude: float
    end_longitude: float
    distance_ft: float
    created_at: datetime

class ThrowSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    start_latitude: float
    start_longitude: float
    created_at: datetime
    throws: list[ThrowResponse] = []
