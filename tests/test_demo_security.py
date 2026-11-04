from datetime import timedelta
import pytest
from tests.test_foundation import client, logged_in
from app.deployment import validate_settings
import app.security as security
import app.throttling as throttling


def test_shared_login_failure_throttle_and_recovery(client, monkeypatch):
    web, _ = client
    start = throttling.now()
    monkeypatch.setattr(throttling, 'now', lambda: start)
    for _ in range(5):
        assert web.post('/api/auth/login', json={'username':'manager','password':'wrong'}).status_code == 401
    response = web.post('/api/auth/login', json={'username':'manager','password':'SufficientlyLongPassword!'})
    assert response.status_code == 429 and int(response.headers['Retry-After']) > 0
    monkeypatch.setattr(throttling, 'now', lambda: start + timedelta(minutes=16))
    logged_in(web)


def test_ip_limit_across_different_unknown_accounts(client):
    web, _ = client
    for i in range(30):
        assert web.post('/api/auth/login', json={'username':f'fictional-{i}','password':'wrong'}).status_code == 401
    assert web.post('/api/auth/login', json={'username':'other','password':'wrong'}).status_code == 429


def test_demo_settings_fail_closed(monkeypatch):
    monkeypatch.setenv('QWOMS_DEMO_MODE', 'true')
    monkeypatch.setattr(security,'SECRET','x'*64)
    monkeypatch.setenv('QWOMS_COOKIE_SECURE','true')
    monkeypatch.setenv('QWOMS_PUBLIC_URL','https://demo.example.invalid')
    monkeypatch.setenv('QWOMS_SYNTHETIC_DATA_ONLY','true')
    monkeypatch.setenv('QWOMS_STORAGE_ROOT','/data')
    monkeypatch.setenv('QWOMS_ALLOWED_ORIGINS','')
    validate_settings('postgresql+psycopg://fictional@db/demo')
    with pytest.raises(RuntimeError,match='PostgreSQL'):
        validate_settings('sqlite:///demo.db')
    monkeypatch.setenv('QWOMS_COOKIE_SECURE','false')
    with pytest.raises(RuntimeError,match='COOKIE_SECURE'):
        validate_settings('postgresql+psycopg://fictional@db/demo')


def test_readiness_security_headers_and_demo_banner_flag(client, monkeypatch):
    web, _ = client
    assert web.get('/readyz').status_code == 200
    monkeypatch.setenv('QWOMS_DEMO_MODE','true')
    assert web.get('/api/public-config').json()=={'demo_mode':True}
    assert 'SYNTHETIC DATA ONLY' in web.get('/').text
    assert web.get('/healthz').headers['X-Frame-Options']=='DENY'
    assert web.get('/healthz').headers['Strict-Transport-Security'].startswith('max-age=')
    monkeypatch.setenv('QWOMS_BUILD_COMMIT','unknown');monkeypatch.setenv('RENDER_GIT_COMMIT','a'*40)
    assert web.get('/healthz').json()['build_commit']=='a'*40
    import app.main as module
    def unavailable(engine):
        raise RuntimeError('Fictional database unavailable')
    monkeypatch.setattr(module,'require_current',unavailable)
    response=web.get('/readyz')
    assert response.status_code==503 and 'Fictional' not in response.text


def test_private_gate_protects_static_and_api_without_exposing_health(client, monkeypatch):
    import base64
    web,_=client
    monkeypatch.setenv('QWOMS_DEMO_MODE','true')
    monkeypatch.setenv('QWOMS_DEMO_ACCESS_MODE','basic')
    monkeypatch.setenv('QWOMS_DEMO_GATE_PASSWORD','fictional-local-gate-'+'x'*40)
    assert web.get('/').status_code==401
    assert web.get('/static/app.js').status_code==401
    assert web.get('/api/public-config').status_code==401
    assert web.get('/healthz').status_code==200
    encoded=base64.b64encode(('demo:fictional-local-gate-'+'x'*40).encode()).decode()
    web.headers['Authorization']='Basic '+encoded
    assert web.get('/api/public-config').json()['demo_mode']
    assert web.get('/api/dashboard').status_code==401  # Gate does not replace individual accounts.


def test_demo_database_file_store_is_atomic(client, monkeypatch):
    import app.main as module
    from app.models import DemoOriginalBlob
    from sqlalchemy import select
    web,Session=client
    logged_in(web)
    monkeypatch.setenv('QWOMS_DEMO_MODE','true')
    monkeypatch.setenv('QWOMS_STORAGE_BACKEND','database')
    payload={'kind':'drawing','paths':'Synthetic/Employee chosen name.PDF'}
    upload={'files':('Employee chosen name.PDF',b'fictional original bytes','application/pdf')}
    response=web.post('/api/files/import-folder',data=payload,files=upload)
    assert response.status_code==200 and response.json()['stored']==1
    f=web.get('/api/files').json()[0]
    assert web.get(f"/api/files/{f['id']}/download").content==b'fictional original bytes'
    conflict=web.post('/api/files/import-folder',data=payload,files={'files':('Employee chosen name.PDF',b'changed')})
    assert len(conflict.json()['conflicts'])==1
    def audit_unavailable(*args,**kwargs):raise RuntimeError('Fictional audit outage')
    monkeypatch.setattr(module,'record',audit_unavailable)
    with pytest.raises(RuntimeError,match='audit outage'):
        web.post('/api/files/import-folder',data={'kind':'drawing','paths':'Synthetic/Rollback.PDF'},files=upload)
    with Session() as db:
        assert db.get(DemoOriginalBlob,'files/Synthetic/Rollback.PDF') is None


def test_synthetic_bootstrap_is_idempotent_without_credential_overwrite(client,monkeypatch):
    from app.demo_bootstrap import seed
    from app.models import User
    from sqlalchemy import select
    web,Session=client
    with Session() as db:
        with pytest.raises(RuntimeError,match='demo mode'):seed(db)
    monkeypatch.setenv('QWOMS_DEMO_MODE','true')
    monkeypatch.setenv('QWOMS_SYNTHETIC_DATA_ONLY','true')
    for key in ['QWOMS_BOOTSTRAP_PASSWORD','QWOMS_DEMO_QUALITY_PASSWORD','QWOMS_DEMO_ENGINEERING_PASSWORD','QWOMS_DEMO_PRODUCTION_PASSWORD']:
        monkeypatch.setenv(key,'Fictional-'+key+'-password')
    with Session() as db:
        seed(db);db.commit()
        before=db.scalar(select(User).where(User.username=='demo.manager')).password_hash
        seed(db);db.commit()
        assert db.scalar(select(User).where(User.username=='demo.manager')).password_hash==before


def test_unicode_basic_credentials_are_rejected_without_server_error(client,monkeypatch):
    import base64
    web,_=client
    monkeypatch.setenv('QWOMS_DEMO_MODE','true');monkeypatch.setenv('QWOMS_DEMO_ACCESS_MODE','basic')
    monkeypatch.setenv('QWOMS_DEMO_GATE_PASSWORD','x'*64)
    encoded=base64.b64encode('demo:неверный'.encode()).decode()
    assert web.get('/',headers={'Authorization':'Basic '+encoded}).status_code==401
