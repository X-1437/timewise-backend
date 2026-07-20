from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from dal.base import BaseFileDAL
from dal.mongodb.utils import id_to_str, to_object_id
from models.file import FileMeta


class FileDAL(BaseFileDAL):
    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db.files

    async def create(
        self,
        filename: str,
        size: int,
        row_count: int,
        column_names: list[str],
        session_id: str | None = None,
    ) -> FileMeta:
        now = datetime.now(timezone.utc)
        doc = {
            "filename": filename,
            "size": size,
            "rowCount": row_count,
            "columnNames": column_names,
            "uploadedAt": now,
            "sessionId": to_object_id(session_id) if session_id else None,
        }
        result = await self._col.insert_one(doc)
        return FileMeta(
            id=str(result.inserted_id),
            filename=filename,
            size=size,
            row_count=row_count,
            column_names=column_names,
            uploaded_at=now,
            session_id=session_id,
        )

    async def get_by_id(self, file_id: str) -> FileMeta | None:
        doc = await self._col.find_one({"_id": to_object_id(file_id)})
        if doc is None:
            return None
        return FileMeta(
            id=id_to_str(doc["_id"]) or "",
            filename=doc["filename"],
            size=doc["size"],
            row_count=doc["rowCount"],
            column_names=doc["columnNames"],
            uploaded_at=doc["uploadedAt"],
            session_id=id_to_str(doc.get("sessionId")),
        )

    async def list(self) -> list[FileMeta]:
        files: list[FileMeta] = []
        cursor = self._col.find({}).sort("uploadedAt", -1)
        async for doc in cursor:
            files.append(
                FileMeta(
                    id=id_to_str(doc["_id"]) or "",
                    filename=doc["filename"],
                    size=doc["size"],
                    row_count=doc["rowCount"],
                    column_names=doc["columnNames"],
                    uploaded_at=doc["uploadedAt"],
                    session_id=id_to_str(doc.get("sessionId")),
                )
            )
        return files
