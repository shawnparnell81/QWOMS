"""Synthetic-only first login never exposes a password in source or logs."""
from sqlalchemy import select
from app.demo_bootstrap import seed
from app.models import User
from app.security import verify_password
from tests.test_foundation import client


def _demo_settings(monkeypatch):
    monkeypatch.setenv("QWOMS_DEMO_MODE", "true")
    monkeypatch.setenv("QWOMS_SYNTHETIC_DATA_ONLY", "true")
    monkeypatch.setenv("QWOMS_DEMO_ACCESS_MODE", "network")
    monkeypatch.setenv("QWOMS_DEMO_INITIAL_PASSWORD", "SYN-TEMP1!")
    for key in (
        "QWOMS_DEMO_QUALITY_PASSWORD",
        "QWOMS_DEMO_ENGINEERING_PASSWORD",
        "QWOMS_DEMO_PRODUCTION_PASSWORD",
    ):
        monkeypatch.setenv(key, "Synthetic-only-password-123!")


def test_legacy_demo_admin_chooses_personal_password_once(client, monkeypatch):
    web, Session = client
    _demo_settings(monkeypatch)
    with Session() as db:
        manager = db.get(User, 1)
        manager.username = "demo.manager"
        manager.is_admin = True
        db.commit()
        preserved_id = manager.id

    with Session() as db:
        seed(db)
        db.commit()
        owner = db.scalar(select(User).where(User.username == "demo"))
        assert owner.id == preserved_id
        assert owner.is_admin and owner.must_change_password
        assert db.scalar(select(User).where(User.username == "demo.manager")) is None

    response = web.post("/api/auth/login", json={"username": "demo", "password": "SYN-TEMP1!"})
    assert response.status_code == 200, response.text
    assert response.json()["must_change_password"] is True
    web.headers["X-QWOMS-CSRF"] = web.cookies["qwoms_csrf"]
    assert web.get("/api/me").status_code == 200
    assert web.get("/api/dashboard").status_code == 403
    assert web.post("/api/parts/import/preview").status_code == 403

    new_password = "Fictional-Personal-Password-2026!"
    result = web.post("/api/me/set-initial-password", json={"new_password": new_password})
    assert result.status_code == 200, result.text
    assert result.json()["reauthenticate"] is True
    assert web.get("/api/dashboard").status_code == 401
    assert web.post("/api/auth/login", json={"username": "demo", "password": "SYN-TEMP1!"}).status_code == 401

    response = web.post("/api/auth/login", json={"username": "demo", "password": new_password})
    assert response.status_code == 200
    assert response.json()["must_change_password"] is False
    assert web.get("/api/dashboard").status_code == 200
    assert web.post("/api/me/set-initial-password", json={"new_password": "Another-Personal-Password-2026!"}).status_code == 409
    with Session() as db:
        seed(db)
        db.commit()
        owner = db.scalar(select(User).where(User.username == "demo"))
        assert owner.id == preserved_id and not owner.must_change_password
        assert verify_password(new_password, owner.password_hash)
        assert not verify_password("SYN-TEMP1!", owner.password_hash)


def test_synthetic_bootstrap_requires_private_initial_password(client, monkeypatch):
    import pytest
    web, Session = client
    _demo_settings(monkeypatch)
    monkeypatch.delenv("QWOMS_DEMO_INITIAL_PASSWORD")
    with Session() as db:
        with pytest.raises(RuntimeError, match="temporary demo password"):
            seed(db)
        db.rollback()
        assert db.scalar(select(User).where(User.username == "demo")) is None
