from io import BytesIO
import hashlib
import pytest
from sqlalchemy import select
from tests.test_foundation import client,logged_in,part_import
from tests.test_security_history import login_as
from tests.test_controlled_revisions import approve,upload
from tests.synthetic_workspace import workbook,pdf
from app.models import User,WorkOrderEvidence,ControlledDocument,StoredFile,AuditEvent
from app.security import hash_password


def setup_parts(web):
    logged_in(web)
    assert part_import(web,[['Fictional Pumps','P100','NP100','','',''],['Fictional Injectors','I200','NI200','','',''],['Fictional Shocks','S300','NS300','','','']]).status_code==200
    return {pn:web.get('/api/parts/search?q='+pn).json()[0] for pn in ['P100','I200','S300']}


def template(web,number,variant,part=None,family=None,subtype=''):
    body={'number':number,'title':'Fictional '+number,'revision':'1','order_type':'Validation / FAI','subtype':subtype,'blank_master_confirmed':'true'}
    if part:body['part_id']=str(part)
    if family:body['family_id']=str(family)
    r=web.post('/api/form-templates',data=body,files={'file':(number+' original.xlsx',workbook(variant))})
    assert r.status_code==201,r.text
    return r.json()


def new_order(web,part,alias=None,subtype='First Article Inspection',assigned_to=None):
    preview=web.post('/api/workflow/preview',json={'order_type':'Validation / FAI','subtype':subtype,'part_ids':[part['id']]}).json()[str(part['id'])]
    r=web.post('/api/work-orders',json={'order_type':'Validation / FAI','subtype':subtype,'title':'Fictional integrated validation',
        'assigned_to':assigned_to,'parts':[{'part_id':part['id'],'selected_part_number':alias or part['aliases'][0]['part_number'],'quantity':2,'rule_ids':preview['rule_ids']}]})
    return r


def test_upload_defined_dissimilar_forms_unknown_fourth_and_retirement(client):
    web,Session=client;parts=setup_parts(web);before=web.get('/api/dashboard').json()['total_work_orders']
    templates=[]
    for number,variant,pn in [('PUMP-FORM','pump','P100'),('INJECTOR-FORM','injector','I200'),('SHOCK-FORM','shock','S300')]:
        t=template(web,number,variant,parts[pn]['id']);templates.append(t)
        assert new_order(web,parts[pn]).status_code==409
        approve(web,t['revision_id'])
    assert web.get('/api/dashboard').json()['total_work_orders']==before
    orders=[]
    for t,pn in zip(templates,['P100','I200','S300']):
        o=new_order(web,parts[pn],parts[pn]['aliases'][1]['part_number']);assert o.status_code==201,o.text;orders.append(o.json()['id'])
        a=web.get(f"/api/work-orders/{o.json()['id']}/attachments").json();assert len(a)==1 and a[0]['number'] in ('PUMP-FORM','INJECTOR-FORM','SHOCK-FORM')
        assert a[0]['revision_id']==t['revision_id']
        assert hashlib.sha256(web.get(f"/api/files/{a[0]['file_id']}/download").content).hexdigest()==t['sha256']
    fourth=template(web,'UNKNOWN-FOURTH','unknown',parts['P100']['id'],subtype='Product Validation');approve(web,fourth['revision_id'])
    o=new_order(web,parts['P100'],subtype='Product Validation');assert o.status_code==201
    assert web.get(f"/api/work-orders/{o.json()['id']}/attachments").json()[0]['revision_id']==fourth['revision_id']
    first=templates[0]
    assert web.post(f"/api/form-templates/{first['id']}/retire").status_code==200
    assert first['id'] not in [t['id'] for t in web.get('/api/form-templates').json()]
    assert first['id'] not in [d['id'] for d in web.get('/api/controlled/documents').json()]
    new=new_order(web,parts['P100']);assert new.status_code==201
    assert web.get(f"/api/work-orders/{new.json()['id']}/attachments").json()==[]
    historical=web.get(f'/api/work-orders/{orders[0]}/attachments').json()[0]
    assert historical['revision_id']==first['revision_id'] and historical['template_retired']
    assert web.get(f"/api/files/{historical['file_id']}/download").status_code==200
    assert web.post(f"/api/form-templates/{first['id']}/restore").status_code==200
    assert web.get('/api/form-templates').json()


def test_specific_form_overrides_family_and_revisions_do_not_rewrite_history(client):
    web,_=client;parts=setup_parts(web);p=parts['P100'];family=template(web,'FAMILY','pump',family=p['family'] if isinstance(p['family'],int) else next(f['id'] for f in web.get('/api/parts/families').json() if f['name']==p['family']))
    approve(web,family['revision_id']);specific=template(web,'SPECIFIC','injector',p['id']);approve(web,specific['revision_id'])
    old=new_order(web,p);assert old.status_code==201
    attachment=web.get(f"/api/work-orders/{old.json()['id']}/attachments").json()[0];assert attachment['revision_id']==specific['revision_id']
    f=upload(web,'Synthetic replacement/different layout.xlsx','form-template',workbook('unknown'))
    r=web.post(f"/api/controlled/documents/{specific['id']}/revisions",json={'file_id':f['id'],'revision':'2','change_summary':'Different uploaded original layout','blank_master_confirmed':True})
    assert r.status_code==201;approve(web,r.json()['id'])
    newer=new_order(web,p);assert newer.status_code==201
    assert web.get(f"/api/work-orders/{newer.json()['id']}/attachments").json()[0]['revision']=='2'
    assert web.get(f"/api/work-orders/{old.json()['id']}/attachments").json()[0]['revision']=='1'


