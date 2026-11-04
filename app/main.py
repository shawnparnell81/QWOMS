"""QWOMS Phase 1 API: real database, assignments, part aliases, drawings and messages.

This is a development foundation, NOT approved for company production data yet.
"""
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from typing import Annotated
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from .db import Base, engine, session, DATABASE_URL
from .imports import load_rows, process_part_import
from .models import (ImportAudit, Message, PartAlias, PhysicalPart, ProductFamily,
                     StoredFile, User, WorkOrder, WorkOrderCounter, WorkOrderPart)
from .security import current_user, hash_password, require_admin, token_for, verify_password
from .schema import require_current
from .storage import original_store, StorageConflict, DatabaseStore
from .audit import record
from .models import AuditEvent, AssignmentEvent, AuthSession, Project
from .deployment import validate_settings, demo_mode, public_origin, demo_gate_ok
from .throttling import check_login, finish_login
from .controlled import mapped_draft, drawing_reference
from .models import ControlledRevision,WorkOrderPart
from .models import ControlledDocument,WorkOrderAttachment,CompletedForm
from .workflows import resolve,validate_values,approved_documents,attach

DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))

APP_ROOT = Path(__file__).resolve().parent
STORAGE_ROOT = Path(os.getenv("QWOMS_STORAGE_ROOT", APP_ROOT.parent / "local-storage")).resolve()
MAX_IMPORT_BYTES = 20 * 1024 * 1024
MAX_FILE_BYTES = 25 * 1024 * 1024
ROLES = {"Quality", "Engineering", "Production", "Management"}
TYPE_CONFIG = {
    "Validation / FAI": {"code": "VAL", "subtypes": ["First Article Inspection", "Product Validation", "Development Validation"], "fields": ["validation_standard", "sample_quantity", "acceptance_criteria"]},
    "Inspection": {"code": "INS", "subtypes": ["AQL", "Non-conformance", "Product Alert", "Customer Complaint", "Supplier Issue", "Re-inspection", "Other Inspection"], "fields": ["inspection_scope", "sampling_plan", "defect_description"]},
    "Test": {"code": "TST", "subtypes": ["Functional Test", "Performance Test", "Durability Test", "Other Test"], "fields": ["test_method", "equipment", "acceptance_criteria"]},
    "Repair": {"code": "REP", "subtypes": ["Repair", "Rework", "Component Replacement"], "fields": ["defect_description", "repair_instructions", "replacement_parts"]},
    "Parts Weighing": {"code": "WGT", "subtypes": ["Individual Weighing", "Batch Weighing", "Weight Verification"], "fields": ["scale_id", "units", "weight_specification"]},
    "Photos": {"code": "PHO", "subtypes": ["Ortery 360°", "Catalog Product Photos", "Detail Photos"], "fields": ["photo_requirements", "catalog_request", "return_location"]},
}

app = FastAPI(title="QWOMS", version="0.1.0", docs_url=None if demo_mode() else "/docs",
              redoc_url=None if demo_mode() else "/redoc", openapi_url=None if demo_mode() else "/openapi.json")
app.mount("/static", StaticFiles(directory=str(APP_ROOT / "static")), name="static")


