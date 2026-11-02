import logging
from sqlalchemy.exc import OperationalError
from app.main import app
from app.database import get_db
from app.logging_config import HealthCheckFilter


class BrokenSession:
    """Stands in for a database session whose connection is down."""
    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("database down"))


def test_health_db_down(client):
    app.dependency_overrides[get_db] = lambda: BrokenSession()
    response = client.get("/health")
    assert response.status_code == 503

def test_health_filter_drops_probe_lines():
    f = HealthCheckFilter()
    probe = logging.LogRecord("uvicorn.access", logging.INFO, "", 0,
                              '%s - "%s %s HTTP/%s" %d', ("10.42.0.1", "GET", "/health", "1.1", 200), None)
    real = logging.LogRecord("uvicorn.access", logging.INFO, "", 0,
                             '%s - "%s %s HTTP/%s" %d', ("10.42.0.1", "GET", "/courses", "1.1", 200), None)
    assert f.filter(probe) is False
    assert f.filter(real) is True

def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"