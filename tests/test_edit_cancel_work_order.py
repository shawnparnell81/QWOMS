"""Safe work order editing and cancellation without changing document revisions."""
from sqlalchemy import select
from app.models import WorkOrder, AuditEvent, WorkOrderPart
from tests.test_foundation import client, logged_in
from tests.test_security_history import create_order, login_as


def test_type_specific_metadata_edit_and_cancel_preserves_evidence(client):
    web, Session = client
    logged_in(web)
    order_id=create_order(web)
    before=web.get(f'/api/work-orders/{order_id}').json()
    number=before['number']
    fields={'inspection_scope':'Synthetic underbody check','sampling_plan':'Sample 5','defect_description':'Mock dent'}
    response=web.patch(f'/api/work-orders/{order_id}',json={
        'title':'Updated synthetic inspection',
        'priority':'High',
        'notes':'Edited for morning preview',
        'details':fields})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['title']=='Updated synthetic inspection'
    assert result['priority']=='High'
    assert result['details']==fields
    assert result['parts']==before['parts']
    assert web.patch(f'/api/work-orders/{order_id}',json={
        'details':{'validation_standard':'wrong category'}}).status_code==422
    assert web.patch(f'/api/work-orders/{order_id}',json={'title':' '}).status_code==422
    assert web.post(f'/api/work-orders/{order_id}/cancel',
                    json={'confirm_number':'WRONG','reason':'Synthetic cancellation reason'}).status_code==422
    assert web.post(f'/api/work-orders/{order_id}/cancel',
                    json={'confirm_number':number,'reason':'short'}).status_code==422
    cancelled=web.post(f'/api/work-orders/{order_id}/cancel',json={
        'confirm_number':number,'reason':'Synthetic part was not needed for evaluation'})
    assert cancelled.status_code==200,cancelled.text
    assert cancelled.json()['status']=='Cancelled'
    assert web.get('/api/dashboard').json()['open_count']==0
    assert web.patch(f'/api/work-orders/{order_id}',json={'title':'After cancellation'}).status_code==409
    assert web.post(f'/api/work-orders/{order_id}/cancel',
                    json={'confirm_number':number,'reason':'Duplicate cancellation attempt'}).status_code==409
    with Session() as db:
        order=db.get(WorkOrder,order_id)
        assert order.number==number and order.status=='Cancelled'
        assert db.scalars(select(WorkOrderPart).where(WorkOrderPart.work_order_id==order_id)).first() is not None
        audit=db.scalars(select(AuditEvent).where(AuditEvent.entity_type=='work_order',
                                                  AuditEvent.entity_id==str(order_id))).all()
        assert any(e.action=='work_order.cancelled' and
                   'not needed' in e.changes['reason'] for e in audit)


def test_production_cannot_cancel_or_edit_other_fields(client):
    web,Session=client
    logged_in(web)
    order_id=create_order(web,assigned_to=2)
    order=web.get(f'/api/work-orders/{order_id}').json()
    # Engineering can safely update work content but cannot delete/restore without Administrator rights.
    login_as(web,'engineer','OtherLongPassword123!')
    assert web.patch(f'/api/work-orders/{order_id}',json={'notes':'Engineering review'}).status_code==200
    assert web.post(f'/api/work-orders/{order_id}/archive',json={
        'confirm_number':order['number'],'reason':'Synthetic test of forbidden action'}).status_code==403
    web.post('/api/auth/logout')
    logged_in(web)
    assert web.post(f'/api/work-orders/{order_id}/cancel',json={
        'confirm_number':order['number'],'reason':'Synthetic cancellation before execution'}).status_code==200
