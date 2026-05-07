"""
Parsers for raw HRM exports.

The Timesheet/OT/Leave files come from the company HRM with:
- Thai Buddhist calendar (BE = AD + 543).  E.g. 01/04/2569 -> 1 April 2026.
- Multi-row headers; first data row of each employee block holds the emp code/name,
  subsequent rows of the same employee block are blank in those columns.
- "Sum / total" rows interspersed.

The parsers in this module turn each raw file into a tidy DataFrame and (where
relevant) write rows into the SQLite database.
"""
from __future__ import annotations
import re
from datetime import date, datetime
import pandas as pd
from . import db


# ----------------------------- date helpers -----------------------------

THAI_DATE_RX = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")


def thai_to_iso(value) -> str | None:
    """Convert a Thai-Buddhist date string '01/04/2569' to ISO '2026-04-01'.
    Accepts strings, datetimes, and pandas Timestamps; returns None if unparseable.
    """
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(value).date().isoformat()
    s = str(value).strip()
    m = THAI_DATE_RX.match(s)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y > 2400:               # Buddhist Era
        y -= 543
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def period_of(iso_date: str) -> str:
    """ISO date -> 'YYYY-MM' period tag."""
    return iso_date[:7] if iso_date else ""


# ----------------------------- name list / manager / cost group -----------------------------

def parse_name_list(file) -> pd.DataFrame:
    """Read the NameList xlsx.  Columns: Emp. No., Emp. Name, TYPE, COST, LEVEL, D/IN."""
    df = pd.read_excel(file)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(
        columns={
            "Emp. No.": "emp_no",
            "Emp. Name": "emp_name",
            "TYPE": "emp_type",
            "COST": "cost_code",
            "LEVEL": "level",
            "D/IN": "d_in",
        }
    )
    keep = [c for c in ["emp_no", "emp_name", "emp_type", "cost_code", "level", "d_in"] if c in df.columns]
    df = df[keep].dropna(subset=["emp_no"])
    df["emp_no"] = df["emp_no"].astype(str).str.strip()
    df["cost_code"] = df["cost_code"].astype(str).str.strip()
    df["level"] = pd.to_numeric(df["level"], errors="coerce").fillna(0).astype(int)
    return df.reset_index(drop=True)


def import_name_list(file) -> int:
    df = parse_name_list(file)
    n = 0
    with db.cursor() as cur:
        # Mark previously-active rows; we'll reactivate the ones still present
        cur.execute("UPDATE employees SET is_active = 0")
        for _, r in df.iterrows():
            cur.execute(
                """INSERT INTO employees(emp_no, emp_name, emp_type, cost_code, level, d_in, is_active)
                   VALUES (?,?,?,?,?,?,1)
                   ON CONFLICT(emp_no) DO UPDATE SET
                     emp_name=excluded.emp_name,
                     emp_type=excluded.emp_type,
                     cost_code=excluded.cost_code,
                     level=excluded.level,
                     d_in=excluded.d_in,
                     is_active=1,
                     updated_at=CURRENT_TIMESTAMP""",
                (r["emp_no"], r["emp_name"], r["emp_type"], r["cost_code"], r["level"], r["d_in"]),
            )
            n += 1
    return n


