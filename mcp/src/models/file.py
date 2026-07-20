from datetime import datetime

from pydantic import BaseModel


class FileMeta(BaseModel):
    id: str
    filename: str
    size: int
    row_count: int
    column_names: list[str]
    uploaded_at: datetime
    session_id: str | None = None
