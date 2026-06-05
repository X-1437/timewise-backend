from fastapi import Request

from dal.mongodb.file_dal import FileDAL
from dal.mongodb.message_dal import MessageDAL
from dal.mongodb.session_dal import SessionDAL
from dal.mongodb.time_series_dal import TimeSeriesDAL
from llm.client import LLMClient
from mcp_layer.client import MCPClient
from services.chat_service import ChatService
from services.file_service import FileService
from services.message_service import MessageService
from services.session_service import SessionService


def get_session_service(request: Request) -> SessionService:
    db = request.app.state.db
    return SessionService(SessionDAL(db))


def get_message_service(request: Request) -> MessageService:
    db = request.app.state.db
    return MessageService(MessageDAL(db), SessionDAL(db))


def get_file_service(request: Request) -> FileService:
    db = request.app.state.db
    return FileService(FileDAL(db), TimeSeriesDAL(db))


def get_chat_service(request: Request) -> ChatService:
    db = request.app.state.db
    mcp_client: MCPClient = request.app.state.mcp_client
    session_service = SessionService(SessionDAL(db))
    message_service = MessageService(MessageDAL(db), SessionDAL(db))
    llm_client = LLMClient()
    return ChatService(
        session_service=session_service,
        message_service=message_service,
        llm_client=llm_client,
        mcp_client=mcp_client,
    )
