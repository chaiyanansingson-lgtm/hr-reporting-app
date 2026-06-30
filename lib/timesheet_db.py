# lib/timesheet_db.py
# Ingests the raw "รายงานผลการคำนวณบันทึกเวลาแสดงตามพนักงาน" (face-scan time
# calculation) .xls — per employee per day: working hours, OT by rate
# (x1/x1.5/x2/x3), no-show, and leave by type (sick / personal / annual).
# Joins the employee master for SG&A/MANU group, Function and Permanent/
# Contract class, and aggregates into the Working-Hour-Report structure.
import datetime as dt
import re
from lib.db import get_conn, IS_POSTGRES, PH


def _bulk_insert(cur, sql_prefix, rows, page_size=1000):
    """Fast multi-row INSERT. `sql_prefix` must end with '... VALUES '.
    Postgres: one execute_values call; SQLite: executemany. Each item in
    `rows` is a full value tuple including the leading upload_id."""
    if not rows:
        return
    if IS_POSTGRES:
        from psycopg2.extras import execute_values
        execute_values(cur, sql_prefix + "%s", rows, page_size=page_size)
    else:
        ph = "(" + ",".join(["?"] * len(rows[0])) + ")"
        cur.executemany(sql_prefix + ph, rows)
from lib import employee_db as edb

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"

# Timesheet column indices (0-based) — mapped from the report layout.
C_ID, C_NAME, C_DATE = 0, 2, 7
C_WORK, C_LATE, C_EARLY = 11, 13, 14
C_OT1, C_OT15, C_OT2, C_OT3 = 17, 18, 19, 20
C_ABSENT, C_SICK, C_PERSONAL, C_ANNUAL = 21, 22, 24, 25

LEAVE_DAY_HOURS = 8.0   # convert leave/absence days -> hours
GORD = {"SG&A": 0, "MANU Support": 1, "MANU": 2}

# cost-centre code -> (group, function) crosswalk (from the FY workbook).
_MANU = {"210": "Machine shop", "213": "Weld", "214": "Small Tool",
         "220": "Laser", "221": "Folding", "222": "Weld", "223": "Misumi",
         "231": "Paint", "240": "Assembly"}
_MSUP = {"263": "Packing", "270": "Supply", "273": "Pro Sub",
         "274": "Pro Sub", "275": "Pro Sub", "280": "QP"}
_SGA = {"300": "Quality", "310": "Engineer", "313": "Engineer",
        "352": "Sales", "353": "Admin", "354": "Admin", "356": "Admin"}


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS ts_uploads (
        id {SERIAL}, label TEXT, date_from TEXT, date_to TEXT,
        n_emp INTEGER, n_days INTEGER, uploaded_at TEXT, uploaded_by TEXT)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS ts_days (
        id {SERIAL}, upload_id INTEGER, emp_no TEXT, work_date TEXT,
        working_hrs REAL, ot1 REAL, ot15 REAL, ot2 REAL, ot3 REAL,
        absent REAL, sick REAL, personal REAL, annual REAL)""")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_tsdays_up ON ts_days(upload_id)")
    conn.commit()


def _num(v):
    return float(v) if isinstance(v, (int, float)) else 0.0


def _idlike(v):
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s if (s.isdigit() and len(s) >= 6) else None


def _isodate(s):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(s).strip())
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y > 2400:           # Buddhist era -> CE
        y -= 543
    try:
        return dt.date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse_timesheet(file_bytes):
    """Returns (rows, meta). rows = list of per-employee-per-day tuples."""
    import xlrd
    sh = xlrd.open_workbook(file_contents=file_bytes,
                            on_demand=True).sheet_by_index(0)
    emp = None
    out = []
    dmin = dmax = None
    for r in range(10, sh.nrows):
        eid = _idlike(sh.cell_value(r, C_ID))
        if eid and str(sh.cell_value(r, C_NAME)).strip():
            emp = eid
        if emp and str(sh.cell_value(r, C_DATE)).strip():
            iso = _isodate(sh.cell_value(r, C_DATE))
            out.append((emp, iso,
                        _num(sh.cell_value(r, C_WORK)),
                        _num(sh.cell_value(r, C_OT1)),
                        _num(sh.cell_value(r, C_OT15)),
                        _num(sh.cell_value(r, C_OT2)),
                        _num(sh.cell_value(r, C_OT3)),
                        _num(sh.cell_value(r, C_ABSENT)),
                        _num(sh.cell_value(r, C_SICK)),
                        _num(sh.cell_value(r, C_PERSONAL)),
                        _num(sh.cell_value(r, C_ANNUAL))))
            if iso:
                dmin = iso if (not dmin or iso < dmin) else dmin
                dmax = iso if (not dmax or iso > dmax) else dmax
    emps = {e for e, *_ in out}
    return out, {"date_from": dmin, "date_to": dmax,
                 "n_emp": len(emps), "n_days": len(out)}


def apply_upload(rows, label, actor, meta):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""INSERT INTO ts_uploads (label, date_from, date_to, n_emp,
        n_days, uploaded_at, uploaded_by)
        VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
                (label, meta["date_from"], meta["date_to"], meta["n_emp"],
                 meta["n_days"], dt.datetime.now().isoformat(timespec="seconds"),
                 actor))
    conn.commit()
    if IS_POSTGRES:
        cur.execute("SELECT MAX(id) FROM ts_uploads"); uid = cur.fetchone()[0]
    else:
        uid = cur.lastrowid
    _bulk_insert(cur,
        """INSERT INTO ts_days (upload_id, emp_no, work_date, working_hrs,
            ot1, ot15, ot2, ot3, absent, sick, personal, annual) VALUES """,
        [(uid,) + tuple(d) for d in rows])
    conn.commit()
    try:
        from lib import upload_log
        upload_log.log('Timesheet (face-scan)', label, f"{meta.get('date_from','')}..{meta.get('date_to','')}", meta.get('n_days',0), actor, f"{meta.get('n_emp',0)} employees")
    except Exception:
        pass
    return uid, meta["n_emp"]


def list_uploads():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""SELECT id, label, date_from, date_to, n_emp, n_days,
        uploaded_at, uploaded_by FROM ts_uploads ORDER BY id DESC""")
    return [{"id": r[0], "label": r[1], "date_from": r[2], "date_to": r[3],
             "n_emp": r[4], "n_days": r[5], "uploaded_at": r[6],
             "uploaded_by": r[7]} for r in cur.fetchall()]


