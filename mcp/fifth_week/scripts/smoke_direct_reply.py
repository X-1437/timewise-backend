"""W5-10: 非分析输入统一引导回复 — 接口级冒烟测试（所有输入不包含分析关键词）。"""

import os
from pathlib import Path

import requests


BASE = os.environ.get("HS_BASE_URL", "http://127.0.0.1:8000/api/v1")
CSV_PATH = Path(r"D:\trae_workspace\data\file\fifth_week\test_data\sample_timeseries.csv")

# 统一引导回复的关键检测子串（不要求逐字完全匹配，但必须包含）
UNIFIED_REPLY_MARKERS = ["时间序列数据分析助手"]


def create_session() -> str:
    resp = requests.post(f"{BASE}/sessions", json={}, timeout=20)
    resp.raise_for_status()
    return resp.json()["data"]["id"]


def upload(path: Path, *, session_id: str) -> dict:
    with path.open("rb") as f:
        resp = requests.post(
            f"{BASE}/files/upload",
            files={"file": (path.name, f, "text/csv")},
            data={"session_id": session_id},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()["data"]


def chat(content: str, *, session_id: str, file_id: str) -> dict:
    resp = requests.post(
        f"{BASE}/chat/messages",
        json={
            "content": content,
            "session_id": session_id,
            "fileId": file_id,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def main() -> int:
    session_id = create_session()
    up = upload(CSV_PATH, session_id=session_id)
    file_id = up["id"]

    # W5-10: 所有输入均不包含分析关键词（如"分析"/"预测"/"预处理"/"eda"等），
    # 预期全部返回统一引导回复。
    non_analysis_cases = [
        "你好",
        "今天天气怎么样",
        "你是谁",
        "你能做什么",
        "讲个笑话",
        "给我推荐一本书",
        "你知道RandomForest吗",
        "用XXX算法",
    ]

    failed = 0
    for content in non_analysis_cases:
        data = chat(content, session_id=session_id, file_id=file_id)
        text = data["content"]
        ok = any(marker in text for marker in UNIFIED_REPLY_MARKERS)
        if ok:
            print(f"✅ {content}  → 统一引导回复")
        else:
            # 检查是否误触发 EDA
            is_eda = "EDA" in text and "数据概览" in text
            label = "误触发EDA" if is_eda else "非预期回复"
            print(f"❌ {content}  → {label}（前80字: {text[:80]}）")
            failed += 1

    print(f"\n结果: {len(non_analysis_cases) - failed}/{len(non_analysis_cases)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
