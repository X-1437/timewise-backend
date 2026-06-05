from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import shutil
from pathlib import Path
from rule_matcher import RuleMatcher

app = FastAPI(title="鸿溯 - 后端服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:5175", "http://127.0.0.1:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

rule_matcher = RuleMatcher()


class ChatMessage(BaseModel):
    content: str
    fileId: str | None = None


@app.post("/api/v1/files/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="只支持CSV文件")
    
    file_path = UPLOAD_DIR / file.filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    rule_matcher.set_current_file(file.filename)
    
    return {
        "id": str(file_path.stem),
        "filename": file.filename,
        "size": file_path.stat().st_size
    }


@app.get("/api/v1/files")
async def list_files():
    files = []
    for file_path in UPLOAD_DIR.glob("*.csv"):
        files.append({
            "id": str(file_path.stem),
            "filename": file_path.name,
            "size": file_path.stat().st_size
        })
    return files


@app.post("/api/v1/chat/messages")
async def send_message(message: ChatMessage):
    response = rule_matcher.match(message.content)
    
    return {
        "id": str(hash(message.content + str(os.urandom(4).hex()))),
        "role": "assistant",
        "content": response
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
