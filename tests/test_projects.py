from tests.test_foundation import client, logged_in
from tests.test_security_history import create_order, login_as


def test_projects_link_independent_orders_and_audit(client):
    web, _ = client
    logged_in(web)
    response = web.post('/api/projects', json={'name':'Fictional shock investigation', 'description':'Synthetic project'})
    assert response.status_code == 201
    project_id = response.json()['id']
    first, second = create_order(web, project_id=project_id), create_order(web)
    for order in [first, second]:
        assert web.patch(f'/api/work-orders/{order}', json={'project_id': project_id}).status_code == 200
    assert web.patch(f'/api/work-orders/{first}', json={'status':'Completed'}).status_code == 200
    project = web.get(f'/api/projects/{project_id}').json()
    assert project['work_order_count'] == 2 and project['open_work_order_count'] == 1
    assert {o['id'] for o in project['work_orders']} == {first, second}
    assert web.patch(f'/api/work-orders/{second}', json={'project_id':None}).status_code == 200
    assert web.get('/api/projects').json()[0]['work_order_count'] == 1
    assert web.get(f'/api/work-orders/{first}').json()['status'] == 'Completed'
    assert web.patch(f'/api/work-orders/{second}', json={'project_id':99999}).status_code == 422
    assert web.get('/api/projects/99999').status_code == 404
    assert web.post('/api/projects', json={'name':'   '}).status_code == 422
    assert any(e['action']=='project.created' for e in web.get('/api/admin/audit').json())
    login_as(web, 'engineer', 'OtherLongPassword123!')
    assert web.get(f'/api/projects/{project_id}').status_code == 200
