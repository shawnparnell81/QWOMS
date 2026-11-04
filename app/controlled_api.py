from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import session
from .models import ControlledDocument,ControlledRevision,RevisionEvent,StoredFile,User,WorkOrder
from .security import current_user
from .controlled import KINDS,create_revision,transition,drawing_reference
from .audit import record

router=APIRouter(prefix='/api/controlled')


class DocumentInput(BaseModel):
    kind: Literal['Drawing','Work instruction','Supporting document','Form template']
    number: str=Field(min_length=1,max_length=150)
    title: str=Field(min_length=3,max_length=200)
    @field_validator('number','title',mode='before')
    @classmethod
    def trim(cls,value):return value.strip() if isinstance(value,str) else value


class RevisionInput(BaseModel):
    file_id: int
    revision: str=Field(min_length=1,max_length=50)
    change_summary: str=Field(min_length=3,max_length=2000)
    blank_master_confirmed: bool=False
    @field_validator('revision','change_summary',mode='before')
    @classmethod
    def trim(cls,value):return value.strip() if isinstance(value,str) else value


class ActionInput(BaseModel):
    action: Literal['submit','review','approve','reject','obsolete']
    reason: str=Field(min_length=3,max_length=2000)
    @field_validator('reason',mode='before')
    @classmethod
    def trim(cls,value):return value.strip() if isinstance(value,str) else value


def manager(user):
    if user.role not in ('Engineering','Management'):raise HTTPException(403,'Engineering or Management required')


def revision_json(db,revision):
    file=db.get(StoredFile,revision.file_id)
    events=db.scalars(select(RevisionEvent).where(RevisionEvent.revision_id==revision.id).order_by(RevisionEvent.id)).all()
    return {'id':revision.id,'revision':revision.revision,'status':revision.status,'file_id':revision.file_id,
            'filename':file.original_name,'relative_path':file.relative_path,'sha256':revision.sha256,
            'created_by':revision.created_by,'reviewed_by':revision.reviewed_by,'approved_by':revision.approved_by,
            'change_summary':revision.change_summary,'blank_master_confirmed':revision.blank_master_confirmed,
            'history':[{'actor_id':e.actor_id,'before':e.previous_status,'status':e.status,'reason':e.reason,'at':e.created_at.isoformat()} for e in events]}


@router.get('/documents')
def list_documents(db:Session=Depends(session),user:User=Depends(current_user)):
    documents=db.scalars(select(ControlledDocument).order_by(ControlledDocument.id.desc())).all()
    return [{'id':d.id,'kind':d.kind,'number':d.number,'title':d.title,
             'revisions':[revision_json(db,r) for r in db.scalars(select(ControlledRevision).where(ControlledRevision.document_id==d.id).order_by(ControlledRevision.id.desc())).all()]} for d in documents]


@router.post('/documents',status_code=201)
def add_document(body:DocumentInput,db:Session=Depends(session),user:User=Depends(current_user)):
    manager(user)
    doc=ControlledDocument(kind=body.kind,number=body.number,identity_key=body.number.casefold(),title=body.title)
    db.add(doc)
    try:db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Controlled document identity already exists')
    record(db,user,'document.created','controlled_document',doc.id,{'kind':doc.kind,'number':doc.number})
    db.commit();return {'id':doc.id,'kind':doc.kind,'number':doc.number,'title':doc.title}


@router.post('/documents/{document_id}/revisions',status_code=201)
def add_revision(document_id:int,body:RevisionInput,db:Session=Depends(session),user:User=Depends(current_user)):
    manager(user)
    doc=db.scalar(select(ControlledDocument).where(ControlledDocument.id==document_id).with_for_update())
    file=db.get(StoredFile,body.file_id)
    if not doc or not file:raise HTTPException(404,'Controlled document or imported original not found')
    revision=create_revision(db,doc,file,body.revision,user,body.change_summary,body.blank_master_confirmed)
    db.commit();return revision_json(db,revision)


@router.post('/revisions/{revision_id}/actions')
def action(revision_id:int,body:ActionInput,db:Session=Depends(session),user:User=Depends(current_user)):
    revision=db.get(ControlledRevision,revision_id)
    if not revision:raise HTTPException(404,'Revision not found')
    transition(db,revision,user,body.action,body.reason)
    db.commit();return revision_json(db,revision)


@router.get('/revisions/{revision_id}')
def get_revision(revision_id:int,db:Session=Depends(session),user:User=Depends(current_user)):
    revision=db.get(ControlledRevision,revision_id)
    if not revision:raise HTTPException(404,'Revision not found')
    return revision_json(db,revision)


@router.post('/work-orders/{order_id}/resolve-drawing-references')
def resolve_drawings(order_id:int,db:Session=Depends(session),user:User=Depends(current_user)):
    if user.role!='Engineering':raise HTTPException(403,'Engineering required')
    order=db.scalar(select(WorkOrder).where(WorkOrder.id==order_id).with_for_update())
    if not order:raise HTTPException(404,'Work order not found')
    if order.status!='Open':raise HTTPException(409,'References can only be resolved before work begins')
    for part in order.parts:
        if part.controlled_revision_id and part.drawing_status=='Approved':continue
        if not part.drawing_number_snapshot:continue
        revision,file,status=drawing_reference(db,part.drawing_number_snapshot,part.drawing_rev_snapshot)
        if status!='Approved' or (part.drawing_file_id and part.drawing_file_id!=file.id) or (part.controlled_revision_id and part.controlled_revision_id!=revision.id):
            raise HTTPException(409,'An exact approved original is required; historical snapshots cannot be rewritten')
        part.controlled_revision_id=revision.id;part.drawing_file_id=file.id;part.drawing_status='Approved'
    record(db,user,'work_order.drawings_resolved','work_order',order.id)
    db.commit();return {'ok':True}