def test_pdf_originals_multiple_persistence_access_duplicates_and_audit(client):
    web,Session=client;parts=setup_parts(web);o=new_order(web,parts['P100']).json()['id']
    with Session() as db:
        for name in ['technician','outsider']:db.add(User(username=name,display_name='Synthetic '+name,role='Quality',password_hash=hash_password('Synthetic-password-123!')))
        db.commit();technician=db.scalar(select(User).where(User.username=='technician')).id
    assert web.patch(f'/api/work-orders/{o}',json={'assigned_to':technician}).status_code==200
    login_as(web,'technician','Synthetic-password-123!')
    assert web.get('/api/me').json()['capabilities']==[]
    original=pdf();endpoint=f'/api/work-orders/{o}/evidence'
    saved=web.post(endpoint,data={'category':'Test result','part_id':parts['P100']['id'],'sample':'1','equipment':'Fictional bench'},files={'file':('Original equipment result.pdf',original)})
    assert saved.status_code==201,saved.text;e=saved.json();assert e['filename']=='Original equipment result.pdf' and e['sha256']==hashlib.sha256(original).hexdigest()
    response=web.get(e['url']);assert response.status_code==200 and response.content==original and response.headers['content-type'].startswith('application/pdf')
    assert response.headers['x-frame-options']=='SAMEORIGIN'
    assert web.post(endpoint,files={'file':('Original equipment result.pdf',pdf('DIFFERENT ORIGINAL'))}).status_code==409
    assert web.post(endpoint,files={'file':('Second original.pdf',pdf('SECOND SAMPLE'))}).status_code==201
    assert web.post(endpoint,files={'file':('not-a-report.pdf',b'not PDF')}).status_code==422
    assert web.post(endpoint,files={'file':('../unsafe.pdf',original)}).status_code==422
    assert web.post(endpoint,data={'part_id':99999},files={'file':('Wrong part.pdf',original)}).status_code==422
    assert len(web.get(f'/api/work-orders/{o}/workspace').json()['evidence'])==2
    with Session() as db:
        assert db.get(WorkOrderEvidence,e['id']).content==original
        assert db.scalar(select(AuditEvent).where(AuditEvent.action=='evidence.uploaded'))
    login_as(web,'outsider','Synthetic-password-123!')
    assert web.get(e['url']).status_code==403
    assert web.post(endpoint,files={'file':('Denied.pdf',original)}).status_code==403
    web.cookies.clear();assert web.get(e['url']).status_code==401


def test_evidence_failure_is_atomic_and_import_permission_is_separate(client,monkeypatch):
    import app.workspace_api as module
    web,Session=client;parts=setup_parts(web);o=new_order(web,parts['P100']).json()['id']
    def failed(*args,**kwargs):raise RuntimeError('Synthetic audit failure')
    monkeypatch.setattr(module,'record',failed)
    with pytest.raises(RuntimeError,match='Synthetic audit failure'):
        web.post(f'/api/work-orders/{o}/evidence',files={'file':('Rollback.pdf',pdf())})
    with Session() as db:assert db.scalar(select(WorkOrderEvidence.id)) is None
    login_as(web,'engineer','OtherLongPassword123!')
    assert web.post('/api/form-templates',data={'number':'DENIED','title':'Denied form','revision':'1','blank_master_confirmed':'true'},files={'file':('Denied.xlsx',workbook('pump'))}).status_code==403


def test_conditional_disposition_separate_and_explicitly_approved(client):
    web,_=client;parts=setup_parts(web);o=new_order(web,parts['P100']).json()['id']
    assert web.post(f'/api/work-orders/{o}/disposition',json={'result':'Conditional Pass'}).status_code==422
    r=web.post(f'/api/work-orders/{o}/disposition',json={'result':'Conditional Pass','rationale':'Synthetic failed measurement exception pending independent review'})
    assert r.status_code==201 and r.json()['state']=='Pending Engineering'
    assert web.patch(f'/api/work-orders/{o}',json={'status':'Completed'}).status_code==409
    assert web.post(f"/api/work-orders/{o}/disposition/{r.json()['id']}/approve").status_code==403
    login_as(web,'engineer','OtherLongPassword123!')
    assert web.get(f'/api/work-orders/{o}/workspace').status_code==200
    assert web.post(f"/api/work-orders/{o}/disposition/{r.json()['id']}/approve").status_code==200
    logged_in(web)
    assert web.patch(f'/api/work-orders/{o}',json={'status':'Completed'}).status_code==200
    assert web.post(f'/api/work-orders/{o}/evidence',files={'file':('Closed.pdf',pdf())}).status_code==409

