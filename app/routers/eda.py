from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from bson import ObjectId
import pandas as pd
import numpy as np
from app.database import get_db, read_data_from_timeseries
from app.core.security import decode_token
from app.config import settings

router = APIRouter(prefix="/projects/{project_id}/eda", tags=["EDA"])


async def get_current_user_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权")
    
    token = auth_header.replace("Bearer ", "")
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="无效的Token")
    
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的Token")
    
    return user_id


@router.get("")
async def get_eda(project_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    if not project.get("data_file"):
        raise HTTPException(status_code=404, detail="该项目没有上传数据")
    
    file_path = project["data_file"]["file_path"]
    data_config = project.get("data_config", {})
    target_column = data_config.get("target_column")
    
    try:
        if project["data_file"]["format"] == "csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取数据文件失败: {str(e)}")
    
    total_rows = len(df)
    total_columns = len(df.columns)
    
    missing_values = {}
    for col in df.columns:
        missing_count = df[col].isnull().sum()
        missing_rate = (missing_count / total_rows * 100) if total_rows > 0 else 0
        missing_values[col] = {
            "count": int(missing_count),
            "rate": float(missing_rate)
        }
    
    total_missing = sum(v["count"] for v in missing_values.values())
    total_missing_rate = (total_missing / (total_rows * total_columns) * 100) if total_rows > 0 and total_columns > 0 else 0
    
    outliers = {}
    if target_column and target_column in df.columns:
        numeric_col = pd.to_numeric(df[target_column], errors="coerce").dropna()
        if len(numeric_col) > 0:
            mean = numeric_col.mean()
            std = numeric_col.std()
            outlier_count = ((numeric_col - mean).abs() > 3 * std).sum()
            outliers["count"] = int(outlier_count)
            outliers["method"] = "zscore"
    
    duplicates = int(df.duplicated().sum())
    
    statistics = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            statistics[col] = {
                "mean": float(df[col].mean()) if not df[col].isnull().all() else 0,
                "median": float(df[col].median()) if not df[col].isnull().all() else 0,
                "std": float(df[col].std()) if not df[col].isnull().all() else 0,
                "min": float(df[col].min()) if not df[col].isnull().all() else 0,
                "max": float(df[col].max()) if not df[col].isnull().all() else 0
            }
    
    time_range = {}
    if data_config.get("time_column") and data_config["time_column"] in df.columns:
        time_col = pd.to_datetime(df[data_config["time_column"]], errors="coerce").dropna()
        if len(time_col) > 0:
            time_range["start"] = time_col.min().isoformat()
            time_range["end"] = time_col.max().isoformat()
    
    trend_data = []
    if target_column and target_column in df.columns:
        numeric_col = pd.to_numeric(df[target_column], errors="coerce").dropna()
        if len(numeric_col) > 0:
            step = max(1, len(numeric_col) // 100)
            trend_data = numeric_col.iloc[::step].tolist()
    
    eda_result = {
        "total_rows": total_rows,
        "total_columns": total_columns,
        "time_range": time_range,
        "missing_values": {
            "total_rate": total_missing_rate,
            "by_column": missing_values
        },
        "outliers": outliers,
        "duplicates": duplicates,
        "statistics": statistics,
        "trend_data": trend_data
    }
    
    await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {
            "eda_result": eda_result,
            "updated_at": datetime.utcnow()
        }}
    )
    
    return eda_result