@app.middleware("http")
async def origin_guard(request: Request, call_next):
    if not demo_gate_ok(request):
        return Response('Private synthetic demo',status_code=401,headers={
            'WWW-Authenticate':'Basic realm="QWOMS synthetic demo", charset="UTF-8"',
            'Cache-Control':'no-store','Strict-Transport-Security':'max-age=31536000'})
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        allowed = set() if demo_mode() else {str(request.base_url).rstrip("/")}
        if public_origin():
            allowed.add(public_origin())
        allowed.update(x.strip() for x in os.getenv("QWOMS_ALLOWED_ORIGINS", "").split(",") if x.strip())
        if origin and origin not in allowed:
            return Response('Cross-origin request denied', status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers['Content-Security-Policy'] = "frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
    response.headers['X-Frame-Options'] = 'DENY'
    if demo_mode():
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.on_event("startup")
def init_db():
    validate_settings(DATABASE_URL)
    require_current(engine)
    original_store(STORAGE_ROOT)


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class CreateUserBody(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    role: str
    site: str = ""

    @field_validator("username", "display_name", mode="before")
    @classmethod
    def trim_identity(cls, value):
        return value.strip() if isinstance(value, str) else value


class PartInput(BaseModel):
    part_id: int
    selected_part_number: str
    quantity: int = Field(ge=1)
    field_values: dict[str,str] = Field(default_factory=dict)
    rule_ids: list[int] | None = None


class CreateWorkOrderBody(BaseModel):
    order_type: str
    subtype: str
    title: str = Field(min_length=3, max_length=250)
    priority: str = "Normal"
    assigned_to: int | None = None
    project_id: int | None = None
    notes: str = ""
    parts: list[PartInput] = Field(min_length=1,max_length=100)
    details: dict[str, str] = Field(default_factory=dict)

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value):
        return value.strip() if isinstance(value, str) else value


class UpdateWorkOrderBody(BaseModel):
    status: str | None = None
    assigned_to: int | None = None
    project_id: int | None = None


class CreateProjectBody(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=10000)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class SendMessageBody(BaseModel):
    recipient_id: int
    body: str = Field(min_length=1, max_length=4000)
    work_order_id: int | None = None


class DrawingMapping(BaseModel):
    drawing_number: str = Field(min_length=1, max_length=150)
    drawing_revision: str = Field(min_length=1, max_length=50)


def allow_roles(user: User, *allowed):
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Insufficient permission")


def serialize_user(user: User):
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role, "site": user.site}


def serialize_part(p: PhysicalPart):
    return {"id": p.id, "family": p.family.name, "description": p.description,
            "drawing_number": p.drawing_number, "drawing_revision": p.drawing_revision, "upc": p.upc,
            "aliases": [{"account": a.account, "part_number": a.part_number} for a in p.aliases]}


def serialize_order(o: WorkOrder):
    return {"id": o.id, "number": o.number, "order_type": o.order_type, "subtype": o.subtype,
            "title": o.title, "status": o.status, "priority": o.priority, "notes": o.notes,
            "details": o.details, "assigned_to": o.assigned_to,
            "assignee": serialize_user(o.assignee) if o.assignee else None,
            "created_by": o.created_by, "created_at": o.created_at.isoformat(),
            "project_id": o.project_id,
            "parts": [{"part_id": p.part_id, "selected_part_number": p.selected_part_number,
                       "quantity": p.quantity, "drawing_number": p.drawing_number_snapshot,
                       "drawing_revision": p.drawing_rev_snapshot,
                       "drawing_status": p.drawing_status,
                       "controlled_revision_id":p.controlled_revision_id,
                       "requirements":p.requirements_snapshot,"field_values":p.field_values,
                       "drawing_file_id": p.drawing_file_id} for p in o.parts]}


def query_order(db, order_id):
    return db.scalar(select(WorkOrder).options(
        selectinload(WorkOrder.assignee), selectinload(WorkOrder.parts))
        .where(WorkOrder.id == order_id))


@app.get("/")
def home():
    return FileResponse(APP_ROOT / "static" / "index.html")


@app.get("/healthz")
def health():
    commit=os.getenv('QWOMS_BUILD_COMMIT','unknown')
    if commit=='unknown':commit=os.getenv('RENDER_GIT_COMMIT','unknown')
    return {"status": "ok", "phase": "synthetic-demo" if demo_mode() else "developer-foundation",
            "build_commit": commit}


@app.get('/api/public-config')
def public_config():
    return {'demo_mode': demo_mode()}


@app.get('/readyz')
def readiness():
    try:
        require_current(engine)
        store = original_store(STORAGE_ROOT)
        if hasattr(store, 'client'):
            store.client.head_bucket(Bucket=store.bucket)
        elif not isinstance(store, DatabaseStore):
            import tempfile
            STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=STORAGE_ROOT) as probe:
                probe.write(b'ready')
                probe.flush()
    except Exception:
        return Response('{"status":"unavailable"}', status_code=503, media_type='application/json')
    return {'status':'ready'}


