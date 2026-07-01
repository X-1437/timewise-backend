from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ToolCall(BaseModel):
    tool_name: str
    tool_args: dict[str, Any]
    tool_result: str
    timestamp: datetime
    data_version: str | None = None
    artifact_path: str | None = None
    warning_flags: list[str] | None = None


class AssistantAction(BaseModel):
    type: str
    id: str
    label: str
    tool_name: str
    tool_args: dict[str, Any]


class Message(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    timestamp: datetime
    file_id: str | None = None
    tool_calls: list[ToolCall] | None = None
    actions: list[AssistantAction] | None = None
