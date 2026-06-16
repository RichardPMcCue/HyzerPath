import json
import logging

from app.logging_config import JsonFormatter
from app.ratelimit import FixedWindowLimiter


def test_rate_limiter_allows_then_blocks():
    limiter = FixedWindowLimiter(max_requests=3, window_seconds=60)
    assert [limiter.allow("a") for _ in range(3)] == [True, True, True]
    assert limiter.allow("a") is False
    # a different key has its own window
    assert limiter.allow("b") is True


def test_rate_limiter_window_expiry():
    now = [1000.0]
    limiter = FixedWindowLimiter(max_requests=1, window_seconds=10)
    # monkeypatch the clock via time.monotonic indirection
    import app.ratelimit as rl

    orig = rl.time.monotonic
    rl.time.monotonic = lambda: now[0]
    try:
        assert limiter.allow("a") is True
        assert limiter.allow("a") is False
        now[0] += 11  # window passed
        assert limiter.allow("a") is True
    finally:
        rl.time.monotonic = orig


def test_json_formatter_includes_extra_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        "hyzerpath", logging.INFO, __file__, 1, "deploy triggered", (), None
    )
    record.ip = "203.0.113.5"
    record.status = 200
    out = json.loads(formatter.format(record))
    assert out["msg"] == "deploy triggered"
    assert out["level"] == "INFO"
    assert out["ip"] == "203.0.113.5"
    assert out["status"] == 200


def test_deploy_rejects_bad_token(client):
    # DEPLOY_SECRET unset in tests → any token is rejected, fail closed
    r = client.post("/deploy", headers={"X-Deploy-Token": "wrong"})
    assert r.status_code == 401


def test_deploy_rate_limited(client):
    from app.main import deploy_limiter

    deploy_limiter.reset()
    statuses = [
        client.post("/deploy", headers={"X-Deploy-Token": "wrong"}).status_code
        for _ in range(deploy_limiter.max_requests + 2)
    ]
    assert statuses.count(401) == deploy_limiter.max_requests
    assert statuses[-1] == 429
    deploy_limiter.reset()
