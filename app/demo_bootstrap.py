"""Idempotent, synthetic-only free-tier bootstrap. Never log or rotate existing credentials."""
import os
from sqlalchemy import select,func
from .models import User, ProductFamily, PhysicalPart, PartAlias
from .security import hash_password,authority_lock
from .audit import record
from .deployment import demo_mode,validate_settings


def seed(db):
    if not demo_mode() or os.getenv('QWOMS_SYNTHETIC_DATA_ONLY','').casefold()!='true':
        raise RuntimeError('Synthetic bootstrap is allowed only in explicitly acknowledged demo mode')
    users=[('demo.manager','Alex Example','Management','QWOMS_BOOTSTRAP_PASSWORD'),
           ('demo.quality','Sam Sample','Quality','QWOMS_DEMO_QUALITY_PASSWORD'),
           ('demo.engineer','Casey Fiction','Engineering','QWOMS_DEMO_ENGINEERING_PASSWORD'),
           ('demo.production','Jordan Demo','Production','QWOMS_DEMO_PRODUCTION_PASSWORD')]
    for username,name,role,variable in users:
        existing=db.scalar(select(User).where(func.lower(User.username)==username))
        if existing:
            if existing.role!=role or not existing.active:
                raise RuntimeError('Reserved synthetic account conflicts with an existing account; review required')
            continue
        password=os.getenv(variable,'')
        if len(password)<16 or len(password)>128:
            raise RuntimeError(f'Securely configure {variable} (16–128 characters); no default password is provided')
        db.add(User(username=username,display_name=name,role=role,site='Fictional Site',password_hash=hash_password(password)))
    db.flush()
    state=authority_lock(db)
    if not state.initialized:
        owner=db.scalar(select(User).where(User.username=='demo.manager'))
        owner.is_admin=True
        engineer=db.scalar(select(User).where(User.username=='demo.engineer'))
        engineer.permissions=['revision.approve']
        state.initialized=True
        record(db,owner,'administrator.synthetic_initial_claim','user',owner.id)
        record(db,owner,'permission.granted','user',engineer.id,{'capability':'revision.approve','synthetic_fixture':True})
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
