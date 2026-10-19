from fastapi import APIRouter, Depends

from backend.dependencies import get_chat_service
from backend.errors import not_found
from backend.schemas import ChatRequest, ChatResponse
from backend.services.chat import ChatService

router = APIRouter(tags=["chat"])


# Plain `def` (not async): plan_trip blocks on Gemini, so FastAPI runs it in a thread pool.
@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, service: ChatService = Depends(get_chat_service)) -> dict:
    """Send a user message (Arabic or English). Returns the agent's reply and, when
    status == "planned", the structured itinerary. Send the returned session_id with
    the next message so answers to clarifying questions ("3 days") are understood."""
    return service.chat(body.message, body.session_id)


@router.get("/sessions/{session_id}")
def get_session(session_id: str, service: ChatService = Depends(get_chat_service)) -> dict:
    session = service.sessions.get(session_id)
    if session is None:
        raise not_found(f"No session {session_id!r} (it may have expired)")
    return {"session_id": session.id, "history": session.history,
            "awaiting_clarification": session.pending_request is not None}


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, service: ChatService = Depends(get_chat_service)) -> None:
    if not service.sessions.delete(session_id):
        raise not_found(f"No session {session_id!r}")
