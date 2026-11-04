from tests.test_foundation import client,logged_in,part_import
from tests.test_security_history import login_as
from app.models import User,AuditEvent
from sqlalchemy import select

PASSWORD='SufficientlyLongPassword!'

def test_zero_inherited_imports_and_admin_authority(client):
    web,Session=client
    logged_in(web)
    for role in ['Quality','Engineering','Production','Management']:
        r=web.post('/api/admin/users',json={'username':role.lower()+'-employee','display_name':'Fictional Employee','role':role,'password':'Fictional-password-123!','site':''})
        assert r.status_code==201
        login_as(web,role.lower()+'-employee','Fictional-password-123!')
        assert not web.get('/api/me').json()['is_admin']
        assert web.get('/api/me').json()['capabilities']==[]
        assert web.get('/api/admin/accounts').status_code==403
        assert part_import(web,[], 'preview').status_code==403
        assert part_import(web,[]).status_code==403
        for kind in ['drawing','document','form-template','work-instruction','other']:
            assert web.post('/api/files/import-folder',data={'kind':kind,'paths':'Synthetic/a.txt'},files={'files':('a.txt',b'fictional')}).status_code==403
        logged_in(web)

def test_grant_revoke_audit_and_last_admin(client):
    web,Session=client;logged_in(web)
    assert web.patch('/api/admin/accounts/1',json={'current_password':PASSWORD,'is_admin':False}).status_code==409
    assert web.delete('/api/admin/accounts/1').status_code==405
    for rights,expected in [(['import.part_master'],200),([],403)]:
        assert web.patch('/api/admin/accounts/2',json={'current_password':PASSWORD,'capabilities':rights}).status_code==200
        login_as(web,'engineer','OtherLongPassword123!')
        assert part_import(web,[],'preview').status_code==expected
        logged_in(web)
    with Session() as db:
        actions=db.scalars(select(AuditEvent).where(AuditEvent.action.in_(['permission.granted','permission.revoked']))).all()
        assert len(actions)==3 # revoke initial approval, grant import, revoke import
        assert all(a.actor_id==1 and a.entity_id=='2' for a in actions)

def test_bootstrap_claim_once_and_audited(client,monkeypatch):
    from app import bootstrap
    from unittest.mock import patch
    web,Session=client
    with Session() as db:
        # A legacy installation has no implicit promotion.
        db.get(User,1).is_admin=False;db.commit()
    monkeypatch.setattr(bootstrap,'SessionLocal',Session)
    monkeypatch.setattr(bootstrap,'engine',Session.kw['bind'])
    with patch('sys.argv',['bootstrap','personal.owner','--display-name','Fictional Owner']),patch('getpass.getpass',return_value='Fictional-owner-password!'):
        bootstrap.main()
        import pytest
        with pytest.raises(SystemExit,match='already claimed'):bootstrap.main()
    with Session() as db:
        admins=db.scalars(select(User).where(User.is_admin.is_(True))).all()
        assert len(admins)==1 and admins[0].username=='personal.owner'
        assert db.scalar(select(AuditEvent).where(AuditEvent.action=='administrator.claimed'))
