from pydantic import BaseModel
from typing import Optional, List


class ReportRequest(BaseModel):
    modules: Optional[List[str]] = ["overview", "eda", "preprocessing", "features", "forecast"]


class ReportResponse(BaseModel):
    report_id: str
    download_url: str
