import os
from pathlib import Path

import requests


BASE = os.environ.get("HS_BASE_URL", "http://127.0.0.1:8000/api/v1")
CSV_PATH = Path(r"D:\trae_workspace\data\file\fifth_week\test_data\sample_timeseries.csv")


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
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def main() -> int:
    session_id = create_session()
    up = upload(CSV_PATH, session_id=session_id)
    file_id = up["id"]
    data = chat("帮我运行全流程", session_id=session_id, file_id=file_id)
    print("session_id:", session_id)
    print("file_id:", file_id)
    print("assistant content:")
    print(data.get("content") or "")
    print("toolCalls count:", len(data.get("toolCalls") or []))
    if data.get("toolCalls"):
        print("toolCalls tools:", [tc.get("toolName") or tc.get("tool_name") for tc in data["toolCalls"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

