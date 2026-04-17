from datetime import datetime
import uuid
import math
import pandas as pd
import numpy as np
from scipy import signal
from fastapi import APIRouter, HTTPException, Depends, Request
from bson import ObjectId
from app.database import get_db, read_data_from_timeseries
from app.core.security import decode_token


def sanitize_value(v):
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
    return v


def sanitize_dict(obj):
    if isinstance(obj, dict):
        return {k: sanitize_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_dict(item) for item in obj]
    else:
        return sanitize_value(obj)

try:
    from statsmodels.tsa.stattools import acf, pacf
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False

try:
    import pywt
    PYWT_AVAILABLE = True
except ImportError:
    PYWT_AVAILABLE = False

router = APIRouter(prefix="/projects/{project_id}/features", tags=["特征"])


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
async def get_feature_options(project_id: str, user_id: str = Depends(get_current_user_id)):
    return {
        "time_features": {
            "trend": ["linear", "poly", "ma"],
            "seasonal": ["hourly", "daily", "weekly", "monthly"],
            "autocorrelation": ["acf", "pacf", "partial"],
            "lag": list(range(1, 29)),
            "rolling": ["mean", "std", "max", "min", "median"],
            "differencing": [1, 2, "seasonal"]
        },
        "freq_features": {
            "fft": [3, 5, 10],
            "wavelet": ["haar", "db4", "sym4"],
            "psd": True,
            "spectrogram": True
        }
    }


@router.post("")
async def extract_features(
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
    if preprocessing_result:
        file_path = preprocessing_result.get("processed_file_path")
    else:
        data_file = project.get("data_file")
        if not data_file:
            raise HTTPException(status_code=404, detail="该项目没有数据文件")
        file_path = data_file.get("file_path")

    if not file_path:
        raise HTTPException(status_code=404, detail="该项目没有数据")

    data_config = project.get("data_config", {})
    target_column = data_config.get("target_column")
    file_format = data_config.get("format", "xlsx")
    
    if file_path.endswith('.csv'):
        file_format = 'csv'

    try:
        if file_format == "csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        print(f"读取数据文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"读取数据文件失败: {str(e)}")
    
    time_features = {}
    freq_features = {}
    charts = {}
    
    time_config = request.get("time_features", {})
    freq_config = request.get("freq_features", {})
    
    if target_column and target_column in df.columns:
        numeric_col = pd.to_numeric(df[target_column], errors="coerce").dropna()
        
        if time_config.get("trend", {}).get("enabled"):
            methods = time_config["trend"].get("methods", [])
            trend_results = {}
            
            if "linear" in methods:
                x = np.arange(len(numeric_col))
                coeffs = np.polyfit(x, numeric_col.values, 1)
                trend_results["linear"] = {"slope": float(coeffs[0]), "intercept": float(coeffs[1])}
            
            if "poly" in methods:
                x = np.arange(len(numeric_col))
                coeffs = np.polyfit(x, numeric_col.values, 2)
                trend_results["poly"] = {"coefficients": [float(c) for c in coeffs], "degree": 2}
            
            if "ma" in methods:
                ma = numeric_col.rolling(window=7, min_periods=1).mean()
                trend_results["ma"] = {"values": [float(v) for v in ma.values]}
            
            time_features["trend"] = trend_results
        
        if time_config.get("seasonal", {}).get("enabled"):
            periods = time_config["seasonal"].get("periods", [])
            seasonal_results = {}
            
            period_map = {
                "hourly": 24,
                "daily": 24,
                "weekly": 7,
                "monthly": 30
            }
            
            for period_name in periods:
                period = period_map.get(period_name, 24)
                period_data = numeric_col.values
                seasonal_component = np.zeros_like(period_data)
                
                for i in range(period, len(period_data)):
                    seasonal_component[i] = period_data[i] - period_data[i - period]
                
                mean_val = np.mean(period_data)
                seasonal_strength = 1 - np.var(seasonal_component) / (np.var(period_data) + 1e-10)
                
                seasonal_results[period_name] = {
                    "period": period,
                    "strength": float(np.clip(seasonal_strength, 0, 1)),
                    "values": [float(v) for v in seasonal_component[:100]]
                }
            
            time_features["seasonal"] = seasonal_results
        
        if time_config.get("autocorrelation", {}).get("enabled"):
            methods = time_config["autocorrelation"].get("methods", [])
            autocorr_results = {}
            nlags = min(20, len(numeric_col) - 1)
            
            if "acf" in methods:
                if STATSMODELS_AVAILABLE:
                    acf_values = acf(numeric_col.values, nlags=nlags, fft=True)
                else:
                    acf_values = np.correlate(numeric_col.values, numeric_col.values, mode='full')
                    acf_values = acf_values[len(acf_values)//2:nlags+1]
                    acf_values = acf_values / acf_values[0]
                autocorr_results["acf"] = [float(v) for v in acf_values[:nlags+1]]
            
            if "pacf" in methods:
                if STATSMODELS_AVAILABLE:
                    pacf_values = pacf(numeric_col.values, nlags=nlags)
                else:
                    pacf_values = np.zeros(nlags + 1)
                    pacf_values[0] = 1.0
                autocorr_results["pacf"] = [float(v) for v in pacf_values[:nlags+1]]
            
            if "partial" in methods:
                if STATSMODELS_AVAILABLE:
                    pacf_values = pacf(numeric_col.values, nlags=nlags)
                else:
                    pacf_values = np.zeros(nlags + 1)
                    pacf_values[0] = 1.0
                autocorr_results["partial"] = [float(v) for v in pacf_values[:nlags+1]]
            
            time_features["autocorrelation"] = autocorr_results
        
        if time_config.get("lag", {}).get("enabled"):
            lags = time_config["lag"].get("lags", [])
            lag_data = {}
            for lag in lags[:5]:
                lag_data[f"lag_{lag}"] = [float(v) for v in numeric_col.shift(lag).fillna(0).values]
            time_features["lag"] = lag_data
        
        if time_config.get("rolling", {}).get("enabled"):
            stats = time_config["rolling"].get("stats", [])
            rolling_results = {}
            for stat in stats:
                rolling_results[stat] = {"values": [float(v) for v in numeric_col.rolling(window=7, min_periods=1).agg(stat).values]}
            time_features["rolling"] = rolling_results
        
        if time_config.get("differencing", {}).get("enabled"):
            orders = time_config["differencing"].get("orders", [])
            diff_results = {}
            for order in orders:
                if isinstance(order, int):
                    diff_results[f"diff_{order}"] = [float(v) for v in numeric_col.diff(order).fillna(0).values]
                elif order == "seasonal":
                    period = 7
                    seasonal_diff = numeric_col.diff(period).fillna(0)
                    diff_results["seasonal"] = {"period": period, "values": [float(v) for v in seasonal_diff.values]}
            time_features["differencing"] = diff_results
        
        if freq_config.get("fft", {}).get("enabled"):
            harmonics = freq_config["fft"].get("harmonics", 5)
            fft = np.fft.fft(numeric_col.values)
            freq = np.fft.fftfreq(len(fft))
            magnitude = np.abs(fft)
            
            top_indices = np.argsort(magnitude)[-harmonics:]
            freq_features["fft"] = {
                "frequencies": [float(freq[i]) for i in top_indices],
                "magnitudes": [float(magnitude[i]) for i in top_indices]
            }
        
        if freq_config.get("wavelet", {}).get("enabled"):
            wavelet_type = freq_config["wavelet"].get("wavelet_type", "db4")
            wavelet_results = {}
            
            if PYWT_AVAILABLE:
                data = numeric_col.values
                max_level = min(3, pywt.dwt_max_level(len(data), pywt.Wavelet(wavelet_type).dec_len))
                
                coeffs = pywt.wavedec(data, wavelet_type, level=max_level)
                
                wavelet_results["levels"] = max_level
                wavelet_results["wavelet"] = wavelet_type
                wavelet_results["coefficients"] = {
                    "approximation": [float(v) for v in coeffs[0][:50]] if len(coeffs[0]) > 0 else [],
                    "details": [[float(v) for v in c[:50]] for c in coeffs[1:]] if len(coeffs) > 1 else []
                }
            else:
                wavelet_results["error"] = "PyWavelets library not available"
            
            freq_features["wavelet"] = wavelet_results
        
        if freq_config.get("psd", {}).get("enabled"):
            freqs, psd = signal.welch(numeric_col.values)
            freq_features["psd"] = {
                "frequencies": [float(f) for f in freqs[:20]],
                "power": [float(p) for p in psd[:20]]
            }
        
        if freq_config.get("spectrogram", {}).get("enabled"):
            fs = 1.0
            nperseg_val = max(2, min(256, len(numeric_col) // 4))
            f, t, sxx = signal.spectrogram(numeric_col.values, fs=fs, nperseg=nperseg_val)
            
            freq_features["spectrogram"] = {
                "frequencies": [float(fi) for fi in f[:20]],
                "times": [float(ti) for ti in t[:10]],
                "power": [[float(v) for v in row[:20]] for row in sxx[:10]]
            }
    
    feature_id = str(uuid.uuid4())

    # 生成分析摘要
    summary = {
        "total_time_features": len(time_features),
        "total_freq_features": len(freq_features),
        "enabled_features": {
            "trend": time_config.get("trend", {}).get("enabled", False),
            "seasonal": time_config.get("seasonal", {}).get("enabled", False),
            "autocorrelation": time_config.get("autocorrelation", {}).get("enabled", False),
            "lag": time_config.get("lag", {}).get("enabled", False),
            "rolling": time_config.get("rolling", {}).get("enabled", False),
            "differencing": time_config.get("differencing", {}).get("enabled", False),
            "fft": freq_config.get("fft", {}).get("enabled", False),
            "wavelet": freq_config.get("wavelet", {}).get("enabled", False),
            "psd": freq_config.get("psd", {}).get("enabled", False),
            "spectrogram": freq_config.get("spectrogram", {}).get("enabled", False),
        },
        "data_points_analyzed": len(numeric_col) if target_column and target_column in df.columns else 0,
        "target_column": target_column
    }

    feature_result = {
        "id": feature_id,
        "config": {"time_features": time_config, "freq_features": freq_config},
        "time_features": sanitize_dict(time_features),
        "freq_features": sanitize_dict(freq_features),
        "charts": charts,
        "summary": sanitize_dict(summary),
        "extracted_at": datetime.utcnow().isoformat()
    }
    
    existing_features = project.get("features", [])
    existing_features.append(feature_result)
    
    await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {
            "features": existing_features,
            "status": "feature_engineering",
            "updated_at": datetime.utcnow()
        }}
    )
    
    return feature_result


@router.get("/{feature_id}")
async def get_feature_result(project_id: str, feature_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    features = project.get("features", [])
    for f in features:
        if f.get("id") == feature_id:
            return f
    
    raise HTTPException(status_code=404, detail="特征结果不存在")
