"""Work-related controlled originals and explicit Engineering approvals; no general QMS."""
import hashlib
from datetime import datetime,timezone
from io import BytesIO
from zipfile import ZipFile,BadZipFile
from fastapi import HTTPException
from sqlalchemy import select,func
from .models import ControlledDocument,ControlledRevision,RevisionEvent,PhysicalPart,StoredFile
from .audit import record

KINDS=('Drawing','Work instruction','Supporting document','Form template')


def validate_xlsx(content):
    try:
        with ZipFile(BytesIO(content)) as archive:
            info=archive.infolist()
            if len(info)>10000 or sum(i.file_size for i in info)>100*1024*1024:
                raise ValueError('Workbook expands beyond the allowed size')
            names=set(archive.namelist())
            if not {'[Content_Types].xml','xl/workbook.xml'}.issubset(names):
                raise ValueError('Not an XLSX workbook')
            if any('vbaproject' in n.casefold() or n.startswith('/') or '..' in n.split('/') for n in names):
                raise ValueError('Macros or unsafe workbook paths are not accepted')
            if archive.testzip() is not None:
                raise ValueError('Workbook checksum validation failed')
    except (BadZipFile,ValueError) as exc:
        raise HTTPException(422,str(exc))


def file_bytes(db,file):
    from . import main
    from .storage import original_store
    try:
        content=original_store(main.STORAGE_ROOT,db).read('files/'+file.relative_path)
    except FileNotFoundError:
        raise HTTPException(409,'Original file is missing from storage')
    if hashlib.sha256(content).hexdigest()!=file.sha256:
        raise HTTPException(409,'Original file integrity check failed')
    return content


def create_revision(db,document,file,label,user,summary,blank=False):
    if db.scalar(select(ControlledRevision.id).where(ControlledRevision.file_id==file.id)):
        raise HTTPException(409,'This original already belongs to a controlled revision')
    if db.scalar(select(ControlledRevision.id).where(ControlledRevision.document_id==document.id,ControlledRevision.revision==label)):
        raise HTTPException(409,'Revision label already exists; original revisions cannot be replaced')
    expected_kind='drawing' if document.kind=='Drawing' else 'form-template' if document.kind=='Form template' else 'document'
    if file.kind!=expected_kind:
        raise HTTPException(422,'Original file category does not match the controlled document kind')
    if document.kind=='Drawing':
        known=db.scalar(select(PhysicalPart.id).where(func.lower(PhysicalPart.drawing_number)==document.identity_key,
                                                     PhysicalPart.drawing_revision==label))
        if not known:
            raise HTTPException(422,'Drawing number and revision must first be recorded in the authoritative Excel Part Master')
        if file.drawing_number and (file.drawing_number.casefold()!=document.identity_key or file.drawing_revision!=label):
            raise HTTPException(409,'Original drawing mapping conflicts with the proposed revision')
        file.drawing_number=document.number;file.drawing_revision=label
    content=file_bytes(db,file)
    if document.kind=='Form template':
        if not file.original_name.lower().endswith('.xlsx') or not blank:
            raise HTTPException(422,'A blank-master confirmation and original .xlsx workbook are required')
        validate_xlsx(content)
    revision=ControlledRevision(document_id=document.id,file_id=file.id,revision=label,sha256=file.sha256,
                                created_by=user.id,change_summary=summary,blank_master_confirmed=blank)
    db.add(revision);db.flush()
    db.add(RevisionEvent(revision_id=revision.id,actor_id=user.id,previous_status='',status='Draft',reason=summary))
    record(db,user,'revision.created','controlled_revision',revision.id,{'document_id':document.id,'revision':label,'file_id':file.id,'sha256':file.sha256})
    return revision


def mapped_draft(db,file,number,label,user):
    existing=db.scalar(select(ControlledRevision).where(ControlledRevision.file_id==file.id))
    if existing:
        doc=db.get(ControlledDocument,existing.document_id)
        if doc.identity_key!=number.casefold() or existing.revision!=label:
            raise HTTPException(409,'Controlled original identity is immutable')
        return existing
    document=db.scalar(select(ControlledDocument).where(ControlledDocument.kind=='Drawing',ControlledDocument.identity_key==number.casefold()))
    if not document:
        document=ControlledDocument(kind='Drawing',number=number,identity_key=number.casefold(),title=number)
        db.add(document);db.flush()
    return create_revision(db,document,file,label,user,'Initial mapping from authoritative Part Master')


def drawing_reference(db,number,label):
    if not number:return None,None,'No drawing recorded'
    if not label:return None,None,'Missing revision'
    revision=db.scalar(select(ControlledRevision).join(ControlledDocument).where(
        ControlledDocument.kind=='Drawing',ControlledDocument.identity_key==number.casefold(),ControlledRevision.revision==label))
    if not revision:return None,None,'Needs Engineering approval'
    file=db.get(StoredFile,revision.file_id)
    state='Approved' if revision.status=='Approved' else revision.status if revision.status in ('Superseded','Obsolete') else 'Needs Engineering approval'
    return revision,file,state


def event(db,revision,user,status,reason):
    previous=revision.status;revision.status=status
    db.add(RevisionEvent(revision_id=revision.id,actor_id=user.id,previous_status=previous,status=status,reason=reason))
    record(db,user,'revision.'+status.casefold().replace(' ','_'),'controlled_revision',revision.id,{'before':previous,'after':status,'reason':reason})


def transition(db,revision,user,action,reason):
    # All approval changes for one identity serialize on the parent document.
    db.scalar(select(ControlledDocument).where(ControlledDocument.id==revision.document_id).with_for_update())
    db.refresh(revision)
    if action=='submit':
        if user.role not in ('Engineering','Management') or revision.status!='Draft':
            raise HTTPException(409 if user.role in ('Engineering','Management') else 403,'Only a draft can be submitted by Engineering or Management')
        event(db,revision,user,'In Review',reason);return
    if user.role!='Engineering':raise HTTPException(403,'Engineering review and approval required')
    if action in ('review','approve') and revision.created_by==user.id:
        raise HTTPException(403,'An author cannot review or approve their own revision')
    if action=='review' and revision.status=='In Review':
        revision.reviewed_by=user.id;event(db,revision,user,'Reviewed',reason)
    elif action=='approve' and revision.status=='Reviewed':
        for previous in db.scalars(select(ControlledRevision).where(ControlledRevision.document_id==revision.document_id,ControlledRevision.status=='Approved')).all():
            event(db,previous,user,'Superseded','Superseded by approved revision '+revision.revision)
        revision.approved_by=user.id;revision.approved_at=datetime.now(timezone.utc)
        event(db,revision,user,'Approved',reason)
    elif action=='reject' and revision.status in ('In Review','Reviewed'):
        event(db,revision,user,'Rejected',reason)
    elif action=='obsolete' and revision.status=='Approved':
        event(db,revision,user,'Obsolete',reason)
    else:raise HTTPException(409,'Invalid revision status transition')
