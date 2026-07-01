from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from dal.base import BaseTimeSeriesDAL
from dal.mongodb.utils import to_object_id


class TimeSeriesDAL(BaseTimeSeriesDAL):
    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db.time_series_data

    async def insert_rows(self, *, file_id: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0

        docs = []
        oid = to_object_id(file_id)
        for row in rows:
            metadata = dict(row.get("metadata") or {})
            metadata["fileId"] = oid
            doc = dict(row)
            doc["metadata"] = metadata
            docs.append(doc)

        result = await self._col.insert_many(docs)
        return len(result.inserted_ids)
