from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from config import settings


async def init_mongo(app: FastAPI) -> None:
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    app.state.mongo_client = client
    app.state.db = db

    await _ensure_collections(db)


async def close_mongo(app: FastAPI) -> None:
    client: AsyncIOMotorClient | None = getattr(app.state, "mongo_client", None)
    if client is not None:
        client.close()


def get_db(app: FastAPI) -> AsyncIOMotorDatabase:
    return app.state.db


async def _ensure_collections(db: AsyncIOMotorDatabase) -> None:
    existing = set(await db.list_collection_names())

    if "sessions" not in existing:
        await db.create_collection("sessions")
    if "messages" not in existing:
        await db.create_collection("messages")
    if "files" not in existing:
        await db.create_collection("files")

    if "time_series_data" not in existing:
        await db.create_collection(
            "time_series_data",
            timeseries={
                "timeField": "timestamp",
                "metaField": "metadata",
                "granularity": "hours",
            },
        )

    await db.sessions.create_index([("updatedAt", -1)])
    await db.messages.create_index([("sessionId", 1), ("timestamp", 1)])
    await db.files.create_index([("sessionId", 1)])
    await db.time_series_data.create_index([("metadata.fileId", 1)])
