from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class Project(BaseModel):
    id: Optional[str] = None
    user_id: str
    name: str
    status: str = "draft"
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()


class DataConfig(BaseModel):
    time_column: Optional[str] = None
    target_column: Optional[str] = None
    configured_at: Optional[datetime] = None


class UploadedFile(BaseModel):
    id: str
    filename: str
    file_size: int
    format: str
    uploaded_at: datetime = datetime.utcnow()


class ProjectDetail(Project):
    data_file: Optional[UploadedFile] = None
    data_config: Optional[DataConfig] = None
    eda_result: Optional[Dict[str, Any]] = None
    preprocessing_result: Optional[Dict[str, Any]] = None
    features: Optional[List[Dict[str, Any]]] = []
    forecasts: Optional[List[Dict[str, Any]]] = []
    reports: Optional[List[Dict[str, Any]]] = []
