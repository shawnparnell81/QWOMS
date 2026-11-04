"""Fictional workbooks and an original equipment-export PDF. No company form layouts."""
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import PatternFill,Font
from openpyxl.formatting.rule import CellIsRule
from openpyxl.worksheet.datavalidation import DataValidation

def workbook(variant):
    w=Workbook();s=w.active
    if variant=='pump':
        s.title='Bench readings';s.merge_cells('A1:H2');s['A1']='SYNTHETIC PUMP BENCH';s['A5']='Sample flow';s['E5']=0;s['F5']=0;s['G5']='=IF(MIN(E5:F5)>=10,"PASS","FAIL")';target='G5';s.column_dimensions['A'].width=30
        w.create_sheet('Equipment context')['A1']='Synthetic equipment, not an approved company master'
    elif variant=='injector':
        s.title='Flow and leak';s.merge_cells('C2:J3');s['C2']='FICTIONAL INJECTOR FLOW';s['F9']=0;s['G9']=0;s['J11']='=IF(AND(F9>=5,G9<=2),"PASS","FAIL")';target='J11';s.column_dimensions['F'].width=22
    elif variant=='shock':
        from tests.excel.synthetic_workbook import workbook_bytes
        return workbook_bytes()
    else:
        s.title='New assembly review';s['N2']='Previously unknown layout';s['Z8']=0;s['AA8']='=IF(Z8=42,"PASS","FAIL")';target='AA8';s.merge_cells('N2:V3');s.column_dimensions['Z'].width=18;w.create_sheet('Trace');w.create_sheet('Notes')
    s['A1'].font=Font(bold=True,size=16)
    for result,color in [('PASS','FF00B050'),('FAIL','FFFF0000')]:s.conditional_formatting.add(target,CellIsRule(operator='equal',formula=['"'+result+'"'],fill=PatternFill('solid',fgColor=color)))
    v=DataValidation(type='list',formula1='"PASS,FAIL"');v.showErrorMessage=True;s.add_data_validation(v);v.add('B12')
    s.page_setup.orientation='landscape';s.page_setup.paperSize=s.PAPERSIZE_A4;s.page_setup.fitToWidth=1
    o=BytesIO();w.save(o);return o.getvalue()


def pdf(label='DYNAMOMETER TEST REPORT'):
    label=label.replace('(','').replace(')','')
    stream=('0.18 0.24 0.42 rg BT /F1 21 Tf 48 735 Td ('+label+') Tj ET\n'
            '0.4 0.47 0.6 rg BT /F1 10 Tf 48 710 Td (SYNTHETIC EQUIPMENT EXPORT - ORIGINAL PDF) Tj ET\n'
            '0.85 0.89 0.96 RG 48 690 m 560 690 l S\n'
            '0.2 0.27 0.4 rg BT /F1 12 Tf 48 652 Td (Equipment: Fictional test bench 01) Tj 0 -23 Td (Sample: 1 / 2) Tj 0 -23 Td (Result: Test completed - engineering review required) Tj ET\n'
            '0.85 0.9 0.96 RG 70 400 m 70 565 l 530 565 l S\n'
            '0.31 0.38 0.83 RG 2 w 70 415 m 140 430 l 210 450 l 280 485 l 350 510 l 425 540 l 530 550 l S\n'
            '0.5 0.58 0.69 rg BT /F1 10 Tf 48 350 Td (Original exported report. QWOMS does not reformat or extract these results.) Tj ET').encode()
    objs=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    out=b'%PDF-1.4\n';offsets=[]
    for i,obj in enumerate(objs,1):offsets.append(len(out));out+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    xref=len(out);out+=b'xref\n0 6\n0000000000 65535 f \n'+b''.join(f'{x:010d} 00000 n \n'.encode() for x in offsets)
    return out+b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(xref).encode()+b'\n%%EOF\n'
