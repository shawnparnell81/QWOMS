"""Generate unique synthetic browser fixtures; never read company workbooks."""
import base64
from io import BytesIO
import json
from pathlib import Path
import sys
import time
from openpyxl import Workbook,load_workbook
from tests.excel.synthetic_workbook import workbook_bytes


def generate(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    master=folder/'Synthetic Shock Validation.xlsx';master.write_bytes(workbook_bytes())
    completed=load_workbook(master);completed['Shock Validation']['B5']=12
    completed.save(folder/'Synthetic completed validation.xlsx')
    stamp=str(time.time_ns());number='SYN-DRAW-'+stamp
    data={'drawing_number':number,'part_numbers':{}}
    for label,revision in [('missing',''),('A','A'),('B','B')]:
        pn='SYN-DRAW-PART-'+stamp+'-'+label;data['part_numbers'][label]=pn
        workbook=Workbook();sheet=workbook.active
        sheet.append(['Product Family',"O'Reilly PN",'NAPA PN','Drawing Number','Rev','UPC'])
        sheet.append(['Synthetic drawing acceptance',pn,'',number,revision,''])
        stream=BytesIO();workbook.save(stream);data[label]=base64.b64encode(stream.getvalue()).decode()
    (folder/'drawing-fixtures.json').write_text(json.dumps(data))


if __name__=='__main__':generate(sys.argv[1])