def parse_manager_list(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    df = df.dropna(subset=["Emp. No."])
    df = df.rename(columns={"Emp. No.": "emp_no", "Title": "title"})
    df["emp_no"] = pd.to_numeric(df["emp_no"], errors="coerce").dropna().astype(int).astype(str)
    return df[["emp_no", "title"]].reset_index(drop=True)


def import_manager_list(file) -> int:
    df = parse_manager_list(file)
    n = 0
    with db.cursor() as cur:
        cur.execute("DELETE FROM managers")
        for _, r in df.iterrows():
            cur.execute(
                "INSERT OR REPLACE INTO managers(emp_no, title, is_manager) VALUES (?,?,1)",
                (r["emp_no"], r["title"]),
            )
            n += 1
    return n


def parse_cost_group(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={"Code": "code", "Department": "department"})
    df = df.dropna(subset=["code"])
    df["code"] = df["code"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df["department"] = df["department"].astype(str).str.strip()
    return df.reset_index(drop=True)


# Default top-level mapping (admin can edit later in UI)
DEFAULT_TOP_LEVEL = {
    "Admin": "SG&A",
    "Eng. Mechanical": "SG&A",
    "Sales": "SG&A",
    "Quality": "SG&A",
    "QP": "MANU Support",
    "Supply": "MANU Support",
    "Pro Sub": "MANU Support",
    "Packing": "MANU Support",
    "CNC": "MANU",
    "Cutting": "MANU",
    "Folding": "MANU",
    "Weld": "MANU",
    "Paint": "MANU",
    "Assembly": "MANU",
    "Misumi": "MANU",
}
TOP_LEVEL_ORDER = {"SG&A": 0, "MANU Support": 1, "MANU": 2}


def import_cost_group(file) -> int:
    df = parse_cost_group(file)
    n = 0
    with db.cursor() as cur:
        for _, r in df.iterrows():
            top = DEFAULT_TOP_LEVEL.get(r["department"], "SG&A")
            sort_o = TOP_LEVEL_ORDER.get(top, 9) * 100
            # Preserve any existing sg_a_manu the admin may have changed
            cur.execute("SELECT sg_a_manu FROM cost_groups WHERE code = ?", (r["code"],))
            existing = cur.fetchone()
            if existing and existing["sg_a_manu"]:
                top = existing["sg_a_manu"]
            cur.execute(
                """INSERT OR REPLACE INTO cost_groups(code, department, sg_a_manu, sort_order)
                   VALUES (?,?,?,?)""",
                (r["code"], r["department"], top, sort_o),
            )
            n += 1
    return n


def parse_holidays(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    df.columns = ["holiday_date", "holiday_name"]
    df["holiday_date"] = pd.to_datetime(df["holiday_date"]).dt.date.astype(str)
    return df


def import_holidays(file) -> int:
    df = parse_holidays(file)
    n = 0
    with db.cursor() as cur:
        for _, r in df.iterrows():
            cur.execute(
                "INSERT OR REPLACE INTO holidays(holiday_date, holiday_name) VALUES (?,?)",
                (r["holiday_date"], r["holiday_name"]),
            )
            n += 1
    return n


# ----------------------------- timesheet (the big one) -----------------------------

# Column indices found via inspection of the raw file:
TS_COLS = {
    "emp_no": 0,
    "emp_name": 2,
    "date": 7,
    "shift": 9,
    "punch": 10,
    "work_hours": 11,
    "late": 13,
    "early": 14,
    "ot1": 17,
    "ot15": 18,
    "ot2": 19,
    "ot3": 20,
    "absent": 21,
    "sick": 22,
    "personal": 24,
    "annual": 25,
}


def _to_float(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return 0.0
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def parse_timesheet(file) -> pd.DataFrame:
    """Parse the raw HRM timesheet xls.  Returns a tidy DataFrame: one row per
    employee+date with hour values for work / late / OT / absent / leaves.
    """
    raw = pd.read_excel(file, header=None)
    rows = []
    current_emp_no = None
    current_emp_name = None

    for i in range(len(raw)):
        row = raw.iloc[i]
        # Pick up employee identity if present
        emp_no_cell = row[TS_COLS["emp_no"]]
        emp_name_cell = row[TS_COLS["emp_name"]]
        if pd.notna(emp_no_cell) and str(emp_no_cell).strip().isdigit():
            current_emp_no = str(emp_no_cell).strip()
            if pd.notna(emp_name_cell):
                current_emp_name = str(emp_name_cell).strip()
        # Date present?  The data rows are the ones with a parseable date.
        iso = thai_to_iso(row[TS_COLS["date"]])
        if not iso or not current_emp_no:
            continue
        rows.append(
            {
                "emp_no": current_emp_no,
                "emp_name": current_emp_name,
                "work_date": iso,
                "period": period_of(iso),
                "shift_code": str(row[TS_COLS["shift"]]) if pd.notna(row[TS_COLS["shift"]]) else "",
                "work_hours": _to_float(row[TS_COLS["work_hours"]]),
                "late_hours": _to_float(row[TS_COLS["late"]]),
                "early_hours": _to_float(row[TS_COLS["early"]]),
                "ot1_hours": _to_float(row[TS_COLS["ot1"]]),
                "ot15_hours": _to_float(row[TS_COLS["ot15"]]),
                "ot2_hours": _to_float(row[TS_COLS["ot2"]]),
                "ot3_hours": _to_float(row[TS_COLS["ot3"]]),
                "absent_hours": _to_float(row[TS_COLS["absent"]]),
                "sick_hours": _to_float(row[TS_COLS["sick"]]),
                "personal_hours": _to_float(row[TS_COLS["personal"]]),
                "annual_hours": _to_float(row[TS_COLS["annual"]]),
            }
        )
    df = pd.DataFrame(rows)
    return df


def import_timesheet(file, replace_period: bool = True) -> tuple[int, list[str]]:
    """Insert all rows from the timesheet file.  If replace_period=True, any
    existing rows for the periods present in the file are deleted first so that
    re-uploading the same month is idempotent."""
    df = parse_timesheet(file)
    if df.empty:
        return 0, []
    periods = sorted(df["period"].unique().tolist())
    n = 0
    with db.cursor() as cur:
        if replace_period:
            for p in periods:
                cur.execute("DELETE FROM timesheet WHERE period = ?", (p,))
        for _, r in df.iterrows():
            cur.execute(
                """INSERT OR REPLACE INTO timesheet(
                       emp_no, work_date, period, shift_code, work_hours, late_hours, early_hours,
                       ot1_hours, ot15_hours, ot2_hours, ot3_hours,
                       absent_hours, sick_hours, personal_hours, annual_hours)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    r["emp_no"], r["work_date"], r["period"], r["shift_code"],
                    r["work_hours"], r["late_hours"], r["early_hours"],
                    r["ot1_hours"], r["ot15_hours"], r["ot2_hours"], r["ot3_hours"],
                    r["absent_hours"], r["sick_hours"], r["personal_hours"], r["annual_hours"],
                ),
            )
            n += 1
    return n, periods


# ----------------------------- OT Detail (NEW dated format) -----------------------------
# This format is preferred over the old monthly summary because every OT occurrence
# carries its own date, so aggregation is correct regardless of timesheet date range.

def parse_ot_detail(file) -> pd.DataFrame:
    """Parse the dated OT detail file (one row per OT occurrence).

    Expected columns (English headers in row 1, Thai sub-header row 2 to skip):
      A Emp. No. | B Emp. Name | C Emp. Type | D Cost Centre | E Cost Group |
      F Department | G Booked Date | H OT From | I OT To | J OT Multiplier |
      K OT Period (TH) | L Multiplier Label | M OT Type (TH) | N Hour | O Minute
    Returns: emp_no | work_date (ISO) | period | multiplier | hours | ot_type | ot_period
    """
    raw = pd.read_excel(file, header=0)
    # Drop the Thai sub-header row if present (row index 0 of data)
    if len(raw) > 0 and pd.isna(raw.iloc[0].get("Emp. No.", None)):
        raw = raw.iloc[1:].reset_index(drop=True)

    # Be flexible with column names — try a few variants
    rename = {}
    for col in raw.columns:
        c = str(col).strip()
        if c in ("Emp. No.", "Emp.No.", "Emp No"):           rename[col] = "emp_no"
        elif c in ("OT From",):                               rename[col] = "ot_from"
        elif c in ("OT To",):                                 rename[col] = "ot_to"
        elif c in ("OT Multiplier", "Multiplier"):            rename[col] = "multiplier"
        elif c in ("Multiplier Label",):                      rename[col] = "multiplier_label"
        elif c in ("OT Type (TH)", "OT Type"):                rename[col] = "ot_type"
        elif c in ("OT Period (TH)", "OT Period"):            rename[col] = "ot_period"
        elif c in ("Hour", "Hours"):                          rename[col] = "hour"
        elif c in ("Minute", "Minutes"):                      rename[col] = "minute"
    df = raw.rename(columns=rename)

    required = ["emp_no", "ot_from", "multiplier", "hour"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"OT detail file is missing required columns: {missing}. "
                         f"Found columns: {list(raw.columns)}")

    df = df.dropna(subset=["emp_no", "ot_from"])
    df["emp_no"] = df["emp_no"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df["work_date"] = df["ot_from"].apply(thai_to_iso)
    df = df.dropna(subset=["work_date"])
    df["period"] = df["work_date"].str[:7]
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce").fillna(0)
    df["minute"] = pd.to_numeric(df.get("minute", 0), errors="coerce").fillna(0)
    df["hours"] = df["hour"] + df["minute"] / 60.0
    df["multiplier"] = pd.to_numeric(df["multiplier"], errors="coerce")
    df = df.dropna(subset=["multiplier"])
    if "ot_type" not in df.columns:
        df["ot_type"] = ""
    if "ot_period" not in df.columns:
        df["ot_period"] = ""

    return df[["emp_no", "work_date", "period", "multiplier", "hours", "ot_type", "ot_period"]].reset_index(drop=True)


def import_ot_detail(file, replace_period: bool = True) -> tuple[int, list[str]]:
    """Import the dated OT detail file. Re-uploading a period replaces it."""
    df = parse_ot_detail(file)
    if df.empty:
        return 0, []
    periods = sorted(df["period"].unique().tolist())
    n = 0
    with db.cursor() as cur:
        if replace_period:
            for p in periods:
                cur.execute("DELETE FROM ot_entries WHERE period = ?", (p,))
        for _, r in df.iterrows():
            cur.execute(
                """INSERT INTO ot_entries(emp_no, work_date, period, multiplier, hours, ot_type, ot_period)
                   VALUES (?,?,?,?,?,?,?)""",
                (r["emp_no"], r["work_date"], r["period"],
                 float(r["multiplier"]), float(r["hours"]),
                 str(r.get("ot_type", "")), str(r.get("ot_period", ""))),
            )
            n += 1
    return n, periods


def parse_ot_any_format(file) -> tuple[str, pd.DataFrame]:
    """Try the dated OT detail format first; fall back to the legacy summary format.

    Returns a tuple (format, dataframe):
        ('dated',  detail_df)   - new dated format suitable for ot_entries table
        ('legacy', summary_df)  - old monthly summary, used as cross-check only
    Raises ValueError if neither format matches.
    """
    # Try dated format first (preferred — supports per-day aggregation)
    try:
        # Reset stream position before each parse attempt
        if hasattr(file, "seek"):
            file.seek(0)
        df = parse_ot_detail(file)
        if not df.empty:
            return "dated", df
    except (ValueError, Exception):
        pass

    # Fall back to legacy monthly summary
    try:
        if hasattr(file, "seek"):
            file.seek(0)
        df = parse_ot_summary(file)
        if not df.empty:
            return "legacy", df
    except Exception:
        pass

    raise ValueError(
        "Could not parse this file as either dated OT Detail or legacy OT summary. "
        "Please use one of the templates from the 'Download templates' section."
    )


# ----------------------------- OT and Leave (legacy summary cross-check) -----------------------------

def parse_ot_summary(file) -> pd.DataFrame:
    raw = pd.read_excel(file, header=None)
    rows = []
    cur_emp = None
    for i in range(len(raw)):
        r = raw.iloc[i]
        cell = r[1]
        if pd.notna(cell) and str(cell).strip().isdigit():
            cur_emp = str(cell).strip()
        desc = r[17] if r.shape[0] > 17 else None
        amount = r[26] if r.shape[0] > 26 else None
        if cur_emp and pd.notna(desc) and pd.notna(amount):
            rows.append({"emp_no": cur_emp, "ot_type": str(desc), "hours": _to_float(amount)})
    return pd.DataFrame(rows)


def parse_leave_summary(file) -> pd.DataFrame:
    raw = pd.read_excel(file, header=None)
    rows = []
    cur_emp = None
    for i in range(len(raw)):
        r = raw.iloc[i]
        cell = r[0]
        if pd.notna(cell) and str(cell).strip().isdigit():
            cur_emp = str(cell).strip()
        desc = r[14] if r.shape[0] > 14 else None
        days = r[19] if r.shape[0] > 19 else None
        if cur_emp and pd.notna(desc) and pd.notna(days):
            rows.append({"emp_no": cur_emp, "leave_type": str(desc), "days": _to_float(days)})
    return pd.DataFrame(rows)


# ============================================================================
# Employee MASTER list parser (rich version with org-chart fields)
# ============================================================================

def parse_employee_master(file) -> pd.DataFrame:
    """Parse the full 'Employee List MASTER' file (Headcount Updated sheet).

    Reads the rich version of the employee list with: Mgr (manager name),
    Title, Dept by Location, Cost Centre Name, Level, etc. — required for
    the org chart.

    Returns a DataFrame with columns:
      emp_no, emp_name, name_th, nickname, dept_by_location, cost_centre_name,
      thai_or_expat, manager_name, level, title, is_mgr_role, d_in,
      joined_date, status, cost_code (extracted from cost_centre_name),
      emp_type (mapped from status: AMS->PER, SUB->SUB, etc.)
    """
    # Try sheets in priority order
    candidate_sheets = ["Headcount Updated", "Headcount", "Sheet1"]
    xl = pd.ExcelFile(file)
    sheet = next((s for s in candidate_sheets if s in xl.sheet_names), xl.sheet_names[0])

    # Find the header row by scanning for "Emp. No." in the first 10 rows
    raw = pd.read_excel(file, sheet_name=sheet, header=None, nrows=12)
    header_row = None
    for r in range(len(raw)):
        if any(str(v).strip() == "Emp. No." for v in raw.iloc[r].values if pd.notna(v)):
            header_row = r
            break
    if header_row is None:
        raise ValueError("Could not find 'Emp. No.' header in the file. "
                          "Is this the Employee List MASTER format?")

    df = pd.read_excel(file, sheet_name=sheet, header=header_row)
    # Normalize column names by stripping whitespace
    df.columns = [str(c).strip() for c in df.columns]

    # Map source columns to internal names
    col_map = {
        "Emp. No.": "emp_no", "Emp.No.": "emp_no",
        "Emp. Name": "emp_name", "Emp.Name": "emp_name",
        "ชื่อ": "name_th",
        "Nick name": "nickname", "Nickname": "nickname",
        "Dept by Location": "dept_by_location", "Department": "dept_by_location",
        "Cost Centre Name": "cost_centre_name", "Cost Center": "cost_centre_name",
        "Thai or Expat": "thai_or_expat",
        "Mgr": "manager_name",
        "Level": "level",
        "Title": "title",
        "Mgr.": "is_mgr_role",
        "Direct / Indirect": "d_in", "D/IN": "d_in",
        "Joined date": "joined_date",
        "Status": "status",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Drop rows without an emp_no
    df = df.dropna(subset=["emp_no"]).copy()
    df["emp_no"] = df["emp_no"].apply(
        lambda x: str(int(x)) if isinstance(x, (int, float)) else str(x).strip()
    )

    # Extract cost code from cost_centre_name (e.g. "354 -Finance&HR..." -> "354")
    if "cost_centre_name" in df.columns:
        df["cost_code"] = df["cost_centre_name"].astype(str).str.extract(r"^\s*(\d+)")
    else:
        df["cost_code"] = ""

    # Map status to emp_type
    def _status_to_emp_type(s):
        if pd.isna(s): return "PER"
        s = str(s).upper().strip()
        if s == "AMS":  return "PER"
        if s == "SUB":  return "SUB"
        if s == "GUARD": return "SUB"
        if s == "CNK":  return "SUB"
        return "PER"
    df["emp_type"] = df["status"].apply(_status_to_emp_type) if "status" in df.columns else "PER"

    # Normalize joined_date to ISO string
    if "joined_date" in df.columns:
        df["joined_date"] = pd.to_datetime(df["joined_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Ensure all expected columns exist
    for c in ["name_th", "nickname", "dept_by_location", "cost_centre_name",
              "thai_or_expat", "manager_name", "level", "title", "is_mgr_role",
              "d_in", "joined_date", "status"]:
        if c not in df.columns:
            df[c] = ""

    # Cast level to int where possible
    df["level"] = pd.to_numeric(df["level"], errors="coerce").fillna(0).astype(int)

    return df[["emp_no", "emp_name", "name_th", "nickname", "dept_by_location",
                "cost_centre_name", "cost_code", "thai_or_expat", "manager_name",
                "level", "title", "is_mgr_role", "d_in", "emp_type",
                "joined_date", "status"]].reset_index(drop=True)


def import_employee_master(file) -> tuple[int, int]:
    """Import the rich Employee Master list. Updates both `employees` and
    `employees_extended` tables, and resolves manager_emp_no by matching the
    'manager_name' text against the existing employee list.

    Returns (employees_inserted_or_updated, managers_resolved_count).
    """
    df = parse_employee_master(file)
    if df.empty:
        return 0, 0

    # First pass: upsert all employees so they all exist before resolving managers
    n_emps = 0
    with db.cursor() as cur:
        # Mark all currently-active employees as inactive — only keep active those re-uploaded
        cur.execute("UPDATE employees SET is_active = 0")

        for _, r in df.iterrows():
            cur.execute("""
                INSERT INTO employees (emp_no, emp_name, emp_type, cost_code, level, d_in, is_active, updated_at)
                  VALUES (?,?,?,?,?,?,1,CURRENT_TIMESTAMP)
                ON CONFLICT(emp_no) DO UPDATE SET
                  emp_name=excluded.emp_name, emp_type=excluded.emp_type,
                  cost_code=excluded.cost_code, level=excluded.level,
                  d_in=excluded.d_in, is_active=1,
                  updated_at=CURRENT_TIMESTAMP
            """, (r["emp_no"], r["emp_name"], r["emp_type"], r["cost_code"],
                  int(r["level"] or 0), r["d_in"]))
            n_emps += 1

    # Second pass: resolve manager_name -> manager_emp_no by name matching
    # Build a name-lookup table
    all_emps = db.list_employees()
    name_to_no = {}
    for e in all_emps:
        if e.get("emp_name"):
            # Strip Thai honorifics for matching
            n = e["emp_name"].replace("Mr.", "").replace("Ms.", "").replace("Mrs.", "")
            n = n.replace("นาย", "").replace("น.ส.", "").replace("นาง", "")
            n = " ".join(n.split())  # normalize spaces
            name_to_no[n.lower()] = e["emp_no"]

    n_resolved = 0
    for _, r in df.iterrows():
        mgr_no = ""
        mgr_name = (r.get("manager_name") or "").strip()
        if mgr_name:
            mgr_clean = mgr_name.replace("Mr.", "").replace("Ms.", "").replace("Mrs.", "")
            mgr_clean = " ".join(mgr_clean.split()).lower()
            if mgr_clean in name_to_no:
                mgr_no = name_to_no[mgr_clean]
                n_resolved += 1
            else:
                # Try matching just first name + last name pieces
                for full_name, eno in name_to_no.items():
                    if mgr_clean and (mgr_clean in full_name or full_name in mgr_clean):
                        # Require at least 2 word match to avoid false positives
                        words_a = set(mgr_clean.split())
                        words_b = set(full_name.split())
                        if len(words_a & words_b) >= 2:
                            mgr_no = eno
                            n_resolved += 1
                            break

        db.upsert_employee_extended(
            r["emp_no"],
            nickname=r.get("nickname") or "",
            name_th=r.get("name_th") or "",
            dept_by_location=r.get("dept_by_location") or "",
            cost_centre_name=r.get("cost_centre_name") or "",
            title=r.get("title") or "",
            manager_name=mgr_name,
            manager_emp_no=mgr_no,
            is_mgr_role=r.get("is_mgr_role") or "",
            thai_or_expat=r.get("thai_or_expat") or "",
            joined_date=r.get("joined_date") or "",
            status=r.get("status") or "",
        )

    return n_emps, n_resolved
