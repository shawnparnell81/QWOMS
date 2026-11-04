"""Real XLSX input/output and HTTP security for the zero-paid-license editor."""
from io import BytesIO
import hashlib
import zipfile
import pytest
from openpyxl import load_workbook,Workbook
from openpyxl.worksheet.datavalidation import DataValidation
from app import free_workbook as engine
from app.workbook_fidelity import compare
from app.models import WorkbookDraft,AuditEvent,User
from sqlalchemy import select
from tests.synthetic_workspace import workbook
from tests.test_foundation import client,logged_in
from tests.test_workspace import setup_parts,template,new_order
from tests.test_controlled_revisions import approve
from tests.test_security_history import login_as
from app.security import hash_password

CASES=[('shock','Shock Validation',{'B5':'12'},'C5'),('pump','Bench readings',{'E5':'12','F5':'11'},'G5'),('injector','Flow and leak',{'F9':'6','G9':'1'},'J11'),('unknown','New assembly review',{'Z8':'42'},'AA8')]

@pytest.mark.parametrize('variant,sheet,values,result',CASES)
def test_measurements_formulas_colors_package_and_reopen(variant,sheet,values,result):
    original=workbook(variant);book=engine.read(original);edits=[{'sheet':sheet,'address':c,'value':v} for c,v in values.items()]
    engine.apply_values(book,edits);calc=engine.Calculator(book).calculate();assert calc.errors=={}
    model=engine.model(book,calc,sheet);cell=next(c for c in model['cells'] if c['address']==result)
    assert cell['display']=='PASS' and cell['style']['backgroundColor']=='#00b050'
    out=engine.patch_package(original,book,edits,calc);assert compare(original,out)['difference_count']==0
    raw=engine.package_evidence(original,out);assert raw['same_parts'] and raw['changed_parts']==['xl/worksheets/sheet1.xml']
    with zipfile.ZipFile(BytesIO(original)) as a,zipfile.ZipFile(BytesIO(out)) as b:
        for name in a.namelist():
            if name!='xl/worksheets/sheet1.xml':assert a.read(name)==b.read(name),name
    saved=load_workbook(BytesIO(out));cached=load_workbook(BytesIO(out),data_only=True)
    assert cached[sheet][result].value=='PASS'
    for c,v in values.items():assert saved[sheet][c].value==float(v)
    # Reopen/re-edit the same values without a full workbook rewrite.
    reopened=engine.read(out);engine.apply_values(reopened,edits);assert compare(original,engine.patch_package(out,reopened,edits,engine.Calculator(reopened).calculate()))['difference_count']==0
    if variant=='shock':
        assert len(model['images'])==1
        assert next(c for c in model['cells'] if c['address']=='B5')['style']['color']=='#000000'
    failed=engine.read(original);bad=[{'sheet':sheet,'address':list(values)[0],'value':'0'}];engine.apply_values(failed,bad)
    fail_model=engine.model(failed,engine.Calculator(failed).calculate(),sheet);failed_cell=next(c for c in fail_model['cells'] if c['address']==result)
    assert failed_cell['display']=='FAIL' and failed_cell['style']['backgroundColor']=='#ff0000'


def test_validation_protection_formula_injection_and_merges():
    book=engine.read(workbook('shock'))
    with pytest.raises(engine.WorkbookIssue,match='Choose PASS or FAIL'):engine.apply_values(book,[{'sheet':'Shock Validation','address':'D5','value':'OTHER'}])
    for address,value,reason in [('C5','7','formulas'),('B5','=WEBSERVICE("http://example.invalid")','measurement'),('B1','7','top-left')]:
        with pytest.raises(engine.WorkbookIssue,match=reason):engine.apply_values(book,[{'sheet':'Shock Validation','address':address,'value':value}])
    book['Shock Validation'].protection.sheet=True
    with pytest.raises(engine.WorkbookIssue,match='protection'):engine.apply_values(book,[{'sheet':'Shock Validation','address':'B5','value':'10'}])


