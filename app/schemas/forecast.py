from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ForecastRequest(BaseModel):
    method: str


class ForecastResult(BaseModel):
    id: str
    method: str
    metrics: Optional[Dict[str, float]] = None
    predictions: Optional[List[Dict[str, Any]]] = None
    chart_data: Optional[Dict[str, Any]] = None
    forecast_at: str
