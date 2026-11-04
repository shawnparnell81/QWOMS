"""Workbook-derived form editing with a bounded, non-executing formula interpreter.

openpyxl reads metadata only. Export patches values/caches in the original ZIP XML;
no workbook serializer rewrites styles, drawings, relationships or print settings.
"""
import base64
import hashlib
import io
import json
import math
import operator
import posixpath
import re
import zipfile
from decimal import Decimal,ROUND_HALF_UP,InvalidOperation
from datetime import date,datetime
from xml.sax.saxutils import escape
from defusedxml import ElementTree as ET
from openpyxl import load_workbook
from openpyxl.formula import Tokenizer
from openpyxl.formula.translate import Translator
from openpyxl.styles.colors import COLOR_INDEX
from openpyxl.utils import get_column_letter,range_boundaries
from openpyxl.utils.datetime import to_excel

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
MAX_CELLS=20000

class WorkbookIssue(ValueError):pass
class FormulaIssue(ValueError):pass


def flatten(value):
    if isinstance(value,list):
        for item in value:yield from flatten(item)
    else:yield value


def number(v):
    if v is None or v=='':return 0
    if isinstance(v,(int,float,bool)):return v
    try:return float(v)
    except (ValueError,TypeError):raise FormulaIssue('#VALUE!')


def compare_values(a,b,op):
    if isinstance(a,str) and isinstance(b,str):a,b=a.casefold(),b.casefold()
    elif a is None or b is None:a,b=(0 if a is None else a),(0 if b is None else b)
    try:return {'=':operator.eq,'<>':operator.ne,'>':operator.gt,'<':operator.lt,'>=':operator.ge,'<=':operator.le}[op](a,b)
    except TypeError:raise FormulaIssue('#VALUE!')


class FormulaParser:
    """Parse Excel tokens to data, never Python eval/exec or external calls."""
    precedence={'=':1,'<>':1,'>':1,'<':1,'>=':1,'<=':1,'&':2,'+':3,'-':3,'*':4,'/':4,'^':5}
    def __init__(self,text):
        if len(text)>8192:raise FormulaIssue('Formula length limit')
        try:self.tokens=[t for t in Tokenizer(text if text.startswith('=') else '='+text).items if t.type!='WHITE-SPACE']
        except Exception:raise FormulaIssue('Unsupported formula syntax')
        if len(self.tokens)>1000:raise FormulaIssue('Formula token limit')
        self.i=0
    def take(self):
        if self.i>=len(self.tokens):raise FormulaIssue('Incomplete formula')
        t=self.tokens[self.i];self.i+=1;return t
    def expression(self,minimum=0):
        t=self.take()
        if t.type=='OPERAND':left=('value',t.subtype,t.value)
        elif t.type=='OPERATOR-PREFIX':left=('unary',t.value,self.expression(6))
        elif (t.type,t.subtype)==('PAREN','OPEN'):
            left=self.expression();end=self.take()
            if (end.type,end.subtype)!=('PAREN','CLOSE'):raise FormulaIssue('Unclosed expression')
        elif (t.type,t.subtype)==('FUNC','OPEN'):
            args=[]
            if self.i<len(self.tokens) and (self.tokens[self.i].type,self.tokens[self.i].subtype)!=('FUNC','CLOSE'):
                while True:
                    args.append(self.expression())
                    if self.i<len(self.tokens) and self.tokens[self.i].type=='SEP':self.i+=1;continue
                    break
            end=self.take()
            if (end.type,end.subtype)!=('FUNC','CLOSE'):raise FormulaIssue('Unclosed function')
            left=('call',t.value[:-1].upper().removeprefix('_XLFN.'),args)
        else:raise FormulaIssue('Unsupported formula construct')
        while self.i<len(self.tokens):
            t=self.tokens[self.i]
            if t.type=='OPERATOR-POSTFIX' and t.value=='%':self.i+=1;left=('percent',left);continue
            prec=self.precedence.get(t.value) if t.type=='OPERATOR-INFIX' else None
            if prec is None or prec<minimum:break
            self.i+=1;left=('binary',t.value,left,self.expression(prec if t.value=='^' else prec+1))
        return left
    def parse(self):
        node=self.expression()
        if self.i!=len(self.tokens):raise FormulaIssue('Unsupported formula syntax')
        return node


