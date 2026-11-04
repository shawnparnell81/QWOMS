"""Verify actual Chromium free-editor exports, not a server-side editing substitute."""
import hashlib,json,sqlite3,subprocess,zipfile
from pathlib import Path
from io import BytesIO
from openpyxl import load_workbook
from app.free_workbook import package_evidence
from app.workbook_fidelity import compare
root=Path('work/excel-editor');out=root/'free-evidence';fixture=json.loads((root/'workspace-fixture.json').read_text());browser=json.loads((out/'browser-results.json').read_text());checks={'browser_assertions':len(browser['checks']),'master_bytes_unchanged':True,'workbooks':{},'equipment_pdf_identical':True}
assert browser['checks'] and all(c['result']=='PASS' for c in browser['checks'])
with sqlite3.connect(root/'review.db') as db:
 for item in browser['workbooks']:
  key=item['key'];code={'shock':'S','pump':'P','injector':'I'}.get(key)
  original=Path(fixture['forms'][code]['path']).read_bytes() if code else (Path(fixture['assets'])/'Unseen assembly original.xlsx').read_bytes()
  results={}
  for mode in ['edited','reopened']:
   data=(out/(key+'-'+mode+'.xlsx')).read_bytes();book=load_workbook(BytesIO(data));cached=load_workbook(BytesIO(data),data_only=True)
   assert cached[item['sheet']][item['result']].value=='PASS'
   for address,value in item['cells']:assert book[item['sheet']][address].value==float(value)
   diff=compare(original,data);assert diff['difference_count']==0
   parts=package_evidence(original,data);assert parts['same_parts'] and parts['changed_parts']==['xl/worksheets/sheet1.xml']
   results[mode]={'feature_difference_count':0,**parts,'measurement_values':item['cells'],'cached_result':'PASS','worksheets':book.sheetnames,'image_count':sum(len(ws._images) for ws in book)}
  digest=hashlib.sha256(original).hexdigest()
  for path,expected in db.execute('select relative_path,sha256 from stored_files where sha256=?',(digest,)):
   assert hashlib.sha256((root/'files'/'files'/path).read_bytes()).hexdigest()==expected
  checks['workbooks'][key]=results
 assert db.execute('select status from work_orders where id=?',(browser['order_id'],)).fetchone()[0]=='Completed'
 assert db.execute('select count(*) from work_order_evidence where work_order_id=?',(browser['order_id'],)).fetchone()[0]==2
assert (out/'equipment-original.pdf').read_bytes()==(Path(fixture['assets'])/'DYNO - sample 1 original.pdf').read_bytes()
pdf=out/'shock-browser-print.pdf';info=subprocess.check_output(['pdfinfo',str(pdf)],text=True);text=subprocess.check_output(['pdftotext',str(pdf),'-'],text=True)
assert '12.00' in text and 'PASS' in text and 'FICTIONAL SHOCK VALIDATION' in text
assert '841.92 x 594.96 pts (A4)' in info or ('841.' in info and '594.' in info)
checks['browser_print']={'actual_pdf':True,'A4_landscape':True,'measurement_and_PASS':True,'exact_Excel_print_equivalence':False}
checks['exact_visual_fidelity']='NOT CERTIFIED: browser font metrics, wrapping, complex formats and print pagination differ; zero file-feature differences do not prove pixel equivalence.'
(out/'verified-artifacts.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps({'browser_assertions':checks['browser_assertions'],'exported_and_reopened_workbooks':len(checks['workbooks']),'feature_differences':0,'only_value_cache_xml_changed':True,'original_pdf_and_masters_unchanged':True,'browser_print':checks['browser_print']}))
