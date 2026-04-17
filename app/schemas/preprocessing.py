from pydantic import BaseModel
from typing import Optional, Dict, Any


class ResamplingConfig(BaseModel):
    enabled: bool = False
    freq: Optional[str] = "1d"


class MissingValueConfig(BaseModel):
    enabled: bool = False
    method: Optional[str] = "linear"


class OutlierConfig(BaseModel):
    enabled: bool = False
    method: Optional[str] = "zscore"
    handling: Optional[str] = "smooth"


class NoiseConfig(BaseModel):
    enabled: bool = False
    filter: Optional[str] = "moving_avg"


class PreprocessingRequest(BaseModel):
    resampling: Optional[ResamplingConfig] = None
    missing_value: Optional[MissingValueConfig] = None
    outlier: Optional[OutlierConfig] = None
    noise: Optional[NoiseConfig] = None


class PreprocessingResult(BaseModel):
    id: str
    config: Dict[str, Any]
    metrics: Dict[str, Any]
    processed_at: str
