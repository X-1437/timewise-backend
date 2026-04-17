from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class TimeFeatureConfig(BaseModel):
    enabled: bool = False
    methods: Optional[List[str]] = []
    periods: Optional[List[str]] = []
    lags: Optional[List[int]] = []
    stats: Optional[List[str]] = []
    orders: Optional[List[Any]] = []


class FreqFeatureConfig(BaseModel):
    enabled: bool = False
    harmonics: Optional[int] = 5
    wavelet_type: Optional[str] = "db4"


class FeatureRequest(BaseModel):
    time_features: Optional[Dict[str, TimeFeatureConfig]] = None
    freq_features: Optional[Dict[str, FreqFeatureConfig]] = None


class FeatureResult(BaseModel):
    id: str
    config: Dict[str, Any]
    time_features: Optional[Dict[str, Any]] = None
    freq_features: Optional[Dict[str, Any]] = None
    charts: Optional[Dict[str, Any]] = None
    summary: Optional[Dict[str, Any]] = None
    extracted_at: str
