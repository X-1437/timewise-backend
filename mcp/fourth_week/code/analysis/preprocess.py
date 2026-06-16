from __future__ import annotations

import pandas as pd

from analysis.data import pick_target_column


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


def preprocess_markdown(df: pd.DataFrame, *, method: str) -> tuple[pd.DataFrame, str]:
    if df.empty:
        return df, "## 预处理结果\n\n未找到可处理的数据。"

    before_rows = int(len(df))
    before_missing = int(df.isnull().sum().sum())

    out = df.copy()

    missing_rows_mask = df.isnull().any(axis=1)
    missing_rows_count = int(missing_rows_mask.sum())
    missing_preview = _md_table(df.loc[missing_rows_mask], max_rows=10) if missing_rows_count else ""

    target_col_for_outlier = pick_target_column(df)
    outlier_rows_count = 0
    outlier_preview = ""
    if method == "outlier_remove" and target_col_for_outlier:
        s0 = pd.to_numeric(df[target_col_for_outlier], errors="coerce")
        s0_valid = s0.dropna()
        std0 = s0_valid.std() if len(s0_valid) else 0.0
        if std0 and std0 == std0:
            mean0 = s0_valid.mean()
            outlier_mask0 = ((s0 - mean0).abs() > 3 * std0).fillna(False)
            outlier_rows_count = int(outlier_mask0.sum())
            outlier_preview = _md_table(df.loc[outlier_mask0], max_rows=10) if outlier_rows_count else ""

    if method == "type_convert":
        for col in out.columns:
            if col == "timestamp":
                continue
            out[col] = pd.to_numeric(out[col], errors="ignore")

    if method in {"missing_fill", "outlier_remove"}:
        for col in out.columns:
            if col == "timestamp":
                continue
            if pd.api.types.is_numeric_dtype(out[col]):
                out[col] = out[col].ffill().bfill()
                if out[col].isnull().any():
                    out[col] = out[col].fillna(out[col].mean())
            else:
                out[col] = out[col].ffill().bfill()

    removed = 0
    if method == "outlier_remove":
        target_col = pick_target_column(out)
        if target_col:
            s = pd.to_numeric(out[target_col], errors="coerce")
            mean = s.mean()
            std = s.std()
            if std and std == std:
                mask = (s - mean).abs() <= 3 * std
                removed = int((~mask).sum())
                out = out[mask]

    after_rows = int(len(out))
    after_missing = int(out.isnull().sum().sum())
    filled = max(0, before_missing - after_missing)

    lines: list[str] = []
    lines.append("## 预处理结果")
    lines.append("")
    lines.append(f"- 方法：{method}")
    if method == "outlier_remove":
        lines.append("- 说明：该模式会先进行缺失值填充，再做异常值移除")
    lines.append("- 后续分析默认使用：预处理后数据（同一会话内，如需用原始数据请显式指定）")
    lines.append(f"- 处理前行数：{before_rows}")
    lines.append(f"- 处理后行数：{after_rows}")
    if method == "outlier_remove":
        lines.append(f"- 移除异常行数：{removed}")
    lines.append(f"- 缺失值变化：{before_missing} -> {after_missing}（填充 {filled}）")
    lines.append("")
    lines.append("### 质量问题（处理前）")
    lines.append(f"- 含缺失值的行数：{missing_rows_count}")
    if method == "outlier_remove":
        lines.append(f"- 异常值行数（3σ，基于 `{target_col_for_outlier or ''}`）：{outlier_rows_count}")
    lines.append("")
    if missing_preview:
        lines.append("#### 缺失值行样例（最多 10 行）")
        lines.append(missing_preview)
        lines.append("")
    if outlier_preview:
        lines.append("#### 异常值行样例（最多 10 行）")
        lines.append(outlier_preview)
        lines.append("")
    lines.append("### 列信息")
    cols = [c for c in out.columns]
    lines.append(f"- 列数：{len(cols)}")
    lines.append(f"- 列名：{', '.join(cols[:30])}{'...' if len(cols) > 30 else ''}")
    return out, "\n".join(lines)
