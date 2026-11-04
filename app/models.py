"""QWOMS domain records. V1 tables are intentionally small and migration-friendly."""
from datetime import datetime, timezone
from sqlalchemy import false, Boolean, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(30), default="Quality")
    site: Mapped[str] = mapped_column(String(100), default="")
    password_hash: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    permissions: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")


class SystemAuthority(Base):
    __tablename__ = "system_authority"
    id: Mapped[int] = mapped_column(primary_key=True)
    initialized: Mapped[bool] = mapped_column(Boolean, default=False)


class ProductFamily(Base):
    __tablename__ = "product_families"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)


class PhysicalPart(Base):
    __tablename__ = "physical_parts"
    id: Mapped[int] = mapped_column(primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("product_families.id"))
    description: Mapped[str] = mapped_column(String(250), default="")
    drawing_number: Mapped[str | None] = mapped_column(String(150), nullable=True)
    drawing_revision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    upc: Mapped[str | None] = mapped_column(String(100), nullable=True)
    aliases: Mapped[list["PartAlias"]] = relationship(back_populates="part", cascade="all, delete-orphan")
    family: Mapped[ProductFamily] = relationship()


class PartAlias(Base):
    __tablename__ = "part_aliases"
    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("physical_parts.id"), index=True)
    account: Mapped[str] = mapped_column(String(100))
    part_number: Mapped[str] = mapped_column(String(150), index=True)
    part: Mapped[PhysicalPart] = relationship(back_populates="aliases")
    __table_args__ = (UniqueConstraint("account", "part_number", name="uq_account_number"),)


class StoredFile(Base):
    __tablename__ = "stored_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    relative_path: Mapped[str] = mapped_column(String(1000), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(40), default="document")
    drawing_number: Mapped[str | None] = mapped_column(String(150), nullable=True)
    drawing_revision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Drawing identity is indexed separately from the original filename / path.
    __table_args__ = (UniqueConstraint("drawing_number", "drawing_revision", "kind", name="uq_drawing_mapping"),)


class WorkOrderCounter(Base):
    __tablename__ = "work_order_counters"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10))
    year: Mapped[int] = mapped_column(Integer)
    value: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("code", "year", name="uq_counter_code_year"),)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="Open")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    order_type: Mapped[str] = mapped_column(String(40))
    subtype: Mapped[str] = mapped_column(String(100), default="")
    title: Mapped[str] = mapped_column(String(250))
    status: Mapped[str] = mapped_column(String(30), default="Open")
    priority: Mapped[str] = mapped_column(String(20), default="Normal")
    notes: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)  # Work-type-specific, validated fields
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    assignee: Mapped[User | None] = relationship(foreign_keys=[assigned_to])
    parts: Mapped[list["WorkOrderPart"]] = relationship(back_populates="work_order", cascade="all, delete-orphan")


class WorkOrderPart(Base):
    __tablename__ = "work_order_parts"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("physical_parts.id"))
    selected_part_number: Mapped[str] = mapped_column(String(150))
    quantity: Mapped[int] = mapped_column(Integer)
    drawing_number_snapshot: Mapped[str | None] = mapped_column(String(150), nullable=True)
    drawing_rev_snapshot: Mapped[str | None] = mapped_column(String(50), nullable=True)
    drawing_file_id: Mapped[int | None] = mapped_column(ForeignKey("stored_files.id"), nullable=True)
    controlled_revision_id: Mapped[int | None] = mapped_column(ForeignKey('controlled_revisions.id'),nullable=True)
    requirements_snapshot: Mapped[dict]=mapped_column(JSON,default=dict,server_default='{}')
    field_values: Mapped[dict]=mapped_column(JSON,default=dict,server_default='{}')
    drawing_status: Mapped[str] = mapped_column(String(50), default="Missing reference")
    work_order: Mapped[WorkOrder] = relationship(back_populates="parts")
    part: Mapped[PhysicalPart] = relationship()


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sender: Mapped[User] = relationship(foreign_keys=[sender_id])
    recipient: Mapped[User] = relationship(foreign_keys=[recipient_id])


