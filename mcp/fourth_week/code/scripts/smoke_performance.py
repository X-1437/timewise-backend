"""W5-13: 性能实测脚本 — 测量首次响应时间和端到端全流程时间。"""

import time
import requests
from pathlib import Path

BASE = "http://127.0.0.1:8000/api/v1"
CSV_PATH = Path(r"D:\trae_workspace\data\file\fifth_week\test_data\sample_timeseries.csv")


def create_session():
    return requests.post(f"{BASE}/sessions", json={}, timeout=20).json()["data"]["id"]


def upload(session_id):
    with CSV_PATH.open("rb") as f:
        r = requests.post(
            f"{BASE}/files/upload",
            files={"file": (CSV_PATH.name, f, "text/csv")},
            data={"session_id": session_id},
            timeout=60,
        )
    return r.json()["data"]["id"]


def chat(content, session_id, file_id, timeout=120):
    return requests.post(
        f"{BASE}/chat/messages",
        json={"content": content, "session_id": session_id, "fileId": file_id},
        timeout=timeout,
    )


def main():
    results = {}

    # 1) 首次响应时间（EDA）
    sid = create_session()
    fid = upload(sid)
    t0 = time.time()
    chat("帮我做一下EDA", sid, fid)
    t1 = time.time()
    first_ms = (t1 - t0) * 1000
    results["首次响应(EDA)"] = f"{first_ms:.0f}ms (阈值 ≤800ms)"

    # 2) 端到端全流程
    sid2 = create_session()
    fid2 = upload(sid2)
    t0 = time.time()
    chat("帮我运行全流程", sid2, fid2, timeout=300)
    t1 = time.time()
    e2e_sec = t1 - t0
    results["端到端全流程"] = f"{e2e_sec:.1f}s (阈值 ≤15s)"

    # 3) 图表渲染（取 EDA 步骤内图片生成，用单步调用估测）
    sid3 = create_session()
    fid3 = upload(sid3)
    t0 = time.time()
    chat("帮我做一下EDA", sid3, fid3)
    t1 = time.time()
    chart_ms = (t1 - t0) * 1000
    # 图表渲染时间包含在首次EDA响应中，取整步时间作为上限估计
    results["图表渲染(含EDA全步)"] = f"≤{chart_ms:.0f}ms (阈值 ≤2000ms)"

    print("=== W5-13 性能实测结果 ===")
    for k, v in results.items():
        print(f"  {k}: {v}")

    # 判断是否达标
    first_ok = first_ms <= 800
    e2e_ok = e2e_sec <= 15
    chart_ok = chart_ms <= 2000
    all_ok = first_ok and e2e_ok and chart_ok

    print(f"\n验收结论: {'全部通过' if all_ok else '存在超标项'}")
    print(f"  首次响应: {'通过' if first_ok else '超标'}")
    print(f"  端到端: {'通过' if e2e_ok else '超标'}")
    print(f"  图表渲染: {'通过' if chart_ok else '超标'}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
