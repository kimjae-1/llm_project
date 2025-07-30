from uuid import uuid4
from typing import List

from fastapi import APIRouter
from sqlalchemy import select, insert, update, delete
import json
from fastapi import Request


from app.core.db.session import AsyncScopedSession
from app.models.schemas.common import BaseResponse, HttpResponse
from app.models.schemas.chat_session import ChatRequest, ChatResponse
from app.core.redis import redis_cache, key_builder
from app.models.db.chat_session import ChatSession
from app.core.graph import CancerRagAgent



router = APIRouter()

@router.post("/rag", response_model=BaseResponse[ChatResponse])
async def rag_answer(request : Request,
    request_body: ChatRequest,
    ) -> BaseResponse[ChatResponse]:
    
    # Redis 키 생성 
    cache_key = key_builder("chat", request_body.user_id, request_body.session_number)
    
    if await redis_cache.exists(cache_key):
        history_json = await redis_cache.get(cache_key)
        history = json.loads(history_json)  # 문자열을 리스트로 변환
    else:
        # DB에서 조회할 때도 메시지가 문자열이면 json.loads 처리 필요
        async with AsyncScopedSession() as session:
            stmt = (
                select(ChatSession.messages)
                .where(ChatSession.user_id == request_body.user_id)
                .where(ChatSession.session_number == request_body.session_number)
            )
            result = await session.execute(stmt)
            messages = result.scalar_one_or_none()
            if messages:
                if isinstance(messages, str):
                    history = json.loads(messages)  # 문자열 → 리스트
                else:
                    history = messages
            else:
                history = []
    
    # print(f'inital history : {history}')
    
    client = request.app.state.openai_client
    vectorstore = request.app.state.vectorstore 
    
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    
    agent = CancerRagAgent(client, retriever)
    
    initial_state = {
    "query": request_body.question,
    "history": history
    }

    result = await agent.get_response(initial_state)   
    
    answer = result.get("final_answer", "")
    if not answer:
        for msg in result.get("update", []):
            if (
                isinstance(msg, dict)
                and msg.get("role") == "assistant"
                and msg.get("content")
            ):
                fallback_content = msg["content"]
                answer = (
                    "※ 이 답변은 문서 기반 검색 결과가 아닌 모델의 일반적인 응답입니다.\n\n"
                    + fallback_content
                )
                break
    
    # result['update'] 메시지들을 순차적으로 추가
    for message in result["update"]:
        if hasattr(message, "model_dump"):
            message = message.model_dump()
        history.append(message)
    
    
    # Redis에 다시 저장 (json.dumps로 문자열 직렬화)
    await redis_cache.set(cache_key, json.dumps(history, ensure_ascii=False))
    
    # DB에도 업데이트
    async with AsyncScopedSession() as session:
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == request_body.user_id)
            .where(ChatSession.session_number == request_body.session_number)
        )
        result = await session.execute(stmt)
        existing_session = result.scalar_one_or_none()

        if existing_session:
            # 기존 메시지 업데이트
            update_stmt = (
                update(ChatSession)
                .where(ChatSession.user_id == request_body.user_id)
                .where(ChatSession.session_number == request_body.session_number)
                .values(messages=json.dumps(history, ensure_ascii=False))
            )
            await session.execute(update_stmt)
        else:
            # 새로 삽입
            insert_stmt = insert(ChatSession).values(
                user_id=request_body.user_id,
                session_number=request_body.session_number,
                messages=json.dumps(history, ensure_ascii=False)
            )
            await session.execute(insert_stmt)

        await session.commit()

    return HttpResponse(
        content=ChatResponse(
            final_message=answer
        )
    )

