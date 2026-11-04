from io import BytesIO
import hashlib
import pytest
from tests.test_foundation import client,logged_in
from tests.test_security_history import login_as
from tests.test_workflow_forms import prepare_parts,form_master,rule,order
from app.models import WorkbookDraft,User
from app import editor_api

@pytest.fixture
def attached(client,monkeypatch):
    web,Session=client;logged_in(web)
    monkeypatch.setenv('QWOMS_WORKBOOK_ENGINE','collabora')
    for name,value in {'QWOMS_OFFICE_ENABLED':'true','QWOMS_OFFICE_LOCAL_DEVELOPMENT':'true','QWOMS_OFFICE_PUBLIC_URL':'http://office.local:9980','QWOMS_OFFICE_INTERNAL_URL':'http://office.local:9980','QWOMS_OFFICE_WOPI_ORIGIN':'http://testserver'}.items():monkeypatch.setenv(name,value)
    monkeypatch.setattr(editor_api,'urlopen',lambda *a,**k:BytesIO(b'<wopi-discovery><net-zone><app name="xlsx"><action name="edit" ext="xlsx" urlsrc="http://office.local:9980/browser/test/cool.html?"/></app></net-zone></wopi-discovery>'))
    parts=prepare_parts(web);doc,master,original,_=form_master(web)
    rule(web,part_id=parts['SHOCK-001']['id'],document_ids=[doc['id']])
    project=web.post('/api/projects',json={'name':'Fictional workbook editing'}).json()['id']
    o=order(web,parts['SHOCK-001'],project_id=project).json()['id'];a=web.get(f'/api/work-orders/{o}/attachments').json()[0]['id']
    begin=web.post(f'/api/work-orders/{o}/attachments/{a}/editor',json={});assert begin.status_code==201,begin.text
    draft=begin.json()['id'];launch=web.post(f'/api/workbooks/{draft}/launch',json={});assert launch.status_code==200,launch.text
    return web,Session,o,a,master,original,draft,launch.json(),project


def test_editor_real_master_copy_locks_filing_reopen_and_export(attached):
    web,Session,o,a,master,original,draft,info,project=attached
    url=f'/wopi/files/{draft}';params={'access_token':info['access_token']}
    meta=web.get(url,params=params);assert meta.status_code==200 and meta.json()['UserCanWrite']
    assert web.get(url+'/contents',params=params).content==original
    assert web.post(url+'/contents',params=params,content=original).status_code==409
    assert web.post(url,params=params,headers={'X-WOPI-Override':'LOCK','X-WOPI-Lock':'synthetic-lock'}).status_code==200
    assert web.post(url,params=params,headers={'X-WOPI-Override':'LOCK','X-WOPI-Lock':'other-lock'}).status_code==409
    assert web.post(url+'/contents',params=params,content=b'not an xlsx',headers={'X-WOPI-Lock':'synthetic-lock'}).status_code==422
    assert web.post(url+'/contents',params=params,content=original,headers={'X-WOPI-Lock':'synthetic-lock'}).status_code==200
    state=web.get(f'/api/workbooks/{draft}').json();assert state['version']==2
    name='Employee entered validated shock.xlsx'
    assert web.post(f'/api/workbooks/{draft}/completed',json={'filename':name,'expected_version':1}).status_code==409
    saved=web.post(f'/api/workbooks/{draft}/completed',json={'filename':name,'expected_version':2});assert saved.status_code==201,saved.text
    assert saved.json()['project_id']==project and saved.json()['relative_path'].endswith('/'+name)
    assert web.post(f'/api/workbooks/{draft}/completed',json={'filename':name,'expected_version':2}).status_code==409
    reopened=web.post(f'/api/work-orders/{o}/attachments/{a}/editor',json={'completed_id':saved.json()['id']});assert reopened.status_code==201
    exported=web.get('/api/workbooks/'+reopened.json()['id']+'/export',params={'filename':'Employee entered export.xlsx'})
    assert exported.status_code==200 and exported.content==original and 'Employee%20entered%20export.xlsx' in exported.headers['content-disposition']
    assert web.get(f"/api/files/{master['id']}/download").content==original
    assert web.patch(f'/api/work-orders/{o}',json={'status':'Completed'}).status_code==200
    assert web.post(f'/api/workbooks/{draft}/completed',json={'filename':'Another.xlsx','expected_version':2}).status_code==409
    assert web.post(url+'/contents',params=params,content=original,headers={'X-WOPI-Lock':'synthetic-lock'}).status_code==409
    view=web.post(f'/api/work-orders/{o}/attachments/{a}/editor',json={'completed_id':saved.json()['id']}).json()['id']
    assert web.post(f'/api/workbooks/{view}/launch',json={}).json()['read_only'] is True


