from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.contests import router as contests_router
from app.api.v1.internal import router as internal_router
from app.api.v1.problems import router as problems_router
from app.api.v1.submissions import router as submissions_router

api_v1_router = APIRouter(prefix="/api/v1")

# Mount sub-routers
api_v1_router.include_router(auth_router)
api_v1_router.include_router(contests_router)
api_v1_router.include_router(problems_router)
api_v1_router.include_router(submissions_router)
api_v1_router.include_router(internal_router)


@api_v1_router.get("/health", tags=["Health"])
async def v1_health():
    return {
        "status": "healthy",
        "api_version": "v1",
    }