def test_supported_functions_cross_sheet_names_and_cycles():
    book=Workbook();ws=book.active;ws.title='Readings';book.create_sheet('Limits')['A1']=10;ws['A1']=12;ws['A2']=8
    formulas={'B1':'=SUM(A1:A2)','B2':'=ROUND(2.675,2)','B3':'=IF(AND(A1>=Limits!A1,A2<10),"PASS","FAIL")','B4':'=IFERROR(1/0,42)','B5':'=IF(TRUE,12,UNSUPPORTED(1))','B6':'=MAX(A1:A2)-MIN(A1:A2)','B7':'=AVERAGE(A1:A2)','B8':'=COUNT(A1:A2)','B9':'=ABS(-3)+MOD(7,4)'}
    for address,f in formulas.items():ws[address]=f
    calc=engine.Calculator(book).calculate();assert not calc.errors
    for address,v in {'B1':20,'B2':2.68,'B3':'PASS','B4':42,'B5':12,'B6':4,'B7':10,'B8':2,'B9':6}.items():assert calc.cell('Readings',address)==v
    ws['C1']='=C2';ws['C2']='=C1';assert engine.Calculator(book).calculate().errors


def test_unsupported_formulas_never_save_stale_pass_cache():
    original=workbook('pump');book=engine.read(original);book['Bench readings']['G5']='=UNSUPPORTED(E5)'
    out=BytesIO();book.save(out);original=out.getvalue();book=engine.read(original);calc=engine.Calculator(book).calculate()
    assert 'Unsupported function' in calc.errors[('Bench readings','G5')]
    model=engine.model(book,calc);assert next(c for c in model['cells'] if c['address']=='G5')['display']=='#UNSUPPORTED'
    with pytest.raises(engine.WorkbookIssue,match='Cannot save stale'):engine.patch_package(original,book,[],calc)


def test_custom_numeric_and_list_validation():
    book=Workbook();ws=book.active;ws['A1']=1;ws['B1']=2
    v=DataValidation(type='whole',operator='between',formula1='1',formula2='10');v.add('A1');ws.add_data_validation(v)
    v=DataValidation(type='custom',formula1='B1>A1');v.add('B1');ws.add_data_validation(v)
    with pytest.raises(engine.WorkbookIssue,match='violates'):engine.apply_values(book,[{'sheet':ws.title,'address':'A1','value':'1.5'}])
    book=Workbook();ws=book.active;ws['A1']='PASS';ws['C1']='PASS';ws['C2']='FAIL';v=DataValidation(type='list',formula1='$C$1:$C$2');v.add('A1');ws.add_data_validation(v)
    engine.apply_values(book,[{'sheet':ws.title,'address':'A1','value':'FAIL'}]);assert ws['A1'].value=='FAIL'


@pytest.fixture
def free_attached(client,monkeypatch):
    web,Session=client;parts=setup_parts(web);monkeypatch.setenv('QWOMS_WORKBOOK_ENGINE','free');monkeypatch.setenv('QWOMS_OFFICE_ENABLED','false')
    master=template(web,'FREE-FORM','shock',parts['S300']['id']);approve(web,master['revision_id']);o=new_order(web,parts['S300']).json()['id']
    attachment=web.get(f'/api/work-orders/{o}/attachments').json()[0]
    begin=web.post(f"/api/work-orders/{o}/attachments/{attachment['id']}/editor",json={});assert begin.status_code==201
    assert '/static/free-editor.html' in begin.json()['url'];draft=begin.json()['id']
    return web,Session,o,attachment,draft


def test_free_api_default_no_office_preview_save_export_reopen(free_attached):
    web,Session,o,a,draft=free_attached;base='/api/workbooks/'+draft
    assert web.get('/api/workbook-editor/status').json()['enabled']
    data=web.get(base+'/form').json();assert data['sheet']=='Shock Validation' and data['version']==1
    original=web.get(f"/api/files/{a['file_id']}/download").content
    body={'expected_version':1,'sheet':'Shock Validation','edits':[{'sheet':'Shock Validation','address':'B5','value':'12'}]}
    preview=web.post(base+'/preview',json=body);assert preview.status_code==200
    with Session() as db:assert db.get(WorkbookDraft,draft).content==original
    save=web.patch(base+'/cells',json=body);assert save.status_code==200,save.text
    assert save.json()['version']==2 and save.json()['package']['changed_parts']==['xl/worksheets/sheet1.xml']
    assert web.patch(base+'/cells',json=body).status_code==409
    completed=web.post(base+'/completed',json={'filename':'Employee chosen free workbook.xlsx','expected_version':2});assert completed.status_code==201,completed.text
    assert web.post(base+'/completed',json={'filename':'Employee chosen free workbook.xlsx','expected_version':2}).status_code==409
    reopened=web.post(f"/api/work-orders/{o}/attachments/{a['id']}/editor",json={'completed_id':completed.json()['id']}).json()['id']
    exported=web.get('/api/workbooks/'+reopened+'/export',params={'filename':'Employee export.xlsx'});assert exported.status_code==200
    assert load_workbook(BytesIO(exported.content),data_only=True)['Shock Validation']['C5'].value=='PASS'
    assert compare(original,exported.content)['difference_count']==0
    assert web.get(f"/api/files/{a['file_id']}/download").content==original
    with Session() as db:assert db.scalar(select(AuditEvent).where(AuditEvent.action=='workbook.measurements_saved'))


