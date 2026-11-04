"""The exact five category-granularity gaps observed on deployed 55c7b3e.

Run against newest code on isolated SQLite/PostgreSQL, never mutate the live demo.
"""
import pytest
from tests.test_foundation import client,logged_in
from tests.test_security_history import login_as
from tests.synthetic_workspace import pdf

CASES=[
 ('separate-import.work_instructions','import.work_instructions','work-instruction','document'),
 ('separate-import.supporting_documents','import.supporting_documents','document','work-instruction'),
 ('separate-import.other','import.other','other','document'),
 ('folder-work-instruction','import.work_instructions','work-instruction','other'),
 ('folder-other','import.other','other','work-instruction'),
]

@pytest.mark.parametrize('case,capability,kind,unrelated',CASES,ids=[c[0] for c in CASES])
def test_previously_failed_category(client,case,capability,kind,unrelated):
    web,_=client;logged_in(web)
    created=web.post('/api/admin/users',json={'username':'synthetic-granularity','display_name':'Synthetic Import Employee','role':'Quality','password':'Synthetic-employee-password-123!','site':''})
    assert created.status_code==201;ident=created.json()['id']
    def upload(category,name):
        return web.post('/api/files/import-folder',data={'kind':category,'paths':'Synthetic permission regression/'+name},files={'files':(name,pdf('SYNTHETIC PERMISSION TEST'))})
    login_as(web,'synthetic-granularity','Synthetic-employee-password-123!')
    assert web.get('/api/me').json()['capabilities']==[]
    assert upload(kind,'Denied before grant.pdf').status_code==403
    logged_in(web)
    grant=web.patch(f'/api/admin/accounts/{ident}',json={'current_password':'SufficientlyLongPassword!','capabilities':[capability]})
    assert grant.status_code==200,grant.text
    login_as(web,'synthetic-granularity','Synthetic-employee-password-123!')
    assert web.get('/api/me').json()['capabilities']==[capability]
    allowed=upload(kind,'Explicitly permitted.pdf');assert allowed.status_code==200,allowed.text
    assert allowed.json()['stored']==1
    assert upload(unrelated,'Unrelated denied.pdf').status_code==403
    token=web.cookies['qwoms_token'];csrf=web.cookies['qwoms_csrf']
    logged_in(web)
    assert web.patch(f'/api/admin/accounts/{ident}',json={'current_password':'SufficientlyLongPassword!','capabilities':[]}).status_code==200
    assert web.get('/api/me',headers={'Cookie':'qwoms_token='+token+'; qwoms_csrf='+csrf}).status_code==401
    login_as(web,'synthetic-granularity','Synthetic-employee-password-123!')
    assert upload(kind,'Denied after revoke.pdf').status_code==403
