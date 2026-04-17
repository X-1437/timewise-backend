from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ProjectCreate(BaseModel):
    name: str


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    sample_values: List[str] = []


class DataConfigure(BaseModel):
    time_column: str
    target_column: str


class DataConfigureResponse(BaseModel):
    time_column: str
    target_column: str
    configured_at: str
