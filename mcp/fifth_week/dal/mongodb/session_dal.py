from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from dal.base import BaseSessionDAL
from dal.mongodb.utils import id_to_str, to_object_id
from models.session import Session


class SessionDAL(BaseSessionDAL):
    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db.sessions

    async def create(self, title: str | None = None) -> Session:
        now = datetime.now(timezone.utc)
        doc = {
            "title": title or "新会话",
            "createdAt": now,
            "updatedAt": now,
        }
        result = await self._col.insert_one(doc)
        return Session(
            id=str(result.inserted_id),
            title=doc["title"],
            created_at=doc["createdAt"],
            updated_at=doc["updatedAt"],
        )

    async def get_by_id(self, session_id: str) -> Session | None:
        doc = await self._col.find_one({"_id": to_object_id(session_id)})
        if doc is None:
            return None
        return Session(
            id=id_to_str(doc["_id"]) or "",
            title=doc["title"],
            created_at=doc["createdAt"],
            updated_at=doc["updatedAt"],
        )

    async def list(self) -> list[Session]:
        sessions: list[Session] = []
        cursor = self._col.find({}).sort("updatedAt", -1)
        async for doc in cursor:
            sessions.append(
                Session(
                    id=id_to_str(doc["_id"]) or "",
                    title=doc["title"],
                    created_at=doc["createdAt"],
                    updated_at=doc["updatedAt"],
                )
            )
        return sessions

    async def update_title(self, session_id: str, title: str) -> Session | None:
        now = datetime.now(timezone.utc)
        doc = await self._col.find_one_and_update(
            {"_id": to_object_id(session_id)},
            {"$set": {"title": title, "updatedAt": now}},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            return None
        return Session(
            id=id_to_str(doc["_id"]) or "",
            title=doc["title"],
            created_at=doc["createdAt"],
            updated_at=doc["updatedAt"],
        )

    async def touch(self, session_id: str) -> None:
        now = datetime.now(timezone.utc)
        await self._col.update_one(
            {"_id": to_object_id(session_id)},
            {"$set": {"updatedAt": now}},
        )

    async def delete(self, session_id: str) -> bool:
        result = await self._col.delete_one({"_id": to_object_id(session_id)})
        return result.deleted_count > 0
