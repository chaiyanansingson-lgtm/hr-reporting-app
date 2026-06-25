# lib/ot_salary_db.py
# ============================================================================
# OT-by-department comparison report (§8).
#
# Ingests a monthly salary report (the same "Salary_for_<Mon>_<yy>up" export
# used for payroll) and extracts Overtime PAID (THB) per cost-centre section,
# then rolls cost centres up into the 18 expanded departments used at the
# level meeting. Stores ONE snapshot per named month so managers can compare
# any two months.
#
# Verified parser (reconciles exactly to payroll):
#   - CSV read with utf-8-sig; every row padded to 30 columns
#   - cost-centre section header  : col[3] starts with "ASM"  (name in col[8])
#   - employee row                : col[0] is a 7-digit number; OT at col[14]
#   - section total (validation)  : col[0] starts with "Total Dept"; OT col[14]
#   April total THB 1,568,130.63  /  May total THB 1,703,715.06
#
# .xls / .xlsx are supported too (read via pandas, header=None) and run through
# the identical column logic.
#
# GATING (enforced in the page, lib/auth):
#   salary.ot_report      -> see the aggregated DEPARTMENT comparison (managers)
#   employee.view_salary  -> upload, see raw per-employee rows, download raw
#                            file  (Super Admin only)
# ============================================================================
import csv
import io
import json
import re
import datetime as dt
from lib.db import get_conn, IS_POSTGRES, PH

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"
BLOB = "BYTEA" if IS_POSTGRES else "BLOB"

C_EMP, C_ASM, C_DEPTNAME, C_OT = 0, 3, 8, 14   # 0-based column indices

# ---------------------------------------------------------------- departments
# Canonical render order (matches the level-meeting infographic).
DEPT_ORDER = [
    "Laser", "Folding", "CNC Machine shop", "Weld", "Paint", "Assembly",
    "Mizumi", "QC", "Packing", "Warehouse",
    "Production Support (ME)", "Production Support (MTN)",
    "Production Support (Prod)", "Planning", "Engineering",
    "Purchasing", "Sales", "Finance / HR / Admin",
]

# cost-centre -> department.  Exact codes are resolved before prefix codes so
# the ASM270 / ASM270.0 / ASM270.1 and ASM275 / ASM275.1 families split right.
_CC_EXACT = {
    "ASM270.0": "Purchasing",
    "ASM270.1": "Warehouse",
    "ASM275.1": "Planning",
}
_CC_PREFIX = [   # checked in order; first startswith wins
    ("ASM223", "Mizumi"),
    ("ASM210", "CNC Machine shop"),
    ("ASM220", "Laser"),
    ("ASM221", "Folding"),
    ("ASM222", "Weld"),
    ("ASM231", "Paint"),
    ("ASM232", "Paint"),
    ("ASM240", "Assembly"),
    ("ASM263", "Packing"),
    ("ASM280", "QC"),
    ("ASM273", "Production Support (ME)"),
    ("ASM274", "Production Support (MTN)"),
    ("ASM275", "Production Support (Prod)"),
    ("ASM310", "Engineering"),
    ("ASM313", "Engineering"),
    ("ASM270", "Warehouse"),
    ("ASM352", "Sales"),
    ("ASM356", "Finance / HR / Admin"),
]


def dept_for_cc(cc):
    """Map a cost-centre code (e.g. 'ASM270.1') to one of DEPT_ORDER, or None."""
    cc = str(cc).strip()
    if cc in _CC_EXACT:
        return _CC_EXACT[cc]
    for pre, dept in _CC_PREFIX:
        if cc.startswith(pre):
            return dept
    return None


