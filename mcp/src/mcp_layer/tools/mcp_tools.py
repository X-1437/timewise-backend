import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import pandas as pd
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
from scipy import signal

from analysis import (
    build_markdown_report,
    eda_markdown,
    feature_markdown,
    load_time_series_df,
    naive_forecast_markdown,
    pick_target_column,
    preprocess_markdown,
)
from config import settings
from dal.mongodb.utils import to_object_id


server = Server("hongsu-time-series")

_mongo_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def _configure_matplotlib_fonts() -> None:
    """Configure a Chinese-capable font fallback for server-side PNG rendering."""
    preferred = [
        "Microsoft YaHei",
        "SimHei",
        "SimSun",
        "KaiTi",
        "FangSong",
        "Noto Sans CJK SC",
        "WenQuanYi Zen Hei",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    selected = [name for name in preferred if name in available]
    if selected:
        matplotlib.rcParams["font.family"] = "sans-serif"
        matplotlib.rcParams["font.sans-serif"] = selected
    matplotlib.rcParams["axes.unicode_minus"] = False


_configure_matplotlib_fonts()


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


_PREPROCESS_METHOD_CN = {
    "missing_fill": "缺失值填充",
    "outlier_remove": "异常值处理（3σ 移除）",
    "type_convert": "类型转换",
}

_FORECAST_METHOD_CN = {
    "next_row": "相邻两行",
    "same_time": "相同时间点",
    "daily_sum": "按天累加",
}


def _format_dt(value) -> str:
    if value is None:
        return ""
    try:
        ts = pd.to_datetime(value, errors="coerce", utc=True)
        if ts is pd.NaT:
            return str(value)
        if int(ts.hour) == 0 and int(ts.minute) == 0 and int(ts.second) == 0:
            return ts.strftime("%Y-%m-%d")
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def _md_table(df: pd.DataFrame, *, max_rows: int = 10, max_cols: int = 8) -> str:
    if df.empty:
        return ""
    cols = df.columns.tolist()[:max_cols]
    view = df.loc[:, cols].head(max_rows).copy()
    for c in cols:
        if c == "timestamp":
            ts = pd.to_datetime(view[c], errors="coerce", utc=True)
            full = ts.dt.strftime("%Y-%m-%d %H:%M:%S")
            date_only = ts.dt.strftime("%Y-%m-%d")
            is_midnight = ts.dt.hour.eq(0) & ts.dt.minute.eq(0) & ts.dt.second.eq(0)
            view[c] = full.where(~is_midnight, date_only).where(ts.notna(), "NA")
        else:
            view[c] = view[c].astype(object).where(~view[c].isnull(), "NA").astype(str)
    lines: list[str] = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines)


def _infer_time_granularity(df: pd.DataFrame) -> str | None:
    if "timestamp" not in df.columns:
        return None
    ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True).dropna().sort_values()
    if len(ts) < 2:
        return None
    diffs = ts.diff().dropna().dt.total_seconds()
    diffs = diffs[diffs > 0]
    if diffs.empty:
        return None
    median_seconds = float(diffs.median())
    if median_seconds >= 86400:
        days = max(1, round(median_seconds / 86400))
        return "按日" if days == 1 else f"约每 {days} 天一条"
    if median_seconds >= 3600:
        hours = max(1, round(median_seconds / 3600))
        return "按小时" if hours == 1 else f"约每 {hours} 小时一条"
    if median_seconds >= 60:
        minutes = max(1, round(median_seconds / 60))
        return "按分钟" if minutes == 1 else f"约每 {minutes} 分钟一条"
    seconds = max(1, round(median_seconds))
    return "按秒" if seconds == 1 else f"约每 {seconds} 秒一条"


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
            return _load_csv_df(p), "预处理后数据", "preprocessed", p, True
        return (
            await load_time_series_df(db, file_id=file_id),
            "原始数据（未找到预处理产物，已回退）",
            "raw",
            None,
            False,
        )
    if has_preprocessed and p:
        return _load_csv_df(p), "预处理后数据", "preprocessed", p, True
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


def _image_block(display_name: str, url: str, insight_lines: list[str] | None = None) -> str:
    lines = [f"#### 图片：{display_name}"]
    if insight_lines:
        normalized = [line if line.startswith("- ") else f"- {line}" for line in insight_lines if line.strip()]
        if normalized:
            lines.extend(["", "##### 看图结论", *normalized])
    lines.extend(["", f"![{display_name}]({url})"])
    return "\n".join(lines).strip()


def _compose_result(
    markdown: str,
    *,
    blocks: list[str] | None = None,
    conclusion_lines: list[str] | None = None,
) -> str:
    lines = (markdown or "").splitlines()
    title = "## 输出"
    body = markdown.strip()
    if lines and lines[0].startswith("## "):
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

    sections: list[str] = [title]
    if conclusion_lines:
        normalized = [line if line.startswith("- ") else f"- {line}" for line in conclusion_lines if line.strip()]
        if normalized:
            sections.append("\n".join(["#### 结论", "", *normalized]).strip())
    if blocks:
        sections.append("\n".join(["#### 图片与分析", "", "\n\n".join(blocks).strip()]).strip())
    if body:
        sections.append(body)
    return "\n\n".join(s for s in sections if s.strip()).strip()


