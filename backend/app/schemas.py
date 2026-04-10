from pydantic import BaseModel
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

    class Config:
        from_attributes = True 

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