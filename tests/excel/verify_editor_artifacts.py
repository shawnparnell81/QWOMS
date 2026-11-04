"""Validate artifacts emitted by REAL Chromium office editing, not a Python editor."""
import hashlib,json,sqlite3,subprocess,sys
from pathlib import Path
from io import BytesIO
from collections import Counter
from openpyxl import load_workbook
from PIL import Image
from app.workbook_fidelity import compare

root=Path(sys.argv[1] if len(sys.argv)>1 else 'work/excel-editor')
result=json.loads((root/'editor-browser-results.json').read_text())
assert all(result.get(key) for key in ('validation_dialog','duplicate_rejected','reopened','exported','reopened_exported','print_pdf'))
connection=sqlite3.connect(root/'review.db')
relative,digest=connection.execute("select relative_path,sha256 from stored_files where kind='form-template' order by id limit 1").fetchone()
original=(root/'files'/'files'/relative).read_bytes()
assert hashlib.sha256(original).hexdigest()==digest
master=load_workbook(BytesIO(original));source=master['Shock Validation']
original_image_hashes=[hashlib.sha256(image._data()).hexdigest() for image in source._images]
checks={'master_sha256_unchanged':True,'source_original_sha256':digest,'exports':{},'visible_colors':{}}
for name in ['editor-export.xlsx','editor-reopened.xlsx']:
    data=(root/name).read_bytes();book=load_workbook(BytesIO(data));values=load_workbook(BytesIO(data),data_only=True);sheet=book['Shock Validation']
    assert book.sheetnames==master.sheetnames
    assert sheet['B5'].value==12 and sheet['C5'].value=='=IF(B5>=AcceptanceMinimum,"PASS","FAIL")'
    assert values['Shock Validation']['C5'].value=='PASS' and sheet['D5'].value=='PASS'
    assert sorted(str(r) for r in sheet.merged_cells.ranges)==sorted(str(r) for r in source.merged_cells.ranges)
    assert len(sheet._images)==1
    assert [hashlib.sha256(image._data()).hexdigest() for image in sheet._images]==original_image_hashes
    assert sheet.page_setup.orientation=='landscape' and sheet.page_setup.paperSize==9 and sheet.page_setup.fitToWidth==1
    assert sheet.print_title_rows==source.print_title_rows and str(sheet.print_area)==str(source.print_area)
    validation=sheet.data_validations.dataValidation[0]
    assert str(validation.sqref)=='D5' and validation.formula1=='"PASS,FAIL"' and validation.showErrorMessage and validation.error=='Choose PASS or FAIL'
    diff=compare(original,data)
    checks['exports'][name]={'measurement':12,'cached_formula_result':'PASS','validation_value':'PASS','sheet_count':len(book.sheetnames),'image_count':len(sheet._images),'landscape_A4_fit_width_1':True,'difference_count':diff['difference_count'],'differences':diff['differences']}
for state in ['pass','fail','final']:
    image=Image.open(root/('editor-'+state+'.png')).convert('RGB')
    pixels=image.crop((392,425,530,439)).tobytes()
    colors=Counter(zip(pixels[0::3],pixels[1::3],pixels[2::3]))
    if state=='fail':expected=sum(count for (r,g,b),count in colors.items() if r>150 and r>g*2 and r>b*2)
    else:expected=sum(count for (r,g,b),count in colors.items() if g>100 and g>r*1.5 and g>b*1.5)
    assert expected>1000,(state,colors.most_common(3))
    checks['visible_colors'][state]={'colored_cell_pixels':expected,'dominant_RGB':colors.most_common(1)[0][0]}
pdf=(root/'editor-print.pdf').read_bytes();assert pdf.startswith(b'%PDF-')
text=subprocess.check_output(['pdftotext',str(root/'editor-print.pdf'),'-'],text=True)
assert '12.00 PASS' in text and 'FICTIONAL SHOCK VALIDATION' in text
info=subprocess.check_output(['pdfinfo',str(root/'editor-print.pdf')],text=True)
assert '841.89 x 595.' in info and 'Pages:           2' in info
checks['print']={'actual_office_pdf':True,'pages':2,'first_page_landscape_A4':True,'measurement_and_PASS_in_print':True}
saved=result['saved'];stored=connection.execute('select work_order_id,project_id from completed_forms where id=?',(saved['id'],)).fetchone()
assert stored==(1,1) and saved['relative_path'].endswith('/'+saved['filename'])
checks['completed_link']={'work_order_id':1,'project_id':1,'filename':saved['filename'],'relative_path':saved['relative_path']}
(root/'editor-verified-artifacts.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps({'master_unchanged':True,'keyboard_measurement':12,'cached_formula_result':'PASS','validation_dialog':True,'visible_colors':checks['visible_colors'],'reopened_xlsx':True,'print':checks['print'],'measured_fidelity_differences':{k:v['difference_count'] for k,v in checks['exports'].items()}}))