@app.post("/api/auth/login")
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(session)):
    throttle = check_login(db, request.client.host if request.client else 'unknown', body.username.strip().casefold())
    user = db.scalar(select(User).where(func.lower(User.username) == body.username.strip().casefold()))
    valid_password = verify_password(body.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not user or not user.active or not valid_password:
        finish_login(db, throttle, False)
        db.commit()
        raise HTTPException(401, "Invalid username or password")
    finish_login(db, throttle, True)
    cookie_secure = os.getenv("QWOMS_COOKIE_SECURE", "false").casefold() == "true"
    token, csrf = token_for(user.id, db)
    record(db, user, "session.login", "user", user.id)
    db.commit()
    response.set_cookie("qwoms_token", token, httponly=True,
                        secure=cookie_secure, samesite="strict", max_age=8*60*60, path="/")
    response.set_cookie("qwoms_csrf", csrf, httponly=False,
                        secure=cookie_secure, samesite="strict", max_age=8*60*60, path="/")
    return serialize_user(user)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(session),
           user: User = Depends(current_user)):
    active_session = db.get(AuthSession, request.state.session_id)
    active_session.revoked_at = datetime.now(timezone.utc)
    record(db, user, "session.logout", "user", user.id)
    db.commit()
    response.delete_cookie("qwoms_token", path="/", samesite="strict")
    response.delete_cookie("qwoms_csrf", path="/", samesite="strict")
    return {"ok": True}


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return serialize_user(user)


@app.get("/api/users")
def users(db: Session = Depends(session), user: User = Depends(current_user)):
    return [serialize_user(u) for u in db.scalars(select(User).where(User.active == True).order_by(User.display_name)).all()]


@app.post("/api/admin/users", status_code=201)
def create_user(body: CreateUserBody, db: Session = Depends(session), manager: User = Depends(require_admin)):
    if body.role not in ROLES:
        raise HTTPException(400, "Unsupported role")
    if db.scalar(select(User).where(func.lower(User.username) == body.username.strip().casefold())):
        raise HTTPException(409, "Username already exists")
    new = User(username=body.username.strip(), display_name=body.display_name.strip(),
               role=body.role, site=body.site.strip(), password_hash=hash_password(body.password))
    db.add(new)
    db.flush()
    record(db, manager, "user.created", "user", new.id, {"role": new.role, "site": new.site})
    db.commit()
    db.refresh(new)
    return serialize_user(new)


@app.get("/api/config/work-types")
def work_types(user: User = Depends(current_user)):
    return TYPE_CONFIG


@app.get("/api/parts/search")
def search_parts(q: str = "", db: Session = Depends(session), user: User = Depends(current_user)):
    q = q.strip()
    if len(q) < 1:
        return []
    matches = db.scalars(select(PartAlias).where(PartAlias.part_number.ilike(f"%{q.replace('%', r'\%').replace('_', r'\_')}%", escape="\\")).limit(40)).all()
    ids = list(dict.fromkeys(a.part_id for a in matches))
    if not ids:
        return []
    parts = db.scalars(select(PhysicalPart).options(selectinload(PhysicalPart.aliases), selectinload(PhysicalPart.family)).where(PhysicalPart.id.in_(ids))).all()
    return [serialize_part(part) for part in parts]


@app.get("/api/parts/families")
def families(db: Session = Depends(session), user: User = Depends(current_user)):
    return [{"id": f.id, "name": f.name} for f in db.scalars(select(ProductFamily).order_by(ProductFamily.name)).all()]


async def excel_payload(file: UploadFile):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Upload an .xlsx Part Master workbook")
    blob = await file.read(MAX_IMPORT_BYTES + 1)
    if len(blob) > MAX_IMPORT_BYTES:
        raise HTTPException(413, "Workbook exceeds 20 MB limit for this development version")
    try:
        return load_rows(blob), blob
    except Exception as exc:
        raise HTTPException(422, f"Cannot read Part Master: {exc}")


@app.post("/api/parts/import/preview")
async def preview_parts(file: UploadFile = File(...), family: str = Form(""),
                        db: Session = Depends(session), user: User = Depends(current_user)):
    allow_roles(user, "Quality", "Engineering", "Management")
    rows, blob = await excel_payload(file)
    return process_part_import(db, rows, family_override=family, preview=True)


