from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from api.deps import get_file_service
from api.response import ok


router = APIRouter(tags=["files"])


@router.post("/files/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="INVALID_FILE_TYPE")
    raw = await file.read()
    service = get_file_service(request)
    file_meta, inserted = await service.ingest_csv(
        filename=file.filename, raw_bytes=raw, session_id=session_id
    )
    payload = file_meta.model_dump()
    payload["inserted_rows"] = inserted
    return ok(payload)


@router.get("/files")
async def list_files(request: Request):
    service = get_file_service(request)
    files = await service.list_files()
    return ok([f.model_dump() for f in files])
