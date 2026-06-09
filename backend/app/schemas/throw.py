from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional

class ThrowSessionCreate(BaseModel):
    start_latitude: float
    start_longitude: float
    label: Optional[str] = None

class ThrowSessionUpdate(BaseModel):
    """Re-mark the start point (e.g. moved up the tee pad) or rename."""
    start_latitude: Optional[float] = None
    start_longitude: Optional[float] = None
    label: Optional[str] = None

class ThrowCreate(BaseModel):
    end_latitude: float
    end_longitude: float
    disc_id: Optional[int] = None

class ThrowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    throw_id: int
    session_id: int
    disc_id: Optional[int] = None
    end_latitude: float
    end_longitude: float
    distance_ft: float
    created_at: datetime

class ThrowSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    label: Optional[str] = None
    start_latitude: float
    start_longitude: float
    created_at: datetime
    throws: list[ThrowResponse] = []
