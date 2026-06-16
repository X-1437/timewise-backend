import sys
import os
from pathlib import Path

import requests


BASE = os.environ.get("HS_BASE_URL", "http://127.0.0.1:8000/api/v1")
CSV_PATH = Path(r"D:\trae_workspace\data\file\fourth_week\test_data\test_sales_dirty.csv")


def upload(path: Path):
    with path.open("rb") as f:
        resp = requests.post(
            f"{BASE}/files/upload",
            files={"file": (path.name, f, "text/csv")},
        )
    resp.raise_for_status()
    return resp.json()["data"]


def chat(content: str, *, session_id: str | None, file_id: str, action: dict | None = None):
    resp = requests.post(
        f"{BASE}/chat/messages",
        json={
            "content": content,
            "session_id": session_id,
            "fileId": file_id,
            "action": action,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def main() -> int:
    if not CSV_PATH.exists():
        print(f"CSV_NOT_FOUND: {CSV_PATH}")
        return 2

    up = upload(CSV_PATH)
    file_id = up["id"]
    session_id = up.get("session_id")
    print("uploaded", file_id, session_id)

    preprocess_msg = chat("帮我清洗一下这个数据", session_id=session_id, file_id=file_id)
    session_id = preprocess_msg.get("session_id") or session_id
    print("preprocess ok")

    eda_confirm = chat("帮我简单分析一下这个数据", session_id=session_id, file_id=file_id)
    assert "需要确认" in eda_confirm["content"], "EDA should require confirmation when raw+preprocessed exist"
    eda_actions = eda_confirm.get("actions") or []
    run_pre = next(
        (a for a in eda_actions if (a.get("label") or "").startswith("查看预处理后 EDA")),
        None,
    )
    assert run_pre, "EDA confirmation missing preprocessed option"

    eda_msg = chat(
        run_pre.get("label") or "查看预处理后 EDA（推荐）",
        session_id=session_id,
        file_id=file_id,
        action={
            "type": "call_tool",
            "tool_name": run_pre["tool_name"],
            "tool_args": run_pre.get("tool_args") or {},
        },
    )
    eda = eda_msg["content"]
    assert "数据版本：" in eda, "EDA missing data version"
    assert "预处理后数据" in eda, "EDA not using preprocessed data"
    print("eda confirm ok")

    up2 = upload(CSV_PATH)
    file_id2 = up2["id"]
    session_id2 = up2.get("session_id")

    feat_confirm = chat("分析一下这个数据具有哪些特征", session_id=session_id2, file_id=file_id2)
    session_id2 = feat_confirm.get("session_id") or session_id2
    assert "需要确认" in feat_confirm["content"], "Feature should require confirmation when no preprocess"
    actions = feat_confirm.get("actions") or []
    assert len(actions) >= 3, "Feature confirmation should provide options"
    run_raw = next((a for a in actions if a.get("tool_name") == "feature_analysis"), None)
    assert run_raw, "Feature confirmation missing run-raw option"

    feat_msg = chat(
        run_raw.get("label") or "直接基于原始数据分析",
        session_id=session_id2,
        file_id=file_id2,
        action={
            "type": "call_tool",
            "tool_name": run_raw["tool_name"],
            "tool_args": run_raw.get("tool_args") or {},
        },
    )
    feat = feat_msg["content"]
    assert "数据版本" in feat, "Feature result missing data version"
    assert "原始数据" in feat, "Feature result should use raw data when user confirms"
    print("feature confirm ok")

    fc_confirm = chat("进行一下朴素预测", session_id=session_id2, file_id=file_id2)
    assert "需要确认" in fc_confirm["content"], "Forecast should require confirmation when no preprocess"
    actions2 = fc_confirm.get("actions") or []
    assert len(actions2) >= 3, "Forecast confirmation should provide options"
    run_raw2 = next((a for a in actions2 if a.get("tool_name") == "naive_forecast"), None)
    assert run_raw2, "Forecast confirmation missing run-raw option"

    fc_msg = chat(
        run_raw2.get("label") or "直接基于原始数据预测",
        session_id=session_id2,
        file_id=file_id2,
        action={
            "type": "call_tool",
            "tool_name": run_raw2["tool_name"],
            "tool_args": run_raw2.get("tool_args") or {},
        },
    )
    fc = fc_msg["content"]
    assert "数据版本" in fc, "Forecast result missing data version"
    assert "原始数据" in fc, "Forecast result should use raw data when user confirms"
    print("forecast confirm ok")

    print("ALL_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
