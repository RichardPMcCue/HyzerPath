import os
import httpx
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from jose import jwt
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

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

    db.commit()
    db.refresh(user)

    payload = {
        "user_id": user.user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7)
    }
    token = jwt.encode(payload, os.environ.get("JWT_SECRET"), algorithm="HS256")

    return RedirectResponse(url=f"{os.environ.get('FRONTEND_URL')}?token={token}")