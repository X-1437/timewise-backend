from dal.base import BaseMessageDAL, BaseSessionDAL
from models.message import Message, ToolCall


class MessageService:
    def __init__(self, message_dal: BaseMessageDAL, session_dal: BaseSessionDAL):
        self._message_dal = message_dal
        self._session_dal = session_dal

    async def create_user_message(
        self, *, session_id: str, content: str, file_id: str | None = None
    ) -> Message:
        msg = await self._message_dal.create(
            session_id=session_id,
            role="user",
            content=content,
            file_id=file_id,
        )
        await self._session_dal.touch(session_id)
        return msg

    async def create_assistant_message(
        self,
        *,
        session_id: str,
        content: str,
        tool_calls: list[ToolCall] | None = None,
        file_id: str | None = None,
    ) -> Message:
        msg = await self._message_dal.create(
            session_id=session_id,
            role="assistant",
            content=content,
            file_id=file_id,
            tool_calls=tool_calls,
        )
        await self._session_dal.touch(session_id)
        return msg

    async def list_by_session(self, session_id: str) -> list[Message]:
        return await self._message_dal.list_by_session(session_id)
