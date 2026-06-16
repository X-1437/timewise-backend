import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import pandas as pd

from analysis import (
    build_markdown_report,
    eda_markdown,
    feature_markdown,
    load_time_series_df,
    naive_forecast_markdown,
    preprocess_markdown,
)
from config import settings
from dal.mongodb.utils import to_object_id


server = Server("hongsu-time-series")

_mongo_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def _get_evidence_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "evidence"


def _format_bytes(n: int | None) -> str:
    if not n:
        return "0 B"
    size = float(n)
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    return f"{size:.4g} {units[idx]}"


def _md_table(df: pd.DataFrame, *, max_rows: int = 10, max_cols: int = 8) -> str:
    if df.empty:
        return ""
    cols = df.columns.tolist()[:max_cols]
    view = df.loc[:, cols].head(max_rows).copy()
    for c in cols:
        if c == "timestamp":
            view[c] = pd.to_datetime(view[c], errors="coerce", utc=True).astype(str)
        else:
            view[c] = view[c].astype(object).where(~view[c].isnull(), "NA").astype(str)
    lines: list[str] = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines)


async def _time_range(db: AsyncIOMotorDatabase, *, file_id: str) -> tuple[str | None, str | None]:
    oid = to_object_id(file_id)
    first = await db.time_series_data.find({"metadata.fileId": oid}).sort("timestamp", 1).limit(1).to_list(1)
    last = await db.time_series_data.find({"metadata.fileId": oid}).sort("timestamp", -1).limit(1).to_list(1)
    if not first or not last:
        return None, None
    return str(first[0].get("timestamp")), str(last[0].get("timestamp"))


async def _latest_artifact_path(
    db: AsyncIOMotorDatabase,
    *,
    session_id: str | None,
    file_id: str,
    artifact_type: str,
) -> str | None:
    q: dict = {"type": artifact_type, "fileId": to_object_id(file_id)}
    if session_id:
        q["sessionId"] = to_object_id(session_id)
    doc = (
        await db.artifacts.find(q).sort("createdAt", -1).limit(1).to_list(1)
    )
    if doc:
        p = doc[0].get("path")
        if p:
            return str(p)
    if session_id:
        q2 = {"type": artifact_type, "fileId": to_object_id(file_id)}
        doc2 = await db.artifacts.find(q2).sort("createdAt", -1).limit(1).to_list(1)
        if doc2:
            p2 = doc2[0].get("path")
            if p2:
                return str(p2)
    return None


