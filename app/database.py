from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client: AsyncIOMotorClient = None
db = None


async def connect_db():
    global client, db
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB]
    
    await db.users.create_index("username", unique=True)
    await db.users.create_index("email", unique=True)
    await db.projects.create_index("user_id")
    
    await create_time_series_collections()


async def create_time_series_collections():
    """创建时序集合（如果不存在）"""
    collection_names = await db.list_collection_names()
    
    if "time_series_data" not in collection_names:
        await db.create_collection(
            "time_series_data",
            timeseries={
                "timeField": "timestamp",
                "metaField": "metadata",
                "granularity": "minutes"
            }
        )
        await db.time_series_data.create_index([("metadata.project_id", 1), ("timestamp", -1)])
        print("时序集合 time_series_data 已创建")


async def close_db():
    global client
    if client:
        client.close()


def get_db():
    return db


async def save_data_to_timeseries(project_id: str, df_data: list, time_column: str = None, value_column: str = None):
    """将数据保存到MongoDB时序集合（统一使用主集合）"""
    ts_collection = db.time_series_data
    
    records = []
    for i, row in enumerate(df_data):
        timestamp = row.get(time_column) if time_column else datetime.utcnow()
        value = row.get(value_column) if value_column else row
        
        if isinstance(value, (int, float)):
            records.append({
                "timestamp": timestamp,
                "metadata": {
                    "project_id": project_id,
                    "row_index": i
                },
                "value": value
            })
    
    if records:
        await ts_collection.insert_many(records)
        print(f"已写入 {len(records)} 条数据到时序集合")
    
    return len(records)


async def read_data_from_timeseries(project_id: str, limit: int = 100):
    """从MongoDB时序集合读取数据"""
    ts_collection = db.time_series_data
    
    cursor = ts_collection.find(
        {"metadata.project_id": project_id}
    ).sort("timestamp", 1).limit(limit)
    
    data = await cursor.to_list(length=limit)
    return data
