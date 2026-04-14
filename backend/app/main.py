import os
import subprocess
from fastapi import FastAPI, Header, HTTPException
from fastapi.security import HTTPBearer
from dotenv import load_dotenv
from app.routers import bag, auth, course

load_dotenv()

app = FastAPI(
    title="HyzerPath API",
    description="Intelligent disc golf caddie",
    version="0.1.0",
    swagger_ui_parameters={"persistAuthorization": True},
)

security = HTTPBearer()

app.include_router(bag.router)
app.include_router(auth.router)
app.include_router(course.router)

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
    subprocess.run(
        ["git", "-C", "/home/hyzerpath/hyzerpath", "pull", "origin", "main"],
        check=True
    )
    subprocess.Popen(["sudo", "systemctl", "restart", "hyzerpath"])
    return {"message": "Deploy successful"}