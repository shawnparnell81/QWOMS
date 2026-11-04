"""Upload-defined workbook masters and persisted matching rules; no cell or sheet schema."""
import hashlib
import uuid
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Form
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import session
from .models import User,ControlledDocument,ControlledRevision,StoredFile,WorkflowRule,PhysicalPart,ProductFamily
from .security import current_user,require_capability
from .controlled import create_revision
from .editor_api import validate_for_editor
from .workflow_api import scope
from .storage import original_store
from .audit import record

router=APIRouter(prefix='/api/form-templates')


@router.get('')
def library(include_retired:bool=False,db:Session=Depends(session),user:User=Depends(current_user)):
    query=select(ControlledDocument).where(ControlledDocument.kind=='Form template').order_by(ControlledDocument.id.desc())
    if not include_retired:query=query.where(ControlledDocument.retired.is_(False))
    result=[]
    for doc in db.scalars(query):
        revisions=[]
        for revision in db.scalars(select(ControlledRevision).where(ControlledRevision.document_id==doc.id).order_by(ControlledRevision.id.desc())):
            file=db.get(StoredFile,revision.file_id)
            revisions.append({'id':revision.id,'revision':revision.revision,'status':revision.status,'filename':file.original_name,'file_id':file.id,'sha256':file.sha256,'created_by':revision.created_by})
        rules=db.scalars(select(WorkflowRule).where(WorkflowRule.active.is_(True))).all()
        result.append({'id':doc.id,'number':doc.number,'title':doc.title,'retired':doc.retired,'revisions':revisions,
            'mappings':[{'rule_id':r.id,'order_type':r.order_type,'subtype':r.subtype,'part_id':r.part_id,'family_id':r.family_id} for r in rules if doc.id in r.document_ids]})
    return result


@router.post('',status_code=201)
async def upload_template(file:UploadFile=File(...),number:str=Form(...,min_length=1,max_length=150),title:str=Form(...,min_length=3,max_length=200),
    revision:str=Form(...,min_length=1,max_length=50),order_type:str=Form('Validation / FAI'),subtype:str=Form(''),
    part_id:int|None=Form(None,gt=0),family_id:int|None=Form(None,gt=0),blank_master_confirmed:bool=Form(False),
    db:Session=Depends(session),user:User=Depends(current_user)):
    require_capability(user,'import.form_masters');scope(order_type,subtype)
    if not blank_master_confirmed:raise HTTPException(422,'Confirm this is the original reusable blank master')
    if not number.strip() or not title.strip() or not revision.strip():raise HTTPException(422,'Enter a document number, title and revision')
    if family_id and not db.get(ProductFamily,family_id):raise HTTPException(422,'Product family not found')
    if part_id:
        part=db.get(PhysicalPart,part_id)
        if not part or (family_id and part.family_id!=family_id):raise HTTPException(422,'Part and product family do not match')
    filename=file.filename or ''
    from .main import safe_relative_path,STORAGE_ROOT,MAX_FILE_BYTES
    if not filename.lower().endswith('.xlsx') or '/' in filename or '\\' in filename or filename!=filename.strip():raise HTTPException(422,'Upload the original .xlsx filename without a path')
    try:safe_relative_path(filename)
    except ValueError:raise HTTPException(422,'Invalid original filename')
    blob=await file.read(MAX_FILE_BYTES+1)
    if len(blob)>MAX_FILE_BYTES:raise HTTPException(413,'Workbook exceeds 25 MB')
    validate_for_editor(blob)
    if db.scalar(select(ControlledDocument.id).where(ControlledDocument.kind=='Form template',ControlledDocument.identity_key==number.strip().casefold())):
        raise HTTPException(409,'Template number already exists; register a controlled new revision or choose a different number')
    path='Form masters/'+str(uuid.uuid4())+'/'+filename
    store=original_store(STORAGE_ROOT,db);key='files/'+path;written=False
    try:
        doc=ControlledDocument(kind='Form template',number=number.strip(),identity_key=number.strip().casefold(),title=title.strip());db.add(doc);db.flush()
        store.put_new(key,blob);written=True
        stored=StoredFile(relative_path=path,original_name=filename,kind='form-template',sha256=hashlib.sha256(blob).hexdigest(),uploaded_by=user.id);db.add(stored);db.flush()
        rev=create_revision(db,doc,stored,revision.strip(),user,'Uploaded original blank validation master',True)
        mapping=WorkflowRule(name=title.strip()[:180]+' · matching rule',order_type=order_type,subtype=subtype,part_id=part_id,family_id=family_id,
            fields=[],instructions='',document_ids=[doc.id],created_by=user.id)
        db.add(mapping);db.flush();record(db,user,'template.imported','controlled_document',doc.id,{'filename':filename,'sha256':stored.sha256,'rule_id':mapping.id,'part_id':part_id,'family_id':family_id})
        db.commit()
    except Exception:
        db.rollback()
        if written and hasattr(store,'discard_new'):store.discard_new(key)
        raise
    return {'id':doc.id,'revision_id':rev.id,'status':rev.status,'filename':filename,'sha256':stored.sha256,'rule_id':mapping.id}


@router.post('/{document_id}/retire')
def retire(document_id:int,db:Session=Depends(session),user:User=Depends(current_user)):
    return lifecycle(document_id,True,db,user)


@router.post('/{document_id}/restore')
def restore(document_id:int,db:Session=Depends(session),user:User=Depends(current_user)):
    return lifecycle(document_id,False,db,user)


def lifecycle(document_id,retired,db,user):
    require_capability(user,'import.form_masters')
    doc=db.scalar(select(ControlledDocument).where(ControlledDocument.id==document_id).with_for_update())
    if not doc or doc.kind!='Form template':raise HTTPException(404,'Form template not found')
    if doc.retired!=retired:
        doc.retired=retired;record(db,user,'template.retired' if retired else 'template.restored','controlled_document',doc.id,{'retired':retired})
    db.commit();return {'id':doc.id,'retired':doc.retired}
