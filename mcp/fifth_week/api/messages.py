from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from typing import Any

from api.deps import get_chat_service, get_message_service
from api.response import ok


router = APIRouter(tags=["messages"])


class ClientAction(BaseModel):
    type: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None


class SendMessageBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    content: str
    session_id: str | None = None
    file_id: str | None = Field(default=None, alias="fileId")
    action: ClientAction | None = None


@router.get("/sessions/{session_id}/messages")
async def list_messages(request: Request, session_id: str):
    service = get_message_service(request)
    msgs = await service.list_by_session(session_id)
    return ok([m.model_dump() for m in msgs])


@router.post("/chat/messages")
async def send_message(request: Request, body: SendMessageBody):
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="EMPTY_MESSAGE")
    chat_service = get_chat_service(request)
    session_id, msg = await chat_service.send_message(
        content=body.content,
        session_id=body.session_id,
        file_id=body.file_id,
        action=body.action.model_dump() if body.action else None,
    )
    payload = msg.model_dump()
    payload["session_id"] = session_id
    return ok(payload)