class Calculator:
    def __init__(self,book):self.book=book;self.cache={};self.visiting=set();self.steps=0;self.errors={};self.style_errors=set()
    def cell(self,sheet,address):
        key=(sheet,address.replace('$','').upper());self.steps+=1
        if self.steps>150000:raise FormulaIssue('Calculation work limit')
        if key in self.cache:return self.cache[key]
        if key in self.visiting or len(self.visiting)>100:raise FormulaIssue('Circular/deep formula reference')
        if sheet not in self.book.sheetnames:raise FormulaIssue('#REF!')
        value=self.book[sheet][key[1]].value
        if self.book[sheet][key[1]].data_type=='f':
            if not isinstance(value,str):raise FormulaIssue('Array/data-table formulas are preserved but calculation is unsupported')
            self.visiting.add(key)
            try:value=self.evaluate(value,sheet)
            finally:self.visiting.remove(key)
        if isinstance(value,(datetime,date)):value=to_excel(value,self.book.epoch)
        self.cache[key]=value;return value
    def reference(self,text,sheet):
        if any(x in text for x in ('[',']','#')):raise FormulaIssue('Unsupported external/structured reference')
        if '!' in text:
            name,text=text.rsplit('!',1);sheet=name.strip("'").replace("''", "'")
        elif not re.fullmatch(r'\$?[A-Za-z]{1,3}\$?\d+(?::\$?[A-Za-z]{1,3}\$?\d+)?',text):
            defined=self.book[sheet].defined_names.get(text) or self.book.defined_names.get(text)
            if not defined:raise FormulaIssue('Unsupported name '+text)
            return self.evaluate('='+defined.attr_text,sheet)
        if not re.fullmatch(r'\$?[A-Za-z]{1,3}\$?\d+(?::\$?[A-Za-z]{1,3}\$?\d+)?',text):raise FormulaIssue('Unsupported reference '+text)
        lo,top,hi,bottom=range_boundaries(text)
        if (hi-lo+1)*(bottom-top+1)>MAX_CELLS or bottom>1048576 or hi>16384:raise FormulaIssue('Range limit')
        values=[self.cell(sheet,f'{get_column_letter(c)}{r}') for r in range(top,bottom+1) for c in range(lo,hi+1)]
        return values if ':' in text else values[0]
    def evaluate(self,text,sheet):return self.node(FormulaParser(text).parse(),sheet)
    def node(self,n,sheet):
        kind=n[0]
        if kind=='value':
            _,sub,value=n
            if sub=='NUMBER':return float(value)
            if sub=='TEXT':return value[1:-1].replace('""','"')
            if sub=='LOGICAL':return value.upper()=='TRUE'
            if sub=='RANGE':return self.reference(value,sheet)
            raise FormulaIssue(value)
        if kind=='unary':return number(self.node(n[2],sheet))*(-1 if n[1]=='-' else 1)
        if kind=='percent':return number(self.node(n[1],sheet))/100
        if kind=='binary':
            a,b=self.node(n[2],sheet),self.node(n[3],sheet);op=n[1]
            if op in ('=','<>','>','<','>=','<='):return compare_values(a,b,op)
            if op=='&':
                joined=str(a if a is not None else '')+str(b if b is not None else '')
                if len(joined)>32767:raise FormulaIssue('Calculated text length limit')
                return joined
            a,b=number(a),number(b)
            if op=='^' and (abs(b)>100 or abs(a)>1e100):raise FormulaIssue('Exponent limit')
            try:value={'+':operator.add,'-':operator.sub,'*':operator.mul,'/':operator.truediv,'^':operator.pow}[op](a,b)
            except (ZeroDivisionError,OverflowError,ValueError):raise FormulaIssue('#DIV/0! or #NUM!')
            if not isinstance(value,(int,float)) or not math.isfinite(value):raise FormulaIssue('#NUM!')
            return value
        name,args=n[1],n[2]
        if name=='IF':
            if len(args) not in (2,3):raise FormulaIssue('IF argument count')
            return self.node(args[1],sheet) if self.node(args[0],sheet) else self.node(args[2],sheet) if len(args)>2 else False
        if name=='IFERROR':
            if len(args)!=2:raise FormulaIssue('IFERROR argument count')
            try:return self.node(args[0],sheet)
            except FormulaIssue:return self.node(args[1],sheet)
        values=[self.node(a,sheet) for a in args];flat=list(flatten(values));nums=[v for v in flat if isinstance(v,(int,float)) and not isinstance(v,bool)]
        try:
            if name=='AND':return all(bool(v) for v in flat)
            if name=='OR':return any(bool(v) for v in flat)
            if name=='NOT' and len(values)==1:return not bool(values[0])
            if name=='SUM':return sum(nums)
            if name=='MIN':return min(nums,default=0)
            if name=='MAX':return max(nums,default=0)
            if name=='AVERAGE':return sum(nums)/len(nums)
            if name=='COUNT':return len(nums)
            if name=='COUNTA':return sum(v is not None and v!='' for v in flat)
            if name=='ABS' and len(values)==1:return abs(number(values[0]))
            if name=='INT' and len(values)==1:return math.floor(number(values[0]))
            if name=='SQRT' and len(values)==1:return math.sqrt(number(values[0]))
            if name=='MOD' and len(values)==2:return number(values[0])%number(values[1])
            if name=='ROUND' and len(values)==2:
                digits=int(number(values[1]))
                if abs(digits)>30:raise FormulaIssue('ROUND digit limit')
                return float(Decimal(str(number(values[0]))).quantize(Decimal(1).scaleb(-digits),rounding=ROUND_HALF_UP))
            if name=='LEN' and len(values)==1:return len(str(values[0] or ''))
            if name=='TRIM' and len(values)==1:return ' '.join(str(values[0] or '').split())
            if name=='UPPER' and len(values)==1:return str(values[0] or '').upper()
            if name=='LOWER' and len(values)==1:return str(values[0] or '').lower()
            if name=='ISNUMBER' and len(values)==1:return isinstance(values[0],(int,float)) and not isinstance(values[0],bool)
        except (ZeroDivisionError,ValueError,OverflowError,InvalidOperation):raise FormulaIssue('#VALUE! or #NUM!')
        raise FormulaIssue('Unsupported function '+name)
    def calculate(self):
        for ws in self.book:
            for c in list(ws._cells.values()):
                if c.data_type=='f':
                    try:self.cell(ws.title,c.coordinate)
                    except (FormulaIssue,RecursionError) as e:self.errors[(ws.title,c.coordinate)]=str(e)
        return self


