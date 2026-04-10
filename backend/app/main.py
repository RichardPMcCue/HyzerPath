import os
import subprocess
from fastapi import FastAPI, Header, HTTPException
from dotenv import load_dotenv
from app.routers import bag

load_dotenv()
app = FastAPI()
app.include_router(bag.router)


@app.post("/deploy")
async def deploy(x_deploy_token: str = Header(...)):
    # 1. Get DEPLOY_SECRET from environment
    secret = os.environ.get("DEPLOY_SECRET")

    # 2. Compare x_deploy_token against secret
    # If they don't match, raise HTTPException with status 401
    if secret != x_deploy_token:
        raise HTTPException(
            status_code=401,
            detail="Deploy Token does not match",
        )

    # 3. Run git pull
    subprocess.run(
        ["git", "-C", "/home/hyzerpath/hyzerpath", "pull", "origin", "main"],
        check=True
    )

    # 4. Restart the service
    subprocess.Popen(
        ["sudo", "systemctl", "restart", "hyzerpath"],
    )

    # 5. Return success
    return {"message": "Deploy successful"}