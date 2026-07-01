import io
import re
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
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
async def download_report(request: Request, session_id: str, file_id: str, format: str = "zip"):
    path = await _latest_artifact_path(
        request,
        session_id=session_id,
        file_id=file_id,
        artifact_type="report_markdown",
    )
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="REPORT_NOT_FOUND")
    if format not in {"zip", "md"}:
        raise HTTPException(status_code=400, detail="INVALID_FORMAT")

    text = path.read_text(encoding="utf-8")

    if format == "md":
        base = str(request.base_url).rstrip("/")
        text = re.sub(r"\((/api/v1/)", f"({base}/api/v1/", text)
        text = re.sub(r"(:\s*)(/api/v1/)", rf"\g<1>{base}/api/v1/", text)
        return Response(
            content=text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
        )

    db = request.app.state.db

    img_pattern = re.compile(
        r"(?:https?://[^)\\s]+)?"
        + re.escape(f"/api/v1/sessions/{session_id}/files/{file_id}/images/")
        + r"([0-9a-fA-F]{24})/download"
    )
    image_ids = sorted(set(img_pattern.findall(text)))
    image_paths: dict[str, Path] = {}
    for image_id in image_ids:
        doc = await db.artifacts.find_one(
            {
                "_id": to_object_id(image_id),
                "type": "image_png",
                "sessionId": to_object_id(session_id),
                "fileId": to_object_id(file_id),
            }
        )
        if not doc:
            continue
        p = doc.get("path")
        if not p:
            continue
        pth = Path(str(p))
        if not pth.exists():
            continue
        image_paths[image_id] = pth

    preprocessed_path = await _latest_artifact_path(
        request,
        session_id=session_id,
        file_id=file_id,
        artifact_type="preprocessed_csv",
    )

    buf = io.BytesIO()
    zip_name = f"{path.stem}.zip"
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for image_id, pth in image_paths.items():
            arc = f"images/{pth.name}"
            z.write(pth, arcname=arc)
            text = re.sub(
                r"\((?:https?://[^\s)]+)?"
                + re.escape(f"/api/v1/sessions/{session_id}/files/{file_id}/images/{image_id}/download")
                + r"\)",
                f"(./{arc})",
                text,
            )

        if preprocessed_path is not None and preprocessed_path.exists():
            arc_csv = f"data/{preprocessed_path.name}"
            z.write(preprocessed_path, arcname=arc_csv)
            text = re.sub(
                r"(?:https?://[^\\s]+)?"
                + re.escape(f"/api/v1/sessions/{session_id}/files/{file_id}/preprocessed/download"),
                f"./{arc_csv}",
                text,
            )

        z.writestr(path.name, text)

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
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


@router.get("/sessions/{session_id}/files/{file_id}/images/{image_id}/download")
async def download_image(request: Request, session_id: str, file_id: str, image_id: str):
    db = request.app.state.db
    doc = await db.artifacts.find_one(
        {
            "_id": to_object_id(image_id),
            "type": "image_png",
            "sessionId": to_object_id(session_id),
            "fileId": to_object_id(file_id),
        }
    )
    if not doc:
        raise HTTPException(status_code=404, detail="IMAGE_NOT_FOUND")
    p = doc.get("path")
    if not p:
        raise HTTPException(status_code=404, detail="IMAGE_NOT_FOUND")
    path = Path(p)
    if not path.exists():
        raise HTTPException(status_code=404, detail="IMAGE_NOT_FOUND")
    return FileResponse(
        path,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )
