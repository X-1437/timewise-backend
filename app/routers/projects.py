from datetime import datetime
from typing import Optional, List
import os
import uuid
import io
import math


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

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Request
from fastapi.responses import FileResponse
from bson import ObjectId
from app.database import get_db, save_data_to_timeseries, read_data_from_timeseries
from app.core.security import decode_token
from app.schemas.project import ProjectCreate, ProjectUpdate, ColumnInfo, DataConfigure, DataConfigureResponse
from app.config import settings

router = APIRouter(prefix="/projects", tags=["项目"])


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
async def get_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    
    skip = (page - 1) * page_size
    cursor = db.projects.find({"user_id": user_id}).skip(skip).limit(page_size)
    projects = await cursor.to_list(length=page_size)
    total = await db.projects.count_documents({"user_id": user_id})
    
    items = []
    for p in projects:
        items.append({
            "id": str(p["_id"]),
            "name": p["name"],
            "status": p.get("status", "draft"),
            "created_at": p["created_at"].isoformat() if p.get("created_at") else None,
            "updated_at": p["updated_at"].isoformat() if p.get("updated_at") else None
        })
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }


@router.post("")
async def create_project(
    project: ProjectCreate,
    user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    
    project_doc = {
        "user_id": user_id,
        "name": project.name,
        "status": "draft",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.projects.insert_one(project_doc)
    project_id = str(result.inserted_id)
    
    return {
        "id": project_id,
        "name": project.name,
        "status": "draft",
        "created_at": project_doc["created_at"].isoformat(),
        "updated_at": project_doc["updated_at"].isoformat()
    }


@router.get("/{project_id}")
async def get_project(project_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    data_config = project.get("data_config")
    columns = project.get("columns", [])
    preview = project.get("preview", [])
    
    result = {
        "id": str(project["_id"]),
        "name": project["name"],
        "status": project.get("status", "draft"),
        "created_at": project["created_at"].isoformat() if project.get("created_at") else None,
        "updated_at": project["updated_at"].isoformat() if project.get("updated_at") else None,
    }
    
    if project.get("data_file"):
        result["data_file"] = {
            "id": str(project["data_file"].get("id", "")),
            "filename": project["data_file"].get("filename", ""),
            "file_size": project["data_file"].get("file_size", 0),
            "format": project["data_file"].get("format", ""),
            "uploaded_at": project["data_file"].get("uploaded_at", "").isoformat() if project["data_file"].get("uploaded_at") else None
        }
    
    if data_config:
        result["data_config"] = {
            "time_column": data_config.get("time_column"),
            "target_column": data_config.get("target_column"),
            "configured_at": data_config.get("configured_at", "").isoformat() if data_config.get("configured_at") else None
        }
    
    if columns:
        result["columns"] = columns
    
    if preview:
        result["preview"] = preview
    
    if project.get("eda_result"):
        result["eda_result"] = project["eda_result"]
    
    if project.get("preprocessing_result"):
        result["preprocessing_result"] = project["preprocessing_result"]
    
    if project.get("features"):
        result["features"] = project["features"]
    
    if project.get("forecasts"):
        result["forecasts"] = sanitize_dict(project["forecasts"])
    
    return sanitize_dict(result)


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    updates: ProjectUpdate,
    user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    update_data = {"updated_at": datetime.utcnow()}
    if updates.name:
        update_data["name"] = updates.name
    if updates.status:
        update_data["status"] = updates.status
    
    await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": update_data}
    )
    
    updated = await db.projects.find_one({"_id": ObjectId(project_id)})
    
    return {
        "id": str(updated["_id"]),
        "name": updated["name"],
        "status": updated.get("status", "draft"),
        "created_at": updated["created_at"].isoformat() if updated.get("created_at") else None,
        "updated_at": updated["updated_at"].isoformat() if updated.get("updated_at") else None
    }


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()

    try:
        result = await db.projects.delete_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="项目不存在")

    return None


@router.post("/{project_id}/upload")
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id)
):
    print(f"Starting upload for project {project_id}")
    print(f"User ID: {user_id}")
    print(f"File: {file.filename}")
    
    try:
        db = get_db()
        
        try:
            project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
            print(f"Project found: {project is not None}")
        except Exception as e:
            print(f"Error finding project: {e}")
            raise HTTPException(status_code=400, detail="无效的项目ID")
        
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        if file.size and file.size > settings.MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="文件大小超过300MB限制")
        
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in [".csv", ".xlsx", ".xls"]:
            raise HTTPException(status_code=400, detail="不支持的文件格式")
        
        file_id = str(uuid.uuid4())
        file_dir = os.path.join(settings.UPLOAD_DIR, user_id)
        os.makedirs(file_dir, exist_ok=True)
        file_path = os.path.join(file_dir, f"{file_id}{file_ext}")
        
        content = await file.read()
        print(f"File content read, size: {len(content)}")
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        print(f"File saved to {file_path}")
        
        file_format = "csv" if file_ext == ".csv" else "excel"
        
        data_file = {
            "id": file_id,
            "filename": file.filename,
            "file_size": file.size or len(content),
            "format": file_format,
            "file_path": file_path,
            "uploaded_at": datetime.utcnow()
        }
        
        columns = []
        preview = []
        df_full = None
        
        try:
            import pandas as pd
            
            if file_format == "csv":
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            df_full = df
            
            print(f"DataFrame shape: {df.shape}")
            
            for col in df.columns:
                col_type = "numeric" if pd.api.types.is_numeric_dtype(df[col]) else "text"
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    col_type = "datetime"
                
                sample_values = df[col].head(5).astype(str).tolist()
                
                columns.append({
                    "name": col,
                    "type": col_type,
                    "nullable": bool(df[col].isnull().any()),
                    "sample_values": sample_values
                })
            
            preview = df.head(10).fillna("").to_dict(orient="records")
            preview = [[str(v) for v in row.values()] for row in preview]
            
        except Exception as e:
            print(f"Error reading file: {e}")
        
        await db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "data_file": data_file,
                "columns": columns,
                "preview": preview,
                "updated_at": datetime.utcnow()
            }}
        )
        
        if df_full is not None:
            try:
                time_col = None
                value_col = None
                for col in columns:
                    if col["type"] == "datetime":
                        time_col = col["name"]
                    elif col["type"] == "numeric" and not value_col:
                        value_col = col["name"]
                
                if value_col:
                    df_dict = df_full.to_dict(orient="records")
                    await save_data_to_timeseries(project_id, df_dict, time_col, value_col)
                    print("数据已写入MongoDB时序集合")
            except Exception as e:
                print(f"写入时序集合失败: {e}")
        
        print("Upload complete!")
        
        return {
            "id": file_id,
            "filename": file.filename,
            "file_size": data_file["file_size"],
            "format": file_format,
            "uploaded_at": data_file["uploaded_at"].isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/{project_id}/columns")
async def get_columns(project_id: str, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    columns = project.get("columns", [])
    preview = project.get("preview", [])
    
    total_rows = 0
    if project.get("data_file") and project["data_file"].get("file_path"):
        try:
            import pandas as pd
            file_path = project["data_file"]["file_path"]
            if project["data_file"]["format"] == "csv":
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            total_rows = len(df)
        except:
            pass
    
    return {
        "columns": columns,
        "total_rows": total_rows,
        "preview": preview
    }


@router.post("/{project_id}/data/configure")
async def configure_data(
    project_id: str,
    config: DataConfigure,
    user_id: str = Depends(get_current_user_id)
):
    db = get_db()
    
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id), "user_id": user_id})
    except:
        raise HTTPException(status_code=400, detail="无效的项目ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    data_config = {
        "time_column": config.time_column,
        "target_column": config.target_column,
        "configured_at": datetime.utcnow()
    }
    
    await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {
            "data_config": data_config,
            "status": "eda",
            "updated_at": datetime.utcnow()
        }}
    )
    
    return DataConfigureResponse(
        time_column=config.time_column,
        target_column=config.target_column,
        configured_at=data_config["configured_at"].isoformat()
    )


@router.get("/{project_id}/data")
async def get_data(
    project_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
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
    file_format = project["data_file"]["format"]
    
    try:
        import pandas as pd
        
        if file_format == "csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        total = len(df)
        skip = (page - 1) * page_size
        paginated_df = df.iloc[skip:skip + page_size]
        
        data = paginated_df.fillna("").to_dict(orient="records")
        data = [[str(v) for v in row.values()] for row in data]
        
        return {
            "total": total,
            "data": data
        }
    except Exception as e:
        print(f"Error reading data: {e}")
        data = project.get("preview", [])
        return {
            "total": len(data),
            "data": data
        }
