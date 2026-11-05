"""Rehearse both historical layouts on disposable synthetic SQLite/PostgreSQL.

Legacy fixture DDL is frozen from 55c7b3e/remote0009; no live DB is read/written.
"""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.db import Base
from app.schema import configuration,upgrade,require_current,inspect_history
from app.models import User,SchemaReconciliation
from tests.test_foundation import client,logged_in
from tests.test_workspace import setup_parts,template,new_order
from tests.test_controlled_revisions import approve
from tests.synthetic_workspace import pdf


def downgrade(engine,revision):
    config=configuration()
    with engine.begin() as c:config.attributes['connection']=c;command.downgrade(config,revision)


def install_legacy(engine,revision):
    """Create only in this disposable fixture after verified baseline0007."""
    with engine.begin() as c:
        c.exec_driver_sql('ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE')
        c.exec_driver_sql("ALTER TABLE users ADD COLUMN permissions JSON NOT NULL DEFAULT '[]'")
        c.exec_driver_sql('CREATE TABLE system_authority (id INTEGER PRIMARY KEY, initialized BOOLEAN NOT NULL)')
        c.execute(sa.text('INSERT INTO system_authority (id,initialized) VALUES (1,:ready)'),{'ready':True})
        if revision=='0009':c.exec_driver_sql('ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT FALSE')
        c.execute(sa.text('UPDATE alembic_version SET version_num=:revision'),{'revision':revision})


def snapshot(engine):
    meta=sa.MetaData();meta.reflect(bind=engine)
    with engine.connect() as c:
        return {name:[dict(r) for r in c.execute(sa.select(table).order_by(*table.primary_key.columns)).mappings()] for name,table in meta.tables.items()}


def prepare(web,Session,revision):
    parts=setup_parts(web);form=template(web,'RECONCILE-FORM','shock',parts['S300']['id']);approve(web,form['revision_id'])
    order=new_order(web,parts['S300'],assigned_to=1).json()['id']
    attachment=web.get(f'/api/work-orders/{order}/attachments').json()[0]
    opened=web.post(f"/api/work-orders/{order}/attachments/{attachment['id']}/editor",json={}).json()['id']
    assert web.patch('/api/workbooks/'+opened+'/cells',json={'expected_version':1,'edits':[{'sheet':'Shock Validation','address':'B5','value':'12'}]}).status_code==200
    assert web.post('/api/workbooks/'+opened+'/completed',json={'filename':'Employee recorded historical form.xlsx','expected_version':2}).status_code==201
    assert web.post('/api/files/import-folder',data={'kind':'document','paths':'Synthetic legacy originals/Equipment original.pdf'},files={'files':('Equipment original.pdf',pdf('LEGACY ORIGINAL'))}).status_code==200
    extras=[]
    for role in ['Quality','Production','Management']:
        r=web.post('/api/admin/users',json={'username':'synthetic-'+role.lower(),'display_name':'Synthetic '+role,'role':role,'password':'Synthetic-migration-password-123!','site':'Synthetic Site'})
        assert r.status_code==201;extras.append(r.json()['id'])
    engine=Session.kw['bind'];downgrade(engine,'0007');install_legacy(engine,revision)
    with engine.begin() as c:
        users=sa.Table('users',sa.MetaData(),autoload_with=c)
        c.execute(users.update().where(users.c.id==1).values(is_admin=True,permissions=[]))
        c.execute(users.update().where(users.c.id==2).values(permissions=['revision.approve']))
        c.execute(users.update().where(users.c.id==extras[0]).values(permissions=['import.documents','import.templates']))
        c.execute(users.update().where(users.c.id==extras[1]).values(permissions=['import.parts','import.drawings']))
        c.execute(users.update().where(users.c.id==extras[2]).values(permissions=[]))
        if revision=='0009':c.execute(users.update().where(users.c.id==extras[0]).values(must_change_password=True))
    return engine,order,form,extras


