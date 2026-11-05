"""An integrated, order-scoped validation workspace with immutable original evidence."""
import hashlib
import io
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import quote
from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException,Request,Response,UploadFile,File,Form
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select,or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import session
from .models import (User,WorkOrder,PhysicalPart,StoredFile,ControlledDocument,ControlledRevision,WorkOrderAttachment,
    WorkOrderEvidence,DispositionEvent,AuditEvent,AuthSession,LaborEntry,CompletedForm,WorkbookDraft)
from .security import current_user,require_capability
from .workflow_api import can_edit,attachments
from .controlled import file_bytes
from .audit import record

router=APIRouter(prefix='/api')
MAX_EVIDENCE=25*1024*1024


def access(db,order_id,user,write=False):
    order=db.scalar(select(WorkOrder).where(WorkOrder.id==order_id).with_for_update().execution_options(populate_existing=True)) if write else db.get(WorkOrder,order_id)
    if not order:raise HTTPException(404,'Work order not found')
    if order.archived_at is not None:
        if write:raise HTTPException(409,'Archived work orders cannot be modified')
        if not user.is_admin:raise HTTPException(404,'Work order not found')
    # New job evidence is restricted to the assignee/creator, Management or Administrator.
    reviewer=user.role=='Engineering' and 'engineering.approve' in (user.capabilities or []) and not write
    if not(user.is_admin or user.role=='Management' or reviewer or user.id in (order.assigned_to,order.created_by)):
        raise HTTPException(403,'This work order is not assigned to you')
    if write:can_edit(user,order)
    return order


def evidence_json(db,e):
    u=db.get(User,e.uploaded_by)
    return {'id':e.id,'filename':e.filename,'category':e.category,'media_type':e.media_type,'bytes':len(e.content),
        'sha256':e.sha256,'uploaded_by':e.uploaded_by,'uploader':u.display_name,'uploaded_at':e.uploaded_at,
        'description':e.description,'equipment':e.equipment,'sample':e.sample,'part_id':e.part_id,
        'url':f'/api/work-orders/{e.work_order_id}/evidence/{e.id}/content'}


def disposition_json(db,e):
    return {'id':e.id,'result':e.result,'state':e.state,'rationale':e.rationale,'actor_id':e.actor_id,
        'actor':db.get(User,e.actor_id).display_name,'created_at':e.created_at,'request_id':e.request_id}