def read(blob):
    from .editor_api import validate_for_editor
    validate_for_editor(blob)
    with zipfile.ZipFile(io.BytesIO(blob)) as package:
        stored=0;merged=0
        for name in package.namelist():
            if name.startswith('xl/worksheets/') and name.endswith('.xml'):
                root=ET.fromstring(package.read(name))
                stored+=sum(1 for _ in root.iter('{'+NS+'}c'))
                for item in root.iter('{'+NS+'}mergeCell'):
                    left,top,right,bottom=range_boundaries(item.get('ref'))
                    merged+=(right-left+1)*(bottom-top+1)
                if stored+merged>100000:raise WorkbookIssue('Workbook exceeds the stored/merged-cell processing limit; original remains available')
    book=load_workbook(io.BytesIO(blob),data_only=False)
    if sum(len(ws._cells) for ws in book)>100000:raise WorkbookIssue('Workbook exceeds the 100,000 stored-cell processing limit; original remains available')
    return book


def typed(value,cell,book):
    if value is None or value=='':return None
    if len(value)>32767:raise WorkbookIssue('Cell text exceeds Excel length limit')
    if any(ord(c)<32 and c not in '\t\n\r' for c in value):raise WorkbookIssue('Unsupported control character in cell')
    if value.startswith('='):raise WorkbookIssue('Enter measurement values; existing formulas are preserved and read-only')
    if cell.number_format=='@':return value
    if value.upper() in ('TRUE','FALSE'):return value.upper()=='TRUE'
    if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',value):
        number_value=float(value)
        if not math.isfinite(number_value) or abs(number_value)>1e100:raise WorkbookIssue('Measurement outside supported numeric range')
        return number_value
    if cell.is_date:
        try:return datetime.fromisoformat(value)
        except ValueError:raise WorkbookIssue('Enter an ISO date/time for this date-formatted cell')
    return value