def restore_synthetic_backup(engine,source,revision):
    """Logical schema+data restore rehearsal, never a production backup tool."""
    current=sa.MetaData();current.reflect(bind=engine)
    with engine.begin() as c:
        for table in reversed(current.sorted_tables):table.drop(c)
    upgrade(engine,'0007');install_legacy(engine,revision)
    restored=sa.MetaData();restored.reflect(bind=engine)
    with engine.begin() as c:
        # install_legacy supplies these seed/version rows; replace from backup.
        c.execute(restored.tables['system_authority'].delete());c.execute(restored.tables['alembic_version'].delete())
        for table in restored.sorted_tables:
            if source[table.name]:c.execute(table.insert(),source[table.name])
        if c.dialect.name=='postgresql':
            for table in restored.sorted_tables:
                if len(table.primary_key.columns)==1:
                    pk=next(iter(table.primary_key.columns))
                    if isinstance(pk.type,sa.Integer):
                        sequence=c.scalar(sa.text('SELECT pg_get_serial_sequence(:table,:column)'),{'table':table.name,'column':pk.name})
                        if sequence:
                            maximum=c.scalar(sa.select(sa.func.max(pk)))
                            c.execute(sa.text('SELECT setval(CAST(:sequence AS regclass),:value,:called)'),{'sequence':sequence,'value':maximum or 1,'called':maximum is not None})


@pytest.mark.parametrize('revision',['0008','0009'])
@pytest.mark.parametrize('storage',['local','database'])
def test_legacy_grants_records_files_restore_and_reupgrade(client,revision,storage,monkeypatch):
    if storage=='database':
        monkeypatch.setenv('QWOMS_DEMO_MODE','true');monkeypatch.setenv('QWOMS_STORAGE_BACKEND','database')
    web,Session=client;engine,order,form,extras=prepare(web,Session,revision);before=snapshot(engine)
    assert inspect_history(engine)['permission_layout']=='legacy'
    with pytest.raises(RuntimeError,match='migration required'):require_current(engine)
    upgrade(engine);require_current(engine);upgrade(engine)
    after=snapshot(engine)
    assert inspect_history(engine)['permission_layout']=='canonical' and inspect_history(engine)['operations_complete']
    for table,rows in before.items():
        if table in ('users','alembic_version','system_authority'):continue
        # Retirement is a new column; every original field and row survives.
        assert [{k:r[k] for k in (rows[0].keys() if rows else [])} for r in after[table]]==rows,table
    for row in before['users']:
        migrated=next(r for r in after['users'] if r['id']==row['id'])
        for key,value in row.items():
            if key!='permissions':assert migrated[key]==value
    with Session() as db:
        assert db.get(User,1).is_admin and db.get(User,1).capabilities==[]
        assert db.get(User,2).capabilities==['engineering.approve']
        assert set(db.get(User,extras[0]).capabilities)=={'import.work_instructions','import.supporting_documents','import.form_masters'}
        assert set(db.get(User,extras[1]).capabilities)=={'import.part_master','import.drawings'}
        assert db.get(User,extras[2]).capabilities==[]
        assert all('import.other' not in u.capabilities for u in db.scalars(sa.select(User)))
        report=db.get(SchemaReconciliation,'legacy_permissions_0013')
        assert report.source_revisions==[revision] and report.report['legacy_authority']==[{'id':1,'initialized':True}]
        assert report.report['operations_created_by_reconciliation_step']==(revision=='0009')
        assert len(report.report['permission_changes'])==len(before['users'])
        assert all(r['is_admin_before']==r['is_admin_after'] for r in report.report['permission_changes'])
    with engine.connect() as c:assert compare_metadata(MigrationContext.configure(c),Base.metadata)==[]
    assert web.get('/api/admin/migration-history').status_code==200
    from tests.test_security_history import login_as
    login_as(web,'engineer','OtherLongPassword123!');assert web.get('/api/admin/migration-history').status_code==403;logged_in(web)
    attachment=web.get(f'/api/work-orders/{order}/attachments').json()[0]
    assert web.get(f"/api/files/{attachment['file_id']}/download").status_code==200
    assert len(attachment['completed'])==1
    from io import BytesIO
    from openpyxl import load_workbook
    completed=web.get(f"/api/files/{attachment['completed'][0]['file_id']}/download")
    assert load_workbook(BytesIO(completed.content),data_only=True)['Shock Validation']['C5'].value=='PASS'
    # The free editor works against the converted records and original master.
    opened=web.post(f"/api/work-orders/{order}/attachments/{attachment['id']}/editor",json={});assert opened.status_code==201
    assert web.get('/api/workbooks/'+opened.json()['id']+'/form').status_code==200
    with pytest.raises(RuntimeError,match='pre-upgrade backup'):downgrade(engine,'0012')
    restore_synthetic_backup(engine,before,revision)
    assert snapshot(engine)==before
    upgrade(engine);require_current(engine)
    with Session() as db:assert db.get(User,extras[2]).capabilities==[]


