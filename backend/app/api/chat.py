"""
Chat endpoint — SSE streaming via FastAPI StreamingResponse.
"""
import json
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.llm.agent import run_agent
from app.llm import memory as mem

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    highlighted_node_ids: list[str] = Field(default_factory=list)


@router.post("")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())

    async def event_stream():
        try:
            async for chunk in run_agent(req.message, session_id, req.highlighted_node_ids):
                # SSE format
                data = json.dumps({"chunk": chunk, "session_id": session_id})
                yield f"data: {data}\n\n"
        except Exception as exc:
            err = json.dumps({"chunk": f"\n[Error: {str(exc)}]", "session_id": session_id})
            yield f"data: {err}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/session/{session_id}")
def clear_session(session_id: str):
    mem.clear_session(session_id)
    return {"status": "cleared"}