def validation_formula(rule,text,address):
    if not address or not text:return text
    base=min(rule.sqref.ranges,key=lambda r:(r.min_row,r.min_col));origin=f'{get_column_letter(base.min_col)}{base.min_row}'
    try:return Translator(text if text.startswith('=') else '='+text,origin=origin).translate_formula(address)
    except Exception:raise WorkbookIssue('Unsupported relative validation formula')


def options(rule,calc,sheet,address=None):
    text=rule.formula1 or ''
    if text.startswith('"') and text.endswith('"'):return text[1:-1].split(',')
    try:return [str(v) for v in flatten(calc.evaluate(validation_formula(rule,text,address),sheet)) if v is not None]
    except FormulaIssue:return None


def validate_measurements(book,edits):
    calc=Calculator(book)
    for edit in edits:
        ws=book[edit['sheet']];cell=ws[edit['address']]
        for rule in ws.data_validations.dataValidation:
            if cell.coordinate not in rule:continue
            if cell.value is None and rule.allowBlank:continue
            try:
                kind=rule.type;value=cell.value
                if kind=='list':
                    allowed=options(rule,calc,ws.title,cell.coordinate)
                    if allowed is None:raise WorkbookIssue('Unsupported dropdown source at '+cell.coordinate)
                    ok=str(value if value is not None else '') in allowed
                elif kind in ('whole','decimal','date','time','textLength'):
                    v=len(str(value or '')) if kind=='textLength' else to_excel(value,book.epoch) if isinstance(value,(datetime,date)) else number(value)
                    a=calc.evaluate(validation_formula(rule,rule.formula1 or '0',cell.coordinate),ws.title);b=calc.evaluate(validation_formula(rule,rule.formula2 or '0',cell.coordinate),ws.title)
                    op=rule.operator or 'between'
                    ok={'between':lambda:a<=v<=b,'notBetween':lambda:not a<=v<=b,'equal':lambda:v==a,'notEqual':lambda:v!=a,'greaterThan':lambda:v>a,'greaterThanOrEqual':lambda:v>=a,'lessThan':lambda:v<a,'lessThanOrEqual':lambda:v<=a}[op]()
                    if kind=='whole':ok=ok and float(v).is_integer()
                elif kind=='custom':ok=bool(calc.evaluate(validation_formula(rule,rule.formula1,cell.coordinate),ws.title))
                elif not kind:continue
                else:raise WorkbookIssue('Unsupported validation '+kind)
            except (FormulaIssue,TypeError,KeyError):raise WorkbookIssue('Validation could not be evaluated at '+cell.coordinate)
            if not ok:raise WorkbookIssue((rule.error or 'Value violates the original workbook validation')+' ('+cell.coordinate+')')


def apply_values(book,edits):
    seen=set()
    if len(edits)>5000:raise WorkbookIssue('At most 5,000 measurements per save')
    for edit in edits:
        sheet,address=edit['sheet'],edit['address'].upper();key=(sheet,address)
        if key in seen:raise WorkbookIssue('Duplicate cell edit')
        seen.add(key)
        if sheet not in book.sheetnames or not re.fullmatch(r'[A-Z]{1,3}[1-9]\d{0,6}',address):raise WorkbookIssue('Unknown worksheet or invalid cell address')
        ws=book[sheet];col,row,_,_=range_boundaries(address)
        if row>ws.max_row or col>ws.max_column:raise WorkbookIssue('Measurement lies outside the uploaded form used range')
        cell=ws[address]
        if cell.row>1048576 or cell.column>16384:raise WorkbookIssue('Cell outside Excel worksheet')
        if ws.sheet_state!='visible':raise WorkbookIssue('Hidden worksheets are read-only in this editor')
        if cell.data_type=='f':raise WorkbookIssue('Existing formulas are read-only')
        if ws.protection.sheet and cell.protection.locked:raise WorkbookIssue('Original workbook cell protection prohibits this edit')
        for merged in ws.merged_cells.ranges:
            if address in merged and address!=merged.start_cell.coordinate:raise WorkbookIssue('Edit the top-left cell of the merged range')
        if getattr(cell,'data_type',None)=='n' and isinstance(cell.value,str):raise WorkbookIssue('Unsupported cell type')
        cell.value=typed(edit['value'],cell,book)
    validate_measurements(book,edits)


