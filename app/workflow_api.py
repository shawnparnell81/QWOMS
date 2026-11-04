import hashlib
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,File,Form,UploadFile
from pydantic import BaseModel,Field,ConfigDict,PositiveInt,model_validator,field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import session
from .security import current_user
from .models import (User,WorkflowRule,ControlledDocument,ControlledRevision,PhysicalPart,ProductFamily,
                     WorkOrder,WorkOrderPart,WorkOrderAttachment,CompletedForm,StoredFile,FormFilingRule)
from .workflows import resolve,validate_values
from .controlled import validate_xlsx
from .storage import original_store,StorageConflict
from .audit import record

router=APIRouter(prefix='/api')


class FieldDefinition(BaseModel):
    model_config=ConfigDict(allow_inf_nan=False)
    key:str=Field(pattern=r'^[a-z][a-z0-9_]{0,49}$')
    label:str=Field(min_length=2,max_length=100)
    type:Literal['text','number','integer','choice']='text'
    required:bool=False
    required_at:Literal['creation','execution','completion']='creation'
    choices:list[str]=Field(default_factory=list,max_length=100)
    unit:str=Field(default='',max_length=30)
    minimum:float|None=None
    maximum:float|None=None
    @field_validator('label','unit',mode='before')
    @classmethod
    def trim_labels(cls,value):return value.strip() if isinstance(value,str) else value
    @model_validator(mode='after')
    def check(self):
        if self.type=='choice' and (not self.choices or len(set(self.choices))!=len(self.choices) or any(not c.strip() or len(c)>200 for c in self.choices)):
            raise ValueError('Choice fields require unique nonblank options')
        if self.minimum is not None and self.maximum is not None and self.minimum>self.maximum:
            raise ValueError('Minimum cannot exceed maximum')
        return self


class RuleInput(BaseModel):
    name:str=Field(min_length=3,max_length=200)
    order_type:str
    subtype:str=''
    family_id:int|None=Field(default=None,gt=0)
    part_id:int|None=Field(default=None,gt=0)
    fields:list[FieldDefinition]=Field(default_factory=list,max_length=50)
    instructions:str=Field(default='',max_length=10000)
    document_ids:list[PositiveInt]=Field(default_factory=list,max_length=50)
    @field_validator('name',mode='before')
    @classmethod
    def trim(cls,v):return v.strip() if isinstance(v,str) else v
    @model_validator(mode='after')
    def meaningful(self):
        if not self.fields and not self.instructions.strip() and not self.document_ids:
            raise ValueError('A requirement rule needs fields, instructions or mandatory documents')
        return self


class PreviewInput(BaseModel):
    order_type:str
    subtype:str
    part_ids:list[PositiveInt]=Field(max_length=100)


class FilingInput(BaseModel):
    order_type:str
    subtype:str=''
    folder:str=Field(min_length=1,max_length=200)


class ValuesInput(BaseModel):
    values:dict[str,str]


def manage(user):
    if user.role not in ('Engineering','Management'):raise HTTPException(403,'Engineering or Management required')


def scope(order_type,subtype,allow_all=True):
    from .main import TYPE_CONFIG
    if order_type not in TYPE_CONFIG or (subtype and subtype not in TYPE_CONFIG[order_type]['subtypes']) or (not allow_all and not subtype):
        raise HTTPException(422,'Invalid work order type/subtype scope')


@router.get('/workflow/rules')
def rules(db:Session=Depends(session),user:User=Depends(current_user)):
    return [{'id':r.id,'name':r.name,'order_type':r.order_type,'subtype':r.subtype,'family_id':r.family_id,'part_id':r.part_id,
             'fields':r.fields,'instructions':r.instructions,'document_ids':r.document_ids,'active':r.active}
            for r in db.scalars(select(WorkflowRule).order_by(WorkflowRule.id.desc())).all()]


