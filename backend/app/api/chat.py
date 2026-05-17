"""
星图智顾 - API 路由：对话（SSE 流式）
"""
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.agent.simple_agent import handle_message
from app.database import async_session
from app.models.analysis import Analysis
from app.schemas.chat import ChatRequest
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["对话"])


@router.post("/stream", summary="AI 对话（SSE 流式）")
async def chat_stream(req: ChatRequest):
    """
    接收用户消息，通过 MVP Agent 调用 skill 后以 SSE 流式返回。
    """

    async def event_generator():
        try:
            history = [item.model_dump() for item in req.history[-8:]]
            result = await handle_message(
                req.message,
                history=history,
                deep_mode=req.deep_mode,
                model_provider=req.model_provider,
            )

            meta = json.dumps(
                {"type": "meta", "skills_used": result.get("skills_used", [])},
                ensure_ascii=False,
            )
            yield f"data: {meta}\n\n"

            for char in result.get("text", ""):
                data = json.dumps({"type": "text", "content": char}, ensure_ascii=False)
                yield f"data: {data}\n\n"
                await asyncio.sleep(0.002)

            cards = json.dumps(
                {"type": "cards", "cards": result.get("cards", [])},
                ensure_ascii=False,
            )
            yield f"data: {cards}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

            async with async_session() as session:
                session.add(
                    Analysis(
                        title=req.message[:60] or "星图问策",
                        query=req.message,
                        response=result.get("text", ""),
                        skills_used=result.get("skills_used", []),
                        fund_codes=[],
                    )
                )
                await session.commit()

        except Exception as e:
            logger.error(f"对话流式输出错误: {e}")
            error_data = json.dumps(
                {"type": "error", "content": str(e)}, ensure_ascii=False
            )
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
