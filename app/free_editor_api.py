"""Free workbook form view, live calculation preview and optimistic measurement saves."""
import hashlib
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy.orm import Session
from .db import session
from .models import User,StoredFile
from .security import current_user
from .editor_api import cookie_draft,active_lock,now
from .workspace_api import access
from .audit import record
from . import free_workbook as workbook
router=APIRouter(prefix='/api/workbooks')

class CellEdit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    sheet:str=Field(min_length=1,max_length=31)
    address:str=Field(pattern=r'^[A-Za-z]{1,3}[1-9][0-9]{0,6}$')
    value:str|None=Field(default=None,max_length=32767)

class Edits(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=1)
    sheet:str|None=Field(default=None,max_length=31)
    edits:list[CellEdit]=Field(default_factory=list,max_length=5000)


def guarded(db,draft_id,user,write=False):
    draft,order=cookie_draft(db,draft_id,user,write=write,locked=write)
    access(db,order.id,user,write=write)
    if write and active_lock(draft):raise HTTPException(409,'This draft is open in another office engine; reopen a separate working copy')
    return draft,order


def render(draft,order,sheet=None,edits=None):
    try:
        book=workbook.read(draft.content)
        if edits:workbook.apply_values(book,edits)
        calc=workbook.Calculator(book).calculate()
        data=workbook.model(book,calc,sheet)
    except workbook.WorkbookIssue as exc:raise HTTPException(422,str(exc))
    data.update({'draft_id':draft.id,'version':draft.version,'order_id':order.id,'project_id':order.project_id,'read_only':order.status in ('Completed','Closed')})
    return data,book,calc


@router.get('/{draft_id}/form')
def form(draft_id:str,sheet:str|None=None,db:Session=Depends(session),user:User=Depends(current_user)):
    draft,order=guarded(db,draft_id,user)
    data,_,_=render(draft,order,sheet)
    data['filename']=db.get(StoredFile,draft.source_file_id).original_name
    data['read_only']=data['read_only'] or not(user.is_admin or user.role=='Management' or user.id in (order.assigned_to,order.created_by))
    return data


@router.post('/{draft_id}/preview')
def preview(draft_id:str,body:Edits,db:Session=Depends(session),user:User=Depends(current_user)):
    draft,order=guarded(db,draft_id,user,write=True)
    if draft.version!=body.expected_version:raise HTTPException(409,'Workbook draft changed; reopen before applying measurements')
    data,_,_=render(draft,order,body.sheet,[e.model_dump() for e in body.edits])
    return data


@router.patch('/{draft_id}/cells')
def cells(draft_id:str,body:Edits,db:Session=Depends(session),user:User=Depends(current_user)):
    draft,order=guarded(db,draft_id,user,write=True)
    if draft.version!=body.expected_version:raise HTTPException(409,'Workbook draft changed; measurements were not overwritten')
    edits=[e.model_dump() for e in body.edits]
    data,book,calc=render(draft,order,body.sheet,edits)
    try:updated=workbook.patch_package(draft.content,book,edits,calc)
    except workbook.WorkbookIssue as exc:raise HTTPException(422,str(exc))
    evidence=workbook.package_evidence(draft.content,updated)
    draft.content=updated;draft.version+=1;draft.updated_at=now()
    record(db,user,'workbook.measurements_saved','workbook_draft',draft.id,{'version':draft.version,'cells':[{'sheet':e['sheet'],'address':e['address']} for e in edits],
        'sha256':hashlib.sha256(updated).hexdigest(),'package':evidence,'engine':'free-workbook-forms'})
    db.commit();data['version']=draft.version;data['package']=evidence
    return data
