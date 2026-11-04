"""Inspect outputs from real browser editing. This script never edits a workbook."""
import hashlib,json,sqlite3
from pathlib import Path
from io import BytesIO
from openpyxl import load_workbook
from app.workbook_fidelity import compare
root=Path('work/excel-editor');out=root/'workspace-evidence';fixture=json.loads((root/'workspace-fixture.json').read_text())
results={'originals_unchanged':True,'workbooks':{},'equipment_pdf_byte_identical':True}
cases=[('workspace','S','Shock Validation',{'B5':14},'C5','workspace-completed.xlsx'),
       ('pump','P','Bench readings',{'E5':12,'F5':11},'G5','pump-edited.xlsx'),
       ('injector','I','Flow and leak',{'F9':6,'G9':1},'J11','injector-edited.xlsx'),
       ('unknown',None,'New assembly review',{'Z8':42},'AA8','unknown-edited.xlsx')]
with sqlite3.connect(root/'review.db') as db:
 for key,code,sheet,measurements,formula,file in cases:
  original=Path(fixture['forms'][code]['path']).read_bytes() if code else (Path(fixture['assets'])/'Unseen assembly original.xlsx').read_bytes()
  original_book=load_workbook(BytesIO(original));data=(out/file).read_bytes();book=load_workbook(BytesIO(data));values=load_workbook(BytesIO(data),data_only=True)
  assert book.sheetnames==original_book.sheetnames
  for cell,value in measurements.items():assert book[sheet][cell].value==value,(key,cell,book[sheet][cell].value)
  assert book[sheet][formula].value==original_book[sheet][formula].value
  assert values[sheet][formula].value=='PASS',(key,values[sheet][formula].value)
  assert sorted(str(x) for x in book[sheet].merged_cells.ranges)==sorted(str(x) for x in original_book[sheet].merged_cells.ranges)
  digest=hashlib.sha256(original).hexdigest()
  assert db.execute('select count(*) from stored_files where sha256=?',(digest,)).fetchone()[0]>=1
  for relative,expected in db.execute('select relative_path,sha256 from stored_files where sha256=?',(digest,)):
   assert hashlib.sha256((root/'files'/'files'/relative).read_bytes()).hexdigest()==expected
  if key!='workspace':
   reopened=(out/(key+'-reopened.xlsx')).read_bytes();rebook=load_workbook(BytesIO(reopened));revalues=load_workbook(BytesIO(reopened),data_only=True)
   assert rebook.sheetnames==book.sheetnames
   for cell,value in measurements.items():assert rebook[sheet][cell].value==value
   assert rebook[sheet][formula].value==book[sheet][formula].value and revalues[sheet][formula].value=='PASS'
  results['workbooks'][key]={'reopened_checked_here':key!='workspace','measurement_values':measurements,'cached_formula_result':'PASS','original_formula_retained':True,'worksheets':book.sheetnames,'merged_ranges_retained':True,'fidelity_differences':compare(original,data)['difference_count']}
source=Path(fixture['assets'])/'DYNO - sample 1 original.pdf';assert source.read_bytes()==(out/'downloaded-original.pdf').read_bytes()
(out/'workspace-verified-artifacts.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results))
