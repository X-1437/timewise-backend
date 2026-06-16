from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.data import pick_target_column


def _acf(values: np.ndarray, *, nlags: int) -> list[float]:
    values = values.astype(float)
    values = values - np.mean(values)
    denom = np.dot(values, values)
    if denom == 0:
        return [1.0] + [0.0] * nlags
    acf = [1.0]
    for lag in range(1, nlags + 1):
        num = np.dot(values[:-lag], values[lag:])
        acf.append(float(num / denom))
    return acf


def feature_markdown(df: pd.DataFrame, *, data_note: str | None = None) -> str:
    if df.empty:
        return "## 特征分析\n\n未找到可分析的数据。"

    target_col = pick_target_column(df)
    if not target_col:
        return "## 特征分析\n\n未找到数值列，无法提取特征。"

    s = pd.to_numeric(df[target_col], errors="coerce").dropna()
    if len(s) < 3:
        return f"## 特征分析\n\n目标列 `{target_col}` 数据量不足。"

    x = np.arange(len(s))
    slope, intercept = np.polyfit(x, s.values, 1)

    nlags = int(min(20, len(s) - 1))
    acf_vals = _acf(s.values, nlags=nlags)

    lines: list[str] = []
    lines.append("## 特征分析结果")
    lines.append("")
    if data_note:
        lines.append(f"- 数据版本：{data_note}")
        lines.append("")
    lines.append(f"- 目标列（自动选择）：{target_col}")
    lines.append("")
    lines.append("### 1. 趋势（线性）")
    lines.append(f"- slope：{float(slope):.6g}")
    lines.append(f"- intercept：{float(intercept):.6g}")
    lines.append("")
    lines.append("### 2. 自相关（ACF）")
    lines.append("| lag | acf |")
    lines.append("|---:|---:|")
    for lag, v in enumerate(acf_vals[: min(len(acf_vals), 11)]):
        lines.append(f"| {lag} | {v:.6g} |")
    lines.append("")
    lines.append("### 3. 滚动统计（窗口=7）")
    roll_mean = s.rolling(window=7, min_periods=1).mean().iloc[-1]
    roll_std = s.rolling(window=7, min_periods=1).std().iloc[-1]
    lines.append(f"- 最近窗口均值：{float(roll_mean):.6g}")
    lines.append(f"- 最近窗口标准差：{float(roll_std if roll_std == roll_std else 0.0):.6g}")
    return "\n".join(lines)
