"""Audited operational time/material records; forklift records never enter chargebacks."""
from datetime import datetime,timezone,timedelta
from decimal import Decimal,ROUND_HALF_UP
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,ConfigDict,model_validator
from sqlalchemy import select,text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import session
from .models import User,WorkOrder,Project,LaborEntry,Pallet,PalletMovement,ForkliftEntry,ChargeItem
from .security import current_user
from .audit import record

router=APIRouter(prefix='/api/operations')
Activity=Literal['Creation','Inspection','Validation','Test','Repair','Replacement','Rebox','Label','Return','Documentation','Management review','Photos','Weighing']
Disposition=Literal['Pending','Inspection','Repair','Reboxed','Returned','Scrapped']

class Input(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)

class LaborInput(Input):
    activity:Activity
    note:str=Field(default='',max_length=1000)
    started_at:datetime|None=None
    duration_seconds:int|None=Field(default=None,ge=1,le=86400)
    @model_validator(mode='after')
    def interval(self):
        if self.started_at is not None and (self.started_at.tzinfo is None or self.duration_seconds is None):
            raise ValueError('Manual labor requires a timezone and duration')
        if self.duration_seconds is not None and self.started_at is None:raise ValueError('Manual labor requires start time')
        if self.started_at and self.started_at+timedelta(seconds=self.duration_seconds)>datetime.now(timezone.utc):raise ValueError('Labor cannot extend into the future')
        return self

class Correction(Input):
    started_at:datetime
    duration_seconds:int=Field(ge=1,le=86400)
    reason:str=Field(min_length=3,max_length=1000)
    @model_validator(mode='after')
    def interval(self):
        if not self.started_at.tzinfo or self.started_at+timedelta(seconds=self.duration_seconds)>datetime.now(timezone.utc):raise ValueError('Invalid labor interval')
        return self

class Approval(Input):
    approved:bool=True
    rate_cents:int=Field(default=0,ge=0,le=10000000)

class PalletInput(Input):
    identifier:str=Field(min_length=1,max_length=100)
    quantity:int=Field(ge=1,le=100000000)
    original_bin:str=Field(min_length=1,max_length=200)
    condition:str=Field(default='',max_length=500)

class Move(Input):
    location:str=Field(min_length=1,max_length=200)
    disposition:Disposition
    reason:str=Field(min_length=3,max_length=1000)
    expected_location:str=Field(min_length=1,max_length=200)

class ForkliftInput(Input):
    duration_seconds:int=Field(ge=1,le=86400)
    estimated:bool
    note:str=Field(min_length=3,max_length=1000)

class CostInput(Input):
    category:Literal['Replacement part','Expense']
    description:str=Field(min_length=3,max_length=1000)
    quantity:int=Field(ge=1,le=1000000)
    unit_cents:int=Field(ge=0,le=100000000)


def lock_employee(db,user):
    if db.bind.dialect.name=='sqlite':db.execute(text('UPDATE users SET id=id WHERE 1=0'))
    db.scalar(select(User).where(User.id==user.id).with_for_update())


def management(user):
    if user.role!='Management':raise HTTPException(403,'Management department required')


def order_access(db,order_id,user,write=False):
    order=db.get(WorkOrder,order_id)
    if not order:raise HTTPException(404,'Work order not found')
    if order.archived_at is not None:
        if write:raise HTTPException(409,'Archived work orders cannot be modified')
        if not user.is_admin:raise HTTPException(404,'Work order not found')
    if user.role=='Production' and order.assigned_to!=user.id:raise HTTPException(403,'Only assigned Production employees may access operations')
    if write and order.status in ('Completed','Closed'):raise HTTPException(409,'Work order is closed')
    return order


def row_json(row):
    return {c.name:getattr(row,c.name) for c in row.__table__.columns}


@router.get('/work-orders/{order_id}')
def overview(order_id:int,db:Session=Depends(session),user:User=Depends(current_user)):
    order_access(db,order_id,user)
    labor=db.scalars(select(LaborEntry).where(LaborEntry.work_order_id==order_id).order_by(LaborEntry.id)).all()
    pallets=db.scalars(select(Pallet).where(Pallet.work_order_id==order_id)).all()
    finished=[e for e in labor if e.stopped_at]
    span=int((max(e.stopped_at for e in finished)-min(e.started_at for e in finished)).total_seconds()) if finished else 0
    return {'recorded_span_seconds':span,'labor':[row_json(e) for e in labor],'labor_seconds':sum(e.duration_seconds or 0 for e in labor),
            'pallets':[{**row_json(p),'movements':[row_json(m) for m in db.scalars(select(PalletMovement).where(PalletMovement.pallet_id==p.id).order_by(PalletMovement.id))]} for p in pallets],
            'costs':[row_json(e) for e in db.scalars(select(ChargeItem).where(ChargeItem.work_order_id==order_id))],
            'forklift':[row_json(e) for e in db.scalars(select(ForkliftEntry).where(ForkliftEntry.work_order_id==order_id))] if user.role=='Management' else []}


