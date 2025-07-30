from fastapi import APIRouter
from app.routers.chat_session import router as chat_session_router

router = APIRouter()

router.include_router(chat_session_router, prefix="/chat_session")
