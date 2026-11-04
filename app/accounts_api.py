"""Administrator-controlled accounts, password lifecycle and immediate session revocation."""
from datetime import datetime,timezone
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select,update
from sqlalchemy.orm import Session
from .db import session
from .models import User,AuthSession
from .security import current_user,require_admin,verify_password,hash_password,CAPABILITIES
from .audit import record

router=APIRouter(prefix='/api')


class AccountChange(BaseModel):
    current_password:str=Field(min_length=1,max_length=128)
    display_name:str|None=Field(default=None,min_length=2,max_length=120)
    site:str|None=Field(default=None,max_length=100)
    role:Literal['Quality','Engineering','Production','Management']|None=None
    active:bool|None=None
    is_admin:bool|None=None
    capabilities:list[str]|None=None
    @field_validator("capabilities")
    @classmethod
    def valid_capabilities(cls,value):
        if value is not None and (len(value)!=len(set(value)) or any(v not in CAPABILITIES for v in value)):
            raise ValueError("Unknown or duplicate capability")
        return value
    @field_validator('display_name','site',mode='before')
    @classmethod
    def trim(cls,v):return v.strip() if isinstance(v,str) else v


class PasswordChange(BaseModel):
    current_password:str=Field(min_length=1,max_length=128)
    new_password:str=Field(min_length=12,max_length=128)


def revoke(db,user_id):
    db.execute(update(AuthSession).where(AuthSession.user_id==user_id,AuthSession.revoked_at.is_(None))
                .values(revoked_at=datetime.now(timezone.utc)))


def step_up(db,manager,password):
    db.refresh(manager)
    if not manager.is_admin or not manager.active:raise HTTPException(403,'Active Administrator access required')
    if not verify_password(password,manager.password_hash):raise HTTPException(403,'Current password verification failed')


@router.get('/admin/accounts')
def accounts(db:Session=Depends(session),manager:User=Depends(require_admin)):
    return [{'id':u.id,'username':u.username,'display_name':u.display_name,'role':u.role,'site':u.site,'active':u.active,'is_admin':u.is_admin,'capabilities':u.capabilities or []}
            for u in db.scalars(select(User).order_by(User.display_name)).all()]


@router.patch('/admin/accounts/{user_id}')
def change_account(user_id:int,body:AccountChange,db:Session=Depends(session),manager:User=Depends(require_admin)):
    if db.bind.dialect.name=="sqlite":
        from sqlalchemy import text
        db.execute(text("UPDATE users SET id=id WHERE 1=0"))
    db.scalars(select(User).where(User.is_admin.is_(True),User.active.is_(True)).order_by(User.id).with_for_update()).all()
    step_up(db,manager,body.current_password)
    target=db.scalar(select(User).where(User.id==user_id).with_for_update().execution_options(populate_existing=True))
    if not target:raise HTTPException(404,'Account not found')
    if target.is_admin and target.active and (body.is_admin is False or body.active is False):
        if len(db.scalars(select(User).where(User.is_admin.is_(True),User.active.is_(True))).all()) <= 1:
            raise HTTPException(409,'Cannot remove the last active Administrator')
    changes={}
    for key in ['display_name','site','role','active','is_admin','capabilities']:
        value=getattr(body,key)
        if value is not None and value!=getattr(target,key):
            changes[key]={'before':getattr(target,key),'after':value};setattr(target,key,value)
    if changes:
        if {'role','active','is_admin','capabilities'} & changes.keys():revoke(db,target.id)
        if 'capabilities' in changes:
            before=set(changes['capabilities']['before'] or []);after=set(changes['capabilities']['after'])
            for capability in sorted(before ^ after):
                record(db,manager,'permission.granted' if capability in after else 'permission.revoked','user',target.id,{'capability':capability})
        record(db,manager,'account.updated','user',target.id,changes)
    db.commit();return {'ok':True,'session_revoked':bool({'role','active','is_admin','capabilities'}&changes.keys())}


@router.post('/admin/accounts/{user_id}/reset-password')
def reset_password(user_id:int,body:PasswordChange,db:Session=Depends(session),manager:User=Depends(require_admin)):
    if db.bind.dialect.name=="sqlite":
        from sqlalchemy import text
        db.execute(text("UPDATE users SET id=id WHERE 1=0"))
    db.scalars(select(User).where(User.is_admin.is_(True),User.active.is_(True)).order_by(User.id).with_for_update()).all()
    step_up(db,manager,body.current_password)
    target=db.scalar(select(User).where(User.id==user_id).with_for_update().execution_options(populate_existing=True))
    if not target:raise HTTPException(404,'Account not found')
    if verify_password(body.new_password,target.password_hash):raise HTTPException(422,'Choose a different password')
    target.password_hash=hash_password(body.new_password);target.must_change_password=False;revoke(db,target.id)
    record(db,manager,'account.password_reset','user',target.id)
    db.commit();return {'ok':True,'reauthenticate':True}


@router.post('/me/change-password')
def change_password(body:PasswordChange,response:Response,db:Session=Depends(session),user:User=Depends(current_user)):
    target=db.scalar(select(User).where(User.id==user.id).with_for_update().execution_options(populate_existing=True))
    if not verify_password(body.current_password,target.password_hash):raise HTTPException(403,'Current password verification failed')
    if verify_password(body.new_password,target.password_hash):raise HTTPException(422,'Choose a different password')
    target.password_hash=hash_password(body.new_password);target.must_change_password=False;revoke(db,target.id)
    record(db,target,'account.password_changed','user',target.id);db.commit()
    response.delete_cookie('qwoms_token',path='/');response.delete_cookie('qwoms_csrf',path='/')
    return {'ok':True,'reauthenticate':True}


class InitialPasswordChange(BaseModel):
    new_password:str=Field(min_length=12,max_length=128)

@router.post('/me/set-initial-password')
def initial_password(body:InitialPasswordChange,response:Response,db:Session=Depends(session),user:User=Depends(current_user)):
    target=db.scalar(select(User).where(User.id==user.id).with_for_update().execution_options(populate_existing=True))
    if not target.must_change_password:raise HTTPException(409,'Initial password setup is not required')
    if verify_password(body.new_password,target.password_hash):raise HTTPException(422,'Choose a different password')
    target.password_hash=hash_password(body.new_password);target.must_change_password=False
    revoke(db,target.id);record(db,target,'account.initial_password_set','user',target.id);db.commit()
    response.delete_cookie('qwoms_token',path='/');response.delete_cookie('qwoms_csrf',path='/')
    return {'ok':True,'reauthenticate':True}


@router.get('/admin/migration-history')
def migration_history(db:Session=Depends(session),manager:User=Depends(require_admin)):
    from .models import SchemaReconciliation
    return [{'id':r.id,'source_revisions':r.source_revisions,'target_revision':r.target_revision,'created_at':r.created_at,'report':r.report}
        for r in db.scalars(select(SchemaReconciliation).order_by(SchemaReconciliation.created_at.desc()))]