@router.get('/work-orders/{order_id}/workspace')
def workspace(order_id:int,db:Session=Depends(session),user:User=Depends(current_user)):
    order=access(db,order_id,user)
    from .main import query_order,serialize_order
    order=query_order(db,order_id)
    parts=[]
    for entry in order.parts:
        part=db.get(PhysicalPart,entry.part_id)
        revision=db.get(ControlledRevision,entry.controlled_revision_id) if entry.controlled_revision_id else None
        parts.append({'part_id':part.id,'selected_part_number':entry.selected_part_number,'quantity':entry.quantity,'description':part.description,'family':part.family.name,
            'aliases':[{'account':a.account,'part_number':a.part_number} for a in part.aliases],
            'drawing':{'number':entry.drawing_number_snapshot,'revision':entry.drawing_rev_snapshot,'status':entry.drawing_status,
                'current_status':revision.status if revision else None,'revision_id':revision.id if revision else None,'file_id':entry.drawing_file_id,
                'url':f'/api/work-orders/{order.id}/resources/{entry.drawing_file_id}/content' if entry.drawing_file_id else None}})
    labor=db.scalars(select(LaborEntry).where(LaborEntry.work_order_id==order.id).order_by(LaborEntry.id)).all()
    completed_ids=[str(i) for i in db.scalars(select(CompletedForm.id).where(CompletedForm.work_order_id==order.id))]
    draft_ids=list(db.scalars(select(WorkbookDraft.id).where(WorkbookDraft.work_order_id==order.id)))
    history=db.scalars(select(AuditEvent).where(or_(
        (AuditEvent.entity_type=='work_order')&(AuditEvent.entity_id==str(order.id)),
        (AuditEvent.entity_type=='labor')&AuditEvent.entity_id.in_([str(e.id) for e in labor]),
        (AuditEvent.entity_type=='completed_form')&AuditEvent.entity_id.in_(completed_ids),
        (AuditEvent.entity_type=='workbook_draft')&AuditEvent.entity_id.in_(draft_ids))).order_by(AuditEvent.id.desc()).limit(100)).all()
    evidence=db.scalars(select(WorkOrderEvidence).where(WorkOrderEvidence.work_order_id==order.id).order_by(WorkOrderEvidence.id.desc())).all()
    dispositions=db.scalars(select(DispositionEvent).where(DispositionEvent.work_order_id==order.id).order_by(DispositionEvent.id.desc())).all()
    return {'order':serialize_order(order),'parts':parts,'attachments':attachments(order.id,db,user),
        'evidence':[evidence_json(db,e) for e in evidence],
        'labor':[{'id':e.id,'employee_id':e.employee_id,'employee':db.get(User,e.employee_id).display_name,'activity':e.activity,
                  'started_at':e.started_at,'stopped_at':e.stopped_at,'seconds':e.duration_seconds} for e in labor],
        'labor_seconds':sum(e.duration_seconds or 0 for e in labor),'dispositions':[disposition_json(db,e) for e in dispositions],
        'activity':[{'id':e.id,'action':e.action,'actor':db.get(User,e.actor_id).display_name if e.actor_id else 'System','at':e.created_at,'changes':e.changes} for e in history],
        'can_edit':order.archived_at is None and order.status not in ('Completed','Closed','Cancelled') and (user.is_admin or user.role=='Management' or user.id in (order.assigned_to,order.created_by)),'can_approve':user.role=='Engineering' and 'engineering.approve' in (user.capabilities or [])}


def media(blob,filename,category):
    ext=PurePosixPath(filename).suffix.lower()
    if category=='Test result' and ext!='.pdf':raise HTTPException(422,'Upload the original equipment PDF for Test Results')
    if category in ('Test result','Supporting document') and ext=='.pdf' and blob.startswith(b'%PDF-') and b'%%EOF' in blob[-4096:]:return 'application/pdf'
    if category=='Photo' and ext in ('.png','.jpg','.jpeg'):
        from PIL import Image
        try:
            with Image.open(io.BytesIO(blob)) as image:
                detected=image.format;image.verify()
            if detected not in ('PNG','JPEG'):raise ValueError()
        except Exception:raise HTTPException(422,'Upload a valid PNG or JPEG image')
        return 'image/png' if detected=='PNG' else 'image/jpeg'
    if category=='Video' and ext in ('.mp4','.webm'):
        if ext=='.mp4' and len(blob)>12 and blob[4:8]==b'ftyp':return 'video/mp4'
        if ext=='.webm' and blob.startswith(b'\x1aE\xdf\xa3'):return 'video/webm'
    if category=='Supporting document' and ext=='.csv':
        try:blob.decode('utf-8-sig')
        except UnicodeError:raise HTTPException(422,'CSV supporting files must be UTF-8')
        return 'text/csv'
    if category=='Supporting document' and ext=='.xlsx':
        from .editor_api import validate_for_editor
        validate_for_editor(blob);return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    raise HTTPException(422,'Supported evidence: original PDF, PNG/JPEG photo, MP4/WebM video, XLSX or UTF-8 CSV supporting file')


