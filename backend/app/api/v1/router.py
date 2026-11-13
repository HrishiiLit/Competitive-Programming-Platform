from fastapi import APIRouter
from app.api.v1.auth import router as auth_router

api_v1_router = APIRouter(prefix="/api/v1")

# Mount sub-routers
api_v1_router.include_router(auth_router)


@api_v1_router.get("/health", tags=["Health"])
async def v1_health():
    return {
        "status": "healthy",
        "api_version": "v1",
    }
