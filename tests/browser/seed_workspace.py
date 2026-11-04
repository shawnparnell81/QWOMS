"""Populate only the isolated local review app with clearly fictional workspace fixtures."""
import hashlib,json,time,subprocess,shutil
from pathlib import Path
from io import BytesIO
from datetime import datetime,timedelta,timezone
import httpx
from openpyxl import Workbook
from PIL import Image,ImageDraw
from tests.synthetic_workspace import workbook,pdf
root=Path('work/excel-editor');assets=root/'workspace-assets';assets.mkdir(exist_ok=True)
username,password=(root/'reviewer.credentials').read_text().splitlines()
base='http://127.0.0.1:8020';stamp=str(int(time.time()));prefix='SYN-'+stamp[-6:]
owner=httpx.Client(base_url=base,timeout=30);engineer=httpx.Client(base_url=base,timeout=30)
def login(client,name):
 r=client.post('/api/auth/login',json={'username':name,'password':password});assert r.status_code==200
 client.headers['X-QWOMS-CSRF']=client.cookies['qwoms_csrf']
def request(client,method,path,**kwargs):
 r=client.request(method,path,**kwargs)
 if not r.is_success:raise RuntimeError(f'Synthetic setup {method} {path}: HTTP {r.status_code}')
 return r.json()
login(owner,username);login(engineer,'synthetic.engineer')
rows=Workbook();sheet=rows.active;sheet.append(['Product Family',"O'Reilly PN",'NAPA PN','Drawing Number','Rev','UPC'])
for code,family,draw in [('S','Synthetic Suspension','FIC-DWG-'+stamp[-6:]),('P','Synthetic Fuel Systems',''),('I','Synthetic Fuel Systems','')]:sheet.append([family,prefix+'-'+code,'ALT-'+prefix+'-'+code,draw,'C' if draw else '',''])
out=BytesIO();rows.save(out);request(owner,'POST','/api/parts/import/commit',files={'file':('Synthetic physical parts.xlsx',out.getvalue())})
parts={code:request(owner,'GET','/api/parts/search?q='+prefix+'-'+code)[0] for code in ['S','P','I']}
def approve(revision_id):
 for client,action in [(owner,'submit'),(engineer,'review'),(engineer,'approve')]:request(client,'POST',f'/api/controlled/revisions/{revision_id}/actions',json={'action':action,'reason':'Independent synthetic workspace fixture review'})
def original(kind,name,body):
 path='Synthetic workspace '+stamp+'/'+name
 request(owner,'POST','/api/files/import-folder',data={'kind':kind,'paths':path},files={'files':(name,body)})
 return next(f for f in request(owner,'GET','/api/files') if f['relative_path']==path)
def controlled(kind,number,title,file,revision):
 doc=request(owner,'POST','/api/controlled/documents',json={'kind':kind,'number':number,'title':title})
 rev=request(owner,'POST',f"/api/controlled/documents/{doc['id']}/revisions",json={'file_id':file['id'],'revision':revision,'change_summary':'Fictional original for integrated workspace testing'})
 approve(rev['id']);return doc
file=original('drawing','Fictional strut engineering drawing.pdf',pdf('ENGINEERING DRAWING - SYNTHETIC'))
drawing=controlled('Drawing','FIC-DWG-'+stamp[-6:],'Fictional strut assembly drawing',file,'C')
wi=original('work-instruction','WI - Synthetic load and dimensional checks.pdf',pdf('WORK INSTRUCTION - SYNTHETIC'))
instruction=controlled('Work instruction','WI-'+stamp[-6:],'Synthetic validation work instruction',wi,'2')
request(owner,'POST','/api/workflow/rules',json={'name':'Synthetic suspension instructions '+stamp,'order_type':'Validation / FAI','part_id':parts['S']['id'],
 'instructions':'Inspect sample identification, record dimensional and load measurements, then retain the original equipment PDFs. Refer to the pinned approved instruction.','document_ids':[instruction['id']]})
forms={}
for code,variant,title in [('S','shock','Strut load and dimensional validation'),('P','pump','Pump bench acceptance'),('I','injector','Injector flow and leakage acceptance')]:
 body=workbook(variant);filename='Synthetic '+variant+' validation master.xlsx';(assets/filename).write_bytes(body)
 template=request(owner,'POST','/api/form-templates',data={'number':'FORM-'+prefix+'-'+code,'title':title,'revision':'1','order_type':'Validation / FAI','part_id':str(parts[code]['id']),'blank_master_confirmed':'true'},files={'file':(filename,body)})
 approve(template['revision_id']);forms[code]={**template,'path':str(assets/filename)}