def sheet_paths(archive):
    wb=ET.fromstring(archive.read('xl/workbook.xml'));rels=ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    targets={r.get('Id'):r.get('Target') for r in rels}
    result={}
    for sheet in wb.find('{'+NS+'}sheets'):
        target=targets[sheet.get('{'+REL+'}id')];path=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        if not path.startswith('xl/worksheets/'):raise WorkbookIssue('Unsupported worksheet relationship')
        result[sheet.get('name')]=path
    return result


def xml_value(value,formula=False):
    if value is None:return '', ''
    if isinstance(value,bool):return 'b', '<v>'+('1' if value else '0')+'</v>'
    if isinstance(value,(datetime,date)):value=to_excel(value)
    if isinstance(value,(int,float)):
        if not math.isfinite(value):raise WorkbookIssue('Nonfinite calculated value')
        return 'n','<v>'+format(value,'.15g')+'</v>'
    if formula:return 'str','<v>'+escape(str(value))+'</v>'
    return 'inlineStr','<is><t xml:space="preserve">'+escape(str(value))+'</t></is>'


def patch_cell(xml,address,value,formula=False):
    # Only cell values and cached results change; surrounding XML is retained verbatim.
    pattern=r'<(?P<q>(?:\w+:)?)c\b(?=[^>]*\br=["\']'+re.escape(address)+r'["\'])[^>]*(?:/>|>.*?</(?P=q)c>)'
    found=re.search(pattern,xml,re.S)
    if not found:
        if formula:raise WorkbookIssue('Formula cell XML not found')
        payload_type,payload=xml_value(value)
        cell='<c r="'+address+'"'+(' t="'+payload_type+'"' if payload_type else '')+'>'+payload+'</c>'
        row_num=int(re.search(r'\d+',address)[0]);row_match=re.search(r'<row\b(?=[^>]*\br=["\']'+str(row_num)+r'["\'])[^>]*(?:/>|>.*?</row>)',xml,re.S)
        if not row_match:raise WorkbookIssue('This unused row has no original XML row; choose an existing form row')
        row=row_match.group(0)
        if row.endswith('/>'):newrow=row[:-2]+'>'+cell+'</row>'
        else:
            col=range_boundaries(address)[0];insert=None
            for c in re.finditer(r'<c\b[^>]*\br=["\']([A-Z]+\d+)["\'][^>]*',row):
                if range_boundaries(c.group(1))[0]>col:insert=c.start();break
            insert=insert if insert is not None else row.rfind('</row>');newrow=row[:insert]+cell+row[insert:]
        return xml[:row_match.start()]+newrow+xml[row_match.end():]
    raw=found.group(0);prefix=found.group('q');end=raw.index('>')+1;opening=raw[:end];body='' if opening.endswith('/>') else raw[end:raw.rfind('</')]
    # Extensions in editable cells are not interpreted; refuse rather than alter them.
    if re.search(r'<(?:\w+:)?extLst\b',body):raise WorkbookIssue('Cell extension metadata is preserved; editing this cell is unsupported')
    body=re.sub(r'<'+re.escape(prefix)+r'(?:v|is)\b[^>]*(?:/>|>.*?</'+re.escape(prefix)+r'(?:v|is)>)','',body,flags=re.S)
    t,payload=xml_value(value,formula)
    if prefix:payload=re.sub(r'<(/?)(v|is|t)(?=[ >])',r'<\1'+prefix+r'\2',payload)
    opening=re.sub(r'\s+t=["\'][^"\']*["\']','',opening)
    opening=opening[:-2]+'>' if opening.endswith('/>') else opening
    if t:opening=opening[:-1]+' t="'+t+'">'
    patched=opening+body+payload+'</'+prefix+'c>'
    return xml[:found.start()]+patched+xml[found.end():]


