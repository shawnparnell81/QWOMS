"""Cookie/CSRF-controlled drafts and a scoped WOPI bridge to a configured office server.

No editor distribution or evaluation license is bundled. WOPI credentials never grant
access to an original master: each token names one employee-owned temporary draft.
"""
import hashlib
import hmac
import io
import os
import secrets
import uuid
import zipfile
from datetime import datetime,timedelta,timezone
from urllib.parse import urlsplit,urlencode,quote
from urllib.request import urlopen
from typing import Literal
from defusedxml import ElementTree
from fastapi import APIRouter,Depends,HTTPException,Request,Response,UploadFile
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import session
from .models import WorkbookDraft,WorkOrder,WorkOrderAttachment,ControlledRevision,CompletedForm,StoredFile,User,AuthSession
from .security import current_user
from .controlled import file_bytes,validate_xlsx
from .workflow_api import can_edit,save_completed
from .audit import record

router=APIRouter()
MAX_BYTES=25*1024*1024

def now():return datetime.now(timezone.utc)
def utc(value):return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def office_settings():
    if os.getenv('QWOMS_OFFICE_ENABLED','false').casefold()!='true':raise HTTPException(503,'Workbook editor service is not configured')
    values=[os.getenv(k,'').rstrip('/') for k in ('QWOMS_OFFICE_PUBLIC_URL','QWOMS_OFFICE_INTERNAL_URL','QWOMS_OFFICE_WOPI_ORIGIN')]
    for value in values:
        u=urlsplit(value)
        if u.scheme not in ('https','http') or not u.hostname or u.username or u.password or u.query or u.fragment or u.path:
            raise HTTPException(503,'Editor URLs must be explicitly configured HTTP(S) origins')
        if u.scheme!='https' and os.getenv('QWOMS_OFFICE_LOCAL_DEVELOPMENT','false').casefold()!='true':raise HTTPException(503,'Editor requires HTTPS outside explicit local development')
    return values

def validate_for_editor(blob):
    validate_xlsx(blob)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for name in archive.namelist():
            if name.startswith(('xl/externalLinks/','xl/embeddings/','xl/activeX/')):
                raise HTTPException(422,'External links, embedded programs and active content are unsupported in the editor')
            if name.endswith('.rels'):
                root=ElementTree.fromstring(archive.read(name))
                if any(item.get('TargetMode','').casefold()=='external' for item in root):
                    raise HTTPException(422,'External workbook relationships must be reviewed before browser editing')
            if name.startswith('xl/worksheets/') and name.endswith('.xml'):
                root=ElementTree.fromstring(archive.read(name))
                for item in root.iter():
                    if item.tag.endswith('}f') and any(function in (item.text or '').upper() for function in ('WEBSERVICE(', 'DDE(', 'RTD(')):
                        raise HTTPException(422,'External data formulas are unsupported in the editor')


def read_access(user,order):
    if user.role=='Production' and order.assigned_to!=user.id:raise HTTPException(403,'Only assigned Production employees may open this workbook')

def approved_attachment(db,order,attachment_id):
    a=db.get(WorkOrderAttachment,attachment_id)
    if not a or a.work_order_id!=order.id or a.kind!='Form template':raise HTTPException(404,'Attached Excel form not found')
    revision=db.get(ControlledRevision,a.revision_id)
    if not revision or revision.status not in ('Approved','Superseded'):raise HTTPException(409,'The pinned blank master is not an approved historical revision')
    return a

class Begin(BaseModel):
    model_config=ConfigDict(extra='forbid')
    completed_id:int|None=Field(default=None,gt=0)

class Save(BaseModel):
    model_config=ConfigDict(extra='forbid')
    filename:str=Field(min_length=6,max_length=255)
    expected_version:int=Field(ge=1)
    acknowledge_fidelity_differences:bool=False


