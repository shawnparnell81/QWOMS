"""Dashboard values must reflect persisted work records, not demo UI numbers."""
from tests.test_foundation import client,logged_in
from tests.test_security_history import create_order
from tests.test_operations import interval


def test_work_order_and_completed_labor_dashboard_totals(client):
    web,_=client
    logged_in(web)
    order1=create_order(web)
    order2=create_order(web)
    before=web.get('/api/dashboard')
    assert before.status_code==200
    assert before.json()['total_work_orders']==2
    assert before.json()['in_progress_count']==0
    assert before.json()['completed_count']==0
    assert before.json()['labor_seconds']==0
    assert web.patch(f'/api/work-orders/{order1}',json={'status':'In Progress'}).status_code==200
    assert web.patch(f'/api/work-orders/{order2}',json={'status':'Completed'}).status_code==200
    entry=web.post(f'/api/operations/work-orders/{order1}/labor',json=interval(3600))
    assert entry.status_code==201,entry.text
    data=web.get('/api/dashboard').json()
    assert data['total_work_orders']==2
    assert data['in_progress_count']==1
    assert data['completed_count']==1
    assert data['labor_seconds']==3600
