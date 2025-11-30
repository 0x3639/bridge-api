from fastapi import APIRouter

from src.api.v1.auth import router as auth_router
from src.api.v1.bridge import router as bridge_router
from src.api.v1.orchestrators import router as orchestrators_router
from src.api.v1.statistics import router as statistics_router
from src.api.v1.users import router as users_router
from src.api.v1.websocket import router as websocket_router

api_router = APIRouter()

# Include all v1 routers
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(orchestrators_router)
api_router.include_router(statistics_router)
api_router.include_router(websocket_router)
api_router.include_router(bridge_router)
