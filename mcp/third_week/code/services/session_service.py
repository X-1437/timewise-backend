from dal.base import BaseSessionDAL
from models.session import Session


class SessionService:
    def __init__(self, session_dal: BaseSessionDAL):
        self._session_dal = session_dal

    async def create(self, title: str | None = None) -> Session:
        return await self._session_dal.create(title=title)

    async def list(self) -> list[Session]:
        return await self._session_dal.list()

    async def get(self, session_id: str) -> Session | None:
        return await self._session_dal.get_by_id(session_id)

    async def update_title(self, session_id: str, title: str) -> Session | None:
        return await self._session_dal.update_title(session_id, title)

    async def delete(self, session_id: str) -> bool:
        return await self._session_dal.delete(session_id)
