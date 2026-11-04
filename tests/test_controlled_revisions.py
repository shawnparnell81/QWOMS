import pytest
from tests.test_foundation import client,logged_in,part_import
from tests.test_security_history import login_as


def upload(web,path,kind='drawing',content=b'%PDF-1.4 fictional synthetic drawing'):
    response=web.post('/api/files/import-folder',data={'kind':kind,'paths':path},files={'files':(path.split('/')[-1],content)})
    assert response.status_code==200 and response.json()['stored']==1,response.text
    return next(f for f in web.get('/api/files').json() if f['relative_path']==path)


def order_for(web,pn):
    part=web.get('/api/parts/search?q='+pn).json()[0]
    response=web.post('/api/work-orders',json={'order_type':'Inspection','subtype':'AQL','title':'Fictional controlled inspection',
                  'assigned_to':1,'parts':[{'part_id':part['id'],'selected_part_number':pn,'quantity':1}]})
    assert response.status_code==201,response.text
    return response.json()


def action(web,revision,verb,expected=200):
    response=web.post(f'/api/controlled/revisions/{revision}/actions',json={'action':verb,'reason':'Fictional Engineering review evidence'})
    assert response.status_code==expected,response.text
    return response


def approve(web,revision):
    action(web,revision,'submit')
    login_as(web,'engineer','OtherLongPassword123!')
    action(web,revision,'review');action(web,revision,'approve')
    logged_in(web)


def mapped(web,pn,number,revision):
    part_import(web,[['Fictional Shocks',pn,'',number,revision,'']])
    file=upload(web,f'Synthetic/{pn} original name.PDF')
    response=web.put(f"/api/files/{file['id']}/drawing-mapping",json={'drawing_number':number,'drawing_revision':revision})
    assert response.status_code==200,response.text
    return file,response.json()['controlled_revision_id']


def test_missing_revision_and_unapproved_execution_blocked(client):
    web,_=client;logged_in(web)
    part_import(web,[['Fictional Shocks','MISSING-001','','DRAW-MISSING','','']])
    order=order_for(web,'MISSING-001')
    assert order['parts'][0]['drawing_status']=='Missing revision'
    assert web.patch(f"/api/work-orders/{order['id']}",json={'status':'In Progress'}).status_code==409
    file,revision=mapped(web,'PENDING-001','DRAW-PENDING','A')
    pending=order_for(web,'PENDING-001')
    assert pending['parts'][0]['drawing_status']=='Needs Engineering approval'
    assert web.patch(f"/api/work-orders/{pending['id']}",json={'status':'Completed'}).status_code==409
    approve(web,revision)
    assert web.post(f"/api/controlled/work-orders/{pending['id']}/resolve-drawing-references").status_code==403
    login_as(web,'engineer','OtherLongPassword123!')
    assert web.post(f"/api/controlled/work-orders/{pending['id']}/resolve-drawing-references").status_code==200
    assert web.patch(f"/api/work-orders/{pending['id']}",json={'status':'In Progress'}).status_code==200


def test_supersession_keeps_old_pin_and_rejects_stale_new_execution(client):
    web,_=client;logged_in(web)
    file,a=mapped(web,'REV-A','DRAW-IMMUTABLE','A');approve(web,a)
    old=order_for(web,'REV-A')
    assert old['parts'][0]['controlled_revision_id']==a
    assert old['parts'][0]['drawing_status']=='Approved'
    _,b=mapped(web,'REV-B','DRAW-IMMUTABLE','B');approve(web,b)
    library=web.get('/api/controlled/documents').json()
    revisions=next(d for d in library if d['number']=='DRAW-IMMUTABLE')['revisions']
    assert next(r for r in revisions if r['id']==a)['status']=='Superseded'
    stale=order_for(web,'REV-A')
    assert stale['parts'][0]['drawing_status']=='Superseded'
    assert web.patch(f"/api/work-orders/{stale['id']}",json={'status':'In Progress'}).status_code==409
    historical=web.get(f"/api/work-orders/{old['id']}").json()
    assert historical['parts']==old['parts']
    assert web.patch(f"/api/work-orders/{old['id']}",json={'status':'In Progress'}).status_code==200
    assert web.put(f"/api/files/{file['id']}/drawing-mapping",json={'drawing_number':'DRAW-IMMUTABLE','drawing_revision':'B'}).status_code==409
    assert web.get(f"/api/files/{file['id']}/download").content==b'%PDF-1.4 fictional synthetic drawing'
    login_as(web,'engineer','OtherLongPassword123!');action(web,b,'obsolete')
    logged_in(web)
    withdrawn=order_for(web,'REV-B')
    assert web.patch(f"/api/work-orders/{withdrawn['id']}",json={'status':'Completed'}).status_code==409


@pytest.mark.parametrize('kind',['Work instruction','Supporting document'])
def test_work_related_document_history_and_permissions(client,kind):
    web,_=client;logged_in(web)
    file=upload(web,'Synthetic/Employee named instructions.pdf','document',b'fictional instruction bytes')
    doc=web.post('/api/controlled/documents',json={'kind':kind,'number':'WI-SYN-001','title':'Fictional shock procedure'}).json()
    response=web.post(f"/api/controlled/documents/{doc['id']}/revisions",json={'file_id':file['id'],'revision':'1','change_summary':'Fictional first issue'})
    assert response.status_code==201,response.text
    revision=response.json()['id']
    action(web,revision,'approve',403)
    approve(web,revision)
    library=web.get('/api/controlled/documents').json()[0]
    assert [e['status'] for e in library['revisions'][0]['history']]==['Draft','In Review','Reviewed','Approved']
    assert web.post(f"/api/controlled/documents/{doc['id']}/revisions",json={'file_id':file['id'],'revision':'2','change_summary':'Cannot replace original'}).status_code==409
    assert web.put(f'/api/controlled/revisions/{revision}',json={'revision':'changed'}).status_code==405


def test_author_cannot_self_review_and_approval_cannot_skip_review(client):
    web,Session=client;logged_in(web)
    with Session() as db:
        from app.models import User
        user=db.get(User,2);user.permissions=[*user.permissions,'import.documents'];db.commit()
    file=upload(web,'Synthetic/Engineering authored.pdf','document')
    login_as(web,'engineer','OtherLongPassword123!')
    doc=web.post('/api/controlled/documents',json={'kind':'Work instruction','number':'WI-SELF','title':'Fictional self review test'}).json()
    revision=web.post(f"/api/controlled/documents/{doc['id']}/revisions",json={'file_id':file['id'],'revision':'1','change_summary':'Fictional original'}).json()['id']
    action(web,revision,'submit');action(web,revision,'review',403);action(web,revision,'approve',403)
    logged_in(web);action(web,revision,'review',403)
