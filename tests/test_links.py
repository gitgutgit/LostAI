"""/api/links: 입장 토큰이 있어야 문서 주소를 준다. author: Mal-Mi-Jal"""
from fastapi.testclient import TestClient

from server import app as app_mod
from server.auth import challenge


def test_links_requires_token(monkeypatch):
    with TestClient(app_mod.app) as c:
        assert c.get("/api/links", params={"token": "nobody.bad"}).status_code == 401
        token = challenge.make_token("Ines")
        assert c.get("/api/links", params={"token": token}).json() == {"sheet": None, "doc": None, "doc_sync": False}

        monkeypatch.setenv("GOOGLE_SHEET_ID", "https://docs.google.com/spreadsheets/d/S_ID/edit")
        monkeypatch.setenv("GOOGLE_DOC_ID", "D_ID")
        r = c.get("/api/links", params={"token": token}).json()
        assert r["sheet"].startswith("https://docs.google.com/spreadsheets/d/S_ID/edit")
        assert r["doc"] == "https://docs.google.com/document/d/D_ID/edit"
