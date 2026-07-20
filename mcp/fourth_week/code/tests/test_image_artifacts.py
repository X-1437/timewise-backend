import os
import unittest
from dataclasses import dataclass
from pathlib import Path

from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.exports import router as exports_router
from mcp_layer.tools import mcp_tools


@dataclass
class _InsertResult:
    inserted_id: ObjectId


class _FakeCollection:
    def __init__(self):
        self.docs: dict[ObjectId, dict] = {}

    async def insert_one(self, doc: dict):
        oid = ObjectId()
        stored = dict(doc)
        stored["_id"] = oid
        self.docs[oid] = stored
        return _InsertResult(inserted_id=oid)

    async def find_one(self, query: dict):
        for doc in self.docs.values():
            ok = True
            for k, v in query.items():
                if doc.get(k) != v:
                    ok = False
                    break
            if ok:
                return dict(doc)
        return None


class _FakeDB:
    def __init__(self):
        self.artifacts = _FakeCollection()


class TestImageArtifacts(unittest.IsolatedAsyncioTestCase):
    async def test_save_image_png_writes_artifact(self):
        db = _FakeDB()
        fig, ax = mcp_tools.plt.subplots(figsize=(3, 2))
        ax.plot([1, 2, 3], [1, 4, 9])
        session_id = str(ObjectId())
        file_id = str(ObjectId())
        image_id = await mcp_tools._save_image_png(
            db,
            session_id=session_id,
            file_id=file_id,
            display_name="EDA-按月可视化",
            fig=fig,
        )
        oid = ObjectId(image_id)
        doc = db.artifacts.docs.get(oid)
        self.assertIsNotNone(doc)
        self.assertEqual(doc["type"], "image_png")
        self.assertEqual(doc["displayName"], "EDA-按月可视化")
        self.assertTrue(Path(doc["path"]).exists())
        os.remove(doc["path"])


class TestDownloadImage(unittest.TestCase):
    def test_download_image_ok(self):
        db = _FakeDB()
        session_id = str(ObjectId())
        file_id = str(ObjectId())

        p = Path(__file__).resolve().parent / "tmp_test.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n")

        oid = ObjectId()
        db.artifacts.docs[oid] = {
            "_id": oid,
            "type": "image_png",
            "path": str(p),
            "displayName": "EDA-按月可视化",
            "createdAt": None,
            "sessionId": ObjectId(session_id),
            "fileId": ObjectId(file_id),
        }

        app = FastAPI()
        app.include_router(exports_router, prefix="/api/v1")
        app.state.db = db
        client = TestClient(app)

        url = f"/api/v1/sessions/{session_id}/files/{file_id}/images/{str(oid)}/download"
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("content-type"), "image/png")

        p.unlink()

    def test_download_image_404(self):
        db = _FakeDB()
        session_id = str(ObjectId())
        file_id = str(ObjectId())
        image_id = str(ObjectId())

        app = FastAPI()
        app.include_router(exports_router, prefix="/api/v1")
        app.state.db = db
        client = TestClient(app)

        url = f"/api/v1/sessions/{session_id}/files/{file_id}/images/{image_id}/download"
        resp = client.get(url)
        self.assertEqual(resp.status_code, 404)

