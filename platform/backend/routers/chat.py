from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import chat_engine

router = APIRouter(prefix="/api", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    agent_id: str
    messages: list[ChatMessage]


@router.get("/agents")
def get_agents():
    return {"agents": chat_engine.list_agents()}


@router.post("/chat")
def chat(req: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in req.messages]

    try:
        reply = chat_engine.run_turn(req.agent_id, history)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    return {"role": "assistant", "content": reply}
