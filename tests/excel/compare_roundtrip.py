"""Compare workbook features after a REAL external editor round-trip; does not calculate Excel."""
import hashlib,json,sys
from openpyxl import load_workbook


def signature(filename):
    wb=load_workbook(filename)
    result={'sheet_names':wb.sheetnames,'defined_names':{k:v.attr_text for k,v in wb.defined_names.items()},'sheets':{}}
    for ws in wb:
        conditional=[]
        for region,rules in ws.conditional_formatting._cf_rules.items():
            for rule in rules:
                conditional.append({'range':str(region.sqref),'type':rule.type,'operator':rule.operator,'formula':rule.formula,
                                    'fill':str(rule.dxf.fill) if rule.dxf and rule.dxf.fill else None})
        result['sheets'][ws.title]={
            'merges':sorted(str(r) for r in ws.merged_cells.ranges),
            'formulas':{c.coordinate:c.value for row in ws for c in row if c.data_type=='f'},
            'conditional':conditional,
            'validation':[{'range':str(d.sqref),'type':d.type,'formula1':d.formula1,'error':d.error,'showError':d.showErrorMessage} for d in ws.data_validations.dataValidation],
            'columns':{k:v.width for k,v in ws.column_dimensions.items()},
            'rows':{str(k):v.height for k,v in ws.row_dimensions.items() if v.height is not None},
            'print':{'orientation':ws.page_setup.orientation,'paper':ws.page_setup.paperSize,'fitWidth':ws.page_setup.fitToWidth,'fitHeight':ws.page_setup.fitToHeight,'area':str(ws.print_area),'titles':ws.print_title_rows,'margins':str(ws.page_margins),'fitToPage':ws.sheet_properties.pageSetUpPr.fitToPage},
            'freeze':ws.freeze_panes,
            'images':[{'width':i.width,'height':i.height,'sha256':hashlib.sha256(i._data()).hexdigest()} for i in ws._images],
            'important_styles':{coordinate:{'font':str(ws[coordinate].font),'fill':str(ws[coordinate].fill),'alignment':str(ws[coordinate].alignment),'number_format':ws[coordinate].number_format} for coordinate in ['A1','B5','C5']},
        }
    return result


def differences(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        out=[]
        for key in sorted(set(a)|set(b)):
            if key not in a or key not in b:out.append({'feature':path+'.'+key,'before':a.get(key),'after':b.get(key)})
            else:out+=differences(a[key],b[key],path+'.'+key)
        return out
    return [] if a==b else [{'feature':path,'before':a,'after':b}]


if __name__=='__main__':
    result=differences(signature(sys.argv[1]),signature(sys.argv[2]))
    print(json.dumps({'difference_count':len(result),'differences':result},indent=2,default=str))
