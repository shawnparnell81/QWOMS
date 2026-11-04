"""Synthetic-only isolated local Excel review; never uses an inherited DATABASE_URL."""
import os,secrets,sys,socket,argparse
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--review-root',type=Path,default=Path(__file__).resolve().parent.parent/'work'/'excel-editor')
parser.add_argument('--seed-only',action='store_true')
args=parser.parse_args()
root=args.review_root.resolve()
root.mkdir(parents=True,exist_ok=True)
os.environ['DATABASE_URL']='sqlite:///'+str(root/'review.db')
os.environ['QWOMS_SECRET_KEY']=secrets.token_urlsafe(48)
os.environ['QWOMS_COOKIE_SECURE']='false'
os.environ['QWOMS_DEMO_MODE']='false'
os.environ['QWOMS_STORAGE_ROOT']=str(root/'files')
os.environ['QWOMS_OFFICE_ENABLED']='true'
os.environ['QWOMS_OFFICE_LOCAL_DEVELOPMENT']='true'
os.environ['QWOMS_OFFICE_PUBLIC_URL']='http://127.0.0.1:9980'
os.environ['QWOMS_OFFICE_INTERNAL_URL']='http://127.0.0.1:9980'
os.environ['QWOMS_OFFICE_WOPI_ORIGIN']='http://'+socket.gethostbyname(socket.gethostname())+':8020'
os.environ['QWOMS_OFFICE_APP_ORIGIN']='http://127.0.0.1:8020'
(root/'office-review.env').write_text('QWOMS_REVIEW_WOPI_ORIGIN='+os.environ['QWOMS_OFFICE_WOPI_ORIGIN']+'\n')
from app.db import engine,SessionLocal
from app.schema import upgrade
from app.models import *
from app.security import hash_password
from app.audit import record
from app.storage import original_store
from tests.excel.synthetic_workbook import workbook_bytes
import hashlib
upgrade(engine)
password=secrets.token_urlsafe(24)
with SessionLocal() as db:
 if not db.query(User).first():
  reviewer=User(username='synthetic.reviewer',display_name='Synthetic Quality Manager',role='Management',is_admin=True,password_hash=hash_password(password));db.add(reviewer);db.flush()
  engineer=User(username='synthetic.engineer',display_name='Synthetic Engineering Approver',role='Engineering',capabilities=['engineering.approve'],password_hash=hash_password(password));db.add(engineer);db.flush()
  family=ProductFamily(name='Fictional Shocks');db.add(family);db.flush();part=PhysicalPart(family_id=family.id,description='Fictional Excel editor review part');db.add(part);db.flush();db.add(PartAlias(part_id=part.id,account='Synthetic',part_number='EXCEL-REVIEW-001'))
  blob=workbook_bytes();path='Synthetic editor review/Approved original shock master.xlsx';original_store(root/'files',db).put_new('files/'+path,blob)
  file=StoredFile(relative_path=path,original_name='Approved original shock master.xlsx',kind='form-template',sha256=hashlib.sha256(blob).hexdigest(),uploaded_by=reviewer.id);db.add(file);db.flush()
  document=ControlledDocument(kind='Form template',number='SYNTHETIC-EXCEL-REVIEW',identity_key='synthetic-excel-review',title='Synthetic original shock form');db.add(document);db.flush()
  revision=ControlledRevision(document_id=document.id,file_id=file.id,revision='1',sha256=file.sha256,created_by=reviewer.id,change_summary='Synthetic review fixture only',blank_master_confirmed=True,status='Approved',reviewed_by=engineer.id,approved_by=engineer.id);db.add(revision);db.flush()
  project=Project(name='Synthetic Excel hands-on review',created_by=reviewer.id);db.add(project);db.flush()
  workflow=WorkflowRule(name='Synthetic automatic Excel attachment',order_type='Validation / FAI',part_id=part.id,fields=[],instructions='Record the measured force in the approved workbook.',document_ids=[document.id],created_by=reviewer.id);db.add(workflow);db.flush()
  order=WorkOrder(number='VAL-SYNTHETIC-EDITOR-001',order_type='Validation / FAI',subtype='First Article Inspection',title='Synthetic Excel hands-on work order',assigned_to=reviewer.id,created_by=reviewer.id,project_id=project.id);db.add(order);db.flush()
  db.add(WorkOrderPart(work_order_id=order.id,part_id=part.id,selected_part_number='EXCEL-REVIEW-001',quantity=1))
  from app.workflows import attach,resolve,approved_documents
  db.add(FormFilingRule(order_type='Validation / FAI',subtype='',folder='Validation/Shocks'));db.flush()
  attachment_requirements=resolve(db,part,order.order_type,order.subtype)
  attach(db,order,part,approved_documents(db,attachment_requirements))
  record(db,reviewer,'synthetic.editor_review_seeded','work_order',order.id);db.commit()
 else:
  for user in db.query(User):
   if not user.username.startswith('synthetic.'):raise RuntimeError('Refusing to alter a database containing non-synthetic accounts')
   user.password_hash=hash_password(password)
  db.commit()
path=root/'reviewer.credentials';path.write_text('synthetic.reviewer\n'+password);path.chmod(0o600)
print('Synthetic editor review: http://127.0.0.1:8020 · Private credential file: '+str(path),flush=True)
if args.seed_only:sys.exit(0)
import uvicorn
uvicorn.run('app.main:app',host='0.0.0.0',port=8020,log_level='warning',access_log=False)
