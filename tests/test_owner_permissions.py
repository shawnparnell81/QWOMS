"""Owner authority is explicit and independent of every employee department."""
import pytest
from sqlalchemy import select
from app.models import User,AuditEvent,SystemAuthority
from app.bootstrap import claim
from tests.test_foundation import client,logged_in,part_import
from tests.test_security_history import login_as
from tests.db_helpers import test_engine as isolated_engine
from app.schema import upgrade
from sqlalchemy.orm import Session as DBSession

PASSWORD='Fictional-permission-test!'


def create_employee(web,role):
    logged_in(web)
    r=web.post('/api/admin/users',json={'username':'synthetic-'+role.lower(),'display_name':'Synthetic '+role,'role':role,'password':PASSWORD,'is_admin':True,'permissions':['import.parts']})
    assert r.status_code==201
    return r.json()['id']


@pytest.mark.parametrize('role',['Management','Engineering','Quality','Production'])
def test_zero_import_defaults_and_no_department_or_payload_escalation(client,role):
    web,Session=client;user_id=create_employee(web,role)
    with Session() as db:
        employee=db.get(User,user_id);assert not employee.is_admin and employee.permissions==[]
    login_as(web,'synthetic-'+role.lower(),PASSWORD)
    assert web.get('/api/admin/accounts').status_code==403
    assert web.post('/api/admin/users',json={'username':'forbidden-user','display_name':'Forbidden User','role':'Management','password':PASSWORD}).status_code==403
    assert part_import(web,[['Synthetic','SYN-1','','DRAW-1','A','']],'preview').status_code==403
    assert part_import(web,[['Synthetic','SYN-1','','DRAW-1','A','']]).status_code==403
    for kind in ['drawing','document','form-template']:
        assert web.post('/api/files/import-folder',data={'paths':'Synthetic/Denied.pdf','kind':kind},files={'files':('Denied.pdf',b'synthetic only')}).status_code==403
    for kind in ['Drawing','Work instruction','Supporting document','Form template']:
        assert web.post('/api/controlled/documents',json={'kind':kind,'number':'DENIED','title':'Synthetic denied import'}).status_code==403
    assert web.put('/api/files/99999/drawing-mapping',json={'drawing_number':'SYN','drawing_revision':'A'}).status_code==403


def test_explicit_grant_is_scoped_revoked_audited_and_not_restored_by_role(client):
    web,Session=client;employee_id=create_employee(web,'Quality')
    body={'current_password':'SufficientlyLongPassword!','permissions':['import.parts']}
    assert web.patch(f'/api/admin/accounts/{employee_id}',json=body).status_code==200
    login_as(web,'synthetic-quality',PASSWORD)
    assert part_import(web,[['Synthetic','SYN-1','','DRAW-1','A','']],'preview').status_code==200
    assert web.post('/api/files/import-folder',data={'paths':'Denied.pdf','kind':'drawing'},files={'files':('Denied.pdf',b'synthetic')}).status_code==403
    logged_in(web)
    assert web.patch(f'/api/admin/accounts/{employee_id}',json={**body,'permissions':[],'role':'Management'}).status_code==200
    login_as(web,'synthetic-quality',PASSWORD)
    assert part_import(web,[['Synthetic','SYN-1','','DRAW-1','A','']],'preview').status_code==403
    with Session() as db:
        events=db.scalars(select(AuditEvent).where(AuditEvent.entity_id==str(employee_id),AuditEvent.action.in_(['permission.granted','permission.revoked'])).order_by(AuditEvent.id)).all()
        assert [e.action for e in events]==['permission.granted','permission.revoked']
        assert all(e.actor_id==1 and e.changes['capability']=='import.parts' and e.created_at for e in events)


def test_last_admin_and_invalid_permissions_protected(client):
    web,Session=client;logged_in(web)
    for change in [{'active':False},{'is_admin':False}]:
        assert web.patch('/api/admin/accounts/1',json={'current_password':'SufficientlyLongPassword!',**change}).status_code==409
    assert web.patch('/api/admin/accounts/2',json={'current_password':'SufficientlyLongPassword!','permissions':['import.everything']}).status_code==422
    assert web.patch('/api/admin/accounts/2',json={'current_password':'wrong','is_admin':True}).status_code==403
    assert web.patch('/api/admin/accounts/2',json={'current_password':'SufficientlyLongPassword!','is_admin':True}).status_code==200
    login_as(web,'engineer','OtherLongPassword123!')
    # A system admin with Engineering department is authorized independently of Management.
    assert web.get('/api/admin/accounts').status_code==200
    assert web.patch('/api/admin/accounts/1',json={'current_password':'OtherLongPassword123!','is_admin':False}).status_code==200
    assert web.patch('/api/admin/accounts/2',json={'current_password':'OtherLongPassword123!','is_admin':False}).status_code==409