def cookie_draft(db,draft_id,user,write=False,locked=False):
    q=select(WorkbookDraft).where(WorkbookDraft.id==draft_id)
    if locked:q=q.with_for_update()
    draft=db.scalar(q)
    if not draft or draft.owner_id!=user.id:raise HTTPException(404,'Workbook draft not found')
    if utc(draft.expires_at)<=now():raise HTTPException(410,'Workbook editing session expired; reopen the original or completed file')
    order=db.get(WorkOrder,draft.work_order_id);read_access(user,order)
    from .workspace_api import access
    access(db,order.id,user,write=write)
    approved_attachment(db,order,draft.attachment_id)
    if write:can_edit(user,order)
    return draft,order


@router.get('/api/workbook-editor/status')
def editor_status(user:User=Depends(current_user)):
    if os.getenv('QWOMS_WORKBOOK_ENGINE','free')=='free':return {'enabled':True,'engine':'QWOMS free workbook forms','license':'No paid editor or office service required','compatibility':'Supported measurement forms; browser rendering is not certified identical to Excel.'}
    try:office_settings()
    except HTTPException:return {'enabled':False}
    return {'enabled':True,'engine':'Collabora Online','compatibility':'Workbook compatibility testing is required; exact Excel fidelity is not certified.'}


@router.post('/api/work-orders/{order_id}/attachments/{attachment_id}/editor',status_code=201)
def begin(order_id:int,attachment_id:int,body:Begin,request:Request,engine:Literal['free','collabora']|None=None,db:Session=Depends(session),user:User=Depends(current_user)):
    selected=engine or os.getenv('QWOMS_WORKBOOK_ENGINE','free')
    if selected not in ('free','collabora'):raise HTTPException(503,'Unknown workbook engine configuration')
    if selected=='collabora':office_settings()
    order=db.get(WorkOrder,order_id)
    if not order:raise HTTPException(404,'Work order not found')
    read_access(user,order)
    from .workspace_api import access
    access(db,order.id,user)
    attachment=approved_attachment(db,order,attachment_id)
    source=db.get(StoredFile,attachment.file_id)
    if body.completed_id:
        saved=db.get(CompletedForm,body.completed_id)
        if not saved or saved.work_order_id!=order.id or saved.attachment_id!=attachment.id:raise HTTPException(404,'Completed workbook does not belong to this attached form')
        source=db.get(StoredFile,saved.file_id)
    elif order.status in ('Completed','Closed'):raise HTTPException(409,'Open a saved completed workbook for a closed order')
    blob=file_bytes(db,source);validate_for_editor(blob)
    if not body.completed_id and hashlib.sha256(blob).hexdigest()!=attachment.sha256:raise HTTPException(409,'Pinned blank master integrity check failed')
    draft=WorkbookDraft(id=str(uuid.uuid4()),work_order_id=order.id,attachment_id=attachment.id,owner_id=user.id,
        auth_session_id=request.state.session_id,source_file_id=source.id,content=blob,expires_at=now()+timedelta(hours=2))
    db.add(draft);db.flush();record(db,user,'workbook.opened','workbook_draft',draft.id,{'work_order_id':order.id,'attachment_id':attachment.id,'source_file_id':source.id})
    db.commit();return {'id':draft.id,'engine':selected,'url':('/static/free-editor.html?draft=' if selected=='free' else '/static/editor.html?draft=')+draft.id}


@router.post('/api/workbooks/{draft_id}/launch')
def launch(draft_id:str,request:Request,db:Session=Depends(session),user:User=Depends(current_user)):
    public,internal,wopi_origin=office_settings();draft,order=cookie_draft(db,draft_id,user,locked=True)
    # Discovery is an administrator-configured URL, never a URL supplied by a user.
    try:
        with urlopen(internal+'/hosting/discovery',timeout=10) as r:data=r.read(1024*1024+1)
        if len(data)>1024*1024:raise ValueError('Discovery too large')
        root=ElementTree.fromstring(data)
        action=next(a for a in root.iter('action') if a.get('ext')=='xlsx' and a.get('name')=='edit')
        discovered=urlsplit(action.attrib['urlsrc']);public_parts=urlsplit(public)
        url=discovered._replace(scheme=public_parts.scheme,netloc=public_parts.netloc,query='',fragment='').geturl()
        if not discovered.path.startswith('/browser/') or not discovered.path.endswith('/cool.html'):raise ValueError('Unexpected editor action')
    except Exception:raise HTTPException(503,'Workbook editor discovery is unavailable')
    token=secrets.token_urlsafe(40);draft.token_hash=hashlib.sha256(token.encode()).hexdigest();draft.auth_session_id=request.state.session_id
    source=db.get(StoredFile,draft.source_file_id);db.commit()
    return {'editor_url':url+'?'+urlencode({'WOPISrc':wopi_origin+'/wopi/files/'+draft.id,'lang':'en-US','closebutton':'1'}),
        'access_token':token,'access_token_ttl':int(utc(draft.expires_at).timestamp()*1000),'office_origin':public,
        'filename':source.original_name,'order_id':order.id,'project_id':order.project_id,'version':draft.version,
        'read_only':order.status in ('Completed','Closed')}


