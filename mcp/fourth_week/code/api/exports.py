from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from dal.mongodb.utils import to_object_id


router = APIRouter(tags=["exports"])


async def _latest_artifact_path(
    request: Request,
    *,
    session_id: str,
    file_id: str,
    artifact_type: str,
) -> Path | None:
    db = request.app.state.db
    cursor = (
        db.artifacts.find(
            {
                "type": artifact_type,
                "sessionId": to_object_id(session_id),
                "fileId": to_object_id(file_id),
            }
        )
        .sort("createdAt", -1)
        .limit(1)
    )
    async for doc in cursor:
        p = doc.get("path")
        if p:
            return Path(p)
    return None


@router.get("/sessions/{session_id}/files/{file_id}/report/download")
async def download_report(request: Request, session_id: str, file_id: str):
    path = await _latest_artifact_path(
        request,
        session_id=session_id,
        file_id=file_id,
        artifact_type="report_markdown",
    )
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="REPORT_NOT_FOUND")
    return FileResponse(
        path,
        media_type="text/markdown; charset=utf-8",
        filename=path.name,
    )


@router.get("/sessions/{session_id}/files/{file_id}/preprocessed/download")
async def download_preprocessed(request: Request, session_id: str, file_id: str):
    path = await _latest_artifact_path(
        request,
        session_id=session_id,
        file_id=file_id,
        artifact_type="preprocessed_csv",
    )
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="PREPROCESSED_FILE_NOT_FOUND")
    return FileResponse(
        path,
        media_type="text/csv; charset=utf-8",
        filename=path.name,
    )

