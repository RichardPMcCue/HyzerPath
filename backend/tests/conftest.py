import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db
from app.models import Base, User
from jose import jwt
from datetime import datetime, timedelta
import os

TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    test_user = User(user_id=1, email="test@test.com", google_id="test_google_id", name="Test")
    db.add(test_user)
    db.commit()
    db.close()

    token = jwt.encode(
        {"user_id": 1, "exp": datetime.utcnow() + timedelta(days=1)},
        os.environ.get("JWT_SECRET"),
        algorithm="HS256"
    )

    yield TestClient(app, headers={"Authorization": f"Bearer {token}"})
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()