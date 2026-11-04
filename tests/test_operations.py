from datetime import datetime,timezone,timedelta
from tests.test_foundation import client,logged_in
from tests.test_security_history import create_order,login_as


def setup(web):
    logged_in(web)
    p=web.post('/api/projects',json={'name':'Fictional operations project'}).json()['id']
    order=create_order(web,project_id=p)
    return p,order


def interval(seconds=3600):
    return {'activity':'Inspection','started_at':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),'duration_seconds':seconds}


def test_approved_project_math_and_total_forklift_exclusion(client):
    web,_=client;p,o=setup(web)
    labor=web.post(f'/api/operations/work-orders/{o}/labor',json=interval()).json()['id']
    assert web.get(f'/api/operations/projects/{p}/chargeback').json()['total_cents']==0
    assert web.post(f'/api/operations/labor/{labor}/approval',json={'rate_cents':2750}).status_code==200
    item=web.post(f'/api/operations/work-orders/{o}/costs',json={'category':'Replacement part','description':'Fictional seal','quantity':3,'unit_cents':125}).json()['id']
    assert web.post(f'/api/operations/costs/{item}/approval',json={}).status_code==200
    assert web.post(f'/api/operations/work-orders/{o}/forklift',json={'duration_seconds':900,'estimated':True,'note':'Fictional internal move'}).status_code==201
    report=web.get(f'/api/operations/projects/{p}/chargeback')
    assert report.json()['total_cents']==3125 and report.json()['labor_seconds']==3600
    assert len(report.json()['lines'])==2 and 'forklift' not in report.text.casefold()
    assert web.post(f'/api/operations/work-orders/{o}/costs',json={'category':'Expense','description':'Forklift time','quantity':1,'unit_cents':0}).status_code==422
    login_as(web,'engineer','OtherLongPassword123!')
    assert web.get(f'/api/operations/projects/{p}/chargeback').status_code==403
    assert web.get(f'/api/operations/work-orders/{o}').json()['forklift']==[]
    assert web.post(f'/api/operations/work-orders/{o}/forklift',json={'duration_seconds':30,'estimated':False,'note':'Fictional move'}).status_code==403


def test_timers_overlap_correction_revokes_approval(client):
    web,_=client;p,o=setup(web)
    first=web.post(f'/api/operations/work-orders/{o}/labor',json={'activity':'Documentation'})
    assert first.status_code==201
    entry=first.json()['id']
    assert web.post(f'/api/operations/work-orders/{o}/labor',json={'activity':'Repair'}).status_code==409
    assert web.post(f'/api/operations/labor/{entry}/approval',json={}).status_code==409
    login_as(web,'engineer','OtherLongPassword123!')
    assert web.post(f'/api/operations/labor/{entry}/stop').status_code==403
    logged_in(web)
    assert web.post(f'/api/operations/labor/{entry}/stop').status_code==200
    assert web.post(f'/api/operations/labor/{entry}/stop').status_code==409
    assert web.post(f'/api/operations/labor/{entry}/approval',json={'rate_cents':3600}).status_code==200
    fix=interval(600);fix.pop('activity');fix['reason']='Fictional correction'
    assert web.patch(f'/api/operations/labor/{entry}',json=fix).status_code==200
    assert web.get(f'/api/operations/projects/{p}/chargeback').json()['lines']==[]
    assert web.post(f'/api/operations/work-orders/{o}/labor',json=interval(600)).status_code==409
    assert any(e['action']=='labor.corrected' for e in web.get('/api/admin/audit').json())


def test_pallet_history_conflicts_and_return_confirmation(client):
    web,_=client;p,o=setup(web)
    body={'identifier':'FICTIONAL-PALLET-1','quantity':80,'original_bin':'Synthetic A1','condition':'Sealed'}
    r=web.post(f'/api/operations/work-orders/{o}/pallets',json=body);assert r.status_code==201
    pallet=r.json()['id']
    assert web.post(f'/api/operations/work-orders/{o}/pallets',json=body).status_code==409
    move={'location':'Synthetic Quality','expected_location':'Synthetic A1','disposition':'Inspection','reason':'Fictional pull'}
    assert web.post(f'/api/operations/pallets/{pallet}/movements',json=move).status_code==200
    assert web.post(f'/api/operations/pallets/{pallet}/movements',json=move).status_code==409
    move.update(location='Synthetic A1',expected_location='Synthetic Quality',disposition='Returned',reason='Fictional return confirmed')
    assert web.post(f'/api/operations/pallets/{pallet}/movements',json=move).status_code==200
    record=web.get(f'/api/operations/work-orders/{o}').json()['pallets'][0]
    assert record['quantity']==80 and record['disposition']=='Returned' and len(record['movements'])==3


def test_invalid_time_and_nonmanagement_approvals(client):
    web,_=client;p,o=setup(web)
    for body in [{'activity':'Forklift'},{'activity':'Inspection','duration_seconds':-1},{'activity':'Repair','started_at':'2026-01-01T00:00:00','duration_seconds':3600}]:
        assert web.post(f'/api/operations/work-orders/{o}/labor',json=body).status_code==422
    entry=web.post(f'/api/operations/work-orders/{o}/labor',json=interval(1)).json()['id']
    login_as(web,'engineer','OtherLongPassword123!')
    assert web.post(f'/api/operations/labor/{entry}/approval',json={}).status_code==403
    assert web.patch(f'/api/operations/labor/{entry}',json={'started_at':interval()['started_at'],'duration_seconds':10,'reason':'Fictional correction'}).status_code==403

def test_person_hours_distinct_from_elapsed_and_closure_timer_gate(client):
    web,_=client;p,o=setup(web)
    body=interval(3600)
    assert web.post(f'/api/operations/work-orders/{o}/labor',json=body).status_code==201
    login_as(web,'engineer','OtherLongPassword123!')
    assert web.post(f'/api/operations/work-orders/{o}/labor',json=body).status_code==201
    data=web.get(f'/api/operations/work-orders/{o}').json()
    assert data['labor_seconds']==7200 and data['recorded_span_seconds']==3600
    timer=web.post(f'/api/operations/work-orders/{o}/labor',json={'activity':'Test'}).json()['id']
    assert web.patch(f'/api/work-orders/{o}',json={'status':'Completed'}).status_code==409
    assert web.post(f'/api/operations/labor/{timer}/stop').status_code==200
    assert web.patch(f'/api/work-orders/{o}',json={'status':'Completed'}).status_code==200
    assert web.post(f'/api/operations/work-orders/{o}/labor',json={'activity':'Repair'}).status_code==409

def test_concurrent_timer_start_has_single_winner(client):
    from concurrent.futures import ThreadPoolExecutor
    web,_=client;p,o=setup(web)
    def start(_):return web.post(f'/api/operations/work-orders/{o}/labor',json={'activity':'Inspection'}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(start,range(2)))==[201,409]
    assert len(web.get(f'/api/operations/work-orders/{o}').json()['labor'])==1