def _annotate_flagged_points(
    ax,
    x_values,
    y_values: np.ndarray,
    mask: np.ndarray,
    scores: np.ndarray,
    *,
    label_prefix: str,
    color: str,
    max_points: int = 5,
) -> None:
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return
    ordered = idx[np.argsort(scores[idx])[-min(max_points, len(idx)) :]]
    ordered = np.sort(ordered)
    for i in ordered:
        x = x_values.iloc[i] if hasattr(x_values, "iloc") else x_values[i]
        y = float(y_values[i])
        try:
            ts_label = pd.to_datetime(x).strftime("%m-%d")
        except Exception:
            ts_label = str(i)
        ax.annotate(
            f"{label_prefix}\n{ts_label}: {y:.2f}",
            xy=(x, y),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color=color,
            bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": color, "alpha": 0.9},
            arrowprops={"arrowstyle": "->", "color": color, "lw": 0.8},
        )


async def _save_artifact(
    db: AsyncIOMotorDatabase,
    *,
    session_id: str | None,
    file_id: str | None,
    artifact_type: str,
    artifact_path: Path,
) -> str:
    doc = {
        "type": artifact_type,
        "path": str(artifact_path),
        "createdAt": datetime.now(timezone.utc),
    }
    if session_id:
        doc["sessionId"] = to_object_id(session_id)
    if file_id:
        doc["fileId"] = to_object_id(file_id)
    res = await db.artifacts.insert_one(doc)
    return str(res.inserted_id)