def test_production_initial_owner_claim_is_one_time_personal_and_empty(tmp_path,monkeypatch):
    monkeypatch.setenv('QWOMS_DEMO_MODE','false')
    with isolated_engine(tmp_path) as engine:
        upgrade(engine)
        with DBSession(engine) as db:
            owner=claim(db,'synthetic.owner',PASSWORD,'Synthetic Owner');db.commit()
            assert owner.is_admin and owner.permissions==[]
            assert len(db.scalars(select(User)).all())==1
            with pytest.raises(ValueError,match='already claimed'):claim(db,'second.owner',PASSWORD,'Another Owner')


def test_legacy_migration_never_promotes_management_and_requires_password_claim(client,monkeypatch):
    web,Session=client;monkeypatch.setenv('QWOMS_DEMO_MODE','false')
    with Session() as db:
        for u in db.scalars(select(User)).all():u.is_admin=False
        db.commit()
        with pytest.raises(ValueError,match='verification failed'):claim(db,'manager','wrong','Synthetic Owner',existing=True)
        user=claim(db,'manager','SufficientlyLongPassword!','Synthetic Owner',existing=True);db.commit()
        assert user.is_admin
        assert not db.get(User,2).is_admin


@pytest.mark.parametrize('kind,capability,document_kind',[('drawing','import.drawings','Drawing'),('document','import.documents','Work instruction'),('form-template','import.templates','Form template')])
def test_each_import_capability_has_independent_backend_grant_and_revoke(client,kind,capability,document_kind):
    web,Session=client;employee_id=create_employee(web,'Production')
    body={'current_password':'SufficientlyLongPassword!','permissions':[capability]}
    assert web.patch(f'/api/admin/accounts/{employee_id}',json=body).status_code==200
    login_as(web,'synthetic-production',PASSWORD)
    response=web.post('/api/files/import-folder',data={'paths':'Synthetic/Original.bin','kind':kind},files={'files':('Original.bin',b'fictional original')})
    assert response.status_code==200 and response.json()['stored']==1
    doc=web.post('/api/controlled/documents',json={'kind':document_kind,'number':'SYN-EXPLICIT','title':'Synthetic explicit delegated import'})
    assert doc.status_code==201
    assert part_import(web,[['Synthetic','SYN-1','','DRAW-1','A','']],'preview').status_code==403
    logged_in(web)
    assert web.patch(f'/api/admin/accounts/{employee_id}',json={**body,'permissions':[]}).status_code==200
    login_as(web,'synthetic-production',PASSWORD)
    assert web.post('/api/files/import-folder',data={'paths':'Synthetic/Second.bin','kind':kind},files={'files':('Second.bin',b'fictional')}).status_code==403
    assert web.post('/api/controlled/documents',json={'kind':document_kind,'number':'SYN-REVOKED','title':'Synthetic denied after revoke'}).status_code==403


def test_engineering_approval_requires_explicit_duty_and_revocation_is_immediate(client):
    from tests.test_controlled_revisions import upload,action
    web,Session=client;logged_in(web)
    file=upload(web,'Synthetic/Approval.pdf','document')
    doc=web.post('/api/controlled/documents',json={'kind':'Work instruction','number':'SYN-APPROVAL','title':'Synthetic approval duty'}).json()
    revision=web.post(f"/api/controlled/documents/{doc['id']}/revisions",json={'file_id':file['id'],'revision':'1','change_summary':'Synthetic initial issue'}).json()['id']
    action(web,revision,'submit')
    assert web.patch('/api/admin/accounts/2',json={'current_password':'SufficientlyLongPassword!','permissions':[]}).status_code==200
    login_as(web,'engineer','OtherLongPassword123!')
    assert web.post(f'/api/controlled/revisions/{revision}/actions',json={'action':'review','reason':'Synthetic denied duty'}).status_code==403
    logged_in(web)
    assert web.patch('/api/admin/accounts/2',json={'current_password':'SufficientlyLongPassword!','permissions':['revision.approve']}).status_code==200
    login_as(web,'engineer','OtherLongPassword123!');action(web,revision,'review')
    logged_in(web)
    assert web.patch('/api/admin/accounts/2',json={'current_password':'SufficientlyLongPassword!','permissions':[]}).status_code==200
    login_as(web,'engineer','OtherLongPassword123!')
    assert web.post(f'/api/controlled/revisions/{revision}/actions',json={'action':'approve','reason':'Synthetic revoked duty'}).status_code==403



def test_system_admin_does_not_inherit_engineering_approval(client):
    from app.security import permitted
    web,Session=client
    with Session() as db:
        engineer=db.get(User,2);engineer.is_admin=True;engineer.permissions=[];db.commit()
        assert permitted(engineer,'import.parts')
        assert not permitted(engineer,'revision.approve')
