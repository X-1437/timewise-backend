import os
import re
from pathlib import Path

import requests
from bson import ObjectId


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


def chat(content: str, *, session_id: str, file_id: str, action: dict | None = None) -> dict:
    resp = requests.post(
        f"{BASE}/chat/messages",
        json={
            "content": content,
            "session_id": session_id,
            "fileId": file_id,
            "action": action,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def extract_image_urls(md_text: str) -> list[str]:
    return re.findall(r"!\[[^\]]*\]\((/api/v1/[^\)]+)\)", md_text or "")


def ensure_image_download(url: str) -> None:
    resp = requests.get(f"http://127.0.0.1:8000{url}", timeout=30)
    resp.raise_for_status()
    ct = resp.headers.get("content-type") or ""
    assert ct.startswith("image/png"), f"unexpected content-type: {ct}"
    assert len(resp.content) > 8, "empty image response"


def main() -> int:
    if not CSV_PATH.exists():
        print(f"CSV_NOT_FOUND: {CSV_PATH}")
        return 2

    session_id = create_session()
    up = upload(CSV_PATH, session_id=session_id)
    file_id = up["id"]

    msg_eda = chat(
        "EDA",
        session_id=session_id,
        file_id=file_id,
        action={"type": "call_tool", "tool_name": "eda_analysis", "tool_args": {"data_version": "raw"}},
    )
    eda_md = msg_eda["content"]
    eda_imgs = extract_image_urls(eda_md)
    assert eda_imgs, "EDA should output at least one image"
    ensure_image_download(eda_imgs[0])
    print("eda ok", len(eda_imgs))

    msg_pre = chat(
        "预处理",
        session_id=session_id,
        file_id=file_id,
        action={"type": "call_tool", "tool_name": "preprocessing", "tool_args": {"method": "outlier_remove"}},
    )
    pre_md = msg_pre["content"]
    pre_imgs = extract_image_urls(pre_md)
    assert len(pre_imgs) >= 2, "Preprocessing should output noise+outlier images"
    ensure_image_download(pre_imgs[0])
    ensure_image_download(pre_imgs[1])
    print("preprocess ok", len(pre_imgs))

    msg_feat = chat(
        "特征分析",
        session_id=session_id,
        file_id=file_id,
        action={"type": "call_tool", "tool_name": "feature_analysis", "tool_args": {"data_version": "raw"}},
    )
    feat_md = msg_feat["content"]
    feat_imgs = extract_image_urls(feat_md)
    assert len(feat_imgs) >= 6, "Feature analysis should output multiple images"
    for u in feat_imgs[:3]:
        ensure_image_download(u)
    print("feature ok", len(feat_imgs))

    msg_fc = chat(
        "朴素预测",
        session_id=session_id,
        file_id=file_id,
        action={
            "type": "call_tool",
            "tool_name": "naive_forecast",
            "tool_args": {"method": "next_row", "periods": 7, "data_version": "raw"},
        },
    )
    fc_md = msg_fc["content"]
    fc_imgs = extract_image_urls(fc_md)
    assert fc_imgs, "Forecast should output at least one image for selected method"
    ensure_image_download(fc_imgs[0])
    print("forecast ok", len(fc_imgs))

    msg_exp = chat(
        "导出报告",
        session_id=session_id,
        file_id=file_id,
        action={"type": "call_tool", "tool_name": "export_markdown", "tool_args": {"scope": "standard_flow"}},
    )
    exp_md = msg_exp["content"]
    m = re.search(r"- 下载：(/api/v1/sessions/[^\s]+/report/download)", exp_md)
    assert m, "export_markdown should return report download url"
    report_url = f"http://127.0.0.1:8000{m.group(1)}"
    resp = requests.get(report_url, timeout=30)
    resp.raise_for_status()
    assert "text/markdown" in (resp.headers.get("content-type") or ""), "report content-type mismatch"
    report_text = resp.text
    report_imgs = extract_image_urls(report_text)
    assert report_imgs, "report should include image references"
    ensure_image_download(report_imgs[0])
    print("export ok", len(report_imgs))

    bad_url = f"/api/v1/sessions/{session_id}/files/{file_id}/images/{ObjectId()}/download"
    resp = requests.get(f"http://127.0.0.1:8000{bad_url}", timeout=30)
    assert resp.status_code == 404, "image 404 expected"
    print("404 ok")

    print("ALL_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