@app.post("/api/parts/import/commit")
async def import_parts(file: UploadFile = File(...), family: str = Form(""),
                       db: Session = Depends(session), user: User = Depends(current_user)):
    allow_roles(user, "Quality", "Engineering", "Management")
    rows, blob = await excel_payload(file)
    result = process_part_import(db, rows, family_override=family, preview=False)
    db.add(ImportAudit(actor_id=user.id, source_name=file.filename,
                       summary=json.dumps({**result["summary"], "sha256": hashlib.sha256(blob).hexdigest()})))
    record(db, user, "part_master.imported", "import", file.filename, result["summary"])
    db.commit()
    return result


def safe_relative_path(raw: str):
    raw = raw.replace("\\", "/")
    parts = raw.split("/")
    if (not parts or any(p in ("", ".", "..") for p in parts)
            or any(":" in p or any(ord(c) < 32 for c in p) for p in parts)
            or raw.startswith("/")):
        raise ValueError("Invalid relative path; folder traversal is not permitted")
    if len(raw) > 950 or len(parts[-1]) > 255:
        raise ValueError("File path or name is too long")
    return "/".join(parts)


@app.post("/api/files/import-folder")
async def import_folder(files: list[UploadFile] = File(...), paths: list[str] = Form(...),
                        kind: str = Form("drawing"), db: Session = Depends(session),
                        user: User = Depends(current_user)):
    allow_roles(user, "Quality", "Engineering", "Management")
    if kind not in ("drawing", "document", "form-template"):
        raise HTTPException(400, "Invalid file category")
    if len(files) != len(paths):
        raise HTTPException(400, "Each file must include its original relative path")
    report = {"stored": 0, "already_present": 0, "conflicts": [], "rejected": []}
    for upload, supplied_path in zip(files, paths):
        try:
            rel = safe_relative_path(supplied_path)
        except ValueError as exc:
            report["rejected"].append({"path": supplied_path, "reason": str(exc)})
            continue
        content = await upload.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            report["rejected"].append({"path": rel, "reason": "File exceeds 25 MB limit"})
            continue
        digest = hashlib.sha256(content).hexdigest()
        existing = db.scalar(select(StoredFile).where(StoredFile.relative_path == rel))
        if existing:
            if existing.sha256 == digest:
                report["already_present"] += 1
            else:
                report["conflicts"].append({"path": rel, "reason": "Filename/path already exists with different contents; nothing overwritten"})
            continue
        try:
            original_store(STORAGE_ROOT, db).put_new("files/" + rel, content)
        except ValueError:
            report["rejected"].append({"path": rel, "reason": "Unsafe storage path"})
            continue
        except StorageConflict as exc:
            report["conflicts"].append({"path": rel, "reason": str(exc)})
            continue
        db.add(StoredFile(relative_path=rel, original_name=rel.split("/")[-1],
                          kind=kind, sha256=digest, uploaded_by=user.id))
        db.flush()
        record(db, user, "file.imported", "file", rel, {"sha256": digest, "kind": kind})
        db.commit()
        report["stored"] += 1
    return report


@app.get("/api/files")
def list_files(kind: str = "", db: Session = Depends(session), user: User = Depends(current_user)):
    query = select(StoredFile).order_by(StoredFile.relative_path)
    if kind:
        query = query.where(StoredFile.kind == kind)
    files = db.scalars(query.limit(500)).all()
    return [{"id": f.id, "relative_path": f.relative_path, "original_name": f.original_name,
             "kind": f.kind, "drawing_number": f.drawing_number,
             "drawing_revision": f.drawing_revision} for f in files]


@app.get("/api/files/{file_id}/download")
def download_file(file_id: int, db: Session = Depends(session), user: User = Depends(current_user)):
    f = db.get(StoredFile, file_id)
    if not f:
        raise HTTPException(404, "File not found")
    try:
        content = original_store(STORAGE_ROOT, db).read("files/" + f.relative_path)
    except FileNotFoundError:
        raise HTTPException(404, "Stored file unavailable")
    if hashlib.sha256(content).hexdigest() != f.sha256:
        raise HTTPException(409, "Stored file integrity check failed")
    return Response(content, media_type="application/octet-stream", headers={
        "Content-Disposition": "attachment; filename*=UTF-8''" + quote(f.original_name, safe=""),
        "X-Content-Type-Options": "nosniff"})


