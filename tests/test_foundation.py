"""Integration tests use a temporary SQLite database and entirely fabricated parts."""
import os
os.environ["QWOMS_SECRET_KEY"] = "development-test-secret-only-" + "x" * 48
os.environ["QWOMS_COOKIE_SECURE"] = "false"
from io import BytesIO
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db import Base, session
from app.main import app
import app.main as module
from app.models import User, PhysicalPart
from app.security import hash_password


def workbook(rows):
    w = Workbook()
    s = w.active
    s.append(["Product Family", "O'Reilly PN", "NAPA PN", "Drawing Number", "Rev", "UPC"])
    for row in rows:
        s.append(row)
    stream = BytesIO()
    w.save(stream)
    return stream.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add(User(username="manager", display_name="Test Manager", role="Management", site="Site A",
                    password_hash=hash_password("SufficientlyLongPassword!")))
        db.add(User(username="engineer", display_name="Test Engineer", role="Engineering", site="Site B",
                    password_hash=hash_password("OtherLongPassword123!")))
        db.commit()
    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[session] = override
    monkeypatch.setattr(module, "STORAGE_ROOT", tmp_path / "storage")
    with TestClient(app) as test_client:
        yield test_client, Session
    app.dependency_overrides.clear()
    engine.dispose()


def logged_in(client):
    r = client.post("/api/auth/login", json={"username": "manager", "password": "SufficientlyLongPassword!"})
    assert r.status_code == 200, r.text