@router.post('/work-orders/{order_id}/labor',status_code=201)
def labor(order_id:int,body:LaborInput,db:Session=Depends(session),user:User=Depends(current_user)):
    lock_employee(db,user);order_access(db,order_id,user,True)
    start=body.started_at or datetime.now(timezone.utc)
    stop=start+timedelta(seconds=body.duration_seconds) if body.duration_seconds else None
    # One active timer per employee, and no overlapping manual intervals.
    existing=db.scalars(select(LaborEntry).where(LaborEntry.employee_id==user.id)).all()
    for e in existing:
        previous_start=e.started_at.replace(tzinfo=timezone.utc) if not e.started_at.tzinfo else e.started_at
        previous_stop=e.stopped_at.replace(tzinfo=timezone.utc) if e.stopped_at and not e.stopped_at.tzinfo else e.stopped_at
        if (stop is None or previous_start<stop) and (previous_stop is None or start<previous_stop):raise HTTPException(409,'Employee labor intervals overlap or timer already active')
    entry=LaborEntry(work_order_id=order_id,employee_id=user.id,activity=body.activity,started_at=start,stopped_at=stop,duration_seconds=body.duration_seconds,note=body.note,department_snapshot=user.role)
    db.add(entry);db.flush();record(db,user,'labor.created','labor',entry.id,{'seconds':entry.duration_seconds,'activity':entry.activity});db.commit();return row_json(entry)


@router.post('/labor/{entry_id}/stop')
def stop(entry_id:int,db:Session=Depends(session),user:User=Depends(current_user)):
    lock_employee(db,user)
    entry=db.scalar(select(LaborEntry).where(LaborEntry.id==entry_id).with_for_update())
    if not entry:raise HTTPException(404,'Labor not found')
    if entry.employee_id!=user.id:raise HTTPException(403,'Only the employee can stop their timer')
    if entry.stopped_at:raise HTTPException(409,'Timer already stopped')
    entry.stopped_at=datetime.now(timezone.utc)
    start=entry.started_at.replace(tzinfo=timezone.utc) if not entry.started_at.tzinfo else entry.started_at
    entry.duration_seconds=max(1,int((entry.stopped_at-start).total_seconds()))
    record(db,user,'labor.stopped','labor',entry.id,{'seconds':entry.duration_seconds});db.commit();return row_json(entry)


@router.patch('/labor/{entry_id}')
def correct(entry_id:int,body:Correction,db:Session=Depends(session),user:User=Depends(current_user)):
    management(user)
    # Lock all employees in stable order before interval correction/creation can race.
    if db.bind.dialect.name=='sqlite':db.execute(text('UPDATE users SET id=id WHERE 1=0'))
    db.scalars(select(User).order_by(User.id).with_for_update()).all()
    entry=db.scalar(select(LaborEntry).where(LaborEntry.id==entry_id).with_for_update())
    if not entry:raise HTTPException(404,'Labor not found')
    if not entry.stopped_at:raise HTTPException(409,'Stop the timer before correction')
    end=body.started_at+timedelta(seconds=body.duration_seconds)
    for other in db.scalars(select(LaborEntry).where(LaborEntry.employee_id==entry.employee_id,LaborEntry.id!=entry.id)):
        begin=other.started_at.replace(tzinfo=timezone.utc) if not other.started_at.tzinfo else other.started_at
        finish=other.stopped_at.replace(tzinfo=timezone.utc) if other.stopped_at and not other.stopped_at.tzinfo else other.stopped_at
        if begin<end and (finish is None or body.started_at<finish):raise HTTPException(409,'Corrected interval overlaps employee labor')
    before={'started_at':entry.started_at.isoformat(),'seconds':entry.duration_seconds,'approved_by':entry.approved_by}
    entry.started_at=body.started_at;entry.stopped_at=end;entry.duration_seconds=body.duration_seconds;entry.approved_by=None;entry.rate_cents=0
    record(db,user,'labor.corrected','labor',entry.id,{'before':before,'after':{'started_at':body.started_at.isoformat(),'seconds':body.duration_seconds},'reason':body.reason});db.commit();return row_json(entry)


@router.post('/labor/{entry_id}/approval')
def approve_labor(entry_id:int,body:Approval,db:Session=Depends(session),user:User=Depends(current_user)):
    management(user)
    entry=db.scalar(select(LaborEntry).where(LaborEntry.id==entry_id).with_for_update())
    if not entry:raise HTTPException(404,'Labor not found')
    if not entry.stopped_at:raise HTTPException(409,'Running timers cannot be approved')
    entry.approved_by=user.id if body.approved else None;entry.rate_cents=body.rate_cents if body.approved else 0
    record(db,user,'labor.approval_changed','labor',entry.id,body.model_dump());db.commit();return row_json(entry)


