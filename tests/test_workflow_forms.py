from io import BytesIO
import hashlib
import pytest
from openpyxl import load_workbook
from tests.test_foundation import client,logged_in,part_import
from tests.test_controlled_revisions import upload,approve
from tests.excel.synthetic_workbook import workbook_bytes
from app.models import WorkOrder


def prepare_parts(web):
    part_import(web,[['Fictional Shocks','SHOCK-001','','','',''],['Fictional Shocks','SHOCK-002','','','',''],['Fictional Brakes','BRAKE-001','','','','']])
    return {pn:web.get('/api/parts/search?q='+pn).json()[0] for pn in ['SHOCK-001','SHOCK-002','BRAKE-001']}


def form_master(web,code='SHOCK-VALIDATION',revision='1',approved=True):
    content=workbook_bytes()
    file=upload(web,f'Synthetic masters/{code} blank revision {revision}.xlsx','form-template',content)
    existing=next((d for d in web.get('/api/controlled/documents').json() if d['number']==code),None)
    document=existing or web.post('/api/controlled/documents',json={'kind':'Form template','number':code,'title':'Fictional Shock Validation Form'}).json()
    response=web.post(f"/api/controlled/documents/{document['id']}/revisions",json={'file_id':file['id'],'revision':revision,'change_summary':'Fictional controlled blank master','blank_master_confirmed':True})
    assert response.status_code==201,response.text
    if approved:approve(web,response.json()['id'])
    return document,file,content,response.json()['id']


def rule(web,**kwargs):
    body={'name':'Fictional Shock Validation requirements','order_type':'Validation / FAI','instructions':'Use the approved Shock Validation Form and record the specified measurements.',**kwargs}
    response=web.post('/api/workflow/rules',json=body)
    assert response.status_code==201,response.text
    return response.json()['id']


def order(web,part,values=None,order_type='Validation / FAI',subtype='First Article Inspection',project_id=None):
    preview=web.post('/api/workflow/preview',json={'order_type':order_type,'subtype':subtype,'part_ids':[part['id']]}).json()[str(part['id'])]
    return web.post('/api/work-orders',json={'order_type':order_type,'subtype':subtype,'title':'Fictional type-specific order','project_id':project_id,
        'parts':[{'part_id':part['id'],'selected_part_number':part['aliases'][0]['part_number'],'quantity':1,'field_values':values or {},'rule_ids':preview['rule_ids']}]})


def test_different_parts_types_subtypes_and_frozen_field_requirements(client):
    web,_=client;logged_in(web);parts=prepare_parts(web)
    family=next(f['id'] for f in web.get('/api/parts/families').json() if f['name']=='Fictional Shocks')
    broad=rule(web,family_id=family,fields=[{'key':'rod_length','label':'Rod length','type':'number','required':True,'minimum':10}])
    specific=rule(web,part_id=parts['SHOCK-002']['id'],subtype='Product Validation',fields=[{'key':'rod_length','label':'Long shock rod length','type':'number','required':True,'minimum':30}])
    assert order(web,parts['SHOCK-001']).status_code==422
    assert order(web,parts['SHOCK-001'],{'rod_length':'NaN'}).status_code==422
    assert order(web,parts['SHOCK-002'],{'rod_length':'12'},subtype='Product Validation').status_code==422
    a=order(web,parts['SHOCK-001'],{'rod_length':'12'});assert a.status_code==201,a.text
    b=order(web,parts['SHOCK-002'],{'rod_length':'35'},subtype='Product Validation');assert b.status_code==201
    assert b.json()['parts'][0]['requirements']['fields'][0]['label']=='Long shock rod length'
    brake=order(web,parts['BRAKE-001']);assert brake.status_code==201
    assert brake.json()['parts'][0]['requirements']['fields']==[]
    inspection=order(web,parts['SHOCK-001'],order_type='Inspection',subtype='AQL');assert inspection.status_code==201
    assert inspection.json()['parts'][0]['requirements']['rule_ids']==[]
    before=a.json()['parts'][0]['requirements']
    assert web.post(f'/api/workflow/rules/{broad}/retire').status_code==200
    assert web.get(f"/api/work-orders/{a.json()['id']}").json()['parts'][0]['requirements']==before
    assert order(web,parts['SHOCK-001']).status_code==201


