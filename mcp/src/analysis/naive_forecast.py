from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.data import pick_target_column


_METHOD_CN = {
    "next_row": "相邻两行",
    "same_time": "相同时间点",
    "daily_sum": "按天累加",
}


def _metrics(actual: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    mae = float(np.mean(np.abs(actual - pred)))
    mse = float(np.mean((actual - pred) ** 2))
    rmse = float(np.sqrt(mse))
    denom = np.where(actual == 0, 1, actual)
    mape = float(np.mean(np.abs((actual - pred) / denom)) * 100)
    return {"mae": mae, "mse": mse, "rmse": rmse, "mape": mape}


def naive_forecast_markdown(
    df: pd.DataFrame,
    *,
    method: str = "next_row",
    periods: int = 7,
    data_note: str | None = None,
) -> str:
    if df.empty:
        return "## 朴素预测\n\n未找到可分析的数据。"

    target_col = pick_target_column(df)
    if not target_col:
        return "## 朴素预测\n\n未找到数值列，无法预测。"

    s = pd.to_numeric(df[target_col], errors="coerce").dropna()
    values = s.values.astype(float)
    if len(values) < 8:
        return f"## 朴素预测\n\n目标列 `{target_col}` 数据量不足（需要至少 8 行）。"

    preds: list[float] = []
    actuals: list[float] = []

    if method == "next_row":
        for i in range(1, len(values)):
            preds.append(float(values[i - 1]))
            actuals.append(float(values[i]))
    elif method == "same_time":
        for i in range(7, len(values)):
            preds.append(float(values[i - 7]))
            actuals.append(float(values[i]))
    elif method == "daily_sum":
        daily_sums = []
        for i in range(7, len(values)):
            daily_sums.append(float(np.sum(values[i - 7 : i])))
        for i in range(1, len(daily_sums)):
            preds.append(float(daily_sums[i - 1]))
            actuals.append(float(daily_sums[i]))
    else:
        method = "next_row"
        for i in range(1, len(values)):
            preds.append(float(values[i - 1]))
            actuals.append(float(values[i]))

    pred_arr = np.array(preds, dtype=float)
    actual_arr = np.array(actuals, dtype=float)
    m = _metrics(actual_arr, pred_arr)

    future = [float(values[-1])] * max(1, int(periods))
    method_cn = _METHOD_CN.get(method, method)

    lines: list[str] = []
    lines.append("## 朴素预测结果")
    lines.append("")
    if data_note:
        lines.append(f"- 数据版本：**{data_note}**")
        lines.append("")
    lines.append(f"- 目标列（自动选择）：**{target_col}**")
    lines.append(f"- 方法：**{method_cn}**")
    lines.append(f"- 未来预测步数：**{int(periods)}**")
    lines.append("")
    lines.append("### 1. 基线回测指标")
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---:|")
    lines.append(f"| 平均绝对误差 | {m['mae']:.6g} |")
    lines.append(f"| 均方误差 | {m['mse']:.6g} |")
    lines.append(f"| 均方根误差 | {m['rmse']:.6g} |")
    lines.append(f"| 平均绝对百分比误差 | {m['mape']:.6g}% |")
    lines.append("")
    lines.append("### 2. 回测样例（前 10 条）")
    lines.append("| 序号 | 实际值 | 预测值 |")
    lines.append("|---:|---:|---:|")
    for i in range(min(10, len(pred_arr))):
        lines.append(f"| {i} | {actual_arr[i]:.6g} | {pred_arr[i]:.6g} |")
    lines.append("")
    lines.append("### 3. 未来朴素预测（基于最后一个值延续）")
    lines.append("| 步数 | 预测值 |")
    lines.append("|---:|---:|")
    for i in range(min(30, len(future))):
        lines.append(f"| {i + 1} | {future[i]:.6g} |")
    return "\n".join(lines)