def latest_upload():
    u = list_uploads()
    return u[0] if u else None


def _code_of(cc):
    m = re.match(r"\s*(\d+)", str(cc or ""))
    return m.group(1) if m else ""


def classify(rec):
    """-> (group, function) for an employee master record."""
    code = _code_of(rec.get("cost_centre"))
    di = rec.get("direct_indirect") or ""
    if code in _MANU:
        return "MANU", _MANU[code]
    if code in _MSUP:
        return "MANU Support", _MSUP[code]
    if code in _SGA:
        return "SG&A", _SGA[code]
    return ("SG&A" if di == "Indirect" else "MANU"), \
           (rec.get("dept_location") or "—")


def is_contract(rec):
    return bool(rec.get("joined_date_sub") or rec.get("subcontract_end"))


def _master_map():
    M = {}
    for r in edb.list_records("active"):
        g, fn = classify(r)
        M[str(r.get("emp_no"))] = {
            "g": g, "fn": fn,
            "cls": "Contract" if is_contract(r) else "Permanent"}
    return M


# the metric keys accumulated per (group, function) bucket
_MK = ["hc", "perm_hc", "con_hc", "work", "perm_work", "con_work",
       "absent_h", "perm_absent_h", "con_absent_h",
       "ot1", "ot15", "ot2", "ot3", "al_h", "perm_al_h", "con_al_h",
       "sick_d", "personal_d", "absent_d", "annual_d"]


