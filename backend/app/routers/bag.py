from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import httpx

from app.database import get_db
from app.models import BagDisc, Disc, DiscCatalog, ThrowMeasurement, User, UserDiscStat
from app.schemas import DiscCreate, DiscResponse, DiscUpdate, DiscStatUpsert, DiscStatResponse
from app.utils import map_discit_category, parse_float
from app.dependencies import get_current_user

DISCIT_API = "https://discit-api.fly.dev/disc"

router = APIRouter(prefix="/bag", tags=["bag"])


def catalog_to_result(row: DiscCatalog) -> dict:
    """Shape a cached catalog row like a DiscIt API result."""
    return {
        "id": row.discit_id,
        "name": row.name,
        "brand": row.brand,
        "category": row.category,
        "speed": row.speed,
        "glide": row.glide,
        "turn": row.turn,
        "fade": row.fade,
        "stability": row.stability,
        "link": row.link,
        "pic": row.pic,
        "color": row.color,
        "background_color": row.background_color,
        "disc_type": map_discit_category(row.category, parse_float(row.speed)),
    }


@router.get("/discs/search")
async def search_discs(
    name: Optional[str] = None,
    brand: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if name is None and brand is None:
        raise HTTPException(status_code=400, detail="Empty Query")

    # Cache-first: serve from our own catalog and only hit the external
    # DiscIt API on a miss, so repeated searches don't hammer their service.
    cache_query = db.query(DiscCatalog)
    if name:
        cache_query = cache_query.filter(DiscCatalog.name.ilike(f"%{name}%"))
    if brand:
        cache_query = cache_query.filter(DiscCatalog.brand.ilike(f"%{brand}%"))
    cached = cache_query.order_by(DiscCatalog.name).limit(25).all()
    if cached:
        return [catalog_to_result(row) for row in cached]

    params = {}
    if name:
        params["name"] = name
    if brand:
        params["brand"] = brand

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(DISCIT_API, params=params, timeout=10)
            response.raise_for_status()
            discs = response.json()
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=503, detail="External API call failed")

    for disc in discs:
        disc["disc_type"] = map_discit_category(disc["category"], parse_float(disc.get("speed")))

    # Upsert results into the catalog for next time
    catalog_fields = (
        "name", "brand", "category", "speed", "glide", "turn", "fade",
        "stability", "link", "pic", "color", "background_color",
    )
    for disc in discs:
        discit_id = disc.get("id")
        if not discit_id or not disc.get("name"):
            continue
        row = db.query(DiscCatalog).filter(DiscCatalog.discit_id == discit_id).first()
        if row is None:
            row = DiscCatalog(discit_id=discit_id)
            db.add(row)
        for field in catalog_fields:
            setattr(row, field, disc.get(field))
    db.commit()

    return discs


@router.get("/discs", response_model=list[DiscResponse])
async def get_discs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    discs = db.query(Disc).filter(Disc.user_id == current_user.user_id).all()
    return discs


@router.post("/discs", response_model=DiscResponse)
async def create_disc(disc_in: DiscCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    disc_dict = disc_in.model_dump()
    # disc_type is NOT NULL in the DB — infer from speed rather than 500
    if disc_dict.get("disc_type") is None:
        disc_dict["disc_type"] = map_discit_category("", disc_dict.get("speed")) or "putter"
    db_disc = Disc(
        user_id=current_user.user_id,
         **disc_dict
    )
    db.add(db_disc)
    db.commit()
    db.refresh(db_disc)
    return db_disc

@router.get("/stats", response_model=list[DiscStatResponse])
async def get_disc_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(UserDiscStat).filter(UserDiscStat.user_id == current_user.user_id).all()


@router.put("/discs/{disc_id}/stats", response_model=DiscStatResponse)
async def upsert_disc_stat(
    disc_id: int,
    stat_in: DiscStatUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    disc = db.query(Disc).filter(
        Disc.disc_id == disc_id,
        Disc.user_id == current_user.user_id
    ).first()
    if disc is None:
        raise HTTPException(status_code=404, detail="Disc not found")

    if stat_in.throw_style not in ("backhand", "forehand"):
        raise HTTPException(status_code=400, detail="throw_style must be backhand or forehand")

    stat = db.query(UserDiscStat).filter(
        UserDiscStat.user_id == current_user.user_id,
        UserDiscStat.disc_id == disc_id,
        UserDiscStat.throw_style == stat_in.throw_style
    ).first()

    if stat is None:
        stat = UserDiscStat(
            user_id=current_user.user_id, disc_id=disc_id, throw_style=stat_in.throw_style
        )
        db.add(stat)

    stat.avg_distance = stat_in.avg_distance
    stat.max_distance = stat_in.max_distance
    stat.sample_size = stat_in.sample_size

    db.commit()
    db.refresh(stat)
    return stat


@router.delete("/discs/{disc_id}/stats")
async def delete_disc_stat(disc_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    stat = db.query(UserDiscStat).filter(
        UserDiscStat.user_id == current_user.user_id,
        UserDiscStat.disc_id == disc_id
    ).first()
    if stat is None:
        raise HTTPException(status_code=404, detail="No stats for this disc")

    db.delete(stat)
    db.commit()
    return {"message": "Disc stats deleted"}


@router.get("/discs/{disc_id}", response_model=DiscResponse)
async def get_disc(disc_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    disc = db.query(Disc).filter(
        Disc.disc_id == disc_id,
        Disc.user_id == current_user.user_id
    ).first()
    
    if disc is None:
        raise HTTPException(status_code=404, detail="Disc not found")
    
    return disc

@router.patch("/discs/{disc_id}", response_model=DiscResponse)
async def patch_disc(disc_in: DiscUpdate, disc_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    disc = db.query(Disc).filter(
        Disc.disc_id == disc_id,
        Disc.user_id == current_user.user_id
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
async def delete_disc(disc_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    disc = db.query(Disc).filter(
        Disc.disc_id == disc_id,
        Disc.user_id == current_user.user_id
    ).first()

    if disc is None:
        raise HTTPException(status_code=404, detail="Disc not found")

    # Clean up dependents first: stats and bag links go, measured throws keep
    # their distance but lose the disc reference
    db.query(UserDiscStat).filter(UserDiscStat.disc_id == disc_id).delete()
    db.query(BagDisc).filter(BagDisc.disc_id == disc_id).delete()
    db.query(ThrowMeasurement).filter(ThrowMeasurement.disc_id == disc_id).update({"disc_id": None})
    from app.models import RoundThrow
    db.query(RoundThrow).filter(RoundThrow.disc_id == disc_id).update({"disc_id": None})

    db.delete(disc)
    db.commit()
    return {"message": "Disc deleted"}