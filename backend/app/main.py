import logging
import os
import subprocess
import time
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from dotenv import load_dotenv
from app.logging_config import configure_logging
from app.ratelimit import FixedWindowLimiter, client_ip
from app.routers import bag, auth, course, throws, rounds

load_dotenv()
configure_logging()
logger = logging.getLogger("hyzerpath")

# Brute-force guard on the deploy token. Generous enough to never block a real
# deploy (one POST on push to main), tight enough that guessing the token is
# hopeless. Overridable via env for testing.
deploy_limiter = FixedWindowLimiter(
    max_requests=int(os.environ.get("DEPLOY_RATE_LIMIT", "10")),
    window_seconds=float(os.environ.get("DEPLOY_RATE_WINDOW", "60")),
)

app = FastAPI(
    title="HyzerPath API",
    description="Intelligent disc golf caddie",
    version="0.1.0",
    swagger_ui_parameters={"persistAuthorization": True},
    # In prod nginx serves this app under /api, so Swagger must fetch the spec
    # from /api/openapi.json. Set ROOT_PATH=/api on the server; unset locally.
    root_path=os.environ.get("ROOT_PATH", ""),
)

# The SvelteKit frontend runs on a different origin
cors_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One structured line per request: method, path, status, latency."""
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.exception(
            "request failed",
            extra={"method": request.method, "path": request.url.path, "duration_ms": duration_ms},
        )
        raise
    duration_ms = round((time.monotonic() - start) * 1000, 1)
    logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


security = HTTPBearer()

app.include_router(bag.router)
app.include_router(auth.router)
app.include_router(course.router)
app.include_router(throws.router)
app.include_router(rounds.router)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer"}
    }
    for path in schema["paths"].values():
        for operation in path.values():
            operation["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.post("/deploy")
async def deploy(request: Request, x_deploy_token: str = Header(...)):
    ip = client_ip(request)
    if not deploy_limiter.allow(ip):
        logger.warning("deploy rate-limited", extra={"ip": ip})
        raise HTTPException(status_code=429, detail="Too many deploy attempts")

    secret = os.environ.get("DEPLOY_SECRET")
    if not secret or secret != x_deploy_token:
        logger.warning("deploy token rejected", extra={"ip": ip})
        raise HTTPException(status_code=401, detail="Deploy Token does not match")

    logger.info("deploy triggered", extra={"ip": ip})
    app_dir = os.environ.get("APP_DIR", "/home/hyzerpath/hyzerpath")
    try:
        subprocess.run(
            ["git", "-C", app_dir, "pull", "origin", "main"],
            check=True
        )
    except subprocess.CalledProcessError:
        logger.exception("deploy git pull failed", extra={"ip": ip})
        raise HTTPException(status_code=500, detail="git pull failed")
    # Detached (new session) so the systemctl restart inside the script
    # doesn't kill the deploy halfway through.
    subprocess.Popen(
        ["bash", f"{app_dir}/infra/deploy.sh"],
        env={**os.environ, "APP_DIR": app_dir},
        start_new_session=True,
    )
    return {"message": "Deploy started"}