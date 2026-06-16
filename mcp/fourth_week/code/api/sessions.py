from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.deps import get_session_service
from api.response import ok


router = APIRouter(tags=["sessions"])


class CreateSessionBody(BaseModel):
    title: str | None = None


class UpdateSessionBody(BaseModel):
    title: str


@router.post("/sessions")
async def create_session(request: Request, body: CreateSessionBody):
    service = get_session_service(request)
    session = await service.create(title=body.title)
    return ok(session.model_dump())


@router.get("/sessions")
async def list_sessions(request: Request):
    service = get_session_service(request)
    sessions = await service.list()
    return ok([s.model_dump() for s in sessions])


@router.get("/sessions/{session_id}")
async def get_session(request: Request, session_id: str):
    service = get_session_service(request)
    session = await service.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
    return ok(session.model_dump())


@router.put("/sessions/{session_id}")
async def update_session(request: Request, session_id: str, body: UpdateSessionBody):
    service = get_session_service(request)
    session = await service.update_title(session_id, body.title)
    if session is None:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
    return ok(session.model_dump())


@router.delete("/sessions/{session_id}")
async def delete_session(request: Request, session_id: str):
    service = get_session_service(request)
    deleted = await service.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
    return ok({"deleted": True})
