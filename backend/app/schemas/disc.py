from pydantic import BaseModel, ConfigDict
from typing import Optional
from enum import Enum

class DiscType(str, Enum):
    putter = "putter"
    midrange = "midrange"
    fairway_driver = "fairway_driver"
    distance_driver = "distance_driver"

class DiscCreate(BaseModel):
    name: str
    manufacturer: str
    disc_type: Optional[DiscType] = None
    color: Optional[str] = None
    speed: Optional[float] = None
    glide: Optional[float] = None
    turn: Optional[float] = None
    fade: Optional[float] = None
    wear: Optional[float] = None
    weight: Optional[int] = None

class DiscResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    disc_id: int
    name: str
    manufacturer: str
    disc_type: Optional[DiscType] = None
    color: Optional[str] = None
    speed: Optional[float] = None
    glide: Optional[float] = None
    turn: Optional[float] = None
    fade: Optional[float] = None
    wear: Optional[float] = None
    weight: Optional[int] = None

class DiscStatUpsert(BaseModel):
    avg_distance: int
    max_distance: Optional[int] = None
    sample_size: Optional[int] = None
    throw_style: str = "backhand"  # 'backhand' | 'forehand'

class DiscStatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stat_id: int
    disc_id: int
    throw_style: str = "backhand"
    avg_distance: int
    max_distance: Optional[int] = None
    sample_size: Optional[int] = None

class DiscUpdate(BaseModel):
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    disc_type: Optional[DiscType] = None
    color: Optional[str] = None
    speed: Optional[float] = None
    glide: Optional[float] = None
    turn: Optional[float] = None
    fade: Optional[float] = None
    wear: Optional[float] = None
    weight: Optional[int] = None