def part_import(client, rows, url="commit"):
    data = workbook(rows)
    return client.post(f"/api/parts/import/{url}", files={"file": ("part-master.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})


def test_login_required_and_accounts(client):
    web, _ = client
    assert web.get("/api/dashboard").status_code == 401
    logged_in(web)
    r = web.get("/api/me")
    assert r.json()["role"] == "Management"
    assert len(web.get("/api/users").json()) == 2
    assert web.post("/api/admin/users", json={"username":"quality1","display_name":"Quality User","password":"A-long-password-123","role":"Quality","site":"Site C"}).status_code == 201


def test_part_import_preview_equivalents_missing_and_duplicate(client):
    web, Session = client
    logged_in(web)
    rows = [["Shocks", "123", "321", "56789abc", "C", ""], ["Shocks", "124", "324", "", "", ""]]
    response = part_import(web, rows, "preview")
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["new"] == 2
    assert web.get("/api/parts/search?q=123").json() == []
    imported = part_import(web, rows)
    assert imported.status_code == 200, imported.text
    assert imported.json()["summary"]["new"] == 2
    found = web.get("/api/parts/search?q=321").json()
    assert len(found) == 1
    assert {a["part_number"] for a in found[0]["aliases"]} == {"123", "321"}
    assert found[0]["drawing_revision"] == "C"
    assert found[0]["upc"] is None
    other = web.get("/api/parts/search?q=124").json()[0]
    assert other["drawing_number"] is None
    again = part_import(web, rows)
    assert again.json()["summary"]["unchanged"] == 2
    with Session() as db:
        assert len(db.scalars(select(PhysicalPart)).all()) == 2
    # Two existing physical parts cannot be merged automatically by a later import.
    conflict = part_import(web, [["Shocks", "123", "324", "56789abc", "C", ""]])
    assert conflict.json()["summary"]["conflict"] == 1


def test_folder_import_mapping_and_revision_snapshot(client):
    web, Session = client
    logged_in(web)
    part_import(web, [["Shocks", "123", "321", "56789abc", "C", ""]])
    res = web.post("/api/files/import-folder", data={"kind":"drawing", "paths":"Engineering Drawings/Shocks/56789abc rev C.PDF"},
                   files=[("files", ("56789abc rev C.PDF", b"%PDF-1.4 fake test", "application/pdf"))])
    assert res.status_code == 200, res.text
    assert res.json()["stored"] == 1
    file_info = web.get("/api/files").json()[0]
    assert file_info["relative_path"] == "Engineering Drawings/Shocks/56789abc rev C.PDF"
    mapped = web.put(f"/api/files/{file_info['id']}/drawing-mapping", json={"drawing_number":"56789abc", "drawing_revision":"C"})
    assert mapped.status_code == 200, mapped.text
    physical = web.get("/api/parts/search?q=123").json()[0]
    new = web.post("/api/work-orders", json={"order_type":"Validation / FAI", "subtype":"First Article Inspection",
                    "title":"Initial shock validation", "assigned_to":1,
                    "details":{"validation_standard":"Shock protocol"},
                    "parts":[{"part_id":physical["id"], "selected_part_number":"321", "quantity":12}]})
    assert new.status_code == 201, new.text
    order = new.json()
    assert order["number"].startswith("VAL-") and order["number"].endswith("-321")
    assert order["parts"][0]["drawing_status"] == "Matched"
    assert order["parts"][0]["drawing_revision"] == "C"
    with Session() as db:
        part = db.get(PhysicalPart, physical["id"])
        part.drawing_revision = "D"
        db.commit()
    historical = web.get(f"/api/work-orders/{order['id']}").json()
    assert historical["parts"][0]["drawing_revision"] == "C"
    assert web.get("/api/dashboard").json()["assigned"][0]["id"] == order["id"]
    assert web.patch(f"/api/work-orders/{order['id']}", json={"status":"In Progress","assigned_to":2}).status_code == 200
    assert web.get("/api/dashboard").json()["open_count"] == 0
    duplicate_file = web.post("/api/files/import-folder",data={"kind":"drawing", "paths":"Engineering Drawings/Shocks/56789abc rev C.PDF"},
                              files=[("files", ("56789abc rev C.PDF", b"modified", "application/pdf"))])
    assert len(duplicate_file.json()["conflicts"]) == 1
    assert web.get(f"/api/files/{file_info['id']}/download").content == b"%PDF-1.4 fake test"


def test_folder_traversal_messages_and_type_fields(client):
    web, _ = client
    logged_in(web)
    rejected = web.post("/api/files/import-folder",data={"kind":"drawing", "paths":"../escape.pdf"},files=[("files", ("escape.pdf", b"fake", "application/pdf"))])
    assert rejected.json()["rejected"]
    msg = web.post("/api/messages",json={"recipient_id":2,"body":"Can you review the shock drawing?"})
    assert msg.status_code == 201
    assert web.get("/api/messages").json()[0]["recipient"] == "Test Engineer"
    config = web.get("/api/config/work-types").json()
    assert len(config) == 6
    assert "sampling_plan" in config["Inspection"]["fields"]
    assert "photo_requirements" in config["Photos"]["fields"]
    assert "sampling_plan" not in config["Photos"]["fields"]


def test_dashboard_counts_all_assignments_beyond_recent_list(client):
    from app.models import WorkOrder
    web, Session = client
    logged_in(web)
    with Session() as db:
        for i in range(35):
            db.add(WorkOrder(number=f"INS-FICTIONAL-{i}", order_type="Inspection",
                             subtype="AQL", title=f"Fictional inspection {i}",
                             assigned_to=1, created_by=1, status="Open"))
        db.commit()
    data = web.get("/api/dashboard").json()
    assert len(data["assigned"]) == 30  # Recent list is intentionally bounded.
    assert data["open_count"] == 35
    assert data["assigned_count"] == 35
    with Session() as db:
        orders = db.query(WorkOrder).order_by(WorkOrder.id).all()
        orders[0].status = "Completed"
        orders[1].status = "Closed"
        orders[2].assigned_to = 2
        db.commit()
    data = web.get("/api/dashboard").json()
    assert data["assigned_count"] == 34
    assert data["open_count"] == 32


def test_import_case_variants_in_one_row_are_idempotent(client):
    web, _ = client
    logged_in(web)
    w = Workbook()
    s = w.active
    s.append(["Product Family", "Demo PN", "demo PN"])
    s.append(["Fictional Shocks", "DEMO-001", "demo-001"])
    stream = BytesIO()
    w.save(stream)
    for endpoint in ("preview", "commit", "commit"):
        response = web.post(f"/api/parts/import/{endpoint}",
                            files={"file": ("fictional.xlsx", stream.getvalue())})
        assert response.status_code == 200, response.text
    parts = web.get("/api/parts/search?q=DEMO-001").json()
    assert len(parts) == 1
    assert len(parts[0]["aliases"]) == 1