def test_correct_blank_form_attachment_completed_filename_category_and_immutability(client,monkeypatch):
    web,Session=client;logged_in(web)
    monkeypatch.setenv('QWOMS_DEMO_MODE','true');monkeypatch.setenv('QWOMS_STORAGE_BACKEND','database')
    parts=prepare_parts(web);document,master,original,revision=form_master(web)
    project=web.post('/api/projects',json={'name':'Fictional form project'}).json()
    rule(web,part_id=parts['SHOCK-001']['id'],document_ids=[document['id']],fields=[{'key':'final_result','label':'Final result','type':'choice','choices':['PASS','FAIL'],'required':True,'required_at':'completion'}])
    assert web.put('/api/workflow/filing-rules',json={'order_type':'Validation / FAI','folder':'Quality Evidence/Shock Validation'}).status_code==200
    response=order(web,parts['SHOCK-001'],project_id=project['id']);assert response.status_code==201,response.text
    order_id=response.json()['id'];attachment=web.get(f'/api/work-orders/{order_id}/attachments').json()[0]
    assert attachment['revision_id']==revision and attachment['filename']==master['original_name']
    assert attachment['sha256']==hashlib.sha256(original).hexdigest()
    assert web.get(f'/api/work-orders/{order_id}/attachments').json()[0]['completed']==[]
    assert web.patch(f'/api/work-orders/{order_id}',json={'status':'Completed'}).status_code==422
    assert web.patch(f"/api/work-orders/{order_id}/parts/{parts['SHOCK-001']['id']}/fields",json={'values':{'final_result':'OTHER'}}).status_code==422
    assert web.patch(f"/api/work-orders/{order_id}/parts/{parts['SHOCK-001']['id']}/fields",json={'values':{'final_result':'PASS'}}).status_code==200
    assert web.patch(f'/api/work-orders/{order_id}',json={'status':'Completed'}).status_code==409
    wb=load_workbook(BytesIO(original));wb['Shock Validation']['B5']=12;output=BytesIO();wb.save(output);completed=output.getvalue()
    endpoint=f"/api/work-orders/{order_id}/attachments/{attachment['id']}/completed"
    filename='Employee chosen shock validation 001.xlsx'
    assert web.post(endpoint,files={'file':('export.xlsx',completed)}).status_code==422
    assert web.post(endpoint,data={'filename':'../unsafe.xlsx'},files={'file':('export.xlsx',completed)}).status_code==422
    assert web.post(endpoint,data={'filename':'Invalid.xlsx'},files={'file':('export.xlsx',b'not an XLSX')}).status_code==422
    # Existing order retains its designated category even after configuration changes.
    web.put('/api/workflow/filing-rules',json={'order_type':'Validation / FAI','folder':'New category'})
    saved=web.post(endpoint,data={'filename':filename},files={'file':('browser generated export.xlsx',completed)})
    assert saved.status_code==201,saved.text
    assert saved.json()['filename']==filename
    assert saved.json()['relative_path']=='Completed forms/Quality Evidence/Shock Validation/'+filename
    assert saved.json()['project_id']==project['id']
    assert web.post(endpoint,data={'filename':filename},files={'file':('different.xlsx',completed)}).status_code==409
    assert web.get(f"/api/files/{saved.json()['file_id']}/download").content==completed
    assert web.get(f"/api/files/{master['id']}/download").content==original
    assert len(web.get('/api/controlled/documents').json()[0]['revisions'])==1
    assert web.patch(f'/api/work-orders/{order_id}',json={'status':'Completed'}).status_code==200
    assert web.post(endpoint,data={'filename':'Another.xlsx'},files={'file':('export.xlsx',completed)}).status_code==409
    with Session() as db:assert db.query(WorkOrder).count()==1


def test_missing_approved_master_blocks_creation_without_blank_orders(client):
    web,Session=client;logged_in(web);parts=prepare_parts(web)
    document,_,_,_=form_master(web,approved=False)
    rule(web,part_id=parts['SHOCK-001']['id'],document_ids=[document['id']])
    response=order(web,parts['SHOCK-001'])
    assert response.status_code==409
    with Session() as db:assert db.query(WorkOrder).count()==0


def test_new_master_revision_affects_only_new_orders(client):
    web,_=client;logged_in(web);parts=prepare_parts(web)
    document,_,_,first=form_master(web)
    rule(web,part_id=parts['SHOCK-001']['id'],document_ids=[document['id']])
    old=order(web,parts['SHOCK-001']).json()
    _,_,_,second=form_master(web,revision='2')
    new=order(web,parts['SHOCK-001']).json()
    assert web.get(f"/api/work-orders/{old['id']}/attachments").json()[0]['revision_id']==first
    assert web.get(f"/api/work-orders/{new['id']}/attachments").json()[0]['revision_id']==second


