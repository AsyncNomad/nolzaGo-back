from fastapi import APIRouter

from app.api.v1.endpoints import auth, chat, health, maps, posts, memories

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(posts.router)
api_router.include_router(memories.router)
api_router.include_router(chat.router)
api_router.include_router(maps.router)