@router.post('/workflow/rules',status_code=201)
def add_rule(body:RuleInput,db:Session=Depends(session),user:User=Depends(current_user)):
    manage(user);scope(body.order_type,body.subtype)
    from .main import TYPE_CONFIG
    reserved={f for config in TYPE_CONFIG.values() for f in config['fields']}
    keys=[f.key for f in body.fields]
    if len(set(keys))!=len(keys) or reserved.intersection(keys):raise HTTPException(422,'Use unique custom field keys, distinct from built-in work-type fields')
    if body.family_id and not db.get(ProductFamily,body.family_id):raise HTTPException(422,'Product family not found')
    if body.part_id:
        part=db.get(PhysicalPart,body.part_id)
        if not part or (body.family_id and part.family_id!=body.family_id):raise HTTPException(422,'Physical part/family scope does not match')
    for doc_id in body.document_ids:
        doc=db.get(ControlledDocument,doc_id)
        if not doc or doc.kind=='Drawing':raise HTTPException(422,'Attach only controlled forms, work instructions or supporting documents; drawings come from Part Master')
    data=body.model_dump();data['fields']=[f.model_dump() for f in body.fields];data['document_ids']=sorted(set(body.document_ids))
    rule=WorkflowRule(**data,created_by=user.id);db.add(rule);db.flush()
    record(db,user,'workflow_rule.created','workflow_rule',rule.id,{'name':rule.name,'order_type':rule.order_type})
    db.commit();return {'id':rule.id}


@router.post('/workflow/rules/{rule_id}/retire')
def retire(rule_id:int,db:Session=Depends(session),user:User=Depends(current_user)):
    manage(user)
    rule=db.get(WorkflowRule,rule_id)
    if not rule:raise HTTPException(404,'Rule not found')
    rule.active=False;record(db,user,'workflow_rule.retired','workflow_rule',rule.id);db.commit();return {'ok':True}


@router.post('/workflow/preview')
def preview(body:PreviewInput,db:Session=Depends(session),user:User=Depends(current_user)):
    scope(body.order_type,body.subtype,False)
    result={}
    for part_id in set(body.part_ids):
        part=db.get(PhysicalPart,part_id)
        if not part:raise HTTPException(422,'Physical part not found')
        requirements=resolve(db,part,body.order_type,body.subtype)
        requirements['documents']=[]
        for doc_id in requirements['document_ids']:
            doc=db.get(ControlledDocument,doc_id)
            approved=db.scalar(select(ControlledRevision).where(ControlledRevision.document_id==doc_id,ControlledRevision.status=='Approved'))
            requirements['documents'].append({'number':doc.number,'kind':doc.kind,'revision':approved.revision if approved else None})
        result[str(part_id)]=requirements
    return result


@router.get('/workflow/filing-rules')
def filing_rules(db:Session=Depends(session),user:User=Depends(current_user)):
    return [{'order_type':r.order_type,'subtype':r.subtype,'folder':r.folder} for r in db.scalars(select(FormFilingRule)).all()]


@router.put('/workflow/filing-rules')
def set_filing(body:FilingInput,db:Session=Depends(session),user:User=Depends(current_user)):
    manage(user);scope(body.order_type,body.subtype)
    from .main import safe_relative_path
    try:folder=safe_relative_path(body.folder)
    except ValueError as exc:raise HTTPException(422,str(exc))
    if folder!=body.folder or folder.strip()!=folder:raise HTTPException(422,'Use an exact, valid folder without leading/trailing whitespace')
    rule=db.scalar(select(FormFilingRule).where(FormFilingRule.order_type==body.order_type,FormFilingRule.subtype==body.subtype).with_for_update())
    if not rule:rule=FormFilingRule(order_type=body.order_type,subtype=body.subtype,folder=folder);db.add(rule)
    else:rule.folder=folder
    record(db,user,'form_filing.configured','filing_scope',body.order_type+':'+body.subtype,{'folder':folder})
    db.commit();return body.model_dump()


@router.get('/work-orders/{order_id}/attachments')
def attachments(order_id:int,db:Session=Depends(session),user:User=Depends(current_user)):
    if not db.get(WorkOrder,order_id):raise HTTPException(404,'Work order not found')
    rows=db.scalars(select(WorkOrderAttachment).where(WorkOrderAttachment.work_order_id==order_id)).all()
    return [{'id':a.id,'part_id':a.part_id,'kind':a.kind,'number':a.number,'revision':a.revision,'revision_id':a.revision_id,
             'file_id':a.file_id,'filename':a.filename,'sha256':a.sha256,'category_folder':a.category_folder,
             'current_status':db.get(ControlledRevision,a.revision_id).status,
             'completed':[{'id':c.id,'file_id':c.file_id,'filename':db.get(StoredFile,c.file_id).original_name,'project_id':c.project_id,'saved_at':c.saved_at.isoformat()}
                          for c in db.scalars(select(CompletedForm).where(CompletedForm.attachment_id==a.id)).all()]}
            for a in rows]


