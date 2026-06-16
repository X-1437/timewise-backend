from __future__ import annotations

from typing import Any

import pandas as pd
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


async def load_time_series_df(db: AsyncIOMotorDatabase, *, file_id: str) -> pd.DataFrame:
    oid = ObjectId(file_id)
    cursor = db.time_series_data.find({"metadata.fileId": oid}).sort("timestamp", 1)
    docs: list[dict[str, Any]] = []
    async for doc in cursor:
        doc.pop("_id", None)
        metadata = doc.pop("metadata", None)
        docs.append(doc)

    if not docs:
        return pd.DataFrame()

    df = pd.DataFrame(docs)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df = df.sort_values("timestamp")
    return df


def pick_target_column(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    cols = [c for c in df.columns if c != "timestamp"]
    if not cols:
        return None
    numeric = df[cols].select_dtypes(include="number").columns.tolist()
    if numeric:
        return numeric[0]
    return None