@app.put("/api/files/{file_id}/drawing-mapping")
def map_drawing(file_id: int, body: DrawingMapping, db: Session = Depends(session),
                user: User = Depends(current_user)):
    allow_roles(user, "Engineering", "Management")
    f = db.get(StoredFile, file_id)
    if not f or f.kind != "drawing":
        raise HTTPException(404, "Drawing file not found")
    if (f.drawing_number,f.drawing_revision)!=(body.drawing_number.strip(),body.drawing_revision.strip()):
        pinned=db.scalar(select(WorkOrderPart.id).where(WorkOrderPart.drawing_file_id==f.id))
        controlled=db.scalar(select(ControlledRevision.id).where(ControlledRevision.file_id==f.id))
        if pinned or controlled:raise HTTPException(409,'A referenced original mapping is immutable; import a new revision')
    # Don't derive drawing revision from filename. Match the revision recorded in Excel.
    known = db.scalar(select(PhysicalPart).where(
        PhysicalPart.drawing_number == body.drawing_number.strip(),
        PhysicalPart.drawing_revision == body.drawing_revision.strip()))
    if not known:
        raise HTTPException(422, "Drawing number/revision must first exist in the Excel Part Master")
    already = db.scalar(select(StoredFile).where(
        StoredFile.kind == "drawing", StoredFile.drawing_number == body.drawing_number.strip(),
        StoredFile.drawing_revision == body.drawing_revision.strip(), StoredFile.id != f.id))
    if already:
        raise HTTPException(409, "This drawing number and revision are already mapped to another file")
    f.drawing_number = body.drawing_number.strip()
    f.drawing_revision = body.drawing_revision.strip()
    revision=mapped_draft(db,f,f.drawing_number,f.drawing_revision,user)
    record(db, user, "drawing.mapped", "file", f.id,
           {"drawing_number": f.drawing_number, "drawing_revision": f.drawing_revision})
    db.commit()
    return {"id": f.id, "relative_path": f.relative_path, "drawing_number": f.drawing_number,
            "drawing_revision": f.drawing_revision,"controlled_revision_id":revision.id,"status":revision.status}


@app.get("/api/work-orders")
def list_orders(assigned_to_me: bool = False, db: Session = Depends(session), user: User = Depends(current_user)):
    query = select(WorkOrder).options(selectinload(WorkOrder.assignee), selectinload(WorkOrder.parts))
    if assigned_to_me:
        query = query.where(WorkOrder.assigned_to == user.id)
    query = query.order_by(WorkOrder.created_at.desc(), WorkOrder.id.desc()).limit(200)
    return [serialize_order(o) for o in db.scalars(query).all()]


