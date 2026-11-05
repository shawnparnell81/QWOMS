"""Archive/restore keeps immutable quality evidence and prevents unauthorized deletion."""
from sqlalchemy import select
from app.models import WorkOrder, WorkOrderPart, AuditEvent
from tests.test_foundation import client, logged_in
from tests.test_security_history import create_order, login_as
from tests.test_operations import interval


def _body(number, reason='Synthetic redundant order created for testing'):
    return {'confirm_number': number, 'reason': reason}


def test_admin_archive_restores_without_erasing_original_work_order(client):
    web, Session = client
    logged_in(web)
    order_id = create_order(web)
    original = web.get(f'/api/work-orders/{order_id}').json()
    num = original['number']
    assert web.get('/api/dashboard').json()['total_work_orders'] == 1
    assert web.post(f'/api/work-orders/{order_id}/archive',
                    json={'confirm_number': 'WRONG', 'reason': 'Synthetic correction'}).status_code == 422
    assert web.post(f'/api/work-orders/{order_id}/archive',
                    json={'confirm_number': num, 'reason': 'no'}).status_code == 422
    archive = web.post(f'/api/work-orders/{order_id}/archive', json=_body(num))
    assert archive.status_code == 200, archive.text
    assert archive.json()['archived'] is True and archive.json()['archive_reason']
    assert web.get('/api/work-orders').json() == []
    assert web.get('/api/dashboard').json()['total_work_orders'] == 0
    assert web.get('/api/work-orders?archived_only=true').json()[0]['id'] == order_id
    assert web.patch(f'/api/work-orders/{order_id}', json={'status':'In Progress'}).status_code == 409
    assert web.post(f'/api/work-orders/{order_id}/archive', json=_body(num)).status_code == 409
    with Session() as db:
        persisted = db.get(WorkOrder, order_id)
        assert persisted.number == num
        assert len(db.scalars(select(WorkOrderPart).where(WorkOrderPart.work_order_id==order_id)).all()) == 1
    login_as(web, 'engineer', 'OtherLongPassword123!')
    assert web.get('/api/work-orders?archived_only=true').status_code == 403
    assert web.get(f'/api/work-orders/{order_id}').status_code == 404
    assert web.post(f'/api/work-orders/{order_id}/restore', json=_body(num)).status_code == 403
    logged_in(web)
    restore = web.post(f'/api/work-orders/{order_id}/restore',
                       json=_body(num, 'Approved restoration of synthetic record'))
    assert restore.status_code == 200, restore.text
    assert restore.json()['archived'] is False
    assert web.get('/api/work-orders').json()[0]['id'] == order_id
    assert web.get('/api/dashboard').json()['total_work_orders'] == 1
    assert web.get('/api/work-orders?archived_only=true').json() == []
    with Session() as db:
        events=db.scalars(select(AuditEvent).where(AuditEvent.entity_type=='work_order', AuditEvent.entity_id==str(order_id))).all()
        assert any(e.action=='work_order.archived' for e in events)
        assert any(e.action=='work_order.restored' for e in events)


def test_active_timers_block_archive_and_existing_labor_preserved(client):
    web,Session=client
    logged_in(web)
    order_id=create_order(web)
    order=web.get(f'/api/work-orders/{order_id}').json()
    num=order['number']
    entry=web.post(f'/api/operations/work-orders/{order_id}/labor',json={'activity':'Inspection'})
    assert entry.status_code == 201
    assert web.post(f'/api/work-orders/{order_id}/archive',json=_body(num)).status_code==409
    assert web.post(f'/api/operations/labor/{entry.json()["id"]}/stop').status_code==200
    assert web.post(f'/api/work-orders/{order_id}/archive',json=_body(num)).status_code==200
    assert web.post(f'/api/operations/work-orders/{order_id}/labor',json=interval(900)).status_code==409
    assert web.get(f'/api/operations/work-orders/{order_id}').json()['labor']
