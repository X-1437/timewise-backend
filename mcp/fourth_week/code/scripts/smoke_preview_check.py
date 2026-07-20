"""测试 run_full_flow 的 content 和 format=md 预览内容。"""

import requests

BASE = "http://127.0.0.1:8000/api/v1"


def main():
    import re
    from pathlib import Path

    csv_path = Path(r"D:\trae_workspace\data\file\fifth_week\test_data\sample_timeseries.csv")

    sid = requests.post(f"{BASE}/sessions", json={}, timeout=20).json()["data"]["id"]
    with csv_path.open("rb") as f:
        r = requests.post(
            f"{BASE}/files/upload",
            files={"file": (csv_path.name, f, "text/csv")},
            data={"session_id": sid},
            timeout=60,
        )
    fid = r.json()["data"]["id"]
    print(f"session={sid}, file={fid}")

    print("Running 帮我运行全流程...")
    r2 = requests.post(
        f"{BASE}/chat/messages",
        json={"content": "帮我运行全流程", "session_id": sid, "fileId": fid},
        timeout=300,
    )
    data = r2.json()["data"]
    content = data["content"]
    tool_calls_count = len(data.get("tool_calls") or [])

    print(f"\n=== response.content (length={len(content)}) ===")
    print(content[:600])

    urls = re.findall(r"/api/v1/sessions/[^\s]+/report/download", content)
    print(f"\nreport URLs: {len(urls)}")
    for u in urls:
        print(f"  {u}")

    if urls:
        report_url = urls[0]
        print(f"\nFetching {report_url}?format=md ...")
        r3 = requests.get(f"http://127.0.0.1:8000{report_url}?format=md", timeout=60)
        md_text = r3.text
        print(f"status={r3.status_code} ct={r3.headers.get('content-type','?')[:60]}")
        print(f"BOM={md_text.startswith(chr(0xFEFF))} len={len(md_text)}")
        print(f"\n=== first 400 chars of format=md ===")
        print(md_text[:400])
        print(f"\n=== 验证关键内容 ===")
        print(f"has ##: {'## ' in md_text}")
        print(f"has 数据集信息: {'数据集信息' in md_text}")
        print(f"has 看图结论: {'看图结论' in md_text}")
        print(f"has 导出完成: {'导出完成' in md_text}")
        print(f"BOLD markers: {md_text.count('**')}")


if __name__ == "__main__":
    main()