@app.get("/api/work-orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(session), user: User = Depends(current_user)):
    order = query_order(db, order_id)
    if not order:
        raise HTTPException(404, "Work order not found")
    return serialize_order(order)


@app.post("/api/work-orders", status_code=201)
def create_order(body: CreateWorkOrderBody, db: Session = Depends(session), user: User = Depends(current_user)):
    allow_roles(user, "Quality", "Engineering", "Management")
    if body.order_type not in TYPE_CONFIG:
        raise HTTPException(422, "Unsupported work order type")
    config = TYPE_CONFIG[body.order_type]
    if body.project_id is not None and not db.get(Project, body.project_id):
        raise HTTPException(422, "Project not found")
    if body.subtype not in config["subtypes"]:
        raise HTTPException(422, "Unsupported subtype for this work order type")
    if body.priority not in ("Low", "Normal", "High", "Urgent"):
        raise HTTPException(422, "Unsupported priority")
    invalid_fields = set(body.details) - set(config["fields"])
    if invalid_fields:
        raise HTTPException(422, "Fields do not belong to this work order type: " + ", ".join(sorted(invalid_fields)))
    if body.assigned_to is not None:
        assignee = db.get(User, body.assigned_to)
        if not assignee or not assignee.active:
            raise HTTPException(422, "Assigned employee not found")
    if len({p.part_id for p in body.parts})!=len(body.parts):
        raise HTTPException(422,'Choose one alias per physical part and combine its quantity')
    prepared=[]
    document_ids=set();drawing_numbers=set()
    for p in body.parts:
        part = db.scalar(select(PhysicalPart).options(selectinload(PhysicalPart.aliases)).where(PhysicalPart.id == p.part_id))
        if not part or not any(a.part_number.casefold() == p.selected_part_number.strip().casefold() for a in part.aliases):
            raise HTTPException(422, "Selected part number is not an alias of the specified physical part")
        requirements=resolve(db,part,body.order_type,body.subtype)
        if requirements['rule_ids'] and sorted(p.rule_ids or [])!=sorted(requirements['rule_ids']):
            raise HTTPException(409,'Work requirements changed or were not reviewed; refresh this part workflow before creating the order')
        validate_values(requirements,p.field_values)
        prepared.append((p,part,requirements))
        document_ids.update(requirements['document_ids'])
        if part.drawing_number:drawing_numbers.add(part.drawing_number.casefold())
    # Lock all affected control identities in one stable order, shared with approvals.
    db.scalars(select(ControlledDocument).where(or_(ControlledDocument.id.in_(document_ids),
        (ControlledDocument.kind=='Drawing') & ControlledDocument.identity_key.in_(drawing_numbers)))
        .order_by(ControlledDocument.id).with_for_update()).all()
    resolved_parts=[]
    for p,part,requirements in prepared:
        revision,drawing,drawing_state=drawing_reference(db,part.drawing_number,part.drawing_revision)
        documents=approved_documents(db,requirements)
        resolved_parts.append((p,part,drawing,revision,drawing_state,requirements,documents))
    year = datetime.now(timezone.utc).year
    counter = db.scalar(select(WorkOrderCounter).where(WorkOrderCounter.code == config["code"],
            WorkOrderCounter.year == year).with_for_update())
    if not counter:
        counter = WorkOrderCounter(code=config["code"], year=year, value=0)
        db.add(counter)
        db.flush()
    counter.value += 1
    # Part number is included only in the automatically generated WORK ORDER number.
    # User-saved documents and completed Excel forms are NEVER renamed automatically.
    suffix = (re.sub(r"[^a-zA-Z0-9_-]", "-", body.parts[0].selected_part_number)[:36] if len(body.parts) == 1 else "MULTI")
    number = f"{config['code']}-{year}-{counter.value:05d}-{suffix}"
    wo = WorkOrder(number=number, order_type=body.order_type, subtype=body.subtype,
                   title=body.title.strip(), priority=body.priority, notes=body.notes,
                   assigned_to=body.assigned_to, created_by=user.id, details=body.details,
                   project_id=body.project_id)
    db.add(wo)
    db.flush()
    for entry, part, drawing, revision, drawing_state, requirements, documents in resolved_parts:
        wo.parts.append(WorkOrderPart(part_id=part.id, selected_part_number=entry.selected_part_number.strip(),
                                     quantity=entry.quantity, drawing_number_snapshot=part.drawing_number,
                                     drawing_rev_snapshot=part.drawing_revision,
                                     drawing_file_id=drawing.id if drawing else None,
                                     controlled_revision_id=revision.id if revision else None,
                                     requirements_snapshot=requirements,field_values=entry.field_values,
                                     drawing_status=drawing_state))
        attach(db,wo,part,documents)
    try:
        db.add(AssignmentEvent(work_order_id=wo.id, actor_id=user.id,
                               previous_user_id=None, assigned_user_id=body.assigned_to))
        record(db, user, "work_order.created", "work_order", wo.id,
               {"number": wo.number, "assigned_to": body.assigned_to, "order_type": body.order_type,
                "project_id": body.project_id})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Work order number conflict; retry creation")
    return serialize_order(query_order(db, wo.id))


@app.patch("/api/work-orders/{order_id}")
def update_order(order_id: int, body: UpdateWorkOrderBody, db: Session = Depends(session),
                 user: User = Depends(current_user)):
    order = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id).with_for_update())
    if not order:
        raise HTTPException(404, "Work order not found")
    if user.role == "Production":
        if order.assigned_to != user.id or body.model_fields_set - {"status"}:
            raise HTTPException(403, "Production may update status only on its own assignments")
    else:
        allow_roles(user, "Quality", "Engineering", "Management")
    changes = {}
    if body.status is not None:
        if body.status not in ("Open", "In Progress", "On Hold", "Completed", "Closed"):
            raise HTTPException(422, "Invalid status")
        if body.status in ('In Progress','Completed','Closed'):
            if any(p.drawing_number_snapshot and (p.drawing_status!='Approved' or not p.controlled_revision_id) for p in order.parts):
                raise HTTPException(409,'Engineering must resolve missing, unapproved or superseded drawing references before execution')
            if any(p.controlled_revision_id and db.get(ControlledRevision,p.controlled_revision_id).status=='Obsolete' for p in order.parts):
                raise HTTPException(409,'An obsolete pinned drawing requires Engineering review before execution')
            phase='execution' if body.status=='In Progress' else 'completion'
            for part in order.parts:validate_values(part.requirements_snapshot,part.field_values,phase)
            for attachment in db.scalars(select(WorkOrderAttachment).where(WorkOrderAttachment.work_order_id==order.id)).all():
                if db.get(ControlledRevision,attachment.revision_id).status=='Obsolete':
                    raise HTTPException(409,'An attached instruction/form was withdrawn; Engineering review required')
                if phase=='completion' and attachment.kind=='Form template' and not db.scalar(select(CompletedForm.id).where(CompletedForm.attachment_id==attachment.id)):
                    raise HTTPException(409,'Save every mandatory completed form before closing this work order')
        if order.status != body.status:
            changes["status"] = {"before": order.status, "after": body.status}
            order.status = body.status
    if "assigned_to" in body.model_fields_set:
        if body.assigned_to is not None:
            target = db.get(User, body.assigned_to)
            if not target or not target.active:
                raise HTTPException(422, "Assigned employee not found")
        if order.assigned_to != body.assigned_to:
            changes["assigned_to"] = {"before": order.assigned_to, "after": body.assigned_to}
            db.add(AssignmentEvent(work_order_id=order.id, actor_id=user.id,
                                   previous_user_id=order.assigned_to, assigned_user_id=body.assigned_to))
            order.assigned_to = body.assigned_to
    if "project_id" in body.model_fields_set and body.project_id != order.project_id:
        if body.project_id is not None and not db.get(Project, body.project_id):
            raise HTTPException(422, "Project not found")
        changes["project_id"] = {"before": order.project_id, "after": body.project_id}
        order.project_id = body.project_id
    if changes:
        record(db, user, "work_order.updated", "work_order", order.id, changes)
    db.commit()
    return serialize_order(query_order(db, order_id))