def test_template_failure_has_no_phantom_records_or_orphan_original(client,monkeypatch):
    import app.template_api as module
    from app import main
    web,Session=client;parts=setup_parts(web)
    before={p for p in main.STORAGE_ROOT.rglob('*') if p.is_file()} if main.STORAGE_ROOT.exists() else set()
    def fail(*args,**kwargs):raise RuntimeError('Synthetic library audit failure')
    monkeypatch.setattr(module,'record',fail)
    with pytest.raises(RuntimeError,match='Synthetic library audit failure'):
        web.post('/api/form-templates',data={'number':'ATOMIC','title':'Fictional atomic template','revision':'1','part_id':parts['P100']['id'],'blank_master_confirmed':'true'},files={'file':('Original arbitrary workbook.xlsx',workbook('unknown'))})
    with Session() as db:
        assert db.scalar(select(ControlledDocument).where(ControlledDocument.number=='ATOMIC')) is None
        assert db.scalar(select(StoredFile).where(StoredFile.original_name=='Original arbitrary workbook.xlsx')) is None
    after={p for p in main.STORAGE_ROOT.rglob('*') if p.is_file()} if main.STORAGE_ROOT.exists() else set()
    assert before==after


def test_image_video_evidence_and_byte_ranges(client):
    from PIL import Image
    web,_=client;parts=setup_parts(web);o=new_order(web,parts['P100']).json()['id']
    image=BytesIO();Image.new('RGB',(12,12),'blue').save(image,format='PNG')
    endpoint=f'/api/work-orders/{o}/evidence'
    r=web.post(endpoint,data={'category':'Photo'},files={'file':('Synthetic photo.png',image.getvalue())});assert r.status_code==201
    assert web.get(r.json()['url']).content==image.getvalue()
    clip=b'\x00\x00\x00\x18ftypmp42'+b'\x00'*20
    r=web.post(endpoint,data={'category':'Video'},files={'file':('Synthetic range fixture.mp4',clip)});assert r.status_code==201
    assert web.get(r.json()['url'],headers={'Range':'bytes=4-7'}).content==b'ftyp'
    response=web.get(r.json()['url'],headers={'Range':'bytes=4-1000'});assert response.status_code==206 and response.content==clip[4:]
    assert web.get(r.json()['url'],headers={'Range':'bytes=-5'}).content==clip[-5:]
    assert web.get(r.json()['url'],headers={'Range':'bytes=1000-'}).status_code==416


def test_retired_source_is_not_an_active_matching_rule_or_picker(client):
    web,_=client;parts=setup_parts(web);t=template(web,'RETIRE-ONLY','unknown',parts['P100']['id']);approve(web,t['revision_id'])
    assert web.post(f"/api/form-templates/{t['id']}/retire").status_code==200
    rule=next(r for r in web.get('/api/workflow/rules').json() if r['id']==t['rule_id'])
    assert not rule['active'] and rule['document_ids']==[]
    assert web.post('/api/workflow/rules',json={'name':'Denied stale selection','order_type':'Validation / FAI','document_ids':[t['id']]}).status_code==422


def test_form_library_explicit_individual_grant_and_immediate_revoke(client):
    web,Session=client;parts=setup_parts(web)
    rights=['engineering.approve','import.form_masters']
    assert web.patch('/api/admin/accounts/2',json={'current_password':'SufficientlyLongPassword!','capabilities':rights}).status_code==200
    login_as(web,'engineer','OtherLongPassword123!')
    uploaded=template(web,'INDIVIDUALLY-GRANTED','unknown',parts['P100']['id'])
    # Import authority does not remove the independent-author Engineering guard.
    assert web.post(f"/api/controlled/revisions/{uploaded['revision_id']}/actions",json={'action':'submit','reason':'Synthetic delegated upload'}).status_code==200
    assert web.post(f"/api/controlled/revisions/{uploaded['revision_id']}/actions",json={'action':'review','reason':'Denied author self-review'}).status_code==403
    assert web.post(f"/api/form-templates/{uploaded['id']}/retire").status_code==200
    logged_in(web)
    assert web.patch('/api/admin/accounts/2',json={'current_password':'SufficientlyLongPassword!','capabilities':['engineering.approve']}).status_code==200
    login_as(web,'engineer','OtherLongPassword123!')
    assert web.post('/api/form-templates',data={'number':'REVOKED','title':'Synthetic revoked upload','revision':'1','blank_master_confirmed':'true'},files={'file':('Denied.xlsx',workbook('pump'))}).status_code==403
    assert web.post(f"/api/form-templates/{uploaded['id']}/restore").status_code==403
    with Session() as db:
        events=db.scalars(select(AuditEvent).where(AuditEvent.entity_id=='2',AuditEvent.action.in_(['permission.granted','permission.revoked']))).all()
        assert {e.action for e in events}=={'permission.granted','permission.revoked'}
