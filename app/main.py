from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.database import connect_db, close_db
from app.routers import auth, users, projects, eda, preprocessing, features, forecast, report


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="TimeWise Analytics API",
    description="TimeWise 时间序列分析平台 API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_user_from_token(request: Request):
    auth_header = request.headers.get("Authorization", "")
    from app.core.security import decode_token
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.replace("Bearer ", "")
    payload = decode_token(token)
    
    if payload:
        return payload.get("user_id")
    return None


app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(eda.router, prefix="/api/v1")
app.include_router(preprocessing.router, prefix="/api/v1")
app.include_router(features.router, prefix="/api/v1")
app.include_router(forecast.router, prefix="/api/v1")
app.include_router(report.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "TimeWise Analytics API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