@app.get("/api/work-orders/{order_id}/assignment-history")
def assignment_history(order_id: int, db: Session = Depends(session), user: User = Depends(current_user)):
    if not db.get(WorkOrder, order_id):
        raise HTTPException(404, "Work order not found")
    entries = db.scalars(select(AssignmentEvent).where(AssignmentEvent.work_order_id == order_id)
                         .order_by(AssignmentEvent.id)).all()
    def name(user_id):
        employee = db.get(User, user_id) if user_id else None
        return employee.display_name if employee else "Unassigned"
    return [{"id": e.id, "actor": name(e.actor_id), "previous_user_id": e.previous_user_id,
             "assigned_user_id": e.assigned_user_id, "previous_employee": name(e.previous_user_id),
             "assigned_employee": name(e.assigned_user_id), "created_at": e.created_at.isoformat()}
            for e in entries]


def serialize_project(project, orders):
    return {"id": project.id, "name": project.name, "description": project.description,
            "status": project.status, "created_at": project.created_at.isoformat(),
            "work_order_count": len(orders),
            "open_work_order_count": sum(o.status not in ("Completed", "Closed") for o in orders)}


@app.get("/api/projects")
def list_projects(db: Session = Depends(session), user: User = Depends(current_user)):
    projects = db.scalars(select(Project).order_by(Project.id.desc()).limit(200)).all()
    ids = [p.id for p in projects]
    orders = db.scalars(select(WorkOrder).where(WorkOrder.project_id.in_(ids))).all() if ids else []
    grouped = {}
    for order in orders:
        grouped.setdefault(order.project_id, []).append(order)
    return [serialize_project(p, grouped.get(p.id, [])) for p in projects]


