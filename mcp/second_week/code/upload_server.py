from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import shutil
from pathlib import Path

app = FastAPI(title="鸿溯 - 文件上传服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(UPLOAD_DIR)), name="static")


@app.post("/api/v1/files/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="只支持CSV文件")
    
    file_path = UPLOAD_DIR / file.filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {
        "id": str(file_path.stem),
        "filename": file.filename,
        "size": file_path.stat().st_size,
        "uploadedAt": file_path.stat().st_mtime
    }


@app.get("/api/v1/files")
async def list_files():
    files = []
    for file_path in UPLOAD_DIR.glob("*.csv"):
        files.append({
            "id": str(file_path.stem),
            "filename": file_path.name,
            "size": file_path.stat().st_size,
            "uploadedAt": file_path.stat().st_mtime
        })
    return files


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
