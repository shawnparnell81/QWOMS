"""Idempotent, synthetic-only free-tier bootstrap. Never log or rotate existing credentials."""
import os
from datetime import datetime, timezone
from sqlalchemy import select,func,update
from .models import User, ProductFamily, PhysicalPart, PartAlias, AuthSession
from .security import hash_password,authority_lock
from .audit import record
from .deployment import demo_mode,validate_settings


def seed(db):
    if not demo_mode() or os.getenv('QWOMS_SYNTHETIC_DATA_ONLY','').casefold()!='true':
        raise RuntimeError('Synthetic bootstrap is allowed only in explicitly acknowledged demo mode')
    # Rename the old synthetic manager once, preserving account ID, work orders,
    # audit history and all existing demo records. On future restarts, never
    # reset the password the user chose during first sign-in.
    legacy=db.scalar(select(User).where(func.lower(User.username)=='demo.manager'))
    owner=db.scalar(select(User).where(func.lower(User.username)=='demo'))
    if legacy and owner:
        raise RuntimeError('Conflicting demo owner accounts; manual review required')
    if legacy:
        initial=os.getenv('QWOMS_DEMO_INITIAL_PASSWORD','')
        if not 10 <= len(initial) <= 128:
            raise RuntimeError('Set a private 10–128 character temporary demo password in Render')
        legacy.username='demo'
        legacy.password_hash=hash_password(initial,demo_initial=True)
        legacy.must_change_password=True
        legacy.active=True
        db.execute(update(AuthSession).where(AuthSession.user_id==legacy.id, AuthSession.revoked_at.is_(None))
                   .values(revoked_at=datetime.now(timezone.utc)))
        db.flush()
    users=[('demo','Alex Example','Management','QWOMS_DEMO_INITIAL_PASSWORD'),
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
        minimum = 10 if username=='demo' else 16
        if not minimum<=len(password)<=128:
            raise RuntimeError(f'Securely configure {variable} ({minimum}–128 characters); no default password is provided')
        db.add(User(username=username,display_name=name,role=role,site='Fictional Site',
                    password_hash=hash_password(password,demo_initial=(username=='demo')),
                    must_change_password=(username=='demo')))
    db.flush()
    state=authority_lock(db)
    if not state.initialized:
        owner=db.scalar(select(User).where(User.username=='demo'))
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
