"""Resolve scope-specific work requirements and freeze approved originals at creation."""
from decimal import Decimal,InvalidOperation
from fastapi import HTTPException
from sqlalchemy import select
from .models import WorkflowRule,ControlledDocument,ControlledRevision,StoredFile,WorkOrderAttachment,FormFilingRule
from .controlled import file_bytes

DEFAULT_FOLDERS={'Validation / FAI':'Validation','Inspection':'Inspection','Test':'Test','Repair':'Repair','Parts Weighing':'Weighing','Photos':'Photos'}


def resolve(db,part,order_type,subtype):
    rules=db.scalars(select(WorkflowRule).where(WorkflowRule.active.is_(True),WorkflowRule.order_type==order_type,
                        WorkflowRule.subtype.in_(['',subtype]),
                        (WorkflowRule.family_id.is_(None))|(WorkflowRule.family_id==part.family_id),
                        (WorkflowRule.part_id.is_(None))|(WorkflowRule.part_id==part.id))).all()
    candidate_ids={i for r in rules for i in r.document_ids}
    retired_ids=set(db.scalars(select(ControlledDocument.id).where(ControlledDocument.id.in_(candidate_ids),ControlledDocument.retired.is_(True))))
    rules=[r for r in rules if r.fields or r.instructions.strip() or any(i not in retired_ids for i in r.document_ids)]
    def score(rule):return (8 if rule.part_id else 0)+(4 if rule.family_id else 0)+(2 if rule.subtype else 0)
    rules.sort(key=lambda r:(score(r),r.id))
    fields={};scores={};instructions=[];documents=set()
    for rule in rules:
        for definition in rule.fields:
            key=definition['key']
            if key in fields and scores[key]==score(rule) and fields[key]!=definition:
                raise HTTPException(409,'Conflicting equally specific field rules; Engineering must reconcile '+key)
            fields[key]=definition;scores[key]=score(rule)
        if rule.instructions:instructions.append({'rule_id':rule.id,'name':rule.name,'text':rule.instructions})
        documents.update(rule.document_ids)
    active={d.id:d for d in db.scalars(select(ControlledDocument).where(ControlledDocument.id.in_(documents),ControlledDocument.retired.is_(False)))}
    documents={i for i in documents if i not in retired_ids}
    form_candidates=[]
    for rule in rules:
        forms={i for i in rule.document_ids if i in active and active[i].kind=='Form template'}
        if forms:form_candidates.append((score(rule),forms))
    if form_candidates:
        best=max(s for s,forms in form_candidates);sets=[forms for s,forms in form_candidates if s==best]
        if any(forms!=sets[0] for forms in sets):raise HTTPException(409,'Conflicting equally specific form-template mappings; reconcile the matching rules')
        documents={i for i in documents if i not in active or active[i].kind!='Form template'}|sets[0]
    return {'rule_ids':[r.id for r in rules],'fields':list(fields.values()),'instructions':instructions,'document_ids':sorted(documents)}


def validate_values(requirements,values,phase='creation'):
    definitions={f['key']:f for f in requirements.get('fields',[])}
    extras=set(values)-set(definitions)
    if extras:raise HTTPException(422,'Fields do not belong to this part workflow: '+', '.join(sorted(extras)))
    rank={'creation':0,'execution':1,'completion':2}
    for key,field in definitions.items():
        value=values.get(key,'').strip()
        if field['required'] and rank[field['required_at']]<=rank[phase] and not value:
            raise HTTPException(422,'Required for this part: '+field['label'])
        if not value:continue
        if len(value)>4000:raise HTTPException(422,'Field value too long: '+field['label'])
        if field['type'] in ('number','integer'):
            try:
                number=Decimal(value)
                if not number.is_finite():raise InvalidOperation
            except InvalidOperation:raise HTTPException(422,'Enter a finite number for '+field['label'])
            if field['type']=='integer' and number!=number.to_integral_value():
                raise HTTPException(422,'Enter a whole number for '+field['label'])
            if field.get('minimum') is not None and number<Decimal(str(field['minimum'])):
                raise HTTPException(422,'Value below minimum for '+field['label'])
            if field.get('maximum') is not None and number>Decimal(str(field['maximum'])):
                raise HTTPException(422,'Value above maximum for '+field['label'])
        if field['type']=='choice' and value not in field['choices']:
            raise HTTPException(422,'Choose an approved option for '+field['label'])


def folder_for(db,order_type,subtype):
    for scope in [subtype,'']:
        rule=db.scalar(select(FormFilingRule).where(FormFilingRule.order_type==order_type,FormFilingRule.subtype==scope))
        if rule:return rule.folder
    return 'Development' if subtype=='Development Validation' else DEFAULT_FOLDERS[order_type]


def approved_documents(db,requirements):
    result=[]
    for document_id in requirements.get('document_ids',[]):
        doc=db.scalar(select(ControlledDocument).where(ControlledDocument.id==document_id).with_for_update().execution_options(populate_existing=True))
        if doc and doc.retired:raise HTTPException(409,'A selected form template was retired; refresh the work requirements')
        revision=db.scalar(select(ControlledRevision).where(ControlledRevision.document_id==document_id,ControlledRevision.status=='Approved'))
        if not doc or not revision:
            raise HTTPException(409,'A mandatory work instruction/form has no approved current revision')
        file=db.get(StoredFile,revision.file_id)
        if revision.sha256!=file.sha256:raise HTTPException(409,'Controlled original checksum metadata mismatch')
        file_bytes(db,file)
        result.append((doc,revision,file))
    return result


def attach(db,order,part,documents):
    folder=folder_for(db,order.order_type,order.subtype)
    for doc,revision,file in documents:
        existing=db.scalar(select(WorkOrderAttachment.id).where(WorkOrderAttachment.work_order_id==order.id,WorkOrderAttachment.part_id==part.id,WorkOrderAttachment.revision_id==revision.id))
        if existing:continue
        db.add(WorkOrderAttachment(work_order_id=order.id,part_id=part.id,revision_id=revision.id,file_id=file.id,
                                  kind=doc.kind,number=doc.number,revision=revision.revision,sha256=revision.sha256,
                                  filename=file.original_name,category_folder=folder))
