from tests.test_foundation import client,logged_in
from tests.test_security_history import login_as
from app.models import User,AuditEvent
from sqlalchemy import select

MANAGER_PASSWORD='SufficientlyLongPassword!'
ENGINEER_PASSWORD='OtherLongPassword123!'


def test_password_change_revokes_all_sessions_and_never_echoes_secret(client):
    web,_=client
    copied=login_as(web,'engineer',ENGINEER_PASSWORD)
    response=web.post('/api/me/change-password',json={'current_password':ENGINEER_PASSWORD,'new_password':'New-fictional-password-2026!'})
    assert response.status_code==200
    assert 'password-2026' not in response.text
    assert web.get('/api/me',headers={'Cookie':'qwoms_token='+copied}).status_code==401
    assert web.post('/api/auth/login',json={'username':'engineer','password':ENGINEER_PASSWORD}).status_code==401
    login_as(web,'engineer','New-fictional-password-2026!')
    assert web.get('/api/me').status_code==200
    response=web.post('/api/me/change-password',json={'current_password':'Short-secret','new_password':'secret'})
    assert response.status_code==422 and 'Short-secret' not in response.text and '"input"' not in response.text


def test_manager_deactivation_reactivation_role_and_session_revocation(client):
    web,_=client;copied=login_as(web,'engineer',ENGINEER_PASSWORD);logged_in(web)
    assert web.patch('/api/admin/accounts/2',json={'current_password':'wrong','active':False}).status_code==403
    assert web.patch('/api/admin/accounts/2',json={'current_password':MANAGER_PASSWORD,'active':False}).status_code==200
    assert web.get('/api/me',headers={'Cookie':'qwoms_token='+copied}).status_code==401
    assert web.post('/api/auth/login',json={'username':'engineer','password':ENGINEER_PASSWORD}).status_code==401
    response=web.get('/api/admin/accounts');assert any(not u['active'] for u in response.json())
    assert 'password_hash' not in response.text
    assert web.patch('/api/admin/accounts/2',json={'current_password':MANAGER_PASSWORD,'active':True,'role':'Quality','site':'Fictional Site C'}).status_code==200
    assert web.get('/api/me',headers={'Cookie':'qwoms_token='+copied}).status_code==401
    login_as(web,'engineer',ENGINEER_PASSWORD)
    assert web.get('/api/me').json()['role']=='Quality'
    assert web.get('/api/admin/accounts').status_code==403


def test_management_cannot_lock_out_self_and_reset_requires_step_up(client):
    web,Session=client;logged_in(web)
    assert web.patch('/api/admin/accounts/1',json={'current_password':MANAGER_PASSWORD,'active':False}).status_code==409
    assert web.patch('/api/admin/accounts/1',json={'current_password':MANAGER_PASSWORD,'role':'Production'}).status_code==200
    logged_in(web)
    assert web.get('/api/me').json()['is_admin'] is True
    assert web.post('/api/admin/accounts/2/reset-password',json={'current_password':'wrong','new_password':'Fictional-reset-password!'}).status_code==403
    assert web.post('/api/admin/accounts/2/reset-password',json={'current_password':MANAGER_PASSWORD,'new_password':'Fictional-reset-password!'}).status_code==200
    assert web.post('/api/auth/login',json={'username':'engineer','password':ENGINEER_PASSWORD}).status_code==401
    login_as(web,'engineer','Fictional-reset-password!')
    with Session() as db:
        audit=db.scalars(select(AuditEvent).where(AuditEvent.action=='account.password_reset')).all()
        assert len(audit)==1 and audit[0].changes=={}


def test_non_management_cannot_mutate_accounts(client):
    web,_=client;login_as(web,'engineer',ENGINEER_PASSWORD)
    assert web.patch('/api/admin/accounts/1',json={'current_password':ENGINEER_PASSWORD,'active':False}).status_code==403
    assert web.post('/api/admin/accounts/1/reset-password',json={'current_password':ENGINEER_PASSWORD,'new_password':'Fictional-forbidden-password!'}).status_code==403


def test_initial_password_blocks_access_then_revokes_temporary_sessions(client):
    from sqlalchemy import select
    from app.models import User,AuditEvent
    from tests.test_foundation import logged_in
    web,Session=client
    with Session() as db:db.get(User,1).must_change_password=True;db.commit()
    logged_in(web)
    assert web.get('/api/me').json()['must_change_password']
    assert web.get('/api/dashboard').status_code==403
    assert web.post('/api/me/set-initial-password',json={'new_password':'SufficientlyLongPassword!'}).status_code==422
    assert web.post('/api/me/set-initial-password',json={'new_password':'Synthetic-personal-password-123!'}).status_code==200
    assert web.get('/api/me').status_code==401
    from tests.test_security_history import login_as
    login_as(web,'manager','Synthetic-personal-password-123!')
    assert not web.get('/api/me').json()['must_change_password']
    assert web.get('/api/dashboard').status_code==200
    assert web.post('/api/me/set-initial-password',json={'new_password':'Another-synthetic-password-123!'}).status_code==409
    with Session() as db:assert db.scalar(select(AuditEvent).where(AuditEvent.action=='account.initial_password_set'))