class ImportAudit(Base):
    __tablename__ = "import_audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source_name: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(100))
    changes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssignmentEvent(Base):
    __tablename__ = "assignment_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    previous_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    window_started: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DemoOriginalBlob(Base):
    __tablename__ = "demo_original_blobs"
    key: Mapped[str] = mapped_column(String(1024), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary)


class ControlledDocument(Base):
    __tablename__ = 'controlled_documents'
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    number: Mapped[str] = mapped_column(String(150))
    identity_key: Mapped[str] = mapped_column(String(150))
    title: Mapped[str] = mapped_column(String(200))
    __table_args__ = (UniqueConstraint('kind','identity_key',name='uq_controlled_identity'),)


class ControlledRevision(Base):
    __tablename__ = 'controlled_revisions'
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('controlled_documents.id'),index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey('stored_files.id'),unique=True)
    revision: Mapped[str] = mapped_column(String(50))
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30),default='Draft')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'),nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'),nullable=True)
    change_summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    blank_master_confirmed: Mapped[bool] = mapped_column(Boolean,default=False)
    __table_args__ = (UniqueConstraint('document_id','revision',name='uq_controlled_revision'),)


class RevisionEvent(Base):
    __tablename__ = 'revision_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey('controlled_revisions.id'),index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    previous_status: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=utcnow)


class WorkflowRule(Base):
    __tablename__='workflow_rules'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(200))
    order_type: Mapped[str]=mapped_column(String(40))
    subtype: Mapped[str]=mapped_column(String(100),default='')
    family_id: Mapped[int | None]=mapped_column(ForeignKey('product_families.id'),nullable=True)
    part_id: Mapped[int | None]=mapped_column(ForeignKey('physical_parts.id'),nullable=True)
    fields: Mapped[list]=mapped_column(JSON,default=list)
    instructions: Mapped[str]=mapped_column(Text,default='')
    document_ids: Mapped[list]=mapped_column(JSON,default=list)
    active: Mapped[bool]=mapped_column(Boolean,default=True)
    created_by: Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)


class FormFilingRule(Base):
    __tablename__='form_filing_rules'
    id: Mapped[int]=mapped_column(primary_key=True)
    order_type: Mapped[str]=mapped_column(String(40))
    subtype: Mapped[str]=mapped_column(String(100),default='')
    folder: Mapped[str]=mapped_column(String(200))
    __table_args__=(UniqueConstraint('order_type','subtype',name='uq_form_filing_scope'),)


class WorkOrderAttachment(Base):
    __tablename__='work_order_attachments'
    id: Mapped[int]=mapped_column(primary_key=True)
    work_order_id: Mapped[int]=mapped_column(ForeignKey('work_orders.id'),index=True)
    part_id: Mapped[int]=mapped_column(ForeignKey('physical_parts.id'))
    revision_id: Mapped[int]=mapped_column(ForeignKey('controlled_revisions.id'))
    file_id: Mapped[int]=mapped_column(ForeignKey('stored_files.id'))
    kind: Mapped[str]=mapped_column(String(30))
    number: Mapped[str]=mapped_column(String(150))
    revision: Mapped[str]=mapped_column(String(50))
    sha256: Mapped[str]=mapped_column(String(64))
    filename: Mapped[str]=mapped_column(String(255))
    category_folder: Mapped[str]=mapped_column(String(200))
    __table_args__=(UniqueConstraint('work_order_id','part_id','revision_id',name='uq_order_part_document'),)


class CompletedForm(Base):
    __tablename__='completed_forms'
    id: Mapped[int]=mapped_column(primary_key=True)
    work_order_id: Mapped[int]=mapped_column(ForeignKey('work_orders.id'),index=True)
    attachment_id: Mapped[int]=mapped_column(ForeignKey('work_order_attachments.id'))
    file_id: Mapped[int]=mapped_column(ForeignKey('stored_files.id'),unique=True)
    project_id: Mapped[int | None]=mapped_column(ForeignKey('projects.id'),nullable=True)
    saved_by: Mapped[int]=mapped_column(ForeignKey('users.id'))
    saved_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
