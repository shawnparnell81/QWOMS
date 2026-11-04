from sqlalchemy import select
from tests.test_foundation import client, logged_in, part_import
from app.models import User, AssignmentEvent, AuditEvent
from app.security import hash_password


def login_as(web, username, password):
    response = web.post('/api/auth/login', json={'username': username, 'password': password})
    assert response.status_code == 200
    web.headers['X-QWOMS-CSRF'] = web.cookies['qwoms_csrf']
    return web.cookies['qwoms_token']


def create_order(web, assigned_to=1, project_id=None):
    part_import(web, [['Fictional Shocks', 'SEC-001', 'SEC-ALT-001', '', '', '']])
    part = web.get('/api/parts/search?q=SEC-001').json()[0]
    response = web.post('/api/work-orders', json={
        'order_type': 'Inspection', 'subtype': 'AQL', 'title': 'Fictional security inspection',
        'assigned_to': assigned_to, 'project_id': project_id, 'parts': [{'part_id': part['id'],
         'selected_part_number': 'SEC-001', 'quantity': 1}]})
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_csrf_origin_and_logout_revokes_copied_session(client):
    web, _ = client
    assert web.post('/api/auth/login', headers={'Origin': 'https://untrusted.example'},
                    json={'username': 'manager', 'password': 'SufficientlyLongPassword!'}).status_code == 403
    logged_in(web)
    copied = web.cookies['qwoms_token']
    csrf = web.headers.pop('X-QWOMS-CSRF')
    assert web.post('/api/messages', json={'recipient_id': 2, 'body': 'Fictional message'}).status_code == 403
    web.headers['X-QWOMS-CSRF'] = csrf
    assert web.post('/api/messages', json={'recipient_id': 2, 'body': 'Fictional message'}).status_code == 201
    assert web.post('/api/auth/logout').status_code == 200
    assert web.get('/api/me', headers={'Cookie': 'qwoms_token=' + copied}).status_code == 401


def test_assignment_history_audit_and_production_permissions(client):
    web, Session = client
    with Session() as db:
        employee = User(username='production', display_name='Fictional Production', role='Production',
                        site='Site B', password_hash=hash_password('Fictional-password-123!'))
        db.add(employee)
        db.commit()
        employee_id = employee.id
    logged_in(web)
    order_id = create_order(web)
    assert web.patch(f'/api/work-orders/{order_id}', json={'assigned_to': employee_id}).status_code == 200
    assert web.patch(f'/api/work-orders/{order_id}', json={'assigned_to': employee_id}).status_code == 200
    history = web.get(f'/api/work-orders/{order_id}/assignment-history').json()
    assert len(history) == 2  # Creation plus actual reassignment, not a duplicate save.
    assert history[-1]['previous_user_id'] == 1
    assert history[-1]['assigned_employee'] == 'Fictional Production'
    audit = web.get('/api/admin/audit').json()
    assert any(e['action'] == 'work_order.updated' and e['changes']['assigned_to']['after'] == employee_id for e in audit)
    assert not any('password' in str(e).lower() or 'csrf' in str(e).lower() for e in audit)
    login_as(web, 'production', 'Fictional-password-123!')
    assert web.get('/api/admin/audit').status_code == 403
    assert web.post('/api/admin/users', json={'username': 'forbidden', 'display_name': 'Fictional User',
                    'password': 'Fictional-password-123!', 'role': 'Management'}).status_code == 403
    assert web.patch(f'/api/work-orders/{order_id}', json={'status': 'In Progress'}).status_code == 200
    assert web.patch(f'/api/work-orders/{order_id}', json={'assigned_to': 1}).status_code == 403
    logged_in(web)
    assert web.patch(f'/api/work-orders/{order_id}', json={'assigned_to': None}).status_code == 200
    login_as(web, 'production', 'Fictional-password-123!')
    assert web.patch(f'/api/work-orders/{order_id}', json={'status': 'Closed'}).status_code == 403
    assert web.get('/api/work-orders/999999/assignment-history').status_code == 404
    with Session() as db:
        assert len(db.scalars(select(AssignmentEvent).where(AssignmentEvent.work_order_id == order_id)).all()) == 3
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == 'work_order.created')) is not None


def test_inactive_account_rejected_and_trimmed_identity_validation(client):
    web, Session = client
    logged_in(web)
    body={'username':'    ', 'display_name':'  ', 'role':'Quality','password':'Fictional-password-123!'}
    assert web.post('/api/admin/users', json=body).status_code == 422
    with Session() as db:
        db.get(User, 1).active = False
        db.commit()
    assert web.get('/api/dashboard').status_code == 401


def test_part_import_rolls_back_when_audit_fails(client, monkeypatch):
    import pytest
    import app.main as module
    web, _ = client
    logged_in(web)
    def unavailable(*args, **kwargs):
        raise RuntimeError('Fictional audit failure')
    monkeypatch.setattr(module, 'record', unavailable)
    with pytest.raises(RuntimeError, match='audit failure'):
        part_import(web, [['Fictional Family', 'ROLLBACK-001', '', '', '', '']])
    assert web.get('/api/parts/search?q=ROLLBACK-001').json() == []


import pytest


@pytest.mark.parametrize('role', ['Quality', 'Engineering', 'Production', 'Management'])
def test_department_permission_matrix(client, role):
    web, Session = client
    with Session() as db:
        employee = User(username='roleuser', display_name='Fictional Role User', role=role,
                        site='Site B', password_hash=hash_password('Fictional-role-password!'))
        db.add(employee)
        db.commit()
        employee_id = employee.id
    logged_in(web)
    order_id = create_order(web, employee_id)
    login_as(web, 'roleuser', 'Fictional-role-password!')
    assert web.get('/api/dashboard').status_code == 200
    assert web.get('/api/files').status_code == 200
    assert web.get('/api/messages').status_code == 200
    assert web.get('/api/projects').status_code == 200
    project = web.post('/api/projects', json={'name':'Fictional department project'})
    assert project.status_code == (403 if role == 'Production' else 201)
    if role == 'Production':
        assert web.patch(f'/api/work-orders/{order_id}', json={'project_id':99999}).status_code == 403
    assert web.get('/api/admin/audit').status_code == (200 if role == 'Management' else 403)
    response = web.patch(f'/api/work-orders/{order_id}', json={'assigned_to': 1})
    assert response.status_code == (403 if role == 'Production' else 200)
