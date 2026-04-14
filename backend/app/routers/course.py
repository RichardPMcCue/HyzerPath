from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Course, User, Hole
from app.schemas import CourseCreate, CourseResponse, CourseUpdate, HoleCreate, HoleResponse
from app.dependencies import get_current_user

router = APIRouter(prefix="/courses", tags=["course"])

@router.post("/{course_id}/holes", response_model=HoleResponse)
async def create_hole(course_id: int, hole_in: HoleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    hole_dict = hole_in.model_dump()
    hole_dict["course_id"] = course_id
    hole_dict["is_approved"] = False
    db_hole = Hole(**hole_dict)
    db.add(db_hole)
    db.commit()
    db.refresh(db_hole)
    return db_hole

@router.get("", response_model=list[CourseResponse])
async def get_courses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    courses = db.query(Course).filter(Course.is_approved == True).all()
    return courses


@router.post("", response_model=CourseResponse)
async def create_course(course_in: CourseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course_dict = course_in.model_dump()
    course_dict["is_approved"] = False
    db_course = Course(
         **course_dict
    )
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course

@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    
    return course

@router.patch("/{course_id}", response_model=CourseResponse)
async def patch_courses(course_in: CourseUpdate, course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    
    for key, value in course_in.model_dump().items():
        if value is not None:
            setattr(course, key, value)

    db.commit()
    db.refresh(course)
    return course

@router.delete("/{course_id}")
async def delete_courses(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    course = db.query(Course).filter(Course.course_id == course_id).first()

    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    
    db.delete(course)
    db.commit()
    return {"message": "Course deleted"}