async def _save_image_png(
    db: AsyncIOMotorDatabase,
    *,
    session_id: str,
    file_id: str,
    display_name: str,
    fig: "plt.Figure",
) -> str:
    evidence_dir = _get_evidence_dir()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"img_{session_id}_{ts}_{uuid4().hex}.png"
    path = evidence_dir / filename
    fig.savefig(path, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    doc = {
        "type": "image_png",
        "path": str(path),
        "displayName": display_name,
        "createdAt": datetime.now(timezone.utc),
        "sessionId": to_object_id(session_id),
        "fileId": to_object_id(file_id),
    }
    res = await db.artifacts.insert_one(doc)
    return str(res.inserted_id)


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
    include_samples: bool = False,
) -> str:
    doc = await db.files.find_one({"_id": to_object_id(file_id)})
    if not doc:
        return "未找到文件信息。"
    filename = doc.get("filename") or ""
    size = int(doc.get("size") or 0)
    row_count = doc.get("rowCount") or 0
    column_names = doc.get("columnNames") or []
    start_ts, end_ts = await _time_range(db, file_id=file_id)
    raw_preview_df = pd.DataFrame()
    granularity_df = pd.DataFrame()
    if include_samples:
        sample_docs = (
            await db.time_series_data.find({"metadata.fileId": to_object_id(file_id)})
            .sort("timestamp", 1)
            .limit(20)
            .to_list(20)
        )
        cleaned_docs: list[dict] = []
        for sample_doc in sample_docs:
            sample_doc.pop("_id", None)
            sample_doc.pop("metadata", None)
            cleaned_docs.append(sample_doc)
        if cleaned_docs:
            granularity_df = pd.DataFrame(cleaned_docs)
            raw_preview_df = pd.DataFrame(cleaned_docs[:5])
            if "timestamp" in granularity_df.columns:
                granularity_df["timestamp"] = pd.to_datetime(granularity_df["timestamp"], errors="coerce", utc=True)
            if "timestamp" in raw_preview_df.columns:
                raw_preview_df["timestamp"] = pd.to_datetime(raw_preview_df["timestamp"], errors="coerce", utc=True)
    granularity = _infer_time_granularity(granularity_df) if include_samples and not granularity_df.empty else None
    preprocessed_path = await _latest_artifact_path(
        db,
        session_id=session_id,
        file_id=file_id,
        artifact_type="preprocessed_csv",
    )
    lines: list[str] = []
    lines.append(f"- 文件名：**{filename}**")
    lines.append(f"- 文件大小：**{_format_bytes(size)}**")
    lines.append(f"- 行数：**{row_count}**")
    lines.append(f"- 列数：**{len(column_names)}**")
    if start_ts and end_ts:
        lines.append(f"- 时间范围：**{_format_dt(start_ts)} ~ {_format_dt(end_ts)}**")
    if granularity:
        lines.append(f"- 时间间隔判断：**{granularity}**")
    if column_names:
        lines.append(f"- 列名：{', '.join(column_names[:30])}{'...' if len(column_names) > 30 else ''}")
    if preprocessed_path:
        lines.append("- 预处理后数据：**已生成**")
    if include_samples and not raw_preview_df.empty:
        raw_preview = _md_table(raw_preview_df, max_rows=5, max_cols=10)
        if raw_preview:
            lines.extend(["", "### 原始数据样例（前 5 行）", raw_preview])
    if include_samples and preprocessed_path and Path(preprocessed_path).exists():
        pre_df = _load_csv_df(preprocessed_path)
        pre_preview = _md_table(pre_df, max_rows=5, max_cols=10)
        if pre_preview:
            lines.extend(["", "### 预处理后数据样例（前 5 行）", pre_preview])
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
        summary = await _file_summary_markdown(
            db,
            file_id=file_id,
            session_id=session_id,
            include_samples=True,
        )
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
        text = eda_markdown(df, data_note=note)
        blocks: list[str] = []
        conclusions: list[str] = []
        if not df.empty:
            conclusions.append(f"本次分析基于{note or '当前数据'}，共 {len(df)} 行、{len(df.columns)} 列。")
            total_cells = len(df) * len(df.columns)
            total_missing = int(df.isnull().sum().sum())
            miss_rate = (total_missing / total_cells * 100) if total_cells else 0.0
            target_col = pick_target_column(df)
            if target_col:
                numeric = pd.to_numeric(df[target_col], errors="coerce").dropna()
                if len(numeric) > 0:
                    mean = float(numeric.mean())
                    std = float(numeric.std())
                    outlier_count = int(((numeric - mean).abs() > 3 * std).sum()) if std > 0 else 0
                    conclusions.append(
                        f"目标列为 `{target_col}`，总缺失率 {miss_rate:.2f}%，3σ 异常点 {outlier_count} 个。"
                    )
        if session_id:
            target_col = pick_target_column(df)
            if target_col and "timestamp" in df.columns:
                view = df.loc[:, ["timestamp", target_col]].copy()
                view["timestamp"] = pd.to_datetime(view["timestamp"], errors="coerce", utc=True)
                view[target_col] = pd.to_numeric(view[target_col], errors="coerce")
                view = view.dropna()
                if not view.empty:
                    s = view.set_index("timestamp")[target_col].sort_index()
                    monthly = s.resample("MS").mean()
                    if len(monthly) > 1:
                        fig, ax = plt.subplots(figsize=(7, 3.5))
                        ax.plot(monthly.index, monthly.values, marker="o", linewidth=1.5)
                        ax.set_title("EDA - 按月可视化")
                        ax.set_xlabel("月份")
                        ax.set_ylabel(target_col)
                        ax.xaxis.set_major_locator(mdates.MonthLocator())
                        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
                        fig.autofmt_xdate()
                        display_name = "EDA-按月可视化"
                        image_id = await _save_image_png(
                            db,
                            session_id=session_id,
                            file_id=file_id,
                            display_name=display_name,
                            fig=fig,
                        )
                        url = f"/api/v1/sessions/{session_id}/files/{file_id}/images/{image_id}/download"
                        monthly_change = np.diff(monthly.values.astype(float))
                        insight_lines = []
                        if len(monthly.values) >= 2:
                            overall = monthly.values[-1] - monthly.values[0]
                            if overall > 0:
                                insight_lines.append("从图上看，月均值整体呈上升。")
                            elif overall < 0:
                                insight_lines.append("从图上看，月均值整体呈下降。")
                            else:
                                insight_lines.append("从图上看，月均值整体较为平稳。")
                            if len(monthly_change) > 0:
                                idx = int(np.argmax(np.abs(monthly_change)))
                                change_month = monthly.index[min(idx + 1, len(monthly.index) - 1)].strftime("%Y-%m")
                                change_value = float(monthly_change[idx])
                                direction = "上升" if change_value > 0 else "下降"
                                insight_lines.append(f"相邻月份中，`{change_month}` 前后的变化最明显，月均值{direction}约 **{abs(change_value):.4g}**。")
                        blocks.append(_image_block(display_name, url, insight_lines))
                        conclusions.append(f"已生成 `{display_name}`，可直接查看跨月份变化趋势。")
                    else:
                        conclusions.append("当前数据覆盖月份较少，按月图仅能展示有限月份点位。")
        text = _compose_result(text, blocks=blocks, conclusion_lines=conclusions)
        return [types.TextContent(type="text", text=text)]

    if name == "preprocessing":
        session_id = arguments.get("session_id")
        file_id = arguments.get("file_id")
        if not file_id:
            return [types.TextContent(type="text", text="缺少 file_id，无法执行预处理。")]
        method = arguments.get("method") or "missing_fill"
        method_cn = _PREPROCESS_METHOD_CN.get(str(method), str(method))
        df = await load_time_series_df(db, file_id=file_id)
        out_df, text = preprocess_markdown(df, method=method)
        blocks: list[str] = []
        conclusions: list[str] = []
        before_rows = int(len(df))
        after_rows = int(len(out_df))
        before_missing = int(df.isnull().sum().sum()) if not df.empty else 0
        after_missing = int(out_df.isnull().sum().sum()) if not out_df.empty else 0
        conclusions.append(f"已完成 {method_cn}，行数 {before_rows} -> {after_rows}，缺失值 {before_missing} -> {after_missing}。")
        if session_id:
            target_col = pick_target_column(df)
            if target_col and "timestamp" in df.columns:
                view = df.loc[:, ["timestamp", target_col]].copy()
                view["timestamp"] = pd.to_datetime(view["timestamp"], errors="coerce", utc=True)
                view[target_col] = pd.to_numeric(view[target_col], errors="coerce")
                view = view.dropna().sort_values("timestamp")
                if not view.empty:
                    ts_values = view["timestamp"]
                    y = view[target_col].astype(float).values
                    window = min(7, len(y) if len(y) % 2 == 1 else len(y) - 1)
                    window = max(3, window)
                    baseline = (
                        pd.Series(y).rolling(window=window, center=True, min_periods=1).median().to_numpy()
                    )
                    residual = y - baseline
                    mad = float(np.median(np.abs(residual)))
                    noise_mask = np.zeros(len(y), dtype=bool)
                    if mad > 0:
                        noise_mask = np.abs(residual) > 3 * mad
                    noise_count = int(noise_mask.sum())

                    fig1, ax1 = plt.subplots(figsize=(7, 3.5))
                    ax1.plot(ts_values, y, color="#666666", linewidth=1, label="原始序列")
                    ax1.plot(ts_values, baseline, color="#1565c0", linewidth=1.4, linestyle="--", label="滚动中位线")
                    if noise_mask.any():
                        ax1.scatter(
                            ts_values[noise_mask],
                            y[noise_mask],
                            color="#d32f2f",
                            s=40,
                            zorder=4,
                            label="识别出的噪音点",
                        )
                        _annotate_flagged_points(
                            ax1,
                            ts_values.reset_index(drop=True),
                            y,
                            noise_mask,
                            np.abs(residual),
                            label_prefix="噪音",
                            color="#d32f2f",
                        )
                    ax1.text(
                        0.02,
                        0.95,
                        f"识别噪音点：{noise_count} 个\n规则：偏离滚动中位线超过 3×MAD",
                        transform=ax1.transAxes,
                        va="top",
                        fontsize=9,
                        bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "#d32f2f", "alpha": 0.9},
                    )
                    ax1.set_title("预处理 - 噪音识别（已标注）")
                    ax1.set_xlabel("时间")
                    ax1.set_ylabel(target_col)
                    ax1.legend(loc="upper right")
                    fig1.autofmt_xdate()
                    display_name_1 = "预处理-噪音识别"
                    image_id_1 = await _save_image_png(
                        db,
                        session_id=session_id,
                        file_id=file_id,
                        display_name=display_name_1,
                        fig=fig1,
                    )
                    url_1 = f"/api/v1/sessions/{session_id}/files/{file_id}/images/{image_id_1}/download"
                    noise_insights = []
                    if noise_count == 0:
                        noise_insights.append("从图上看，原始序列与滚动中位线整体贴合，没有识别出明显偏离点。")
                    else:
                        noise_insights.append(f"从图上看，共识别出 **{noise_count}** 个明显偏离滚动中位线的噪音点。")
                        noise_insights.append("红色标注点就是波动最异常的位置，建议优先检查这些点位前后的变化。")
                    blocks.append(_image_block(display_name_1, url_1, noise_insights))

                    mean = float(np.mean(y))
                    std = float(np.std(y))
                    outlier_mask = np.zeros(len(y), dtype=bool)
                    if std > 0:
                        outlier_mask = np.abs(y - mean) > 3 * std
                    outlier_count = int(outlier_mask.sum())

                    fig2, ax2 = plt.subplots(figsize=(7, 3.5))
                    ax2.plot(ts_values, y, color="#666666", linewidth=1, label="原始序列")
                    upper = mean + 3 * std
                    lower = mean - 3 * std
                    if std > 0:
                        ax2.axhline(upper, color="#7b1fa2", linestyle="--", linewidth=1, label="+3σ 阈值")
                        ax2.axhline(lower, color="#7b1fa2", linestyle="--", linewidth=1, label="-3σ 阈值")
                    if outlier_mask.any():
                        ax2.scatter(
                            ts_values[outlier_mask],
                            y[outlier_mask],
                            color="#7b1fa2",
                            s=40,
                            zorder=4,
                            label="识别出的异常点",
                        )
                        _annotate_flagged_points(
                            ax2,
                            ts_values.reset_index(drop=True),
                            y,
                            outlier_mask,
                            np.abs(y - mean),
                            label_prefix="异常",
                            color="#7b1fa2",
                        )
                    ax2.text(
                        0.02,
                        0.95,
                        f"识别异常点：{outlier_count} 个\n规则：超出均值 ± 3σ",
                        transform=ax2.transAxes,
                        va="top",
                        fontsize=9,
                        bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "#7b1fa2", "alpha": 0.9},
                    )
                    ax2.set_title("预处理 - 异常值处理（已标注）")
                    ax2.set_xlabel("时间")
                    ax2.set_ylabel(target_col)
                    ax2.legend(loc="upper right")
                    fig2.autofmt_xdate()
                    display_name_2 = "预处理-异常值处理"
                    image_id_2 = await _save_image_png(
                        db,
                        session_id=session_id,
                        file_id=file_id,
                        display_name=display_name_2,
                        fig=fig2,
                    )
                    url_2 = f"/api/v1/sessions/{session_id}/files/{file_id}/images/{image_id_2}/download"
                    outlier_insights = []
                    if outlier_count == 0:
                        outlier_insights.append("从图上看，序列整体落在均值 ± 3σ 范围内，没有识别出异常点。")
                    else:
                        outlier_insights.append(f"从图上看，共识别出 **{outlier_count}** 个超出均值 ± 3σ 的异常点。")
                        outlier_insights.append("紫色高亮点表示需要重点复核的极端值。")
                    blocks.append(_image_block(display_name_2, url_2, outlier_insights))
                    conclusions.append(
                        f"已识别噪音点 {noise_count} 个、异常点 {outlier_count} 个，图中已用高亮点和文字标注。"
                    )
                    conclusions.append("后续分析默认使用预处理后数据，建议优先根据图中标注检查异常点是否符合业务预期。")
        text = _compose_result(text, blocks=blocks, conclusion_lines=conclusions)

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

        preview = _md_table(out_df, max_rows=10, max_cols=10)
        extra = "\n".join(
            [
                "",
                "#### 预处理后数据样例（前 10 行）",
                "",
                preview if preview else "暂无可展示预览。",
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
        blocks: list[str] = []
        conclusions: list[str] = []
        target_col = pick_target_column(df)
        if target_col:
            s = pd.to_numeric(df[target_col], errors="coerce").dropna()
            if len(s) >= 3:
                x = np.arange(len(s))
                slope, _ = np.polyfit(x, s.values, 1)
                if slope > 0:
                    trend_desc = "整体呈上升趋势"
                elif slope < 0:
                    trend_desc = "整体呈下降趋势"
                else:
                    trend_desc = "整体基本平稳"
                conclusions.append(f"目标列为 `{target_col}`，样本数 {len(s)}，{trend_desc}（斜率={float(slope):.4g}）。")
        if session_id:
            if target_col and "timestamp" in df.columns:
                view = df.loc[:, ["timestamp", target_col]].copy()
                view["timestamp"] = pd.to_datetime(view["timestamp"], errors="coerce", utc=True)
                view[target_col] = pd.to_numeric(view[target_col], errors="coerce")
                view = view.dropna().sort_values("timestamp")
                if not view.empty:
                    ts_values = view["timestamp"]
                    y = view[target_col].astype(float).values
                    n = len(y)
                    if n >= 10:
                        roll = pd.Series(y).rolling(window=min(96, max(10, n // 20)), min_periods=1).mean().values
                        fig_t, ax_t = plt.subplots(figsize=(7, 3.5))
                        ax_t.plot(ts_values, y, color="#9e9e9e", linewidth=1)
                        ax_t.plot(ts_values, roll, color="#1565c0", linewidth=1.8)
                        ax_t.set_title("特征提取 - 趋势")
                        ax_t.set_xlabel("时间")
                        ax_t.set_ylabel(target_col)
                        fig_t.autofmt_xdate()
                        dn = "特征提取-趋势"
                        img_id = await _save_image_png(db, session_id=session_id, file_id=file_id, display_name=dn, fig=fig_t)
                        trend_insights = []
                        trend_delta = float(roll[-1] - roll[0]) if len(roll) >= 2 else 0.0
                        if trend_delta > 0:
                            trend_insights.append("从图上看，平滑后的主趋势整体向上。")
                        elif trend_delta < 0:
                            trend_insights.append("从图上看，平滑后的主趋势整体向下。")
                        else:
                            trend_insights.append("从图上看，平滑后的主趋势整体较为平稳。")
                        trend_insights.append(f"序列首尾平滑值变化约 **{abs(trend_delta):.4g}**。")
                        blocks.append(_image_block(dn, f"/api/v1/sessions/{session_id}/files/{file_id}/images/{img_id}/download", trend_insights))

                        y0 = y - np.mean(y)
                        max_lag = int(min(200, n - 2))
                        if max_lag >= 10:
                            corr = np.correlate(y0, y0, mode="full")
                            mid = len(corr) // 2
                            acf = corr[mid : mid + max_lag + 1]
                            denom = acf[0] if acf[0] else 1.0
                            acf = acf / denom
                            lags = np.arange(len(acf))
                            fig_acf, ax_acf = plt.subplots(figsize=(7, 3.2))
                            ax_acf.stem(lags[: min(len(lags), 120)], acf[: min(len(acf), 120)], linefmt="#006c4a", markerfmt="o", basefmt=" ")
                            ax_acf.set_title("特征提取 - 时域周期性（ACF）")
                            ax_acf.set_xlabel("滞后阶数")
                            ax_acf.set_ylabel("ACF")
                            dn = "特征提取-时域-周期性"
                            img_id = await _save_image_png(db, session_id=session_id, file_id=file_id, display_name=dn, fig=fig_acf)
                            acf_peak_idx = int(np.argmax(acf[1: min(len(acf), 121)])) + 1
                            acf_peak_val = float(acf[acf_peak_idx])
                            acf_insights = [
                                f"从图上看，最明显的自相关峰出现在滞后 **{acf_peak_idx}**，对应自相关系数约 **{acf_peak_val:.4g}**。"
                            ]
                            if acf_peak_val > 0.7:
                                acf_insights.append("这说明相邻一段时间内的数据延续性较强。")
                            blocks.append(_image_block(dn, f"/api/v1/sessions/{session_id}/files/{file_id}/images/{img_id}/download", acf_insights))

                        numeric_cols = df.select_dtypes(include="number").columns.tolist()
                        if len(numeric_cols) >= 2:
                            cols = numeric_cols[: min(10, len(numeric_cols))]
                            corr_m = df.loc[:, cols].corr(numeric_only=True).fillna(0.0).values
                            fig_c, ax_c = plt.subplots(figsize=(7, 5))
                            im = ax_c.imshow(corr_m, cmap="coolwarm", vmin=-1, vmax=1)
                            ax_c.set_xticks(range(len(cols)))
                            ax_c.set_yticks(range(len(cols)))
                            ax_c.set_xticklabels(cols, rotation=45, ha="right")
                            ax_c.set_yticklabels(cols)
                            fig_c.colorbar(im, ax=ax_c, fraction=0.046, pad=0.04)
                            ax_c.set_title("特征提取 - 相关性")
                            dn = "特征提取-时域-相关性"
                            img_id = await _save_image_png(db, session_id=session_id, file_id=file_id, display_name=dn, fig=fig_c)
                            corr_copy = corr_m.copy()
                            np.fill_diagonal(corr_copy, 0.0)
                            flat_idx = int(np.argmax(np.abs(corr_copy)))
                            r, c = divmod(flat_idx, corr_copy.shape[1])
                            corr_insights = [
                                f"从图上看，相关性最强的一组变量是 **{cols[r]}** 和 **{cols[c]}**，相关系数约 **{corr_m[r, c]:.4g}**。"
                            ]
                            blocks.append(_image_block(dn, f"/api/v1/sessions/{session_id}/files/{file_id}/images/{img_id}/download", corr_insights))
                        elif n >= 3:
                            fig_lp, ax_lp = plt.subplots(figsize=(4.5, 4.5))
                            ax_lp.scatter(y[:-1], y[1:], s=6, color="#6a1b9a", alpha=0.6)
                            ax_lp.set_title("特征提取 - 相关性（滞后1散点）")
                            ax_lp.set_xlabel("y[t-1]")
                            ax_lp.set_ylabel("y[t]")
                            dn = "特征提取-时域-相关性"
                            img_id = await _save_image_png(db, session_id=session_id, file_id=file_id, display_name=dn, fig=fig_lp)
                            lag_corr = float(np.corrcoef(y[:-1], y[1:])[0, 1]) if len(y) >= 3 else 0.0
                            blocks.append(
                                _image_block(
                                    dn,
                                    f"/api/v1/sessions/{session_id}/files/{file_id}/images/{img_id}/download",
                                    [f"从图上看，相邻时点的散点大致沿对角线分布，滞后 1 相关系数约 **{lag_corr:.4g}**。"],
                                )
                            )

                        tss = pd.to_datetime(ts_values, utc=True)
                        season_dn = "特征提取-时域-季节性"
                        by_hour = pd.Series(y).groupby(tss.dt.hour).mean()
                        by_weekday = pd.Series(y).groupby(tss.dt.dayofweek).mean()
                        by_month = pd.Series(y).groupby(tss.dt.month).mean()

                        season_kind = None
                        season_series = None
                        season_xlabel = None
                        if len(by_hour) >= 6:
                            season_kind = "小时均值"
                            season_series = by_hour
                            season_xlabel = "小时"
                        elif len(by_weekday) >= 4:
                            season_kind = "星期均值"
                            season_series = by_weekday
                            season_xlabel = "星期（0=周一）"
                        elif len(by_month) >= 2:
                            season_kind = "月均值"
                            season_series = by_month
                            season_xlabel = "月份"

                        if season_series is not None:
                            fig_s, ax_s = plt.subplots(figsize=(7, 3.2))
                            ax_s.plot(
                                season_series.index,
                                season_series.values,
                                marker="o",
                                linewidth=1.5,
                                color="#ff6f00",
                            )
                            ax_s.set_title(f"特征提取 - 季节性（{season_kind}）")
                            ax_s.set_xlabel(season_xlabel or "")
                            ax_s.set_ylabel(target_col)
                            img_id = await _save_image_png(
                                db,
                                session_id=session_id,
                                file_id=file_id,
                                display_name=season_dn,
                                fig=fig_s,
                            )
                            blocks.append(
                                _image_block(
                                    season_dn,
                                    f"/api/v1/sessions/{session_id}/files/{file_id}/images/{img_id}/download",
                                    [
                                        f"从图上看，按 **{season_kind}** 聚合后存在明显高低差，最高均值约 **{float(season_series.max()):.4g}**，最低均值约 **{float(season_series.min()):.4g}**。"
                                    ],
                                )
                            )

                        y_fill = np.nan_to_num(y0, nan=0.0)
                        fft = np.fft.rfft(y_fill)
                        amp = np.abs(fft)
                        freq = np.fft.rfftfreq(len(y_fill), d=1.0)
                        if len(freq) > 5:
                            fig_f, ax_f = plt.subplots(figsize=(7, 3.2))
                            ax_f.plot(freq[1: min(len(freq), 400)], amp[1: min(len(amp), 400)], color="#1565c0", linewidth=1)
                            ax_f.set_title("特征提取 - 傅里叶变换（幅度谱）")
                            ax_f.set_xlabel("频率")
                            ax_f.set_ylabel("幅度")
                            dn = "特征提取-频域-傅里叶变换"
                            img_id = await _save_image_png(db, session_id=session_id, file_id=file_id, display_name=dn, fig=fig_f)
                            peak_idx = int(np.argmax(amp[1: min(len(amp), 400)])) + 1
                            peak_freq = float(freq[peak_idx])
                            peak_amp = float(amp[peak_idx])
                            blocks.append(
                                _image_block(
                                    dn,
                                    f"/api/v1/sessions/{session_id}/files/{file_id}/images/{img_id}/download",
                                    [f"从图上看，主频峰值出现在频率 **{peak_freq:.4g}**，对应幅度约 **{peak_amp:.4g}**。"],
                                )
                            )

                            power = amp**2
                            freq2 = freq.copy()
                            freq2[0] = np.nan
                            period = 1.0 / freq2
                            mask = np.isfinite(period) & (period > 0) & np.isfinite(power)
                            period = period[mask]
                            power_p = power[mask]
                            if len(period) > 10:
                                idx = np.argsort(period)
                                period = period[idx]
                                power_p = power_p[idx]
                                fig_p, ax_p = plt.subplots(figsize=(7, 3.2))
                                ax_p.plot(period[: min(len(period), 400)], power_p[: min(len(power_p), 400)], color="#2e7d32", linewidth=1)
                                ax_p.set_title("特征提取 - 频域周期性（周期-能量）")
                                ax_p.set_xlabel("周期（点数）")
                                ax_p.set_ylabel("能量")
                                dn = "特征提取-频域-周期性"
                                img_id = await _save_image_png(db, session_id=session_id, file_id=file_id, display_name=dn, fig=fig_p)
                                peak_period_idx = int(np.argmax(power_p))
                                blocks.append(
                                    _image_block(
                                        dn,
                                        f"/api/v1/sessions/{session_id}/files/{file_id}/images/{img_id}/download",
                                        [f"从图上看，能量最集中的主周期约为 **{float(period[peak_period_idx]):.4g}** 个点。"],
                                    )
                                )

                        widths = np.arange(1, min(64, max(8, n // 8)))
                        if len(widths) >= 8:
                            cwtmatr = signal.cwt(y_fill, signal.morlet2, widths, w=5)
                            fig_w, ax_w = plt.subplots(figsize=(7, 4))
                            ax_w.imshow(np.abs(cwtmatr), aspect="auto", cmap="viridis", origin="lower")
                            ax_w.set_title("特征提取 - 小波变换（时频图）")
                            ax_w.set_xlabel("时间索引")
                            ax_w.set_ylabel("尺度")
                            dn = "特征提取-频域-小波变换"
                            img_id = await _save_image_png(db, session_id=session_id, file_id=file_id, display_name=dn, fig=fig_w)
                            energy = np.abs(cwtmatr)
                            dominant_scale = int(widths[np.argmax(np.mean(energy, axis=1))])
                            blocks.append(
                                _image_block(
                                    dn,
                                    f"/api/v1/sessions/{session_id}/files/{file_id}/images/{img_id}/download",
                                    [f"从图上看，能量主要集中在尺度 **{dominant_scale}** 附近，说明该尺度对应的波动更明显。"],
                                )
                            )
        if blocks:
            conclusions.append(f"已生成 {len(blocks)} 张特征图，可按“趋势 -> 时域 -> 频域”顺序查看。")
        text = _compose_result(text, blocks=blocks, conclusion_lines=conclusions)
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
        method_cn = _FORECAST_METHOD_CN.get(str(method), str(method))
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
        blocks: list[str] = []
        conclusions: list[str] = []
        if session_id:
            target_col = pick_target_column(df)
            if target_col and "timestamp" in df.columns:
                view = df.loc[:, ["timestamp", target_col]].copy()
                view["timestamp"] = pd.to_datetime(view["timestamp"], errors="coerce", utc=True)
                view[target_col] = pd.to_numeric(view[target_col], errors="coerce")
                view = view.dropna().sort_values("timestamp")
                if not view.empty:
                    ts_values = view["timestamp"].reset_index(drop=True)
                    y = view[target_col].astype(float).reset_index(drop=True).values
                    actual = None
                    pred = None
                    ts_plot = None
                    display_name = None
                    if method == "next_row" and len(y) >= 2:
                        actual = y[1:]
                        pred = y[:-1]
                        ts_plot = ts_values.iloc[1:]
                        display_name = "朴素预测-相邻两行"
                    elif method == "same_time" and len(y) >= 8:
                        lag = 7
                        actual = y[lag:]
                        pred = y[:-lag]
                        ts_plot = ts_values.iloc[lag:]
                        display_name = "朴素预测-相同时间点"
                    elif method == "daily_sum" and len(y) >= 15:
                        lag = 7
                        sums = []
                        for i in range(lag, len(y)):
                            sums.append(float(np.sum(y[i - lag : i])))
                        sums_arr = np.array(sums, dtype=float)
                        if len(sums_arr) >= 2:
                            actual = sums_arr[1:]
                            pred = sums_arr[:-1]
                            ts_plot = ts_values.iloc[lag + 1 :]
                            display_name = "朴素预测-按天累加"
                    if actual is not None and pred is not None and ts_plot is not None and display_name:
                        mae = float(np.mean(np.abs(actual - pred)))
                        rmse = float(np.sqrt(np.mean((actual - pred) ** 2)))
                        denom = np.where(actual == 0, 1, actual)
                        mape = float(np.mean(np.abs((actual - pred) / denom)) * 100)
                        k = int(min(200, len(actual)))
                        fig, ax = plt.subplots(figsize=(7, 3.5))
                        ax.plot(ts_plot.iloc[:k], actual[:k], color="#1565c0", linewidth=1.6, label="实际值")
                        ax.plot(ts_plot.iloc[:k], pred[:k], color="#006c4a", linewidth=1.2, label="预测值")
                        ax.set_title(f"{display_name}（对比前{k}点）")
                        ax.set_xlabel("时间")
                        ax.set_ylabel(target_col)
                        ax.legend(loc="best")
                        fig.autofmt_xdate()
                        image_id = await _save_image_png(
                            db,
                            session_id=session_id,
                            file_id=file_id,
                            display_name=display_name,
                            fig=fig,
                        )
                        url = f"/api/v1/sessions/{session_id}/files/{file_id}/images/{image_id}/download"
                        forecast_insights = [
                            f"从图上看，预测值整体跟随实际值变化，平均绝对误差约 **{mae:.4g}**，均方根误差约 **{rmse:.4g}**。"
                        ]
                        if mape <= 5:
                            forecast_insights.append("整体偏差较小，作为基线参考具有较好的可读性。")
                        elif mape <= 15:
                            forecast_insights.append("整体能跟住主要变化，但局部点位仍有一定偏差。")
                        else:
                            forecast_insights.append("图中可见部分区间的偏差较明显，适合作为基线对照，不适合直接当作高精度结果。")
                        blocks.append(_image_block(display_name, url, forecast_insights))
                        conclusions.append(
                            f"本次使用“{method_cn}”方法对 `{target_col}` 做基线回测，样本 {len(actual)} 条，平均绝对百分比误差 {mape:.2f}%，均方根误差 {rmse:.3g}。"
                        )
                        conclusions.append(f"已生成 `{display_name}` 对比图，可优先查看实际值与预测值的偏差。")
        text = _compose_result(text, blocks=blocks, conclusion_lines=conclusions)
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

        summary = await _file_summary_markdown(
            db,
            file_id=file_id,
            session_id=session_id,
            include_samples=True,
        )
        blocks: list[str] = []
        override_blocks = arguments.get("step_blocks")
        if isinstance(override_blocks, list) and all(isinstance(x, str) for x in override_blocks):
            blocks = [str(x).strip() for x in override_blocks if str(x).strip()]
        else:
            cursor = db.messages.find({"sessionId": to_object_id(session_id)}).sort("timestamp", 1)
        display_names = {
            "upload_data": "数据集确认",
            "eda_analysis": "EDA",
            "preprocessing": "预处理",
            "feature_analysis": "特征分析",
            "naive_forecast": "朴素预测",
        }
        step_no = 0
        if not blocks:
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
                    if tool_name in {"upload_data", "export_markdown"}:
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
                f"- 下载离线包（ZIP）：{download_url}",
                f"- 纯 Markdown（在线预览用）：{download_url}?format=md",
                "",
                "离线包解压后，直接打开 report_*.md 即可查看（图片与预处理 CSV 会随包一起提供）。",
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
