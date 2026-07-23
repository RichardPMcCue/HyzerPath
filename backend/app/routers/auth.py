import os
import httpx
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from jose import jwt
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from app.database import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models import User, UserThrowStyle

router = APIRouter(prefix="/auth", tags=["auth"])


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    name: str | None = None
    username: str | None = None
    estimated_drive_ft: int | None = None
    is_admin: bool | None = None


class MeUpdate(BaseModel):
    username: str | None = None
    estimated_drive_ft: int | None = None


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=MeResponse)
async def update_me(
    update: MeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if update.username is not None:
        username = update.username.strip()
        if not (2 <= len(username) <= 30):
            raise HTTPException(status_code=400, detail="Username must be 2-30 characters")
        taken = db.query(User).filter(
            User.username == username, User.user_id != current_user.user_id
        ).first()
        if taken is not None:
            raise HTTPException(status_code=409, detail="Username is already taken")
        current_user.username = username

    if update.estimated_drive_ft is not None:
        drive = update.estimated_drive_ft
        if not (100 <= drive <= 800):
            raise HTTPException(status_code=400, detail="Drive distance must be 100-800 ft")
        current_user.estimated_drive_ft = drive

    db.commit()
    db.refresh(current_user)
    return current_user


class ThrowStyleRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    throw_type: str  # 'backhand' | 'forehand'
    hand: str  # 'right' | 'left'
    priority: int = 1  # 1 = primary; equal priorities = no preference


@router.get("/me/throw-styles", response_model=list[ThrowStyleRow])
async def get_throw_styles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(UserThrowStyle).filter(
        UserThrowStyle.user_id == current_user.user_id
    ).order_by(UserThrowStyle.priority).all()


@router.put("/me/throw-styles", response_model=list[ThrowStyleRow])
async def set_throw_styles(
    rows: list[ThrowStyleRow],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not 1 <= len(rows) <= 2:
        raise HTTPException(status_code=400, detail="Provide one or two throw styles")
    if len({r.throw_type for r in rows}) != len(rows):
        raise HTTPException(status_code=400, detail="Duplicate throw style")
    for r in rows:
        if r.throw_type not in ("backhand", "forehand"):
            raise HTTPException(status_code=400, detail="throw_type must be backhand or forehand")
        if r.hand not in ("right", "left"):
            raise HTTPException(status_code=400, detail="hand must be right or left")

    db.query(UserThrowStyle).filter(
        UserThrowStyle.user_id == current_user.user_id
    ).delete()
    for r in rows:
        db.add(UserThrowStyle(
            user_id=current_user.user_id,
            throw_type=r.throw_type,
            hand=r.hand,
            priority=r.priority,
        ))
    db.commit()
    return db.query(UserThrowStyle).filter(
        UserThrowStyle.user_id == current_user.user_id
    ).order_by(UserThrowStyle.priority).all()


class UserAdminUpdate(BaseModel):
    is_admin: bool


@router.get("/users", response_model=list[MeResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    return db.query(User).order_by(User.user_id).all()


@router.patch("/users/{user_id}", response_model=MeResponse)
async def set_user_admin(
    user_id: int,
    update: UserAdminUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    if user_id == current_user.user_id and not update.is_admin:
        raise HTTPException(status_code=400, detail="You cannot remove your own admin access")

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_admin = update.is_admin
    db.commit()
    db.refresh(user)
    return user

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


@router.get("/login")
async def login():
    params = {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
        "redirect_uri": os.environ.get("REDIRECT_URI"),
        "response_type": "code",
        "scope": "openid email profile",
    }
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/callback")
async def callback(code: str, db: Session = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        token_response = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "redirect_uri": os.environ.get("REDIRECT_URI"),
            "grant_type": "authorization_code",
        })
        token_response.raise_for_status()
        id_token = token_response.json()["id_token"]

    identity = jwt.decode(
        id_token,
        key="",
        options={
            "verify_signature": False,
            "verify_aud": False,
            "verify_at_hash": False,
        }
    )

    user = db.query(User).filter(User.google_id == identity["sub"]).first()
    if user is None:
        user = User(
            google_id=identity["sub"],
            email=identity["email"],
            name=identity["name"],
        )
        db.add(user)
    else:
        user.name = identity["name"]
        user.email = identity["email"]

    # Emails listed in ADMIN_EMAILS (comma-separated) are promoted on login
    admin_emails = {
        e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
    }
    if user.email.lower() in admin_emails:
        user.is_admin = True

    db.commit()
    db.refresh(user)

    payload = {
        "user_id": user.user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7)
    }
    token = jwt.encode(payload, os.environ.get("JWT_SECRET"), algorithm="HS256")

    return RedirectResponse(url=f"{os.environ.get('FRONTEND_URL')}?token={token}")