from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.exports import router as exports_router
from api.files import router as files_router
from api.messages import router as messages_router
from api.sessions import router as sessions_router
from dal.mongodb.connection import close_mongo, init_mongo
from mcp_layer.client import close_mcp, init_mcp


app = FastAPI(title="鸿溯 - 后端服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router, prefix="/api/v1")
app.include_router(messages_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")
app.include_router(exports_router, prefix="/api/v1")


@app.on_event("startup")
async def on_startup():
    await init_mongo(app)
    await init_mcp(app)


@app.on_event("shutdown")
async def on_shutdown():
    await close_mcp(app)
    await close_mongo(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=False)
