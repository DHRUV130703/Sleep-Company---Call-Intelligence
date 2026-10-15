"""Workspaces (app/workspaces.py): one app, each account sees only its own workspace's database."""

import json

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app import config, db
from app.main import app
from app.models import Lead
from app.workspaces import database_urls, in_workspace

ACCOUNTS = {
    "dhruv.gohil@thesleepcompany.in": {"password": "pw-d", "workspace": "main"},
    "ashish.kumar@thesleepcompany.in": {"password": "pw-a", "workspace": "ashish"},
    "teammate@thesleepcompany.in": "pw-t",  # plain password = workspace "main"
}


def _setup(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APP_USERS", json.dumps(ACCOUNTS))
    monkeypatch.setenv("APP_SECRET", "s")
    monkeypatch.setenv("WORKSPACE_DATABASES", json.dumps({"ashish": f"sqlite:///{tmp_path / 'ashish.db'}"}))
    config.get_settings.cache_clear()
    db.clear_engines()
    for ws, names in (("main", ["Main lead 1", "Main lead 2"]), ("ashish", ["Ashish lead"])):
        with in_workspace(ws):
            SQLModel.metadata.create_all(db.get_engine())
            with Session(db.get_engine()) as s:
                s.add_all([Lead(name=n) for n in names])
                s.commit()


def _signed_in(email: str, password: str) -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": password}).status_code == 200
    return c


def test_each_account_sees_only_its_own_workspace(isolated_data_dir, monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert list(database_urls()) == ["main", "ashish"]

    dhruv = _signed_in("dhruv.gohil@thesleepcompany.in", "pw-d")
    ashish = _signed_in("ashish.kumar@thesleepcompany.in", "pw-a")
    teammate = _signed_in("teammate@thesleepcompany.in", "pw-t")

    assert dhruv.get("/api/leads").json()["total"] == 2
    assert ashish.get("/api/leads").json()["total"] == 1
    assert teammate.get("/api/leads").json()["total"] == 2  # same workspace as Dhruv: shared data
    assert ashish.get("/api/auth/status").json()["workspace"] == "ashish"
    names = [row["name"] for row in ashish.get("/api/leads").json()["items"]]
    assert names == ["Ashish lead"]  # nothing from the main workspace leaks through


def test_account_with_unknown_workspace_is_refused(isolated_data_dir, monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setenv("APP_USERS", json.dumps({"x@y.in": {"password": "p", "workspace": "nowhere"}}))
    config.get_settings.cache_clear()
    c = _signed_in("x@y.in", "p")
    r = c.get("/api/leads")
    assert r.status_code == 401 and "workspace" in r.json()["error"]["message"]


def test_shared_report_links_open_in_their_own_workspace():
    from app.auth import report_link_workspace

    assert report_link_workspace("/api/reports/AbC_123-xyz/report.pdf") == "main"
    assert report_link_workspace("/api/reports/ashish.AbC_123-xyz/report.pdf") == "ashish"
