from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable


def build_markdown_report(
    *,
    title: str,
    file_summary: str,
    step_blocks: Iterable[str],
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## 数据集信息")
    lines.append("")
    lines.append(file_summary.strip() if file_summary.strip() else "未提供文件信息。")
    lines.append("")
    lines.append("## 分析步骤与结果")
    lines.append("")
    for block in step_blocks:
        b = (block or "").strip()
        if not b:
            continue
        lines.append(b)
        lines.append("")
    lines.append("## 生成信息")
    lines.append("")
    lines.append(f"- 生成时间（UTC）：{now}")
    return "\n".join(lines).strip() + "\n"
