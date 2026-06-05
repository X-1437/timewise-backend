from datetime import datetime, timezone

from llm.client import LLMClient
from mcp_layer.client import MCPClient
from models.message import Message, ToolCall
from services.message_service import MessageService
from services.session_service import SessionService


class ChatService:
    def __init__(
        self,
        *,
        session_service: SessionService,
        message_service: MessageService,
        llm_client: LLMClient,
        mcp_client: MCPClient,
    ):
        self._session_service = session_service
        self._message_service = message_service
        self._llm_client = llm_client
        self._mcp_client = mcp_client

    async def send_message(
        self,
        *,
        content: str,
        session_id: str | None = None,
        file_id: str | None = None,
    ) -> tuple[str, Message]:
        session = None
        if session_id:
            session = await self._session_service.get(session_id)
        if session is None:
            session = await self._session_service.create()
            session_id = session.id

        await self._message_service.create_user_message(
            session_id=session_id, content=content, file_id=file_id
        )

        intent = self._llm_client.analyze_intent(content)
        tool_name = intent["tool"]
        tool_args = dict(intent["args"])

        tool_output = await self._mcp_client.call_tool(tool_name, tool_args)

        tool_call = ToolCall(
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_output,
            timestamp=datetime.now(timezone.utc),
        )

        assistant_content = tool_output
        assistant_msg = await self._message_service.create_assistant_message(
            session_id=session_id,
            content=assistant_content,
            tool_calls=[tool_call],
            file_id=file_id,
        )
        return session_id, assistant_msg