def test_editor_scoped_token_no_bypass_or_cross_employee_access(attached):
    web,Session,o,a,master,original,draft,info,_=attached
    url=f'/wopi/files/{draft}'
    assert web.get(url).status_code==401
    assert web.get(url,params={'access_token':'wrong'}).status_code==401
    login_as(web,'engineer','OtherLongPassword123!')
    assert web.get(f'/api/workbooks/{draft}').status_code==404
    assert web.post(f'/api/workbooks/{draft}/launch',json={}).status_code==404
    with Session() as db:
        db.get(User,1).active=False;db.commit()
    assert web.get(url,params={'access_token':info['access_token']}).status_code==401


def test_editor_token_rotation_and_revoked_session(attached):
    web,Session,o,a,master,original,draft,info,_=attached
    rotated=web.post(f'/api/workbooks/{draft}/launch',json={}).json()
    assert web.get(f'/wopi/files/{draft}',params={'access_token':info['access_token']}).status_code==401
    assert web.get(f'/wopi/files/{draft}',params={'access_token':rotated['access_token']}).status_code==200
    assert web.post('/api/auth/logout').status_code==200
    assert web.get(f'/wopi/files/{draft}',params={'access_token':rotated['access_token']}).status_code==401


def test_editor_denies_unsafe_filenames_and_unknown_attachments(attached):
    web,Session,o,a,master,original,draft,info,_=attached
    for name in ['../out.xlsx',' blank.xlsx','file.pdf','folder\\file.xlsx']:
        assert web.get(f'/api/workbooks/{draft}/export',params={'filename':name}).status_code==422
        assert web.post(f'/api/workbooks/{draft}/completed',json={'filename':name,'expected_version':1}).status_code==422
    assert web.post(f'/api/work-orders/{o}/attachments/{a}/editor',json={'completed_id':999999}).status_code==404
    assert web.post(f'/api/work-orders/{o}/attachments/999999/editor',json={}).status_code==404

def test_editor_fidelity_changes_are_visible_and_require_acknowledgment(attached):
    from openpyxl import load_workbook
    web,Session,o,a,master,original,draft,info,_=attached
    workbook=load_workbook(BytesIO(original));workbook['Shock Validation']['A1'].value='Fictional edited title'
    workbook['Shock Validation'].column_dimensions['A'].width=35
    out=BytesIO();workbook.save(out)
    with Session() as db:
        db.get(WorkbookDraft,draft).content=out.getvalue();db.commit()
    comparison=web.get(f'/api/workbooks/{draft}/compatibility');assert comparison.status_code==200
    assert any(c['feature']=='.sheets.Shock Validation.columns.A' for c in comparison.json()['differences'])
    body={'filename':'Employee reviewed differences.xlsx','expected_version':1}
    assert web.post(f'/api/workbooks/{draft}/completed',json=body).status_code==409
    assert web.post(f'/api/workbooks/{draft}/completed',json={**body,'acknowledge_fidelity_differences':True}).status_code==201
    assert web.get(f"/api/files/{master['id']}/download").content==original


def test_editor_rejects_external_relationships_and_data_formulas():
    from openpyxl import load_workbook
    from tests.excel.synthetic_workbook import workbook_bytes
    from fastapi import HTTPException
    source=workbook_bytes()
    for value in ['=WEBSERVICE("https://example.com")','https://example.com']:
        book=load_workbook(BytesIO(source));sheet=book.active
        if value.startswith('='):sheet['F5']=value
        else:sheet['F5'].hyperlink=value
        output=BytesIO();book.save(output)
        with pytest.raises(HTTPException) as error:editor_api.validate_for_editor(output.getvalue())
        assert error.value.status_code==422

def test_assigned_employee_edits_without_master_import_grants(attached):
    from app.security import hash_password
    web,Session,o,a,master,original,draft,info,_=attached
    with Session() as db:
        employee=User(username='synthetic.production',display_name='Synthetic Production',role='Production',password_hash=hash_password('Synthetic-production-password!'))
        db.add(employee);db.commit();employee_id=employee.id
    login_as(web,'synthetic.production','Synthetic-production-password!')
    assert web.post(f'/api/work-orders/{o}/attachments/{a}/editor',json={}).status_code==403
    assert web.get(f'/api/workbooks/{draft}').status_code==404
    logged_in(web)
    assert web.patch(f'/api/work-orders/{o}',json={'assigned_to':employee_id}).status_code==200
    login_as(web,'synthetic.production','Synthetic-production-password!')
    assert web.get('/api/me').json()['capabilities']==[]
    begin=web.post(f'/api/work-orders/{o}/attachments/{a}/editor',json={})
    assert begin.status_code==201
    employee_draft=begin.json()['id']
    assert web.post(f'/api/workbooks/{employee_draft}/completed',json={'filename':'Employee execution without imports.xlsx','expected_version':1}).status_code==201


def test_editor_expiry_closes_token_and_cookie_draft(attached):
    from datetime import datetime,timedelta,timezone
    web,Session,o,a,master,original,draft,info,_=attached
    with Session() as db:
        db.get(WorkbookDraft,draft).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    assert web.get(f'/wopi/files/{draft}',params={'access_token':info['access_token']}).status_code==401
    assert web.get(f'/api/workbooks/{draft}').status_code==410
