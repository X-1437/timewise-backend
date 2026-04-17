from datetime import datetime
import uuid
import pandas as pd
import numpy as np
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from bson import ObjectId
from app.database import get_db, read_data_from_timeseries
from app.core.security import decode_token

router = APIRouter(prefix="/projects/{project_id}/forecast", tags=["预测"])


async def get_current_user_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权")
    
    token = auth_header.replace("Bearer ", "")
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="无效的Token")
    
    return payload.get("user_id", "")


@router.get("/options")
async def get_forecast_options(project_id: str, user_id: str = Depends(get_current_user_id)):
    return {
        "methods": [
            {"key": "next_row", "name": "隔行平移预测", "description": "用第n行的值作为第n+1行的预测值"},
            {"key": "same_time", "name": "相隔天平移预测", "description": "用昨天同一时间点的值当作今天同一时间点的预测值"},
            {"key": "daily_sum", "name": "按天累加后隔行预测", "description": "把目标列按天累加后，用上一天的值当作下一天的预测值"}
        ]
    }


@router.post("")
async def run_forecast(
    project_id: str,
    request: dict,
    user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    preprocessing_result = project.get("preprocessing_result")
    data_file = project.get("data_file")
    if preprocessing_result:
        file_path = preprocessing_result.get("processed_file_path")
    elif data_file:
        file_path = data_file.get("file_path")
    else:
        file_path = None

    if not file_path:
        raise HTTPException(status_code=404, detail="该项目没有数据")

    data_config = project.get("data_config", {})
    target_column = data_config.get("target_column")
    file_format = data_file.get("format", "xlsx") if data_file else "xlsx"

    try:
        if file_format == "csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        print(f"读取数据文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"读取数据文件失败: {str(e)}")
    
    method = request.get("method", "next_row")
    
    if not target_column or target_column not in df.columns:
        raise HTTPException(status_code=400, detail="目标列不存在")
    
    numeric_col = pd.to_numeric(df[target_column], errors="coerce").dropna()
    values = numeric_col.values
    
    predictions = []
    actuals = []
    
    if method == "next_row":
        for i in range(1, len(values)):
            predictions.append(float(values[i - 1]))
            actuals.append(float(values[i]))
    elif method == "same_time":
        for i in range(7, len(values)):
            predictions.append(float(values[i - 7]))
            actuals.append(float(values[i]))
    elif method == "daily_sum":
        daily_sums = []
        for i in range(7, len(values)):
            day_sum = np.sum(values[i-7:i])
            daily_sums.append(day_sum)
        
        for i in range(1, len(daily_sums)):
            predictions.append(float(daily_sums[i - 1]))
            actuals.append(float(daily_sums[i]))
    else:
        raise HTTPException(status_code=400, detail="不支持的预测方法")
    
    predictions = np.array(predictions)
    actuals = np.array(actuals)
    
    mae = float(np.mean(np.abs(actuals - predictions)))
    mse = float(np.mean((actuals - predictions) ** 2))
    rmse = float(np.sqrt(mse))
    mape = float(np.mean(np.abs((actuals - predictions) / np.where(actuals == 0, 1, actuals))) * 100)
    
    metrics = {
        "mae": mae,
        "mse": mse,
        "rmse": rmse,
        "mape": mape
    }
    
    pred_data = []
    for i in range(len(predictions)):
        pred_data.append({
            "actual": float(actuals[i]),
            "predicted": float(predictions[i])
        })
    
    forecast_id = str(uuid.uuid4())
    forecast_result = {
        "id": forecast_id,
        "method": method,
        "metrics": metrics,
        "predictions": pred_data,
        "forecast_at": datetime.utcnow().isoformat()
    }
    
    existing_forecasts = project.get("forecasts", [])
    existing_forecasts.append(forecast_result)
    
    await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {
            "forecasts": existing_forecasts,
            "status": "forecasting",
            "updated_at": datetime.utcnow()
        }}
    )
    
    return forecast_result


@router.get("/download")
async def download_forecast(project_id: str, forecast_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    forecasts = project.get("forecasts", [])
    forecast = None
    for f in forecasts:
        if f.get("id") == forecast_id:
            forecast = f
            break
    
    if not forecast:
        raise HTTPException(status_code=404, detail="预测结果不存在")
    
    predictions = forecast.get("predictions", [])
    
    import io
    csv_data = "actual,predicted\n"
    for p in predictions:
        csv_data += f"{p.get('actual', 0)},{p.get('predicted', 0)}\n"
    
    return FileResponse(
        io.BytesIO(csv_data.encode()),
        media_type="text/csv",
        filename="forecast_results.csv"
    )