@router.post('/work-orders/{order_id}/evidence',status_code=201)
async def upload_evidence(order_id:int,file:UploadFile=File(...),category:Literal['Test result','Photo','Video','Supporting document']=Form('Test result'),
    part_id:int|None=Form(None,gt=0),sample:str=Form('',max_length=100),equipment:str=Form('',max_length=200),description:str=Form('',max_length=2000),
    db:Session=Depends(session),user:User=Depends(current_user)):
    order=access(db,order_id,user,True)
    if part_id and not any(p.part_id==part_id for p in order.parts):raise HTTPException(422,'Evidence part is not on this work order')
    filename=file.filename or ''
    from .main import safe_relative_path
    if filename!=filename.strip() or '/' in filename or '\\' in filename or len(filename)>255:raise HTTPException(422,'Retain a valid original filename without a path')
    try:safe_relative_path(filename)
    except ValueError:raise HTTPException(422,'Invalid original filename')
    if db.scalar(select(WorkOrderEvidence.id).where(WorkOrderEvidence.work_order_id==order.id,WorkOrderEvidence.filename==filename)):
        raise HTTPException(409,'That evidence filename already exists on this work order; nothing overwritten')
    blob=await file.read(MAX_EVIDENCE+1)
    if not blob or len(blob)>MAX_EVIDENCE:raise HTTPException(413,'Evidence must be a nonempty file of at most 25 MB')
    kind=media(blob,filename,category)
    e=WorkOrderEvidence(work_order_id=order.id,part_id=part_id,filename=filename,category=category,media_type=kind,content=blob,
        sha256=hashlib.sha256(blob).hexdigest(),uploaded_by=user.id,sample=sample,equipment=equipment,description=description)
    db.add(e)
    try:
        db.flush();record(db,user,'evidence.uploaded','work_order',order.id,{'evidence_id':e.id,'filename':filename,'sha256':e.sha256,'category':category})
        db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Evidence filename collision; nothing overwritten')
    return evidence_json(db,e)