def _load_csv_df(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df = df.sort_values("timestamp")
    return df


async def _load_analysis_df(
    db: AsyncIOMotorDatabase,
    *,
    file_id: str,
    session_id: str | None,
    data_version: str | None,
) -> tuple[pd.DataFrame, str, str, str | None, bool]:
    p = await _latest_artifact_path(
        db,
        session_id=session_id,
        file_id=file_id,
        artifact_type="preprocessed_csv",
    )
    has_preprocessed = bool(p and Path(p).exists())
    if data_version == "raw":
        return await load_time_series_df(db, file_id=file_id), "原始数据", "raw", None, has_preprocessed
    if data_version == "preprocessed":
        if has_preprocessed and p:
            return _load_csv_df(p), f"预处理后数据（{Path(p).name}）", "preprocessed", p, True
        return (
            await load_time_series_df(db, file_id=file_id),
            "原始数据（未找到预处理产物，已回退）",
            "raw",
            None,
            False,
        )
    if has_preprocessed and p:
        return _load_csv_df(p), f"预处理后数据（{Path(p).name}）", "preprocessed", p, True
    return await load_time_series_df(db, file_id=file_id), "原始数据", "raw", None, False


def _prepend_notice(title: str, message: str, body: str) -> str:
    return "\n".join(
        [
            f"## {title}",
            "",
            f"- {message}",
            "",
            body.strip(),
        ]
    ).strip()


async def _save_artifact(
    db: AsyncIOMotorDatabase,
    *,
    session_id: str | None,
    file_id: str | None,
    artifact_type: str,
    artifact_path: Path,
) -> None:
    doc = {
        "type": artifact_type,
        "path": str(artifact_path),
        "createdAt": datetime.now(timezone.utc),
    }
    if session_id:
        doc["sessionId"] = to_object_id(session_id)
    if file_id:
        doc["fileId"] = to_object_id(file_id)
    await db.artifacts.insert_one(doc)


async def _get_db() -> AsyncIOMotorDatabase:
    global _mongo_client, _db
    if _db is not None:
        return _db
    _mongo_client = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _mongo_client[settings.mongodb_db_name]
    return _db


async def _file_summary_markdown(
    db: AsyncIOMotorDatabase,
    *,
    file_id: str,
    session_id: str | None = None,
) -> str:
    doc = await db.files.find_one({"_id": to_object_id(file_id)})
    if not doc:
        return "未找到文件信息。"
    filename = doc.get("filename") or ""
    size = int(doc.get("size") or 0)
    row_count = doc.get("rowCount") or 0
    column_names = doc.get("columnNames") or []
    uploaded_at = doc.get("uploadedAt")
    start_ts, end_ts = await _time_range(db, file_id=file_id)
    preprocessed_path = await _latest_artifact_path(
        db,
        session_id=session_id,
        file_id=file_id,
        artifact_type="preprocessed_csv",
    )
    lines: list[str] = []
    lines.append(f"- 文件名：{filename}")
    lines.append(f"- 文件大小：{_format_bytes(size)}")
    lines.append(f"- 行数：{row_count}")
    lines.append(f"- 列数：{len(column_names)}")
    if start_ts and end_ts:
        lines.append(f"- 时间范围：{start_ts} ~ {end_ts}")
    if column_names:
        lines.append(f"- 列名：{', '.join(column_names[:30])}{'...' if len(column_names) > 30 else ''}")
    if preprocessed_path:
        lines.append(f"- 预处理产物：{Path(preprocessed_path).name}")
    if uploaded_at:
        lines.append(f"- 上传时间（UTC）：{uploaded_at.isoformat()}")
    lines.append(f"- 内部标识：{file_id}")
    return "\n".join(lines)


@server.list_resources()
async def handle_list_resources():
    return []


@server.list_tools()
async def handle_list_tools():
    return [
        types.Tool(
            name="upload_data",
            description="确认/绑定当前会话的数据文件，返回文件信息与数据样例",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "file_id": {"type": "string"},
                },
                "required": ["file_id"],
            },
        ),
        types.Tool(
            name="eda_analysis",
            description="执行探索性数据分析（EDA），包括数据概览、缺失值统计、基本统计量",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "file_id": {"type": "string"},
                    "data_version": {"type": "string", "enum": ["raw", "preprocessed"]},
                },
                "required": ["file_id"],
            },
        ),
        types.Tool(
            name="preprocessing",
            description="数据预处理：缺失值填充/异常值移除/数据类型转换",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "file_id": {"type": "string"},
                    "method": {
                        "type": "string",
                        "enum": ["missing_fill", "outlier_remove", "type_convert"],
                        "default": "missing_fill",
                    },
                },
                "required": ["file_id"],
            },
        ),
        types.Tool(
            name="feature_analysis",
            description="特征分析：趋势、自相关、滚动统计等基础特征结论",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "file_id": {"type": "string"},
                    "data_version": {"type": "string", "enum": ["raw", "preprocessed"]},
                },
                "required": ["file_id"],
            },
        ),
        types.Tool(
            name="naive_forecast",
            description="朴素预测（基线）：next_row/same_time/daily_sum 等方法",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "file_id": {"type": "string"},
                    "data_version": {"type": "string", "enum": ["raw", "preprocessed"]},
                    "method": {
                        "type": "string",
                        "enum": ["next_row", "same_time", "daily_sum"],
                        "default": "next_row",
                    },
                    "periods": {"type": "integer", "default": 7},
                },
                "required": ["file_id"],
            },
        ),
        types.Tool(
            name="export_markdown",
            description="导出 Markdown 报告（标准流程结果汇总）",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "file_id": {"type": "string"},
                    "scope": {"type": "string", "enum": ["standard_flow"], "default": "standard_flow"},
                },
                "required": ["session_id", "file_id"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name, arguments):
    db = await _get_db()

    if name == "upload_data":
        session_id = arguments.get("session_id")
        file_id = arguments.get("file_id")
        if not file_id:
            return [types.TextContent(type="text", text="缺少 file_id，无法确认数据文件。")]
        summary = await _file_summary_markdown(db, file_id=file_id, session_id=session_id)
        df = await load_time_series_df(db, file_id=file_id)
        sample = ""
        if not df.empty:
            sample = _md_table(df, max_rows=5)
        text = "\n".join(
            [
                "## 数据文件已确认",
                "",
                "### 文件信息",
                summary,
                "",
                "### 数据样例（前 5 行）",
                sample if sample else "暂无可展示样例。",
            ]
        ).strip()
        return [types.TextContent(type="text", text=text)]

    if name == "eda_analysis":
        session_id = arguments.get("session_id")
        file_id = arguments.get("file_id")
        if not file_id:
            return [types.TextContent(type="text", text="缺少 file_id，无法执行 EDA。")]
        data_version = arguments.get("data_version")
        df, note, _, _, _ = await _load_analysis_df(
            db,
            file_id=file_id,
            session_id=session_id,
            data_version=data_version,
        )
        return [types.TextContent(type="text", text=eda_markdown(df, data_note=note))]

    if name == "preprocessing":
        session_id = arguments.get("session_id")
        file_id = arguments.get("file_id")
        if not file_id:
            return [types.TextContent(type="text", text="缺少 file_id，无法执行预处理。")]
        method = arguments.get("method") or "missing_fill"
        df = await load_time_series_df(db, file_id=file_id)
        out_df, text = preprocess_markdown(df, method=method)

        evidence_dir = _get_evidence_dir()
        evidence_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        processed_path = evidence_dir / f"preprocessed_{file_id}_{ts}.csv"
        out_df.to_csv(processed_path, index=False, encoding="utf-8")
        await _save_artifact(
            db,
            session_id=session_id,
            file_id=file_id,
            artifact_type="preprocessed_csv",
            artifact_path=processed_path,
        )

        download_url = f"/api/v1/sessions/{session_id}/files/{file_id}/preprocessed/download" if session_id else None
        extra = "\n".join(
            [
                "",
                "### 预处理文件",
                f"- 路径：{str(processed_path)}",
                f"- 下载：{download_url}" if download_url else "- 下载：请在调用时提供 session_id 以生成下载地址",
            ]
        )
        return [types.TextContent(type="text", text=(text + extra).strip())]

    if name == "feature_analysis":
        session_id = arguments.get("session_id")
        file_id = arguments.get("file_id")
        if not file_id:
            return [types.TextContent(type="text", text="缺少 file_id，无法执行特征分析。")]
        data_version = arguments.get("data_version")
        df, note, actual_version, _, has_preprocessed = await _load_analysis_df(
            db,
            file_id=file_id,
            session_id=session_id,
            data_version=data_version,
        )
        if not has_preprocessed and actual_version == "raw":
            note = "原始数据（未预处理）"
        text = feature_markdown(df, data_note=note)
        if data_version == "preprocessed" and actual_version == "raw":
            text = _prepend_notice(
                "执行提示",
                "你指定了预处理后数据，但当前会话未找到可用的预处理产物，系统已回退到原始数据。",
                text,
            )
        elif not has_preprocessed and actual_version == "raw":
            text = _prepend_notice(
                "执行提示",
                "当前尚未进行预处理，原始数据可能包含缺失值、异常值或类型问题，这会影响特征分析结果。建议先进行预处理后再分析。",
                text,
            )
        return [types.TextContent(type="text", text=text)]

    if name == "naive_forecast":
        session_id = arguments.get("session_id")
        file_id = arguments.get("file_id")
        if not file_id:
            return [types.TextContent(type="text", text="缺少 file_id，无法执行朴素预测。")]
        method = arguments.get("method") or "next_row"
        periods = int(arguments.get("periods") or 7)
        data_version = arguments.get("data_version")
        df, note, actual_version, _, has_preprocessed = await _load_analysis_df(
            db,
            file_id=file_id,
            session_id=session_id,
            data_version=data_version,
        )
        if not has_preprocessed and actual_version == "raw":
            note = "原始数据（未预处理）"
        text = naive_forecast_markdown(df, method=method, periods=periods, data_note=note)
        if data_version == "preprocessed" and actual_version == "raw":
            text = _prepend_notice(
                "执行提示",
                "你指定了预处理后数据，但当前会话未找到可用的预处理产物，系统已回退到原始数据。",
                text,
            )
        elif not has_preprocessed and actual_version == "raw":
            text = _prepend_notice(
                "执行提示",
                "当前尚未进行预处理，原始数据中的缺失值、异常值或类型问题可能直接影响预测结果。建议先完成预处理后再进行预测。",
                text,
            )
        return [
            types.TextContent(
                type="text",
                text=text,
            )
        ]

    if name == "export_markdown":
        session_id = arguments.get("session_id")
        file_id = arguments.get("file_id")
        if not session_id or not file_id:
            return [types.TextContent(type="text", text="缺少 session_id 或 file_id，无法导出报告。")]

        summary = await _file_summary_markdown(db, file_id=file_id, session_id=session_id)
        cursor = db.messages.find({"sessionId": to_object_id(session_id)}).sort("timestamp", 1)
        blocks: list[str] = []
        display_names = {
            "upload_data": "数据集确认",
            "eda_analysis": "EDA",
            "preprocessing": "预处理",
            "feature_analysis": "特征分析",
            "naive_forecast": "朴素预测",
        }
        step_no = 0
        async for msg in cursor:
            if msg.get("role") != "assistant":
                continue
            tool_calls = msg.get("toolCalls") or []
            for tc in tool_calls:
                tool_name = tc.get("tool_name") or tc.get("toolName") or ""
                tool_result = (tc.get("tool_result") or tc.get("toolResult") or "").strip()
                data_version = (tc.get("data_version") or tc.get("dataVersion") or "").strip()
                if not tool_result:
                    continue
                if tool_name == "export_markdown":
                    continue
                if data_version and "数据版本：" not in tool_result:
                    tool_result = "\n".join([f"- 数据版本：{data_version}", "", tool_result]).strip()
                if tool_name:
                    step_no += 1
                    title = display_names.get(tool_name, tool_name)
                    blocks.append(f"### {step_no}. {title}\n\n{tool_result}")
                else:
                    blocks.append(tool_result)

        file_doc = await db.files.find_one({"_id": to_object_id(file_id)})
        report_title = "时间序列数据分析报告"
        if file_doc and file_doc.get("filename"):
            report_title = f"{report_title} - {file_doc.get('filename')}"
        report = build_markdown_report(
            title=report_title,
            file_summary=summary,
            step_blocks=blocks,
        )

        evidence_dir = _get_evidence_dir()
        evidence_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_path = evidence_dir / f"report_{session_id}_{ts}.md"
        report_path.write_text(report, encoding="utf-8")
        await _save_artifact(
            db,
            session_id=session_id,
            file_id=file_id,
            artifact_type="report_markdown",
            artifact_path=report_path,
        )
        download_url = f"/api/v1/sessions/{session_id}/files/{file_id}/report/download"
        text = "\n".join(
            [
                "## 导出完成",
                "",
                f"- 路径：{str(report_path)}",
                f"- 下载：{download_url}",
                "",
                "你可以通过下载地址直接下载报告，或在本地打开该 Markdown 文件查看。",
            ]
        ).strip()
        return [types.TextContent(type="text", text=text)]

    return [types.TextContent(type="text", text=f"未知工具：{name}")]


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="hongsu-time-series",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