project=request(owner,'POST','/api/projects',json={'name':'Synthetic component qualification','description':'Hands-on integrated workspace testing with fictional parts and unmodified equipment PDFs.'})
orders={}
for code in ['S','P','I']:
 p=parts[code];preview=request(owner,'POST','/api/workflow/preview',json={'order_type':'Validation / FAI','subtype':'First Article Inspection','part_ids':[p['id']]})[str(p['id'])]
 title={'S':'Strut assembly qualification','P':'Pump bench qualification','I':'Injector flow qualification'}[code]
 orders[code]=request(owner,'POST','/api/work-orders',json={'order_type':'Validation / FAI','subtype':'First Article Inspection','title':title,'priority':'High' if code=='S' else 'Normal',
  'project_id':project['id'],'assigned_to':1,'details':{'sample_quantity':'2','validation_standard':'Synthetic dimensional & load protocol','acceptance_criteria':'Use the approved original workbook and retain raw test evidence.'},
  'parts':[{'part_id':p['id'],'selected_part_number':p['aliases'][1]['part_number'],'quantity':2,'rule_ids':preview['rule_ids']}]})
main=orders['S']['id']
for filename,title,sample,equipment in [('DYNO - sample 1 original.pdf','DYNAMOMETER TEST REPORT','Sample 1','Fictional dynamometer 01'),('SPRING - sample 2 original.pdf','SPRING RATE TEST REPORT','Sample 2','Fictional spring bench 02')]:
 body=pdf(title);(assets/filename).write_bytes(body);request(owner,'POST',f'/api/work-orders/{main}/evidence',data={'category':'Test result','part_id':parts['S']['id'],'sample':sample,'equipment':equipment,'description':'Original synthetic equipment export; no reformatting or metric extraction.'},files={'file':(filename,body)})
image=Image.new('RGB',(960,600),'#f7f9fd');d=ImageDraw.Draw(image);d.rounded_rectangle((408,115,535,505),radius=25,fill='#a7b7ca',outline='#7387a2',width=7);d.rectangle((458,65,488,220),fill='#c9d5e2');d.ellipse((425,35,520,115),outline='#556c8c',width=15)
for y in range(235,430,30):d.line((370,y,570,y+20),fill='#455b77',width=12)
d.text((35,35),'FICTIONAL TEST FIXTURE - SYNTHETIC ONLY',fill='#445976');out=BytesIO();image.save(out,format='PNG');photo=out.getvalue();(assets/'Synthetic strut fixture.png').write_bytes(photo)
request(owner,'POST',f'/api/work-orders/{main}/evidence',data={'category':'Photo','part_id':parts['S']['id'],'description':'Synthetic fixture illustration for upload and preview acceptance.'},files={'file':('Synthetic strut fixture.png',photo)})
clip=assets/'Synthetic bench overview.mp4'
if shutil.which('ffmpeg'):subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=0x6474bd:s=480x270:d=1','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart','-y',str(clip)],check=True)
if clip.exists():request(owner,'POST',f'/api/work-orders/{main}/evidence',data={'category':'Video','part_id':parts['S']['id'],'description':'One-second synthetic test clip.'},files={'file':(clip.name,clip.read_bytes())})
for client,seconds in [(owner,1800),(engineer,900)]:request(client,'POST',f'/api/operations/work-orders/{main}/labor',json={'activity':'Validation','started_at':(datetime.now(timezone.utc)-timedelta(hours=3)).isoformat(),'duration_seconds':seconds,'note':'Synthetic fixture measurement setup'})
(assets/'Unseen assembly original.xlsx').write_bytes(workbook('unknown'))
fixture={'prefix':prefix,'main_order_id':main,'orders':{k:v['id'] for k,v in orders.items()},'parts':{k:v['id'] for k,v in parts.items()},'forms':forms,'project_id':project['id'],'assets':str(assets),'drawing_id':drawing['id'],'instruction_id':instruction['id']}
(root/'workspace-fixture.json').write_text(json.dumps(fixture,indent=2))
print(json.dumps({'synthetic_workspace_order':main,'url':base+'/#work-order-'+str(main),'templates':3,'evidence':4 if clip.exists() else 3,'labor_person_hours':0.75}))