@router.get('/work-orders/{order_id}/evidence/{evidence_id}/content')
def get_evidence(order_id:int,evidence_id:int,request:Request,download:bool=False,db:Session=Depends(session),user:User=Depends(current_user)):
    access(db,order_id,user)
    e=db.get(WorkOrderEvidence,evidence_id)
    if not e or e.work_order_id!=order_id:raise HTTPException(404,'Evidence not found on this work order')
    if hashlib.sha256(e.content).hexdigest()!=e.sha256:raise HTTPException(409,'Evidence integrity check failed')
    headers={'Content-Disposition':('attachment' if download else 'inline')+"; filename*=UTF-8''"+quote(e.filename,safe=''),
        'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
    if e.media_type.startswith('video/'):
        # Browser native video controls use byte ranges; return original bytes only.
        start=0;end=len(e.content)-1
        supplied=request.headers.get('range')
        if supplied:
            import re
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',supplied)
            if not match or not any(match.groups()):raise HTTPException(416,'Invalid evidence byte range')
            if match[1]:
                start=int(match[1]);end=min(int(match[2]),end) if match[2] else end
            else:
                suffix=int(match[2]);start=max(0,len(e.content)-suffix)
                if not suffix:raise HTTPException(416,'Invalid evidence suffix range')
            if start>end or start>=len(e.content):raise HTTPException(416,'Evidence range outside file')
            headers['Content-Range']=f'bytes {start}-{end}/{len(e.content)}'
        headers['Accept-Ranges']='bytes'
        return Response(e.content[start:end+1],status_code=206 if supplied else 200,media_type=e.media_type,headers=headers)
    return Response(e.content,media_type=e.media_type,headers=headers)


@router.get('/work-orders/{order_id}/resources/{file_id}/content')
def resource(order_id:int,file_id:int,download:bool=False,db:Session=Depends(session),user:User=Depends(current_user)):
    order=access(db,order_id,user)
    pinned=any(p.drawing_file_id==file_id for p in order.parts)
    attached=db.scalar(select(WorkOrderAttachment.id).where(WorkOrderAttachment.work_order_id==order.id,WorkOrderAttachment.file_id==file_id))
    completed=db.scalar(select(CompletedForm.id).where(CompletedForm.work_order_id==order.id,CompletedForm.file_id==file_id))
    if not(pinned or attached or completed):raise HTTPException(404,'This original is not linked to this work order')
    file=db.get(StoredFile,file_id);blob=file_bytes(db,file)
    mime='application/pdf' if file.original_name.lower().endswith('.pdf') else 'application/octet-stream'
    return Response(blob,media_type=mime,headers={'Content-Disposition':('attachment' if download else 'inline')+"; filename*=UTF-8''"+quote(file.original_name,safe=''),'Cache-Control':'no-store'})


class DispositionInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    result:Literal['Pass','Fail','Conditional Pass']
    rationale:str=Field(default='',max_length=2000)


@router.post('/work-orders/{order_id}/disposition',status_code=201)
def disposition(order_id:int,body:DispositionInput,db:Session=Depends(session),user:User=Depends(current_user)):
    access(db,order_id,user,True)
    if body.result=='Conditional Pass' and len(body.rationale)<3:raise HTTPException(422,'Conditional disposition requires a rationale and independent Engineering approval')
    event=DispositionEvent(work_order_id=order_id,result=body.result,state='Pending Engineering' if body.result=='Conditional Pass' else 'Recorded',rationale=body.rationale,actor_id=user.id)
    db.add(event);db.flush();record(db,user,'disposition.recorded','work_order',order_id,{'result':event.result,'state':event.state,'disposition_id':event.id,'rationale':event.rationale});db.commit()
    return disposition_json(db,event)


@router.post('/work-orders/{order_id}/disposition/{event_id}/approve')
def approve_disposition(order_id:int,event_id:int,db:Session=Depends(session),user:User=Depends(current_user)):
    require_capability(user,'engineering.approve')
    if user.role!='Engineering':raise HTTPException(403,'Engineering department approval required')
    order=db.scalar(select(WorkOrder).where(WorkOrder.id==order_id).with_for_update())
    if not order:raise HTTPException(404,'Work order not found')
    can_edit(user,order)
    latest=db.scalar(select(DispositionEvent).where(DispositionEvent.work_order_id==order.id).order_by(DispositionEvent.id.desc()))
    if not latest or latest.id!=event_id or latest.state!='Pending Engineering':raise HTTPException(409,'Only the current pending request can be approved')
    if latest.actor_id==user.id:raise HTTPException(403,'Independent Engineering approval is required')
    e=DispositionEvent(work_order_id=order.id,result=latest.result,state='Approved',rationale=latest.rationale,actor_id=user.id,request_id=latest.id)
    db.add(e);db.flush();record(db,user,'disposition.approved','work_order',order.id,{'disposition_id':e.id,'request_id':latest.id});db.commit();return disposition_json(db,e)


class CommentInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    text:str=Field(min_length=1,max_length=2000)

@router.post('/work-orders/{order_id}/comments',status_code=201)
def comment(order_id:int,body:CommentInput,db:Session=Depends(session),user:User=Depends(current_user)):
    access(db,order_id,user,True)
    record(db,user,'work_order.comment_added','work_order',order_id,{'text':body.text})
    db.commit();return {'saved':True}

@router.get('/work-orders/{order_id}/drawing-history/{part_id}')
def drawing_history(order_id:int,part_id:int,db:Session=Depends(session),user:User=Depends(current_user)):
    order=access(db,order_id,user)
    part=next((p for p in order.parts if p.part_id==part_id),None)
    if not part:raise HTTPException(404,'Part not on this work order')
    if not part.controlled_revision_id:return {'pinned_revision_id':None,'revisions':[]}
    pinned=db.get(ControlledRevision,part.controlled_revision_id)
    from .controlled_api import revision_json
    return {'pinned_revision_id':pinned.id,'revisions':[revision_json(db,r) for r in db.scalars(select(ControlledRevision).where(ControlledRevision.document_id==pinned.document_id).order_by(ControlledRevision.id.desc()))]}