@router.get('/api/workbooks/{draft_id}')
def draft_status(draft_id:str,db:Session=Depends(session),user:User=Depends(current_user)):
    draft,order=cookie_draft(db,draft_id,user)
    return {'id':draft.id,'version':draft.version,'bytes':len(draft.content),'updated_at':draft.updated_at,'order_id':order.id,'attachment_id':draft.attachment_id,'project_id':order.project_id}


def compatibility_for(db,draft):
    from .workbook_fidelity import compare
    attachment=db.get(WorkOrderAttachment,draft.attachment_id)
    master=db.get(StoredFile,attachment.file_id)
    return compare(file_bytes(db,master),draft.content)


@router.get('/api/workbooks/{draft_id}/compatibility')
def compatibility(draft_id:str,db:Session=Depends(session),user:User=Depends(current_user)):
    draft,_=cookie_draft(db,draft_id,user)
    return {**compatibility_for(db,draft),'version':draft.version}


@router.post('/api/workbooks/{draft_id}/completed',status_code=201)
async def completed(draft_id:str,body:Save,db:Session=Depends(session),user:User=Depends(current_user)):
    draft,order=cookie_draft(db,draft_id,user,write=True,locked=True)
    if draft.version!=body.expected_version:raise HTTPException(409,'Workbook changed after editor save; save again before filing')
    comparison=compatibility_for(db,draft)
    if comparison['difference_count'] and not body.acknowledge_fidelity_differences:
        raise HTTPException(409,'Workbook fidelity differences require explicit review before filing this test copy')
    if comparison['difference_count']:
        record(db,user,'workbook.fidelity_acknowledged','workbook_draft',draft.id,{'difference_count':comparison['difference_count'],'version':draft.version})
    # Reuse the same audited, duplicate-safe, employee-named filing path as uploads.
    return await save_completed(order.id,draft.attachment_id,body.filename,UploadFile(io.BytesIO(draft.content),filename=body.filename),db,user)


@router.get('/api/workbooks/{draft_id}/export')
def export(draft_id:str,filename:str,acknowledge_fidelity_differences:bool=False,db:Session=Depends(session),user:User=Depends(current_user)):
    draft,_=cookie_draft(db,draft_id,user)
    from .main import safe_relative_path
    if not filename.lower().endswith('.xlsx') or filename!=filename.strip() or '/' in filename or '\\' in filename:raise HTTPException(422,'Enter an exact .xlsx filename without a path')
    try:safe_relative_path(filename)
    except ValueError:raise HTTPException(422,'Invalid export filename')
    if compatibility_for(db,draft)['difference_count'] and not acknowledge_fidelity_differences:
        raise HTTPException(409,'Review the measured fidelity differences before exporting this test copy')
    return Response(draft.content,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(filename),'Cache-Control':'no-store'})


def wopi_draft(db,request,draft_id,write=False):
    office_settings()
    token=getattr(request.state,'wopi_token',None) or request.query_params.get('access_token','')
    if len(token)>200:raise HTTPException(401,'Invalid workbook access token')
    q=select(WorkbookDraft).where(WorkbookDraft.id==draft_id)
    if write:q=q.with_for_update()
    draft=db.scalar(q)
    if not draft or not token or not draft.token_hash or not hmac.compare_digest(draft.token_hash,hashlib.sha256(token.encode()).hexdigest()):raise HTTPException(401,'Invalid workbook access token')
    if utc(draft.expires_at)<=now():raise HTTPException(401,'Workbook token expired')
    user=db.get(User,draft.owner_id);auth=db.get(AuthSession,draft.auth_session_id)
    if not user or not user.active or not auth or auth.user_id!=user.id or auth.revoked_at or utc(auth.expires_at)<=now():raise HTTPException(401,'Workbook account session revoked')
    order=db.get(WorkOrder,draft.work_order_id);read_access(user,order);approved_attachment(db,order,draft.attachment_id)
    if write:can_edit(user,order)
    return draft,user,order