def _num(v):
    """Parse a THB cell to float; strips thousands separators and blanks."""
    s = str(v).replace(",", "").strip()
    if s in ("", "nan", "None", "-"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


# ---------------------------------------------------------------- parsing
def _rows_from_bytes(file_bytes, filename):
    """Return a list of row-lists from a CSV / XLS / XLSX upload."""
    name = (filename or "").lower()
    if name.endswith((".xls", ".xlsx")):
        import pandas as pd
        engine = "xlrd" if name.endswith(".xls") else "openpyxl"
        df = pd.read_excel(io.BytesIO(file_bytes), header=None,
                           dtype=str, engine=engine)
        rows = df.where(df.notna(), "").values.tolist()
        return [[("" if c is None else str(c)) for c in r] for r in rows]
    # default: CSV (utf-8-sig)
    text = file_bytes.decode("utf-8-sig", errors="replace")
    return list(csv.reader(io.StringIO(text)))


def parse_salary(file_bytes, filename=""):
    """Parse a monthly salary report.

    Returns dict:
      dept_totals : {dept: ot_thb}      (only mapped departments, full order)
      grand_total : float               (sum of employee OT, all sections)
      total_dept  : float               (sum of Total-Dept rows, validation)
      reconciled  : bool                (grand_total == total_dept within 0.5)
      n_emp       : int
      n_cc        : int                 (cost-centre sections seen)
      unmapped    : [(asm_code, name, ot), ...]   cost centres with no dept
      emp_rows    : [(emp_no, asm_code, dept, ot), ...]   (Super-Admin detail)
    """
    rows = _rows_from_bytes(file_bytes, filename)
    dept_totals = {d: 0.0 for d in DEPT_ORDER}
    emp_rows = []
    unmapped = {}
    grand = 0.0
    total_dept = 0.0
    n_emp = 0
    n_cc = 0
    cur_code = cur_name = cur_dept = None

    for r in rows:
        c = list(r) + [""] * (30 - len(r))
        asm = str(c[C_ASM]).strip()
        emp = str(c[C_EMP]).strip()
        if asm.startswith("ASM"):
            cur_code = asm
            cur_name = str(c[C_DEPTNAME]).strip()
            cur_dept = dept_for_cc(asm)
            n_cc += 1
            if cur_dept is None:
                unmapped.setdefault(asm, [asm, cur_name, 0.0])
            continue
        if re.fullmatch(r"\d{7}", emp):
            ot = _num(c[C_OT])
            grand += ot
            n_emp += 1
            if cur_dept is not None:
                dept_totals[cur_dept] += ot
                emp_rows.append((emp, cur_code, cur_dept, ot))
            elif cur_code is not None:
                unmapped[cur_code][2] += ot
                emp_rows.append((emp, cur_code, "(unmapped)", ot))
            continue
        if emp.startswith("Total Dept"):
            total_dept += _num(c[C_OT])
            continue

    dept_totals = {d: round(v, 2) for d, v in dept_totals.items()}
    return {
        "dept_totals": dept_totals,
        "grand_total": round(grand, 2),
        "total_dept": round(total_dept, 2),
        "reconciled": abs(grand - total_dept) < 0.5,
        "n_emp": n_emp,
        "n_cc": n_cc,
        "unmapped": list(unmapped.values()),
        "emp_rows": emp_rows,
    }


# ---------------------------------------------------------------- storage
def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS ot_salary_months (
        id {SERIAL},
        label TEXT UNIQUE,
        period_from TEXT,
        period_to TEXT,
        total_ot REAL,
        n_emp INTEGER,
        n_cc INTEGER,
        reconciled INTEGER,
        dept_json TEXT,
        emp_json TEXT,
        raw_file {BLOB},
        raw_filename TEXT,
        src_kind TEXT,
        uploaded_at TEXT,
        uploaded_by TEXT)""")
    conn.commit()


def _ts():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_month(label, period_from, period_to, parsed, raw_bytes,
               raw_filename, actor):
    """Insert or replace the snapshot for `label` (upsert by label)."""
    conn = get_conn(); cur = conn.cursor()
    dept_json = json.dumps(parsed["dept_totals"], ensure_ascii=False)
    emp_json = json.dumps(parsed["emp_rows"], ensure_ascii=False)
    src_kind = ("xlsx" if (raw_filename or "").lower().endswith(".xlsx")
                else "xls" if (raw_filename or "").lower().endswith(".xls")
                else "csv")
    rb = raw_bytes
    if rb is not None and not isinstance(rb, (bytes, bytearray)):
        rb = bytes(rb)
    # delete any existing row with this label, then insert
    cur.execute(f"DELETE FROM ot_salary_months WHERE label={PH}", (label,))
    cur.execute(f"""INSERT INTO ot_salary_months
        (label, period_from, period_to, total_ot, n_emp, n_cc, reconciled,
         dept_json, emp_json, raw_file, raw_filename, src_kind,
         uploaded_at, uploaded_by)
        VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},
                {PH},{PH})""",
        (label, period_from, period_to, parsed["grand_total"],
         parsed["n_emp"], parsed["n_cc"], 1 if parsed["reconciled"] else 0,
         dept_json, emp_json, rb, raw_filename, src_kind, _ts(), actor))
    conn.commit()


def list_months():
    """Lightweight list for the comparison pickers (no blobs / emp detail)."""
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""SELECT label, period_from, period_to, total_ot, n_emp,
                          n_cc, reconciled, uploaded_at, uploaded_by
                   FROM ot_salary_months ORDER BY uploaded_at DESC""")
    out = []
    for row in cur.fetchall():
        out.append({
            "label": row[0], "period_from": row[1], "period_to": row[2],
            "total_ot": row[3], "n_emp": row[4], "n_cc": row[5],
            "reconciled": bool(row[6]), "uploaded_at": row[7],
            "uploaded_by": row[8],
        })
    return out


def get_month(label, with_raw=False):
    """Full snapshot for one label. dept_totals always returned; emp_rows and
    raw_file only when with_raw=True (caller must check employee.view_salary)."""
    conn = get_conn(); cur = conn.cursor()
    cols = ("label, period_from, period_to, total_ot, n_emp, n_cc, "
            "reconciled, dept_json, emp_json, raw_filename, src_kind, "
            "uploaded_at, uploaded_by")
    if with_raw:
        cols += ", raw_file"
    cur.execute(f"SELECT {cols} FROM ot_salary_months WHERE label={PH}",
                (label,))
    row = cur.fetchone()
    if not row:
        return None
    d = {
        "label": row[0], "period_from": row[1], "period_to": row[2],
        "total_ot": row[3], "n_emp": row[4], "n_cc": row[5],
        "reconciled": bool(row[6]),
        "dept_totals": json.loads(row[7]) if row[7] else {},
        "raw_filename": row[9], "src_kind": row[10],
        "uploaded_at": row[11], "uploaded_by": row[12],
    }
    if with_raw:
        d["emp_rows"] = json.loads(row[8]) if row[8] else []
        rb = row[13]
        d["raw_file"] = bytes(rb) if rb is not None else None
    return d


def delete_month(label):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"DELETE FROM ot_salary_months WHERE label={PH}", (label,))
    conn.commit()
