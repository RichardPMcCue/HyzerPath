import os
import subprocess
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from dotenv import load_dotenv
from app.routers import bag, auth, course, throws, rounds

load_dotenv()

app = FastAPI(
    title="HyzerPath API",
    description="Intelligent disc golf caddie",
    version="0.1.0",
    swagger_ui_parameters={"persistAuthorization": True},
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
async def deploy(x_deploy_token: str = Header(...)):
    secret = os.environ.get("DEPLOY_SECRET")
    if secret != x_deploy_token:
        raise HTTPException(status_code=401, detail="Deploy Token does not match")

    app_dir = os.environ.get("APP_DIR", "/home/hyzerpath/hyzerpath")
    subprocess.run(
        ["git", "-C", app_dir, "pull", "origin", "main"],
        check=True
    )
    # Detached (new session) so the systemctl restart inside the script
    # doesn't kill the deploy halfway through.
    subprocess.Popen(
        ["bash", f"{app_dir}/infra/deploy.sh"],
        env={**os.environ, "APP_DIR": app_dir},
        start_new_session=True,
    )
    return {"message": "Deploy started"}