from pydantic import BaseModel, ConfigDict
from typing import Optional

class HoleCreate(BaseModel):
    hole_number: int
    par: int
    distance: int
    elevation: int

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