def patch_package(blob,book,edits,calc):
    if calc.errors:raise WorkbookIssue('Cannot save stale formula results: '+ '; '.join(s+'!'+a+': '+e for (s,a),e in list(calc.errors.items())[:5]))
    changes={}
    for e in edits:changes.setdefault(e['sheet'],{})[e['address'].upper()]=(book[e['sheet']][e['address'].upper()].value,False)
    for ws in book:
        for cell in list(ws._cells.values()):
            if cell.data_type=='f':changes.setdefault(ws.title,{})[cell.coordinate]=(calc.cell(ws.title,cell.coordinate),True)
    output=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(blob)) as source,zipfile.ZipFile(output,'w') as target:
        paths=sheet_paths(source);updated={}
        for sheet,values in changes.items():
            try:xml=source.read(paths[sheet]).decode('utf-8')
            except UnicodeDecodeError:raise WorkbookIssue('Non-UTF-8 worksheet XML is preserved but cannot be edited by this version')
            for address,(value,formula) in values.items():xml=patch_cell(xml,address,value,formula)
            ET.fromstring(xml);updated[paths[sheet]]=xml.encode('utf-8')
        for entry in source.infolist():target.writestr(entry,updated.get(entry.filename,source.read(entry.filename)))
        target.comment=source.comment
    return output.getvalue()


def package_evidence(original,edited):
    with zipfile.ZipFile(io.BytesIO(original)) as a,zipfile.ZipFile(io.BytesIO(edited)) as b:
        names=a.namelist();same=set(names)==set(b.namelist())
        changed=[n for n in names if n not in b.namelist() or a.read(n)!=b.read(n)]
        return {'same_parts':same,'changed_parts':changed,'unchanged_parts':len(names)-len(changed),'original_sha256':hashlib.sha256(original).hexdigest(),'edited_sha256':hashlib.sha256(edited).hexdigest()}


def color(value,book,default=None):
    if not value:return default
    if value.type=='rgb':rgb=value.rgb[-6:]
    elif value.type=='indexed':rgb=COLOR_INDEX[value.indexed][-6:] if value.indexed<len(COLOR_INDEX) else None
    elif value.type=='theme' and book.loaded_theme:
        root=ET.fromstring(book.loaded_theme);scheme=root.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}clrScheme')
        try:
            theme_order=[1,0,3,2,4,5,6,7,8,9,10,11];node=list(scheme)[theme_order[value.theme]][0];rgb=node.get('lastClr') or node.get('val')
        except (IndexError,TypeError):rgb=None
    else:rgb=None
    if not rgb or not re.fullmatch('[0-9a-fA-F]{6}',rgb):return default
    tint=value.tint or 0
    channels=[int(rgb[i:i+2],16) for i in (0,2,4)]
    if tint:channels=[round(v*(1+tint) if tint<0 else v*(1-tint)+255*tint) for v in channels]
    return '#'+''.join(f'{max(0,min(255,v)):02x}' for v in channels)


def css_style(cell,book,dxf=None):
    font=dxf.font if dxf and dxf.font else cell.font;fill=dxf.fill if dxf and dxf.fill else cell.fill
    align=dxf.alignment if dxf and dxf.alignment else cell.alignment;border=dxf.border if dxf and dxf.border else cell.border
    result={'fontFamily':json.dumps(font.name or cell.font.name or 'Calibri')+', Carlito, "Liberation Sans", Arial, sans-serif','fontSize':str(font.sz or cell.font.sz or 11)+'pt','fontWeight':'700' if font.b else '400','fontStyle':'italic' if font.i else 'normal',
        'color':color(font.color,book,'#172338'),'backgroundColor':color(fill.fgColor,book,'#ffffff') if fill.patternType=='solid' else '#ffffff',
        'textAlign':align.horizontal if align.horizontal in ('left','center','right','justify') else 'right' if isinstance(cell.value,(int,float)) else 'left',
        'verticalAlign':{'center':'middle','top':'top','bottom':'bottom'}.get(align.vertical,'bottom'),'whiteSpace':'pre-wrap' if align.wrap_text else 'pre',
        'textDecoration':'underline' if font.u else 'line-through' if font.strike else 'none'}
    for name in ['left','right','top','bottom']:
        side=getattr(border,name)
        if side and side.style:
            thickness=3 if side.style=='thick' else 2 if side.style in ('medium','double') else 1
            line='double' if side.style=='double' else 'dashed' if 'dash' in side.style.lower() else 'dotted' if side.style=='dotted' else 'solid'
            result['border'+name.title()]=f'{thickness}px {line} '+color(side.color,book,'#334155')
    if align.textRotation:result['--cell-rotation']=str(align.textRotation)+'deg'
    return result


