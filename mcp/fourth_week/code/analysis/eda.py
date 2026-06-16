from __future__ import annotations

import pandas as pd

from analysis.data import pick_target_column


def eda_markdown(df: pd.DataFrame, *, data_note: str | None = None) -> str:
    if df.empty:
        return "## EDA\n\n未找到可分析的数据。"

    total_rows = int(len(df))
    total_columns = int(len(df.columns))

    time_range = None
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True).dropna()
        if len(ts) > 0:
            time_range = (ts.min().isoformat(), ts.max().isoformat())

    missing_by_col: list[tuple[str, int, float]] = []
    for col in df.columns:
        missing_count = int(df[col].isnull().sum())
        missing_rate = float(missing_count / total_rows * 100) if total_rows else 0.0
        missing_by_col.append((col, missing_count, missing_rate))
    total_missing = sum(v[1] for v in missing_by_col)
    total_missing_rate = (
        float(total_missing / (total_rows * total_columns) * 100)
        if total_rows and total_columns
        else 0.0
    )

    duplicates = int(df.duplicated().sum())

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    stats_rows: list[str] = []
    for col in numeric_cols:
        s = df[col]
        if s.isnull().all():
            continue
        stats_rows.append(
            f"| {col} | {float(s.mean()):.6g} | {float(s.median()):.6g} | {float(s.std()):.6g} | {float(s.min()):.6g} | {float(s.max()):.6g} |"
        )

    target_col = pick_target_column(df)
    outlier_count = None
    if target_col:
        numeric = pd.to_numeric(df[target_col], errors="coerce").dropna()
        if len(numeric) > 0:
            mean = numeric.mean()
            std = numeric.std()
            if std and std == std:
                outlier_count = int(((numeric - mean).abs() > 3 * std).sum())
            else:
                outlier_count = 0

    lines: list[str] = []
    lines.append("## EDA 结果")
    lines.append("")
    if data_note:
        lines.append(f"- 数据版本：{data_note}")
        lines.append("")
    lines.append("### 1. 数据概览")
    lines.append(f"- 行数：{total_rows}")
    lines.append(f"- 列数：{total_columns}")
    if time_range:
        lines.append(f"- 时间范围：{time_range[0]} ~ {time_range[1]}")
    lines.append(f"- 重复行数：{duplicates}")
    if target_col and outlier_count is not None:
        lines.append(f"- 目标列（自动选择）：{target_col}")
        lines.append(f"- 异常值数量（zscore 3σ）：{outlier_count}")
    lines.append("")

    lines.append("### 2. 缺失值")
    lines.append(f"- 总缺失率：{total_missing_rate:.4g}%")
    lines.append("")
    lines.append("| 列 | 缺失数 | 缺失率 |")
    lines.append("|---|---:|---:|")
    for col, cnt, rate in sorted(missing_by_col, key=lambda x: x[1], reverse=True)[:20]:
        lines.append(f"| {col} | {cnt} | {rate:.4g}% |")
    lines.append("")

    lines.append("### 3. 数值统计")
    if stats_rows:
        lines.append("| 列 | 均值 | 中位数 | 标准差 | 最小值 | 最大值 |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        lines.extend(stats_rows[:20])
    else:
        lines.append("未找到数值列。")
    return "\n".join(lines)
