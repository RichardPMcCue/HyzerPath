from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Disc
from app.schemas import DiscCreate, DiscResponse, DiscUpdate

router = APIRouter(prefix="/bag", tags=["bag"])

# Stub user until auth is implemented
STUB_USER_ID = 1

@router.get("/discs", response_model=list[DiscResponse])
async def get_discs(db: Session = Depends(get_db)):
    discs = db.query(Disc).filter(Disc.user_id == STUB_USER_ID).all()
    return discs


@router.post("/discs", response_model=DiscResponse)
async def create_disc(disc_in: DiscCreate, db: Session = Depends(get_db)):
    disc_dict = disc_in.model_dump()
    db_disc = Disc(
        user_id=STUB_USER_ID,
         **disc_dict
    )
    db.add(db_disc)
    db.commit()
    db.refresh(db_disc)
    return db_disc

@router.get("/discs/{disc_id}", response_model=DiscResponse)
async def get_disc(disc_id: int, db: Session = Depends(get_db)):
    disc = db.query(Disc).filter(
        Disc.disc_id == disc_id,
        Disc.user_id == STUB_USER_ID
    ).first()
    
    if disc is None:
        raise HTTPException(status_code=404, detail="Disc not found")
    
    return disc

@router.patch("/discs/{disc_id}", response_model=DiscResponse)
async def patch_disc(disc_in: DiscUpdate, disc_id: int, db: Session = Depends(get_db)):
    disc = db.query(Disc).filter(
        Disc.disc_id == disc_id,
        Disc.user_id == STUB_USER_ID
    ).first()
    
    if disc is None:
        raise HTTPException(status_code=404, detail="Disc not found")
    
    for key, value in disc_in.model_dump().items():
        if value is not None:
            setattr(disc, key, value)

    db.commit()
    db.refresh(disc)
    return disc

@router.delete("/discs/{disc_id}")
async def delete_disc(disc_id: int, db: Session = Depends(get_db)):
    disc = db.query(Disc).filter(
        Disc.disc_id == disc_id,
        Disc.user_id == STUB_USER_ID
    ).first()

    if disc is None:
        raise HTTPException(status_code=404, detail="Disc not found")
    
    db.delete(disc)
    db.commit()
    return {"message": "Disc deleted"}