from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from dal.base import BaseMessageDAL
from dal.mongodb.utils import id_to_str, to_object_id
from models.message import Message, ToolCall


class MessageDAL(BaseMessageDAL):
    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db.messages

    async def create(
        self,
        session_id: str,
        role: str,
        content: str,
        file_id: str | None = None,
        tool_calls: list[ToolCall] | None = None,
    ) -> Message:
        now = datetime.now(timezone.utc)
        doc = {
            "sessionId": to_object_id(session_id),
            "role": role,
            "content": content,
            "timestamp": now,
            "fileId": to_object_id(file_id) if file_id else None,
            "toolCalls": [tc.model_dump() for tc in tool_calls] if tool_calls else None,
        }
        result = await self._col.insert_one(doc)
        return Message(
            id=str(result.inserted_id),
            session_id=session_id,
            role=role,
            content=content,
            timestamp=now,
            file_id=file_id,
            tool_calls=tool_calls,
        )

    async def list_by_session(self, session_id: str) -> list[Message]:
        messages: list[Message] = []
        cursor = self._col.find({"sessionId": to_object_id(session_id)}).sort("timestamp", 1)
        async for doc in cursor:
            tool_calls = None
            if doc.get("toolCalls"):
                tool_calls = [ToolCall(**tc) for tc in doc["toolCalls"]]
            messages.append(
                Message(
                    id=id_to_str(doc["_id"]) or "",
                    session_id=id_to_str(doc["sessionId"]) or "",
                    role=doc["role"],
                    content=doc["content"],
                    timestamp=doc["timestamp"],
                    file_id=id_to_str(doc.get("fileId")),
                    tool_calls=tool_calls,
                )
            )
        return messages
