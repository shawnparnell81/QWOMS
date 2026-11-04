"""Representative synthetic fixture only; never a replacement for an original company form."""
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.drawing.image import Image
from PIL import Image as PILImage


def workbook_bytes(opaque=False, matching_background=False):
    prefix="FF" if opaque else ""
    wb=Workbook();ws=wb.active;ws.title='Shock Validation'
    ws.merge_cells('A1:F1');ws['A1']='FICTIONAL SHOCK VALIDATION — SYNTHETIC ONLY'
    ws['A1'].font=Font(name='Calibri',size=14,bold=True,color=prefix+'FFFFFF')
    ws['A1'].fill=PatternFill('solid',fgColor=prefix+'17365D');ws['A1'].alignment=Alignment(horizontal='center')
    ws.row_dimensions[1].height=30
    ws.column_dimensions['A'].width=28;ws.column_dimensions['B'].width=18;ws.column_dimensions['C'].width=20
    ws['A3']='Acceptance minimum';ws['B3']=10
    ws['A5']='Measured force';ws['B5']=0;ws['B5'].number_format='0.00'
    ws['C5']='=IF(B5>=AcceptanceMinimum,"PASS","FAIL")'
    wb.defined_names.add(DefinedName('AcceptanceMinimum',attr_text="'Shock Validation'!$B$3"))
    for result,color in [('PASS','00B050'),('FAIL','FF0000')]:
        fill=PatternFill('solid',fgColor=prefix+color)
        if matching_background:fill.bgColor=prefix+color
        ws.conditional_formatting.add('C5',CellIsRule(operator='equal',formula=['"'+result+'"'],fill=fill))
    validation=DataValidation(type='list',formula1='"PASS,FAIL"',allow_blank=True)
    validation.errorTitle='Choose a result';validation.error='Choose PASS or FAIL';validation.showErrorMessage=True
    ws.add_data_validation(validation);validation.add('D5')
    ws.merge_cells('A8:C9');ws['A8']='Fictional work instruction: record the measured force and inspect the calculated result.'
    ws['A8'].alignment=Alignment(wrap_text=True,vertical='top')
    ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=0
    ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.print_area='A1:F20';ws.print_title_rows='1:2'
    ws.freeze_panes='B4'
    picture=BytesIO();PILImage.new('RGB',(40,20),(23,54,93)).save(picture,format='PNG');picture.seek(0)
    image=Image(picture);ws.add_image(image,'E3')
    extra=wb.create_sheet('Measurements');extra.append(['Sample','Force']);extra.append(['Fictional sample',12])
    output=BytesIO();wb.save(output);return output.getvalue()


if __name__=='__main__':
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser();parser.add_argument('filename');parser.add_argument('--opaque-colors',action='store_true');parser.add_argument('--matching-conditional-background',action='store_true');args=parser.parse_args()
    Path(args.filename).write_bytes(workbook_bytes(args.opaque_colors,args.matching_conditional_background))