@app.post("/api/projects", status_code=201)
def create_project(body: CreateProjectBody, db: Session = Depends(session), user: User = Depends(current_user)):
    allow_roles(user, "Quality", "Engineering", "Management")
    project = Project(name=body.name, description=body.description, created_by=user.id)
    db.add(project)
    db.flush()
    record(db, user, "project.created", "project", project.id, {"name": project.name})
    db.commit()
    return serialize_project(project, [])


@app.get("/api/projects/{project_id}")
def get_project(project_id: int, db: Session = Depends(session), user: User = Depends(current_user)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    orders = db.scalars(select(WorkOrder).options(selectinload(WorkOrder.assignee), selectinload(WorkOrder.parts))
                        .where(WorkOrder.project_id == project_id).order_by(WorkOrder.id.desc())).all()
    return {**serialize_project(project, orders), "work_orders": [serialize_order(o) for o in orders]}


@app.get("/api/admin/audit")
def audit_history(before_id: int | None = None, db: Session = Depends(session),
                  manager: User = Depends(require_admin)):
    query = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(100)
    if before_id is not None:
        query = query.where(AuditEvent.id < before_id)
    return [{"id": e.id, "actor_id": e.actor_id, "action": e.action, "entity_type": e.entity_type,
             "entity_id": e.entity_id, "changes": e.changes, "created_at": e.created_at.isoformat()}
            for e in db.scalars(query).all()]


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(session), user: User = Depends(current_user)):
    assigned = db.scalars(select(WorkOrder).options(selectinload(WorkOrder.assignee), selectinload(WorkOrder.parts))
                          .where(WorkOrder.assigned_to == user.id).order_by(WorkOrder.id.desc()).limit(30)).all()
    unread = db.scalar(select(func.count()).select_from(Message).where(Message.recipient_id == user.id, Message.read_at.is_(None))) or 0
    assigned_count = db.scalar(select(func.count()).select_from(WorkOrder).where(
        WorkOrder.assigned_to == user.id)) or 0
    open_count = db.scalar(select(func.count()).select_from(WorkOrder).where(
        WorkOrder.assigned_to == user.id,
        WorkOrder.status.notin_(("Completed", "Closed")))) or 0
    return {"assigned": [serialize_order(o) for o in assigned],
            "assigned_count": assigned_count,
            "open_count": open_count,
            "unread_messages": unread,
            "total_work_orders": db.scalar(select(func.count()).select_from(WorkOrder)) or 0,
            "total_parts": db.scalar(select(func.count()).select_from(PhysicalPart)) or 0}


@app.get("/api/messages")
def messages(db: Session = Depends(session), user: User = Depends(current_user)):
    items = db.scalars(select(Message).options(selectinload(Message.sender), selectinload(Message.recipient)).where(
        or_(Message.sender_id == user.id, Message.recipient_id == user.id))
        .order_by(Message.id.desc()).limit(150)).all()
    return [{"id": m.id, "sender_id": m.sender_id, "sender": m.sender.display_name,
             "recipient_id": m.recipient_id, "recipient": m.recipient.display_name,
             "body": m.body, "work_order_id": m.work_order_id,
             "read_at": m.read_at.isoformat() if m.read_at else None,
             "created_at": m.created_at.isoformat()} for m in items]


@app.post("/api/messages", status_code=201)
def send_message(body: SendMessageBody, db: Session = Depends(session), user: User = Depends(current_user)):
    recipient = db.get(User, body.recipient_id)
    if not recipient or not recipient.active:
        raise HTTPException(422, "Recipient does not exist")
    if body.work_order_id and not db.get(WorkOrder, body.work_order_id):
        raise HTTPException(422, "Work order does not exist")
    msg = Message(sender_id=user.id, recipient_id=body.recipient_id,
                  work_order_id=body.work_order_id, body=body.body.strip())
    if not msg.body:
        raise HTTPException(422, "Message cannot be blank")
    db.add(msg)
    db.commit()
    return {"id": msg.id, "ok": True}

from .controlled_api import router as controlled_router
app.include_router(controlled_router)
from .workflow_api import router as workflow_router
app.include_router(workflow_router)