@pytest.mark.parametrize('failure',['unknown-grant','partial-operations','both-columns','ledger-write-failure'])
def test_refused_migration_rolls_back_schema_version_and_data(client,failure,monkeypatch):
    web,Session=client;engine,_,_,extras=prepare(web,Session,'0009')
    with engine.begin() as c:
        if failure=='unknown-grant':
            users=sa.Table('users',sa.MetaData(),autoload_with=c);c.execute(users.update().where(users.c.id==extras[0]).values(permissions=['unreviewed.legacy.permission']))
        if failure=='partial-operations':c.exec_driver_sql('CREATE TABLE labor_entries (id INTEGER PRIMARY KEY)')
        if failure=='both-columns':c.exec_driver_sql("ALTER TABLE users ADD COLUMN capabilities JSON NOT NULL DEFAULT '[]'")
    if failure=='ledger-write-failure':
        # Fail after rename/data conversion/table creation to prove DDL atomicity.
        from sqlalchemy import event
        def fail(c,cursor,statement,parameters,context,many):
            if statement.lstrip().upper().startswith('INSERT INTO SCHEMA_RECONCILIATIONS'):raise RuntimeError('Synthetic ledger outage')
        event.listen(engine,'before_cursor_execute',fail)
    before=snapshot(engine)
    try:
        with pytest.raises(RuntimeError):upgrade(engine)
    finally:
        if failure=='ledger-write-failure':event.remove(engine,'before_cursor_execute',fail)
    assert snapshot(engine)==before


def test_current_database_operations_evidence_and_drafts_survive(client):
    web,Session=client;parts=setup_parts(web);t=template(web,'CANONICAL-RECONCILE','pump',parts['P100']['id']);approve(web,t['revision_id']);o=new_order(web,parts['P100'],assigned_to=1).json()['id']
    assert web.post(f'/api/work-orders/{o}/evidence',files={'file':('Original equipment.pdf',pdf())}).status_code==201
    assert web.post(f'/api/operations/work-orders/{o}/labor',json={'activity':'Validation','started_at':(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat(),'duration_seconds':60}).status_code==201
    attachment=web.get(f'/api/work-orders/{o}/attachments').json()[0]
    assert web.post(f"/api/work-orders/{o}/attachments/{attachment['id']}/editor",json={}).status_code==201
    engine=Session.kw['bind'];downgrade(engine,'0012');before=snapshot(engine);upgrade(engine)
    after=snapshot(engine)
    for table,rows in before.items():
        if table!='alembic_version':
            # Forward migrations may add nullable columns while preserving
            # every pre-existing value and original quality record.
            assert [{key:item[key] for key in (rows[0].keys() if rows else [])}
                    for item in after[table]] == rows,table
    assert all(o['archived_at'] is None and o['archived_by'] is None and o['archive_reason'] is None
               for o in after['work_orders'])
    assert after['schema_reconciliations']==[]
    require_current(engine)


def test_version_stamp_cannot_hide_legacy_schema(client):
    web,Session=client;engine,_,_,_=prepare(web,Session,'0009')
    with engine.begin() as c:c.execute(sa.text("UPDATE alembic_version SET version_num='0014'"))
    with pytest.raises(RuntimeError,match='schema history is incompatible'):require_current(engine)
