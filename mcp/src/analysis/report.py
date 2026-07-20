from __future__ import annotations

from typing import Iterable


def _normalize_step_block(block: str) -> str:
    raw = (block or "").strip()
    if not raw:
        return ""

    lines = raw.splitlines()
    head = ""
    body_lines = lines
    if lines and lines[0].startswith("### "):
        head = lines[0]
        body_lines = lines[1:]
        if body_lines and not body_lines[0].strip():
            body_lines = body_lines[1:]

    if body_lines and body_lines[0].startswith("## "):
        body_lines = body_lines[1:]
        if body_lines and not body_lines[0].strip():
            body_lines = body_lines[1:]

    normalized: list[str] = []
    for line in body_lines:
        if line.startswith("### "):
            normalized.append("#### " + line[4:])
        elif line.startswith("## "):
            normalized.append("#### " + line[3:])
        else:
            normalized.append(line)

    if head:
        return "\n".join([head, "", *normalized]).strip()
    return "\n".join(normalized).strip()


def build_markdown_report(
    *,
    title: str,
    file_summary: str,
    step_blocks: Iterable[str],
) -> str:
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
        b = _normalize_step_block(block)
        if not b:
            continue
        lines.append(b)
        lines.append("")
    return "\n".join(lines).strip() + "\n"