def can_edit(user,order):
    if user.role=='Production' and order.assigned_to!=user.id:raise HTTPException(403,'Only assigned Production employees may record this work')
    if order.status in ('Completed','Closed'):raise HTTPException(409,'Completed records cannot be rewritten')


@router.patch('/work-orders/{order_id}/parts/{part_id}/fields')
def update_fields(order_id:int,part_id:int,body:ValuesInput,db:Session=Depends(session),user:User=Depends(current_user)):
    order=db.scalar(select(WorkOrder).where(WorkOrder.id==order_id).with_for_update())
    if not order:raise HTTPException(404,'Work order not found')
    can_edit(user,order)
    entries=[p for p in order.parts if p.part_id==part_id]
    if not entries:raise HTTPException(404,'Physical part not in work order')
    changes=[]
    for entry in entries:
        merged={**entry.field_values,**body.values};validate_values(entry.requirements_snapshot,merged)
        delta={key:{'before':entry.field_values.get(key),'after':value} for key,value in body.values.items() if entry.field_values.get(key)!=value}
        if delta:changes.append({'part_entry_id':entry.id,'values':delta})
        entry.field_values=merged
    if changes:record(db,user,'work_order.fields_updated','work_order',order.id,{'part_id':part_id,'changes':changes})
    db.commit();return {'ok':True}


@router.post('/work-orders/{order_id}/attachments/{attachment_id}/completed',status_code=201)
async def save_completed(order_id:int,attachment_id:int,filename:str=Form(...),file:UploadFile=File(...),
                         db:Session=Depends(session),user:User=Depends(current_user)):
    order=db.scalar(select(WorkOrder).where(WorkOrder.id==order_id).with_for_update())
    if not order:raise HTTPException(404,'Work order not found')
    can_edit(user,order)
    attachment=db.get(WorkOrderAttachment,attachment_id)
    if not attachment or attachment.work_order_id!=order_id or attachment.kind!='Form template':raise HTTPException(422,'Choose an attached form master on this work order')
    if db.get(ControlledRevision,attachment.revision_id).status=='Obsolete':raise HTTPException(409,'Attached form was withdrawn; Engineering review required')
    from .main import safe_relative_path,STORAGE_ROOT,MAX_FILE_BYTES
    if filename!=filename.strip() or '/' in filename or '\\' in filename or not filename.lower().endswith('.xlsx'):
        raise HTTPException(422,'Enter an exact .xlsx filename, without a path or leading/trailing spaces')
    try:safe_relative_path(filename)
    except ValueError as exc:raise HTTPException(422,str(exc))
    blob=await file.read(MAX_FILE_BYTES+1)
    if len(blob)>MAX_FILE_BYTES:raise HTTPException(413,'Completed workbook exceeds 25 MB')
    validate_xlsx(blob)
    relative='Completed forms/'+attachment.category_folder+'/'+filename
    if db.scalar(select(StoredFile.id).where(StoredFile.relative_path==relative)):
        raise HTTPException(409,'Completed filename already exists in this category; choose another name')
    try:original_store(STORAGE_ROOT,db).put_new('files/'+relative,blob)
    except StorageConflict:raise HTTPException(409,'Completed filename already exists; nothing overwritten')
    stored=StoredFile(relative_path=relative,original_name=filename,kind='completed-form',sha256=hashlib.sha256(blob).hexdigest(),uploaded_by=user.id)
    db.add(stored);db.flush()
    completed=CompletedForm(work_order_id=order.id,attachment_id=attachment.id,file_id=stored.id,project_id=order.project_id,saved_by=user.id)
    db.add(completed);db.flush()
    record(db,user,'form.completed_saved','completed_form',completed.id,{'work_order_id':order.id,'project_id':order.project_id,'filename':filename,'folder':attachment.category_folder,'master_revision_id':attachment.revision_id})
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Completed filename collision; nothing overwritten')
    return {'id':completed.id,'file_id':stored.id,'filename':filename,'relative_path':relative,'project_id':completed.project_id}