def report_rows(upload_id, date_from=None, date_to=None, absent_types=None,
                day_hours=None, weekday_hours=None, type_hours=None):
    """Aggregate into the Working-Hour-Report structure.
    absent_types: subset of {'absent','sick','personal','annual'} counted as
    absence. annual leave is ALSO always reported separately as AL.
    day_hours: flat standard working hours per day (legacy single value).
    weekday_hours: optional {0..6 (Mon..Sun): hours} — each leave/absence day
        converts using THAT weekday's standard.
    type_hours: optional {'absent'/'sick'/'personal'/'annual': hours} — a type
        override that forces that many hours per day for that type (wins over
        the weekday standard). When weekday_hours/type_hours are given, the
        per-day path is used; otherwise the flat day_hours path runs."""
    if absent_types is None:
        absent_types = {"absent", "sick", "personal"}
    if day_hours is None:
        day_hours = LEAVE_DAY_HOURS
    weekday_hours = weekday_hours or {}
    type_hours = type_hours or {}
    use_perday = bool(weekday_hours or type_hours)
    conn = get_conn(); cur = conn.cursor()

    def _fac(t, wkday):
        if t in type_hours and type_hours[t] is not None:
            return type_hours[t]
        return weekday_hours.get(wkday, day_hours)

    per = {}   # emp_no -> normalized dict (absh/alh already in hours)
    if use_perday:
        sql = (f"""SELECT emp_no, work_date, working_hrs, ot1, ot15, ot2, ot3,
            absent, sick, personal, annual FROM ts_days WHERE upload_id={PH}""")
        args = [upload_id]
        if date_from:
            sql += f" AND work_date>={PH}"; args.append(date_from)
        if date_to:
            sql += f" AND work_date<={PH}"; args.append(date_to)
        cur.execute(sql, args)
        import datetime as _dt
        for row in cur.fetchall():
            (emp_no, wd, work, ot1, ot15, ot2, ot3,
             absent, sick, personal, annual) = row
            try:
                wkday = _dt.date.fromisoformat(str(wd)).weekday()
            except Exception:
                wkday = 0
            absh = (((absent or 0) * _fac("absent", wkday)
                     if "absent" in absent_types else 0)
                    + ((sick or 0) * _fac("sick", wkday)
                       if "sick" in absent_types else 0)
                    + ((personal or 0) * _fac("personal", wkday)
                       if "personal" in absent_types else 0)
                    + ((annual or 0) * _fac("annual", wkday)
                       if "annual" in absent_types else 0))
            alh = (annual or 0) * _fac("annual", wkday)
            a = per.setdefault(emp_no, {"work": 0.0, "ot1": 0.0, "ot15": 0.0,
                                        "ot2": 0.0, "ot3": 0.0, "absh": 0.0,
                                        "alh": 0.0, "absent": 0.0, "sick": 0.0,
                                        "personal": 0.0, "annual": 0.0})
            a["work"] += work or 0
            a["ot1"] += ot1 or 0; a["ot15"] += ot15 or 0
            a["ot2"] += ot2 or 0; a["ot3"] += ot3 or 0
            a["absh"] += absh; a["alh"] += alh
            a["absent"] += absent or 0; a["sick"] += sick or 0
            a["personal"] += personal or 0; a["annual"] += annual or 0
    else:
        sql = (f"""SELECT emp_no, SUM(working_hrs), SUM(ot1), SUM(ot15),
            SUM(ot2), SUM(ot3), SUM(absent), SUM(sick), SUM(personal),
            SUM(annual) FROM ts_days WHERE upload_id={PH}""")
        args = [upload_id]
        if date_from:
            sql += f" AND work_date>={PH}"; args.append(date_from)
        if date_to:
            sql += f" AND work_date<={PH}"; args.append(date_to)
        sql += " GROUP BY emp_no"
        cur.execute(sql, args)
        for r in cur.fetchall():
            (work, ot1, ot15, ot2, ot3, absent, sick,
             personal, annual) = r[1:]
            absd = ((absent if "absent" in absent_types else 0)
                    + (sick if "sick" in absent_types else 0)
                    + (personal if "personal" in absent_types else 0)
                    + (annual if "annual" in absent_types else 0))
            per[r[0]] = {"work": work or 0, "ot1": ot1 or 0, "ot15": ot15 or 0,
                         "ot2": ot2 or 0, "ot3": ot3 or 0,
                         "absh": (absd or 0) * day_hours,
                         "alh": (annual or 0) * day_hours,
                         "absent": absent or 0, "sick": sick or 0,
                         "personal": personal or 0, "annual": annual or 0}

    M = _master_map()
    from collections import defaultdict
    buckets = defaultdict(lambda: {k: 0.0 for k in _MK})
    for eid, a in per.items():
        m = M.get(eid)
        if not m:
            continue
        work = a["work"]; absh = a["absh"]; alh = a["alh"]
        perm = m["cls"] == "Permanent"
        b = buckets[(m["g"], m["fn"])]
        b["hc"] += 1
        b["perm_hc"] += 1 if perm else 0
        b["con_hc"] += 0 if perm else 1
        b["work"] += work
        b["perm_work"] += work if perm else 0
        b["con_work"] += 0 if perm else work
        b["absent_h"] += absh
        b["perm_absent_h"] += absh if perm else 0
        b["con_absent_h"] += 0 if perm else absh
        b["al_h"] += alh
        b["perm_al_h"] += alh if perm else 0
        b["con_al_h"] += 0 if perm else alh
        b["ot1"] += a["ot1"]; b["ot15"] += a["ot15"]
        b["ot2"] += a["ot2"]; b["ot3"] += a["ot3"]
        b["sick_d"] += a["sick"]; b["personal_d"] += a["personal"]
        b["absent_d"] += a["absent"]; b["annual_d"] += a["annual"]

    def finalize(b):
        d = dict(b)
        d["tp_hc"] = 0
        d["total_ot"] = b["ot1"] + b["ot15"] + b["ot2"] + b["ot3"]
        base = b["work"] + b["absent_h"]
        pbase = b["perm_work"] + b["perm_absent_h"]
        cbase = b["con_work"] + b["con_absent_h"]
        d["pct_absent"] = (b["absent_h"] / base * 100) if base else 0.0
        d["pct_perm_absent"] = (b["perm_absent_h"] / pbase * 100) if pbase else 0.0
        d["pct_con_absent"] = (b["con_absent_h"] / cbase * 100) if cbase else 0.0
        d["pct_ot"] = (d["total_ot"] / b["work"] * 100) if b["work"] else 0.0
        return d

    rows = []
    for (g, fn), b in sorted(buckets.items(),
                             key=lambda kv: (GORD.get(kv[0][0], 9), kv[0][1])):
        d = finalize(b); d["group"] = g; d["function"] = fn
        rows.append(d)
    return rows


def months(upload_id):
    """Distinct YYYY-MM present in the upload."""
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT DISTINCT substr(work_date,1,7) FROM ts_days
        WHERE upload_id={PH} AND work_date IS NOT NULL ORDER BY 1""",
                (upload_id,))
    return [r[0] for r in cur.fetchall() if r[0]]
