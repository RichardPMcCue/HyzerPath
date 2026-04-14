import os
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from jose import jwt
from app.database import get_db
from app.models import User

async def get_current_user(authorization: str = Header(...), db: Session = Depends(get_db)):
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, os.environ.get("JWT_SECRET"), algorithms=["HS256"])
        user = db.query(User).filter(User.user_id == payload["user_id"]).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")