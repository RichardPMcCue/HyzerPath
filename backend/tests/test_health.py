from sqlalchemy.exc import OperationalError
from app.main import app
from app.database import get_db


class BrokenSession:
    """Stands in for a database session whose connection is down."""
    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("database down"))


def test_health_db_down(client):
    app.dependency_overrides[get_db] = lambda: BrokenSession()
    response = client.get("/health")
    assert response.status_code == 503


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"