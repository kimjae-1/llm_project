# app/db/session.py

from asyncio import current_task
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    async_scoped_session,
    create_async_engine,
)
# from app.core.db.session import AsyncScopedSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs

from app.core.config import config

# ✅ DeclarativeBase 정의 (ORM 모델 작성 시 상속)
class Base(AsyncAttrs, DeclarativeBase):
    pass

# ✅ 비동기 엔진 생성 (커넥션 풀 세팅 포함)
engine = create_async_engine(
    config.DATABASE_URL,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
)

# ✅ 세션 팩토리
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ✅ 코루틴 단위 세션 스코프 설정
AsyncScopedSession = async_scoped_session(
    async_session_factory,
    scopefunc=current_task,
)

# ✅ FastAPI 종속성 주입용 get_db()
async def get_db():
    async with AsyncScopedSession() as session:
        yield session

# ✅ DB 연결 확인용 (헬스 체크)
async def ping_db():
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

# ✅ DB 연결 종료 (앱 종료 시)
async def close_db():
    await engine.dispose()

# ✅ DB 테이블 초기화 (앱 시작 시)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
