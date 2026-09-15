from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from wsgiref.util import setup_testing_defaults


TEST_ROOT = Path(tempfile.mkdtemp(prefix="calendar-python-test-"))
os.environ.setdefault("DATA_DIR", str(TEST_ROOT / "data"))
os.environ.setdefault("FRONTEND_DIR", str(Path(__file__).resolve().parents[2]))

from app.main import application  # noqa: E402


def request(method: str, path: str, payload=None, headers=None, raw: bytes | None = None, content_type="application/json"):
    environ = {}
    setup_testing_defaults(environ)
    body = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else b"")
    environ.update({
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(body),
    })
    for key, value in (headers or {}).items():
        environ["HTTP_" + key.upper().replace("-", "_")] = value
    captured = {}
    result = b"".join(application(environ, lambda status, response_headers: captured.update(status=status, headers=dict(response_headers))))
    parsed = json.loads(result) if captured["headers"]["Content-Type"].startswith("application/json") else result
    return captured["status"], parsed


class ServerTests(unittest.TestCase):
    owner = {"X-Device-Id": "device_test_123"}

    def test_health_and_legal_documents(self):
        status, health = request("GET", "/api/health")
        self.assertEqual(status, "200 OK")
        self.assertTrue(health["ok"])
        status, legal = request("GET", "/api/legal")
        self.assertEqual(status, "200 OK")
        slugs = {item["slug"] for item in legal["documents"]}
        self.assertTrue({"terms", "offer", "privacy", "personal-data-consent", "storage", "operator"} <= slugs)

    def test_project_round_trip(self):
        project = {"id": "project_123", "title": "Семейный календарь", "payload": {"pages": [True, False], "events": []}}
        status, saved = request("POST", "/api/projects", project, self.owner)
        self.assertEqual(status, "200 OK")
        self.assertTrue(saved["ok"])
        status, listed = request("GET", "/api/projects", headers=self.owner)
        self.assertEqual(status, "200 OK")
        self.assertEqual(listed["projects"][0]["title"], "Семейный календарь")

    def test_support_and_separate_consent(self):
        status, support = request("POST", "/api/support", {"message": "Не определяется страница", "page_number": 6, "step": "scan"}, self.owner)
        self.assertEqual(status, "201 Created")
        self.assertTrue(support["id"].startswith("SUP-"))
        status, consent = request("POST", "/api/consents", {"document_slug": "personal-data-consent", "accepted": True, "source": "registration"}, self.owner)
        self.assertEqual(status, "201 Created")
        self.assertTrue(consent["accepted"])

    def test_page_upload_validation(self):
        status, result = request("PUT", "/api/projects/project_123/pages/6/processed", headers=self.owner, raw=b"x" * 200, content_type="image/jpeg")
        self.assertEqual(status, "201 Created")
        self.assertEqual(result["page"], 6)
        status, _ = request("PUT", "/api/projects/project_123/pages/13/source", headers=self.owner, raw=b"x" * 200, content_type="image/jpeg")
        self.assertEqual(status, "400 Bad Request")


if __name__ == "__main__":
    unittest.main()