def active_lock(draft):
    return draft.lock_value if draft.lock_expires_at and utc(draft.lock_expires_at)>now() else ''


def lock_conflict(value):return Response(status_code=409,headers={'X-WOPI-Lock':value,'X-WOPI-LockFailureReason':'Workbook lock does not match'})


@router.get('/wopi/files/{draft_id}')
def check_file(draft_id:str,request:Request,db:Session=Depends(session)):
    draft,user,order=wopi_draft(db,request,draft_id)
    source=db.get(StoredFile,draft.source_file_id)
    return {'BaseFileName':source.original_name,'OwnerId':str(user.id),'Size':len(draft.content),'UserId':str(user.id),
        'UserFriendlyName':user.display_name,'Version':str(draft.version),'UserCanWrite':order.status not in ('Completed','Closed'),
        'ReadOnly':order.status in ('Completed','Closed'),'SupportsUpdate':True,'SupportsLocks':True,'SupportsGetLock':True,
        'UserCanNotWriteRelative':True,'PostMessageOrigin':os.getenv('QWOMS_OFFICE_APP_ORIGIN',os.getenv('QWOMS_OFFICE_WOPI_ORIGIN','')),
        'HideExportOption':True,'HideSaveOption':False,'HidePrintOption':False,'EnableOwnerTermination':False}


@router.get('/wopi/files/{draft_id}/contents')
def get_contents(draft_id:str,request:Request,db:Session=Depends(session)):
    draft,_,_=wopi_draft(db,request,draft_id)
    return Response(draft.content,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'X-WOPI-ItemVersion':str(draft.version),'Cache-Control':'no-store'})


@router.post('/wopi/files/{draft_id}')
def locks(draft_id:str,request:Request,db:Session=Depends(session)):
    draft,_,_=wopi_draft(db,request,draft_id,True);existing=active_lock(draft)
    supplied=request.headers.get('x-wopi-lock','');operation=request.headers.get('x-wopi-override','')
    if len(supplied)>1024:raise HTTPException(400,'Workbook lock too long')
    if operation=='GET_LOCK':return Response(status_code=200,headers={'X-WOPI-Lock':existing})
    if operation not in ('LOCK','REFRESH_LOCK','UNLOCK'):raise HTTPException(501,'Unsupported WOPI operation')
    if not supplied or (existing and existing!=supplied) or (operation in ('REFRESH_LOCK','UNLOCK') and not existing):return lock_conflict(existing)
    draft.lock_value='' if operation=='UNLOCK' else supplied;draft.lock_expires_at=None if operation=='UNLOCK' else now()+timedelta(minutes=30)
    db.commit();return Response(status_code=200,headers={'X-WOPI-ItemVersion':str(draft.version)})


@router.post('/wopi/files/{draft_id}/contents')
async def put_contents(draft_id:str,request:Request,db:Session=Depends(session)):
    draft,user,_=wopi_draft(db,request,draft_id,True)
    existing=active_lock(draft)
    if not existing or request.headers.get('x-wopi-lock','')!=existing:return lock_conflict(existing)
    blob=bytearray()
    async for chunk in request.stream():
        blob.extend(chunk)
        if len(blob)>MAX_BYTES:raise HTTPException(413,'Workbook exceeds 25 MB')
    validate_for_editor(bytes(blob))
    draft.content=bytes(blob);draft.version+=1;draft.updated_at=now()
    record(db,user,'workbook.draft_saved','workbook_draft',draft.id,{'version':draft.version,'sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob)})
    db.commit();return Response(status_code=200,headers={'X-WOPI-ItemVersion':str(draft.version)})
