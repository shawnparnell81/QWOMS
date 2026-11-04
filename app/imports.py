"""Part Master import. Imported Excel is data; original work-order forms are separate files.

Every non-empty spreadsheet row identifies one physical part and possibly several aliases.
Existing records are merged ONLY via matching aliases, never merely via UPC/drawing.
Conflicting rows are flagged, not silently overwritten.
"""
from io import BytesIO
import re
from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .models import PhysicalPart, PartAlias, ProductFamily

MISSING = {"", "none", "nan", "null", "n/a", "-"}


def cell_text(cell):
    v = cell.value
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, int) and re.fullmatch(r"0{2,}", cell.number_format or ""):
        return str(v).zfill(len(cell.number_format))
    return str(v).strip()


def clean(v):
    s = str(v or "").strip()
    return "" if s.casefold() in MISSING else s


def classify_header(header):
    original = clean(header)
    h = re.sub(r"\s+", " ", original.lower()).strip()
    simplified = re.sub(r"[^a-z0-9]+", " ", h).strip()
    if any(x in simplified for x in ("drawing revision", "drawing rev", "dwg rev")) or simplified in ("rev", "revision"):
        return ("field", "drawing_revision")
    if any(x in simplified for x in ("drawing number", "drawing no", "drawing pn", "dwg number", "dwg no")) or simplified in ("drawing", "dwg"):
        return ("field", "drawing_number")
    if "upc" in simplified:
        return ("field", "upc")
    if "family" in simplified or "product group" in simplified:
        return ("field", "family")
    if "description" in simplified:
        return ("field", "description")
    if ("part" in simplified or re.search(r"\bpn\b", simplified)) and not "drawing" in simplified and not "dwg" in simplified:
        account = re.sub(r"\b(part|number|no|pn|customer|sku|code)\b", "", original, flags=re.I).strip(" -_:.")
        return ("alias", account or "Internal")
    return ("ignore", original)


def load_rows(blob):
    wb = load_workbook(BytesIO(blob), read_only=True, data_only=True)
    ws = wb.active
    raw = ws.iter_rows()
    try:
        headers = [classify_header(cell_text(c)) for c in next(raw)]
    except StopIteration:
        return []
    if not any(kind == "alias" for kind, _ in headers):
        raise ValueError("No part number columns found. Expected headers such as O'Reilly PN or NAPA PN.")
    rows = []
    for row_number, cells in enumerate(raw, 2):
        payload = {"aliases": [], "row": row_number}
        for idx, cell in enumerate(cells):
            if idx >= len(headers):
                break
            value = clean(cell_text(cell))
            kind, name = headers[idx]
            if not value:
                continue
            if kind == "alias":
                payload["aliases"].append((name, value))
            elif kind == "field":
                payload[name] = value
        if any(v for _, v in payload["aliases"]):
            rows.append(payload)
    wb.close()
    return rows


def _family(db: Session, name: str):
    name = name or "Uncategorized"
    family = db.scalar(select(ProductFamily).where(func.lower(ProductFamily.name) == name.casefold()))
    if not family:
        family = ProductFamily(name=name)
        db.add(family)
        db.flush()
    return family


def process_part_import(db: Session, rows: list[dict], family_override: str = "", preview: bool = True):
    """Preview uses an isolated transaction savepoint; commit creates an audit separately."""
    results = []
    counts = {"new": 0, "updated": 0, "unchanged": 0, "conflict": 0, "skipped": 0}
    nested = db.begin_nested()
    try:
        for item in rows:
            aliases = list(dict.fromkeys((clean(a), clean(n)) for a, n in item["aliases"] if clean(n)))
            if not aliases:
                counts["skipped"] += 1
                continue
            found = []
            for account, number in aliases:
                part_alias = db.scalar(select(PartAlias).where(
                    func.lower(PartAlias.account) == account.casefold(),
                    func.lower(PartAlias.part_number) == number.casefold()))
                if part_alias:
                    found.append(part_alias.part_id)
            ids = set(found)
            if len(ids) > 1:
                counts["conflict"] += 1
                results.append({"row": item["row"], "status": "conflict", "reason": "Part-number aliases point to different existing physical parts"})
                continue
            part = db.get(PhysicalPart, next(iter(ids))) if ids else None
            family_name = clean(item.get("family")) or clean(family_override)
            fields = ["description", "drawing_number", "drawing_revision", "upc"]
            mismatches = [f for f in fields if part and clean(getattr(part, f)) and clean(item.get(f))
                          and clean(getattr(part, f)).casefold() != clean(item[f]).casefold()]
            if part and family_name and part.family.name.casefold() != family_name.casefold() and part.family.name != "Uncategorized":
                mismatches.append("family")
            if mismatches:
                counts["conflict"] += 1
                results.append({"row": item["row"], "status": "conflict", "reason": "Conflicting values: " + ", ".join(mismatches)})
                continue
            if part is None:
                family = _family(db, family_name or "Uncategorized")
                part = PhysicalPart(family_id=family.id, **{f: clean(item.get(f)) or None for f in fields})
                db.add(part)
                db.flush()
                state = "new"
            else:
                state = "unchanged"
                if part.family.name == "Uncategorized" and family_name:
                    part.family = _family(db, family_name)
                    state = "updated"
                for f in fields:
                    if not clean(getattr(part, f)) and clean(item.get(f)):
                        setattr(part, f, clean(item[f]))
                        state = "updated"
            for account, number in aliases:
                found_alias = db.scalar(select(PartAlias).where(
                    func.lower(PartAlias.account) == account.casefold(),
                    func.lower(PartAlias.part_number) == number.casefold()))
                if not found_alias:
                    db.add(PartAlias(part_id=part.id, account=account, part_number=number))
                    if state != "new":
                        state = "updated"
            db.flush()  # Later rows in the workbook must see aliases just added.
            counts[state] += 1
            results.append({"row": item["row"], "status": state, "aliases": [f"{a}: {n}" for a, n in aliases]})
        if preview:
            nested.rollback()
        else:
            nested.commit()
            # The request commits data together with its audit records.
    except Exception:
        nested.rollback()
        db.rollback()
        raise
    finally:
        # Fresh request session closes after completion; preview never commits.
        if preview:
            db.rollback()
    return {"total_rows": len(rows), "summary": counts, "examples": results[:100]}