@router.post('/work-orders/{order_id}/pallets',status_code=201)
def pallet(order_id:int,body:PalletInput,db:Session=Depends(session),user:User=Depends(current_user)):
    order_access(db,order_id,user,True)
    p=Pallet(work_order_id=order_id,location=body.original_bin,**body.model_dump());db.add(p)
    try:db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'Pallet ID already exists')
    db.add(PalletMovement(pallet_id=p.id,actor_id=user.id,previous_location='',location=p.location,disposition='Pending',reason='Initial pallet registration'))
    record(db,user,'pallet.created','pallet',p.id,body.model_dump());db.commit();return row_json(p)


@router.post('/pallets/{pallet_id}/movements')
def move(pallet_id:int,body:Move,db:Session=Depends(session),user:User=Depends(current_user)):
    if db.bind.dialect.name=='sqlite':db.execute(text('UPDATE users SET id=id WHERE 1=0'))
    p=db.scalar(select(Pallet).where(Pallet.id==pallet_id).with_for_update())
    if not p:raise HTTPException(404,'Pallet not found')
    order_access(db,p.work_order_id,user,True)
    if p.location!=body.expected_location:raise HTTPException(409,'Pallet moved; refresh before recording movement')
    previous=p.location;p.location=body.location;p.disposition=body.disposition
    db.add(PalletMovement(pallet_id=p.id,actor_id=user.id,previous_location=previous,location=p.location,disposition=p.disposition,reason=body.reason))
    record(db,user,'pallet.moved','pallet',p.id,{'before':previous,**body.model_dump()});db.commit();return row_json(p)


@router.post('/work-orders/{order_id}/forklift',status_code=201)
def forklift(order_id:int,body:ForkliftInput,db:Session=Depends(session),user:User=Depends(current_user)):
    management(user);order_access(db,order_id,user,True)
    entry=ForkliftEntry(work_order_id=order_id,recorded_by=user.id,**body.model_dump());db.add(entry);db.flush()
    record(db,user,'forklift.recorded','forklift',entry.id,body.model_dump());db.commit();return row_json(entry)


@router.post('/work-orders/{order_id}/costs',status_code=201)
def cost(order_id:int,body:CostInput,db:Session=Depends(session),user:User=Depends(current_user)):
    management(user);order_access(db,order_id,user,True)
    # Forklift activities have their own internal-only ledger; prevent relabeling in recoverables.
    if 'forklift' in body.description.casefold():raise HTTPException(422,'Forklift records belong in the internal ledger')
    entry=ChargeItem(work_order_id=order_id,created_by=user.id,**body.model_dump());db.add(entry);db.flush();record(db,user,'cost.created','cost',entry.id,body.model_dump());db.commit();return row_json(entry)


@router.post('/costs/{item_id}/approval')
def approve_cost(item_id:int,body:Approval,db:Session=Depends(session),user:User=Depends(current_user)):
    management(user)
    item=db.scalar(select(ChargeItem).where(ChargeItem.id==item_id).with_for_update())
    if not item:raise HTTPException(404,'Cost not found')
    item.approved_by=user.id if body.approved else None
    record(db,user,'cost.approval_changed','cost',item.id,{'approved':body.approved});db.commit();return row_json(item)


@router.get('/projects/{project_id}/chargeback')
def chargeback(project_id:int,db:Session=Depends(session),user:User=Depends(current_user)):
    management(user)
    if not db.get(Project,project_id):raise HTTPException(404,'Project not found')
    orders=db.scalars(select(WorkOrder).where(WorkOrder.project_id==project_id, WorkOrder.archived_at.is_(None))).all();ids=[o.id for o in orders]
    entries=db.scalars(select(LaborEntry).where(LaborEntry.work_order_id.in_(ids),LaborEntry.approved_by.is_not(None),LaborEntry.stopped_at.is_not(None))).all()
    costs=db.scalars(select(ChargeItem).where(ChargeItem.work_order_id.in_(ids),ChargeItem.approved_by.is_not(None))).all()
    lines=[{'kind':'labor','id':e.id,'work_order_id':e.work_order_id,'employee_id':e.employee_id,'department':e.department_snapshot,'activity':e.activity,'seconds':e.duration_seconds,'rate_cents':e.rate_cents,'amount_cents':int((Decimal(e.duration_seconds)*Decimal(e.rate_cents)/3600).quantize(Decimal('1'),rounding=ROUND_HALF_UP))} for e in entries]
    lines += [{'kind':e.category,'id':e.id,'work_order_id':e.work_order_id,'description':e.description,'quantity':e.quantity,'unit_cents':e.unit_cents,'amount_cents':e.quantity*e.unit_cents} for e in costs]
    # Intentionally no query/join/line for the internal forklift ledger, even at zero cost.
    return {'project_id':project_id,'work_orders':[{'id':o.id,'number':o.number} for o in orders],'labor_seconds':sum(e.duration_seconds for e in entries),'total_cents':sum(e['amount_cents'] for e in lines),'lines':lines}