def test_equal_specificity_conflicts_and_bad_scopes_rejected(client):
    web,_=client;logged_in(web);parts=prepare_parts(web)
    rule(web,part_id=parts['SHOCK-001']['id'],fields=[{'key':'fixture','label':'Fixture A'}])
    rule(web,part_id=parts['SHOCK-001']['id'],fields=[{'key':'fixture','label':'Conflicting fixture B'}])
    preview=web.post('/api/workflow/preview',json={'order_type':'Validation / FAI','subtype':'First Article Inspection','part_ids':[parts['SHOCK-001']['id']]})
    assert preview.status_code==409
    assert web.post('/api/workflow/rules',json={'name':'Wrong scope','order_type':'Inspection','subtype':'Ortery 360°'}).status_code==422
    assert web.put('/api/workflow/filing-rules',json={'order_type':'Inspection','folder':'../escape'}).status_code==422


def test_unreviewed_rule_version_and_production_upload_rejected(client):
    from tests.test_security_history import login_as
    web,_=client;logged_in(web);parts=prepare_parts(web)
    document,_,content,_=form_master(web)
    rule_id=rule(web,part_id=parts['SHOCK-001']['id'],document_ids=[document['id']])
    response=web.post('/api/work-orders',json={'order_type':'Validation / FAI','subtype':'First Article Inspection','title':'Unreviewed synthetic requirements',
        'parts':[{'part_id':parts['SHOCK-001']['id'],'selected_part_number':'SHOCK-001','quantity':1,'rule_ids':[]}]})
    assert response.status_code==409
    created=order(web,parts['SHOCK-001']).json();attachment=web.get(f"/api/work-orders/{created['id']}/attachments").json()[0]
    user=web.post('/api/admin/users',json={'username':'production','display_name':'Fictional Production','password':'Fictional-production-password!','role':'Production'});assert user.status_code==201
    login_as(web,'production','Fictional-production-password!')
    endpoint=f"/api/work-orders/{created['id']}/attachments/{attachment['id']}/completed"
    assert web.post(endpoint,data={'filename':'Unassigned.xlsx'},files={'file':('input.xlsx',content)}).status_code==403
    assert web.post('/api/workflow/rules',json={'name':'Forbidden rule','order_type':'Inspection','instructions':'Fictional instructions'}).status_code==403
    assert web.patch(f"/api/work-orders/{created['id']}/parts/{parts['SHOCK-001']['id']}/fields",json={'values':{}}).status_code==403


def test_completed_form_audit_failure_rolls_back_original_bytes(client,monkeypatch):
    from app.models import DemoOriginalBlob,CompletedForm,StoredFile
    import app.workflow_api as module
    from sqlalchemy import select
    web,Session=client;logged_in(web)
    monkeypatch.setenv('QWOMS_DEMO_MODE','true');monkeypatch.setenv('QWOMS_STORAGE_BACKEND','database')
    parts=prepare_parts(web);document,master,content,_=form_master(web)
    rule(web,part_id=parts['SHOCK-001']['id'],document_ids=[document['id']])
    created=order(web,parts['SHOCK-001']).json();attachment=web.get(f"/api/work-orders/{created['id']}/attachments").json()[0]
    def unavailable(*args,**kwargs):raise RuntimeError('Fictional completed-form audit outage')
    monkeypatch.setattr(module,'record',unavailable)
    with pytest.raises(RuntimeError,match='audit outage'):
        web.post(f"/api/work-orders/{created['id']}/attachments/{attachment['id']}/completed",data={'filename':'Must roll back.xlsx'},files={'file':('input.xlsx',content)})
    with Session() as db:
        assert db.get(DemoOriginalBlob,'files/Completed forms/Validation/Must roll back.xlsx') is None
        assert db.scalar(select(StoredFile.id).where(StoredFile.original_name=='Must roll back.xlsx')) is None
        assert db.query(CompletedForm).count()==0
    assert web.get(f"/api/files/{master['id']}/download").content==content


@pytest.mark.parametrize('malformed',['<!DOCTYPE workbook [<!ENTITY example SYSTEM "file:///etc/passwd">]><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">&example;</workbook>','<malformed'])
def test_xlsx_metadata_entities_rejected_without_modifying_master(malformed):
    from zipfile import ZipFile
    from app.controlled import validate_xlsx
    from fastapi import HTTPException
    output=BytesIO()
    with ZipFile(output,'w') as archive:
        archive.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr('xl/workbook.xml',malformed)
    with pytest.raises(HTTPException) as error:validate_xlsx(output.getvalue())
    assert error.value.status_code==422