def conditional_style(ws,cell,calc):
    candidates=[]
    for region,rules in ws.conditional_formatting._cf_rules.items():
        if cell.coordinate in region.sqref:
            for rule in rules:candidates.append((rule.priority,rule,region))
    result=None
    for _,rule,region in sorted(candidates,key=lambda item:item[0]):
        try:
            base=next(iter(region.sqref.ranges));origin=f'{get_column_letter(base.min_col)}{base.min_row}'
            def operand(i):
                f=rule.formula[i];f=f if f.startswith('=') else '='+f
                return calc.evaluate(Translator(f,origin=origin).translate_formula(cell.coordinate),ws.title)
            value=calc.cell(ws.title,cell.coordinate)
            op=rule.operator
            if rule.type=='cellIs':
                a=operand(0)
                if op in ('between','notBetween'):
                    match=a<=value<=operand(1);match=not match if op=='notBetween' else match
                else:match=compare_values(value,a,{'equal':'=','notEqual':'<>','greaterThan':'>','lessThan':'<','greaterThanOrEqual':'>=','lessThanOrEqual':'<='}[op])
            elif rule.type=='expression':match=bool(operand(0))
            elif rule.type in ('containsText','notContainsText','beginsWith','endsWith'):
                text=str(value or '').casefold();needle=(rule.text or '').casefold();match=needle in text if rule.type=='containsText' else needle not in text if rule.type=='notContainsText' else text.startswith(needle) if rule.type=='beginsWith' else text.endswith(needle)
            elif rule.type=='containsBlanks':match=value is None or str(value).strip()==''
            elif rule.type=='notContainsBlanks':match=value is not None and str(value).strip()!=''
            else:continue
            if match and rule.dxf:
                if result is None:result=rule.dxf
                if rule.stopIfTrue:break
        except (FormulaIssue,ValueError,TypeError,KeyError) as error:
            calc.style_errors.add(ws.title+'!'+cell.coordinate+': conditional rule not rendered ('+str(error)+')');continue
    return result


def display(value,fmt):
    if value is None:return ''
    if isinstance(value,bool):return 'TRUE' if value else 'FALSE'
    if isinstance(value,(datetime,date)):return value.isoformat(sep=' ') if isinstance(value,datetime) else value.isoformat()
    if isinstance(value,(int,float)):
        if fmt=='General':return format(value,'.12g')
        section=fmt.split(';')[0];percent='%' in section
        cleaned=re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', '',section)
        decimal=re.search(r'\.([0#]+)',cleaned);digits=len(decimal.group(1)) if decimal else 0
        if re.search('[0#]',cleaned) and not re.search(r'[ymdhHsS]',cleaned):
            grouping=',' in cleaned.split('.')[0]
            return format(value*(100 if percent else 1),(',' if grouping else '')+'.'+str(digits)+'f')+('%' if percent else '')
        return format(value,'.12g')
    return str(value)


