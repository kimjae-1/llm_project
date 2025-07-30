import asyncio
import json
from app.core.redis import redis_cache
from app.core.db.session import AsyncScopedSession
from app.models.db.chat_session import ChatSession
from sqlalchemy import select

SYNC_INTERVAL_SECONDS = 300  # 5분 주기

async def sync_redis_to_db_periodically():
    while True:
        keys = await redis_cache.redis.keys("chat:*")
        for key in keys:
            ttl = await redis_cache.redis.ttl(key)
            if ttl != -1 and ttl <= 300:  # TTL 5분 이하일 때
                key_str = key.decode()
                _, user_id, session_number = key_str.split(":")
                history = await redis_cache.get(key_str)

                async with AsyncScopedSession() as session:
                    stmt = select(ChatSession).where(
                        ChatSession.user_id == user_id,
                        ChatSession.session_number == int(session_number),
                    )
                    result = await session.execute(stmt)
                    chat_session = result.scalar_one_or_none()

                    if chat_session:
                        chat_session.messages = json.dumps(history, ensure_ascii=False)
                    else:
                        chat_session = ChatSession(
                            user_id=user_id,
                            session_number=int(session_number),
                            messages=json.dumps(history, ensure_ascii=False),
                        )
                        session.add(chat_session)

                    await session.commit()
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)