def test_free_api_access_revocation_closed_orders_and_csrf(free_attached):
    web,Session,o,a,draft=free_attached;base='/api/workbooks/'+draft
    with Session() as db:
        db.add(User(username='free-outsider',display_name='Fictional outsider',role='Quality',password_hash=hash_password('Synthetic-outsider-123!')));db.commit()
    login_as(web,'free-outsider','Synthetic-outsider-123!')
    assert web.post(f"/api/work-orders/{o}/attachments/{a['id']}/editor",json={}).status_code==403
    assert web.get(base+'/form').status_code==404
    assert web.patch(base+'/cells',json={'expected_version':1,'edits':[]}).status_code==404
    logged_in(web);csrf=web.headers.pop('X-QWOMS-CSRF');assert web.post(base+'/preview',json={'expected_version':1,'edits':[]}).status_code==403;web.headers['X-QWOMS-CSRF']=csrf
    assert web.patch(base+'/cells',json={'expected_version':1,'edits':[{'sheet':'Shock Validation','address':'B5','value':'12'}]}).status_code==200
    assert web.post(base+'/completed',json={'filename':'Synthetic read-only completion.xlsx','expected_version':2}).status_code==201
    assert web.patch(f'/api/work-orders/{o}',json={'status':'Completed'}).status_code==200
    assert web.patch(base+'/cells',json={'expected_version':1,'edits':[]}).status_code==409
    assert web.get(base+'/form').json()['read_only']
    assert web.post('/api/auth/logout').status_code==200
    assert web.get(base+'/form').status_code==401


def test_free_api_invalid_values_and_audit_rollback(free_attached,monkeypatch):
    import app.free_editor_api as module
    web,Session,o,a,draft=free_attached;base='/api/workbooks/'+draft
    for address,value in [('C5','0'),('B5','=1+1'),('D5','OTHER')]:
        assert web.patch(base+'/cells',json={'expected_version':1,'edits':[{'sheet':'Shock Validation','address':address,'value':value}]}).status_code==422
    before=web.get(base+'/form').json()['version']
    def failed(*args,**kwargs):raise RuntimeError('Synthetic free editor audit failure')
    monkeypatch.setattr(module,'record',failed)
    with pytest.raises(RuntimeError,match='Synthetic free editor audit failure'):
        web.patch(base+'/cells',json={'expected_version':1,'edits':[{'sheet':'Shock Validation','address':'B5','value':'12'}]})
    assert web.get(base+'/form').json()['version']==before


def test_oversized_merges_are_rejected_before_openpyxl_allocates():
    original=workbook('pump');output=BytesIO()
    with zipfile.ZipFile(BytesIO(original)) as src,zipfile.ZipFile(output,'w') as dst:
        for entry in src.infolist():
            content=src.read(entry.filename)
            if entry.filename=='xl/worksheets/sheet1.xml':content=content.replace(b'A1:H2',b'A1:XFD1048576')
            dst.writestr(entry,content)
    with pytest.raises(engine.WorkbookIssue,match='processing limit'):engine.read(output.getvalue())


def test_text_cells_relative_validation_and_literal_xml_preservation():
    book=Workbook();ws=book.active;ws['A1']='template';ws['A2']='';ws['A2'].number_format='@';ws['B1']=1;ws['B2']=2
    v=DataValidation(type='custom',formula1='B1>0');v.add('B1:B2');ws.add_data_validation(v)
    engine.apply_values(book,[{'sheet':ws.title,'address':'A2','value':'00123'}]);assert ws['A2'].value=='00123'
    with pytest.raises(engine.WorkbookIssue,match='violates'):engine.apply_values(book,[{'sheet':ws.title,'address':'B2','value':'-1'}])
    out=BytesIO();book.save(out);source=out.getvalue();book=engine.read(source)
    edits=[{'sheet':ws.title,'address':'A1','value':'<fictional & literal> "quoted"'}];engine.apply_values(book,edits);result=engine.patch_package(source,book,edits,engine.Calculator(book).calculate())
    assert load_workbook(BytesIO(result)).active['A1'].value=='<fictional & literal> "quoted"'
    assert compare(source,result)['difference_count']==0