def model(book,calc,sheet=None):
    visible=[ws.title for ws in book if ws.sheet_state=='visible']
    sheet=sheet or visible[0]
    if sheet not in visible:raise WorkbookIssue('Choose a visible worksheet')
    ws=book[sheet];cols=min(max(ws.max_column,1),100);rows=min(max(ws.max_row,1),500,MAX_CELLS//cols)
    warnings=['Browser layout and printing are not certified identical to Microsoft Excel. Original XLSX formatting parts are preserved on save.']
    if ws.max_row>rows or ws.max_column>cols:warnings.append(f'Browser view limited to {rows} rows × {cols} columns; undisplayed original cells remain in the file.')
    if calc.errors:warnings.extend(s+'!'+a+': '+e for (s,a),e in list(calc.errors.items())[:20])
    unsupported=sorted({r.type for rules in ws.conditional_formatting._cf_rules.values() for r in rules if r.type not in ('cellIs','expression','containsText','notContainsText','beginsWith','endsWith','containsBlanks','notContainsBlanks')})
    if unsupported:warnings.append('Conditional rules preserved but not rendered: '+', '.join(unsupported))
    if ws._charts:warnings.append('Charts are preserved in XLSX but are not rendered in this browser view.')
    if any(c.alignment.textRotation for c in ws._cells.values()):warnings.append('Rotated text is preserved in XLSX; browser rotation is approximate.')
    merges=[];covered=set();anchors={}
    for region in ws.merged_cells.ranges:
        if region.max_row>rows or region.max_col>cols:continue
        merges.append(str(region));anchors[region.start_cell.coordinate]=(region.max_row-region.min_row+1,region.max_col-region.min_col+1)
        for r,c in region.cells:
            if (r,c)!=(region.min_row,region.min_col):covered.add((r,c))
    cells=[]
    for r in range(1,rows+1):
        for c in range(1,cols+1):
            if (r,c) in covered:continue
            cell=ws.cell(r,c);formula=(cell.value if isinstance(cell.value,str) else getattr(cell.value,'text','Unsupported array/data-table formula')) if cell.data_type=='f' else None
            error=calc.errors.get((sheet,cell.coordinate));value=calc.cache.get((sheet,cell.coordinate)) if formula else cell.value
            dxf=conditional_style(ws,cell,calc)
            raw=cell.value.isoformat() if isinstance(cell.value,(datetime,date)) else '' if cell.value is None or formula else str(cell.value)
            validations=[v for v in ws.data_validations.dataValidation if cell.coordinate in v]
            dropdown=next((options(v,calc,sheet,cell.coordinate) for v in validations if v.type=='list'),None)
            spans=anchors.get(cell.coordinate,(1,1))
            cells.append({'address':cell.coordinate,'row':r,'column':c,'raw':raw,'display':'#UNSUPPORTED' if error else display(value,cell.number_format),'formula':formula,'error':error,
                'style':css_style(cell,book,dxf),'rowspan':spans[0],'colspan':spans[1],'editable':not formula and not(ws.protection.sheet and cell.protection.locked),
                'options':dropdown,'validation':validations[0].error or validations[0].prompt if validations else None,'comment':cell.comment.text if cell.comment else None})
    widths=[]
    for c in range(1,cols+1):
        dimension=next((v for v in ws.column_dimensions.values() if (v.min or 0)<=c<=(v.max or 0)),ws.column_dimensions.get(get_column_letter(c)))
        widths.append(0 if dimension and dimension.hidden else round(((dimension.width if dimension and dimension.width else ws.sheet_format.defaultColWidth or 8.43)*7+5),2))
    heights=[0 if ws.row_dimensions[r].hidden else float(ws.row_dimensions[r].height or ws.sheet_format.defaultRowHeight or 15)*96/72 for r in range(1,rows+1)]
    images=[]
    for image in ws._images:
        try:
            anchor=image.anchor;origin=anchor._from;data=image._data()
            if image.format not in ('png','jpeg','jpg','gif','bmp') or len(data)>5*1024*1024 or image.width*image.height>25000000:raise ValueError()
            images.append({'src':'data:image/'+image.format+';base64,'+base64.b64encode(data).decode(),'left':sum(widths[:origin.col])+origin.colOff/9525,'top':sum(heights[:origin.row])+origin.rowOff/9525,
                'width':anchor.ext.cx/9525 if hasattr(anchor,'ext') else image.width,'height':anchor.ext.cy/9525 if hasattr(anchor,'ext') else image.height})
        except (AttributeError,ValueError):warnings.append('An original picture anchor/format is preserved but cannot be displayed here.')
    warnings.extend(sorted(calc.style_errors)[:20])
    return {'sheet':sheet,'sheets':visible,'rows':rows,'columns':cols,'cells':cells,'widths':widths,'heights':heights,'images':images,'merges':merges,
        'warnings':warnings,'calculation_errors':[{'sheet':s,'address':a,'reason':e} for (s,a),e in calc.errors.items()],
        'print':{'area':str(ws.print_area),'title_rows':ws.print_title_rows,'orientation':ws.page_setup.orientation or 'portrait','paper':ws.page_setup.paperSize,'fit_width':ws.page_setup.fitToWidth,
        'margins':{k:getattr(ws.page_margins,k) for k in ('left','right','top','bottom','header','footer')}},
        'engine':'QWOMS free workbook forms','supported_functions':['IF','IFERROR','AND','OR','NOT','SUM','MIN','MAX','AVERAGE','COUNT','COUNTA','ABS','INT','SQRT','MOD','ROUND','LEN','TRIM','UPPER','LOWER','ISNUMBER']}
