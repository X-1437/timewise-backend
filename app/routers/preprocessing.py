from datetime import datetime
import uuid
import pandas as pd
import numpy as np
import os

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from bson import ObjectId
from app.database import get_db, save_data_to_timeseries
from app.core.security import decode_token
from app.schemas.preprocessing import PreprocessingRequest

router = APIRouter(prefix="/projects/{project_id}/preprocessing", tags=["预处理"])


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
async def get_preprocessing_options(project_id: str, user_id: str = Depends(get_current_user_id)):
    return {
        "resampling": ["15min", "1h", "1d", "1w", "1M", "1y"],
        "resampling_methods": ["mean", "sum", "max", "min", "count", "first", "last"],
        "missing_value": ["linear", "mean", "forward", "backward", "spline", "knn", "median"],
        "outlier_detection": ["zscore", "iqr", "mad", "isolation"],
        "outlier_handling": ["remove", "smooth", "clip", "flag"],
        "noise_filter": ["moving_avg", "ewma", "kalman", "savgol", "wavelet"]
    }


@router.post("")
async def execute_preprocessing(
    project_id: str,
    request: PreprocessingRequest,
    user_id: str = Depends(get_current_user_id)
):
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

    original_rows = len(df)
    config = {}
    metrics = {
        "original_rows": original_rows,
        "processed_rows": original_rows,
        "missing_filled": 0,
        "outliers_handled": 0,
        "outliers_flagged": 0
    }

    # 数据重采样
    if request.resampling and request.resampling.enabled:
        freq_map = {
            "15min": "15T", "1h": "H", "1d": "D", "1w": "W", "1M": "M", "1y": "Y"
        }
        freq = freq_map.get(request.resampling.freq, "D")

        # 获取聚合方法，默认为mean
        agg_method = getattr(request.resampling, 'method', 'mean') if hasattr(request.resampling, 'method') else 'mean'

        if data_config.get("time_column") and data_config["time_column"] in df.columns:
            df[data_config["time_column"]] = pd.to_datetime(df[data_config["time_column"]], errors="coerce")
            df = df.set_index(data_config["time_column"])
            # 只对数值列进行重采样
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                if agg_method == "mean":
                    df_numeric = df[numeric_cols].resample(freq).mean()
                elif agg_method == "sum":
                    df_numeric = df[numeric_cols].resample(freq).sum()
                elif agg_method == "max":
                    df_numeric = df[numeric_cols].resample(freq).max()
                elif agg_method == "min":
                    df_numeric = df[numeric_cols].resample(freq).min()
                elif agg_method == "count":
                    df_numeric = df[numeric_cols].resample(freq).count()
                elif agg_method == "first":
                    df_numeric = df[numeric_cols].resample(freq).first()
                elif agg_method == "last":
                    df_numeric = df[numeric_cols].resample(freq).last()
                else:
                    df_numeric = df[numeric_cols].resample(freq).mean()
                df = df_numeric.reset_index()
            else:
                df = df.reset_index()

        config["resampling"] = {"enabled": True, "freq": request.resampling.freq, "method": agg_method}

    # 缺失值插补
    if request.missing_value and request.missing_value.enabled:
        method = request.missing_value.method

        for col in df.columns:
            if df[col].isnull().any():
                missing_count = df[col].isnull().sum()

                if method == "linear":
                    df[col] = df[col].interpolate(method="linear")
                elif method == "mean":
                    df[col] = df[col].fillna(df[col].mean())
                elif method == "median":
                    df[col] = df[col].fillna(df[col].median())
                elif method == "forward":
                    df[col] = df[col].ffill()
                elif method == "backward":
                    df[col] = df[col].bfill()
                elif method == "spline":
                    df[col] = df[col].interpolate(method="spline", order=3)
                elif method == "knn":
                    # KNN插补
                    from sklearn.impute import KNNImputer
                    numeric_cols = df.select_dtypes(include=[np.number]).columns
                    if col in numeric_cols:
                        imputer = KNNImputer(n_neighbors=3)
                        df[numeric_cols] = imputer.fit_transform(df[numeric_cols])

                metrics["missing_filled"] += int(missing_count)

        config["missing_value"] = {"enabled": True, "method": method}

    # 异常值检测和处理
    if request.outlier and request.outlier.enabled:
        method = request.outlier.method
        handling = request.outlier.handling

        if target_column and target_column in df.columns:
            numeric_col = pd.to_numeric(df[target_column], errors="coerce")

            if method == "zscore":
                mean = numeric_col.mean()
                std = numeric_col.std()
                outliers = (numeric_col - mean).abs() > 3 * std
            elif method == "iqr":
                q1 = numeric_col.quantile(0.25)
                q3 = numeric_col.quantile(0.75)
                iqr = q3 - q1
                outliers = (numeric_col < q1 - 1.5 * iqr) | (numeric_col > q3 + 1.5 * iqr)
            elif method == "mad":
                # MAD (Median Absolute Deviation) 绝对中位差
                median = numeric_col.median()
                mad = (numeric_col - median).abs().median()
                # MAD的缩放因子约为1.4826，使其与标准差一致
                scaled_mad = mad * 1.4826
                # 使用3倍MAD作为阈值
                outliers = (numeric_col - median).abs() > 3 * scaled_mad
            elif method == "isolation":
                # 孤立森林
                from sklearn.ensemble import IsolationForest
                # 准备数据，去除NaN
                valid_idx = numeric_col.notna()
                valid_data = numeric_col[valid_idx].values.reshape(-1, 1)

                if len(valid_data) > 0:
                    iso_forest = IsolationForest(contamination=0.1, random_state=42)
                    predictions = iso_forest.fit_predict(valid_data)
                    # -1 表示异常值
                    outlier_mask = pd.Series(False, index=df.index)
                    outlier_mask[valid_idx] = predictions == -1
                    outliers = outlier_mask
                else:
                    outliers = pd.Series([False] * len(df))
            else:
                outliers = pd.Series([False] * len(numeric_col))

            outlier_count = outliers.sum()

            if handling == "remove":
                df = df[~outliers]
            elif handling == "smooth":
                df.loc[outliers, target_column] = numeric_col[~outliers].mean()
            elif handling == "clip":
                mean = numeric_col[~outliers].mean()
                std = numeric_col[~outliers].std()
                df.loc[outliers, target_column] = mean + 3 * std
            elif handling == "flag":
                # 仅标记不处理，添加标记列
                df['outlier_flag'] = outliers.astype(int)
                metrics["outliers_flagged"] = int(outlier_count)

            metrics["outliers_handled"] = int(outlier_count)

        config["outlier"] = {"enabled": True, "method": method, "handling": handling}

    # 噪声处理
    if request.noise and request.noise.enabled:
        filter_type = request.noise.filter

        if target_column and target_column in df.columns:
            numeric_col = pd.to_numeric(df[target_column], errors="coerce").copy()

            if filter_type == "moving_avg":
                df[target_column] = numeric_col.rolling(window=3, min_periods=1).mean()
            elif filter_type == "ewma":
                df[target_column] = numeric_col.ewm(span=3, min_periods=1).mean()
            elif filter_type == "savgol":
                from scipy.signal import savgol_filter
                values = numeric_col.fillna(0).values
                if len(values) > 5:
                    df[target_column] = savgol_filter(values, 5, 2)
            elif filter_type == "kalman":
                # 卡尔曼滤波
                try:
                    from filterpy.kalman import KalmanFilter
                    values = numeric_col.fillna(method='ffill').fillna(method='bfill').values

                    kf = KalmanFilter(dim_x=1, dim_z=1)
                    kf.x = np.array([values[0]])  # 初始状态
                    kf.F = np.array([[1.]])       # 状态转移矩阵
                    kf.H = np.array([[1.]])       # 观测矩阵
                    kf.P *= 1.                    # 协方差矩阵
                    kf.R = 1.                     # 观测噪声
                    kf.Q = 0.01                   # 过程噪声

                    filtered_values = []
                    for z in values:
                        kf.predict()
                        kf.update(np.array([z]))
                        filtered_values.append(kf.x[0])

                    df[target_column] = filtered_values
                except ImportError:
                    # 如果没有安装filterpy，使用简化版本
                    values = numeric_col.fillna(method='ffill').fillna(method='bfill').values
                    # 简化的卡尔曼滤波实现
                    n = len(values)
                    filtered = np.zeros(n)
                    filtered[0] = values[0]
                    P = 1.0
                    Q = 0.01  # 过程噪声
                    R = 1.0   # 观测噪声

                    for i in range(1, n):
                        # 预测
                        P = P + Q
                        # 更新
                        K = P / (P + R)
                        filtered[i] = filtered[i-1] + K * (values[i] - filtered[i-1])
                        P = (1 - K) * P

                    df[target_column] = filtered
            elif filter_type == "wavelet":
                # 小波去噪
                try:
                    import pywt
                    values = numeric_col.fillna(method='ffill').fillna(method='bfill').values
                    # 使用db4小波进行3层分解
                    coeffs = pywt.wavedec(values, 'db4', level=3)
                    # 对细节系数进行阈值处理
                    threshold = np.std(coeffs[-1]) * np.sqrt(2 * np.log(len(values)))
                    coeffs[1:] = [pywt.threshold(c, threshold, mode='soft') for c in coeffs[1:]]
                    # 重构信号
                    denoised = pywt.waverec(coeffs, 'db4')
                    df[target_column] = denoised[:len(values)]
                except ImportError:
                    # 如果没有安装pywt，使用移动平均替代
                    df[target_column] = numeric_col.rolling(window=5, min_periods=1).mean()

        config["noise"] = {"enabled": True, "filter": filter_type}

    metrics["processed_rows"] = len(df)

    processed_dir = "uploads/processed"
    os.makedirs(processed_dir, exist_ok=True)

    processed_file_id = str(uuid.uuid4())
    processed_file_path = f"{processed_dir}/{processed_file_id}.csv"
    df.to_csv(processed_file_path, index=False)

    preprocessing_id = str(uuid.uuid4())
    preprocessing_result = {
        "id": preprocessing_id,
        "config": config,
        "metrics": metrics,
        "processed_file_path": processed_file_path,
        "processed_at": datetime.utcnow().isoformat()
    }

    await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {
            "preprocessing_result": preprocessing_result,
            "status": "preprocessing",
            "updated_at": datetime.utcnow()
        }}
    )

    preview_rows = min(100, len(df))
    preview_data = df.head(preview_rows).values.tolist()
    preview_columns = df.columns.tolist()
    
    return {
        "id": preprocessing_id,
        "config": config,
        "metrics": metrics,
        "processed_at": preprocessing_result["processed_at"],
        "preview": preview_data,
        "columns": preview_columns
    }


@router.get("/download")
async def download_preprocessed_data(project_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()

    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    preprocessing_result = project.get("preprocessing_result")
    if not preprocessing_result:
        raise HTTPException(status_code=404, detail="该项目没有预处理结果")

    file_path = preprocessing_result.get("processed_file_path")
    if not file_path or not os.path.exists(file_path):
        file_path = project["data_file"]["file_path"]

    return FileResponse(
        file_path,
        media_type="text/csv",
        filename="processed_data.csv"
    )
