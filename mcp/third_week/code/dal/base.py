from abc import ABC, abstractmethod
from typing import Any

from models.file import FileMeta
from models.message import Message, ToolCall
from models.session import Session


class BaseSessionDAL(ABC):
    @abstractmethod
    async def create(self, title: str | None = None) -> Session:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, session_id: str) -> Session | None:
        raise NotImplementedError

    @abstractmethod
    async def list(self) -> list[Session]:
        raise NotImplementedError

    @abstractmethod
    async def update_title(self, session_id: str, title: str) -> Session | None:
        raise NotImplementedError

    @abstractmethod
    async def touch(self, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        raise NotImplementedError


class BaseMessageDAL(ABC):
    @abstractmethod
    async def create(
        self,
        session_id: str,
        role: str,
        content: str,
        file_id: str | None = None,
        tool_calls: list[ToolCall] | None = None,
    ) -> Message:
        raise NotImplementedError

    @abstractmethod
    async def list_by_session(self, session_id: str) -> list[Message]:
        raise NotImplementedError


class BaseFileDAL(ABC):
    @abstractmethod
    async def create(
        self,
        filename: str,
        size: int,
        row_count: int,
        column_names: list[str],
        session_id: str | None = None,
    ) -> FileMeta:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, file_id: str) -> FileMeta | None:
        raise NotImplementedError

    @abstractmethod
    async def list(self) -> list[FileMeta]:
        raise NotImplementedError


class BaseTimeSeriesDAL(ABC):
    @abstractmethod
    async def insert_rows(
        self,
        *,
        file_id: str,
        rows: list[dict[str, Any]],
    ) -> int:
        raise NotImplementedError
