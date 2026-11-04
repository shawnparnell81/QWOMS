"""Idempotent, synthetic-only free-tier bootstrap. Never log or rotate existing credentials."""
import os
import base64
from datetime import datetime,timezone
from sqlalchemy import select,func,update
from .models import User, ProductFamily, PhysicalPart, PartAlias,AuthSession
from .audit import record
from .security import hash_password
from .deployment import demo_mode,validate_settings


def initial_demo_password():
    encoded=os.getenv('QWOMS_DEMO_INITIAL_PASSWORD_B64','')
    if encoded:
        try:return base64.b64decode(encoded,validate=True).decode('utf-8')
        except (ValueError,UnicodeDecodeError):raise RuntimeError('Invalid private encoded demo credential')
    return os.getenv('QWOMS_DEMO_INITIAL_PASSWORD','')


def seed(db):
    if not demo_mode() or os.getenv('QWOMS_SYNTHETIC_DATA_ONLY','').casefold()!='true':
        raise RuntimeError('Synthetic bootstrap is allowed only in explicitly acknowledged demo mode')
    initial=initial_demo_password()
    owner_name='demo' if initial else 'demo.manager'
    if initial:
        if not 10<=len(initial)<=128:raise RuntimeError('Set a private 10–128 character temporary demo password')
        legacy=db.scalar(select(User).where(func.lower(User.username)=='demo.manager'))
        owner=db.scalar(select(User).where(func.lower(User.username)=='demo'))
        if legacy and owner:raise RuntimeError('Conflicting demo owner accounts; manual review required')
        if legacy:
            legacy.username='demo';legacy.password_hash=hash_password(initial,demo_initial=True);legacy.must_change_password=True
            db.execute(update(AuthSession).where(AuthSession.user_id==legacy.id,AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
            record(db,legacy,'account.synthetic_initial_transition','user',legacy.id);db.flush()
    users=[(owner_name,'Alex Example','Management','QWOMS_BOOTSTRAP_PASSWORD'),
           ('demo.quality','Sam Sample','Quality','QWOMS_DEMO_QUALITY_PASSWORD'),
           ('demo.engineer','Casey Fiction','Engineering','QWOMS_DEMO_ENGINEERING_PASSWORD'),
           ('demo.production','Jordan Demo','Production','QWOMS_DEMO_PRODUCTION_PASSWORD')]
    for username,name,role,variable in users:
        existing=db.scalar(select(User).where(func.lower(User.username)==username))
        if existing:
            if existing.role!=role or not existing.active:
                raise RuntimeError('Reserved synthetic account conflicts with an existing account; review required')
            continue
        password=initial if initial and username==owner_name else os.getenv(variable,'')
        minimum=10 if initial and username==owner_name else 16
        if len(password)<minimum or len(password)>128:
            raise RuntimeError(f'Securely configure {variable} (16–128 characters); no default password is provided')
        account=User(username=username,display_name=name,role=role,is_admin=(username==owner_name),capabilities=['engineering.approve'] if role=='Engineering' else [],site='Fictional Site',password_hash=hash_password(password,demo_initial=bool(initial and username==owner_name)),must_change_password=bool(initial and username==owner_name))
        db.add(account);db.flush()
        record(db,account,'demo.account_created','user',account.id,{'is_admin':account.is_admin,'capabilities':account.capabilities})
    if not db.scalar(select(PhysicalPart.id).limit(1)):
        family=ProductFamily(name='Fictional Shocks');db.add(family);db.flush()
        part=PhysicalPart(family_id=family.id,description='Fictional demonstration shock',drawing_number=None,drawing_revision=None)
        db.add(part);db.flush()
        db.add_all([PartAlias(part_id=part.id,account="O'Reilly",part_number='DEMO-001'),
                    PartAlias(part_id=part.id,account='NAPA',part_number='DEMO-ALT-001')])
    db.flush()


if __name__=='__main__':
    from .db import SessionLocal,DATABASE_URL,engine
    from .schema import require_current
    validate_settings(DATABASE_URL)
    require_current(engine)
    with SessionLocal() as db:
        seed(db)
        db.commit()
    print('Synthetic demo bootstrap completed; credentials were not printed.')
