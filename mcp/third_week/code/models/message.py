from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ToolCall(BaseModel):
    tool_name: str
    tool_args: dict[str, Any]
    tool_result: str
    timestamp: datetime


class Message(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    timestamp: datetime
    file_id: str | None = None
    tool_calls: list[ToolCall] | None = None
