# lib/employee_db.py
# ============================================================================
# Employee Data + Leave/OT module — database layer.
# Works on BOTH SQLite (local dev) and Supabase Postgres (production),
# reusing your existing lib/db.py get_conn() switch.
#
# Every write goes through _audit() -> table employee_audit_log records
# who / when / what (old value -> new value, JSON), satisfying requirement 4
# ("update log to track who's update the data").
# ============================================================================

import json
import datetime as dt

try:  # your existing connection switch (SQLite <-> Supabase Postgres)
    from lib.db import get_conn, IS_POSTGRES
except ImportError:  # standalone fallback for local testing of this module
    import sqlite3, os
    IS_POSTGRES = False

    def get_conn():
        os.makedirs("data", exist_ok=True)
        c = sqlite3.connect("data/hr.db")
        c.row_factory = sqlite3.Row
        return c

from lib.employee_schema import FIELDS, BY_KEY, RECORD_STATUSES

PH = "%s" if IS_POSTGRES else "?"


def _ts():
    return dt.datetime.now().isoformat(timespec="seconds")


def _col_sql(f):
    t = {"int": "INTEGER", "float": "REAL" if not IS_POSTGRES else "NUMERIC",
         "date": "TEXT", "bool": "INTEGER"}.get(f.typ, "TEXT")
    return f"{f.key} {t}"


SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"
BLOB = "BYTEA" if IS_POSTGRES else "BLOB"


def migrate():
    """Idempotent — safe to call from init_db() on every boot."""
    conn = get_conn()
    cur = conn.cursor()
    field_cols = ",\n        ".join(_col_sql(f) for f in FIELDS)

    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS employees (
        id {SERIAL},
        record_status TEXT NOT NULL DEFAULT 'candidate',
        {field_cols},
        photo {BLOB},
        photo_mime TEXT,
        created_at TEXT, created_by TEXT,
        updated_at TEXT, updated_by TEXT,
        pdpa_consent_at TEXT,
        candidate_token TEXT
    )""")

    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS employee_change_requests (
        id {SERIAL},
        employee_id INTEGER NOT NULL,
        field_key TEXT NOT NULL,
        old_value TEXT, new_value TEXT,
        requested_by TEXT NOT NULL, requested_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',   -- pending/approved/rejected
        reviewed_by TEXT, reviewed_at TEXT, review_note TEXT
    )""")

    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS employee_audit_log (
        id {SERIAL},
        at TEXT NOT NULL, actor TEXT NOT NULL,
        action TEXT NOT NULL,           -- create/update/promote/bulk_upload/
                                        -- approve_change/reject_change/export/...
        employee_id INTEGER, emp_no TEXT,
        detail TEXT                     -- JSON map of field -> [old, new]
    )""")

    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS leave_requests (
        id {SERIAL},
        employee_id INTEGER NOT NULL, emp_no TEXT,
        leave_type TEXT NOT NULL,       -- annual/sick/business/maternity/
                                        -- without_pay/other
        date_from TEXT NOT NULL, date_to TEXT NOT NULL,
        period TEXT NOT NULL DEFAULT 'full',  -- full/half_am/half_pm
        days REAL, reason TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        requested_by TEXT, requested_at TEXT,
        approver TEXT, approved_at TEXT, approve_note TEXT
    )""")

    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS ot_requests (
        id {SERIAL},
        employee_id INTEGER NOT NULL, emp_no TEXT,
        ot_date TEXT NOT NULL,
        time_from TEXT NOT NULL, time_to TEXT NOT NULL,
        hours REAL, rate REAL,          -- 1.5 / 2.0 / 3.0 (per your payroll
                                        -- codes 1120/1130/1140, divisor 176)
        ot_type TEXT,                   -- scenario key (after_workday/holiday…)
        work_order_no TEXT,             -- Work Order No. (req. 5)
        shift TEXT,                     -- day / night
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        requested_by TEXT, requested_at TEXT,
        approver TEXT, approved_at TEXT, approve_note TEXT
    )""")

    # Shift-change requests (req. 6). Carries requester_emp_no/requester_name
    # so approval_db.pending_overview() can show it in the HR pipeline.
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS shift_change_requests (
        id {SERIAL},
        employee_id INTEGER NOT NULL, emp_no TEXT,
        requester_emp_no TEXT, requester_name TEXT,
        current_shift TEXT NOT NULL,    -- day / night
        requested_shift TEXT NOT NULL,  -- day / night
        date_from TEXT NOT NULL, date_to TEXT,
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        requested_by TEXT, requested_at TEXT,
        approver TEXT, approved_at TEXT, approve_note TEXT
    )""")

    # Face-scan time-edit / time-record requests (req. 9, FM-HR time-edit form).
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS time_edit_requests (
        id {SERIAL},
        employee_id INTEGER NOT NULL, emp_no TEXT,
        requester_emp_no TEXT, requester_name TEXT,
        work_date TEXT NOT NULL, shift TEXT,
        doc_type TEXT,                  -- 'edit' (แก้ไข) / 'record' (บันทึกลงเวลา)
        original_scans TEXT,            -- what the face-scan currently shows
        req_time_in TEXT, req_time_out TEXT,
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        requested_by TEXT, requested_at TEXT,
        approver TEXT, approved_at TEXT, approve_note TEXT
    )""")
    conn.commit()

    # Document number on each request (issued from lib.doc_numbers). Added by
    # ALTER so existing databases pick it up without a rebuild.
    for _t in ("leave_requests", "ot_requests", "shift_change_requests",
               "time_edit_requests"):
        try:
            cur.execute(f"ALTER TABLE {_t} ADD COLUMN doc_no TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
    # Leave: unit/hours (hourly leave) + evidence upload (item 8 / 10)
    for _col, _type in (("unit", "TEXT"), ("hours", "REAL"),
                        ("evidence_name", "TEXT"), ("evidence_mime", "TEXT"),
                        ("evidence_data", "TEXT")):
        try:
            cur.execute(f"ALTER TABLE leave_requests ADD COLUMN {_col} {_type}")
            conn.commit()
        except Exception:
            conn.rollback()

    # Backfill columns on databases created before req. 5 (existing prod data).
    _ensure_cols(conn, "ot_requests",
                 [("ot_type", "TEXT"), ("work_order_no", "TEXT"),
                  ("shift", "TEXT")])
    return conn


def _ensure_cols(conn, table, cols):
    """Add missing columns to an existing table, one at a time, committing
    each so a duplicate-column error on one never aborts the others
    (mirrors the Postgres-safe pattern used across the app)."""
    cur = conn.cursor()
    for name, ddl in cols:
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass


# ---------------------------------------------------------------- audit
def _audit(conn, actor, action, employee_id=None, emp_no=None, detail=None):
    conn.cursor().execute(
        f"""INSERT INTO employee_audit_log (at, actor, action, employee_id,
            emp_no, detail) VALUES ({PH},{PH},{PH},{PH},{PH},{PH})""",
        (_ts(), actor, action, employee_id, emp_no,
         json.dumps(detail, ensure_ascii=False) if detail else None))


def audit_log(limit=500, employee_id=None):
    conn = get_conn(); cur = conn.cursor()
    if employee_id:
        cur.execute(f"""SELECT * FROM employee_audit_log
                        WHERE employee_id={PH}
                        ORDER BY id DESC LIMIT {int(limit)}""", (employee_id,))
    else:
        cur.execute(f"""SELECT * FROM employee_audit_log
                        ORDER BY id DESC LIMIT {int(limit)}""")
    return cur.fetchall()


# ---------------------------------------------------------------- CRUD
def create_record(values: dict, actor: str, record_status="candidate",
                  pdpa_consent=False, token=None):
    conn = get_conn(); cur = conn.cursor()
    keys = [k for k in values if k in BY_KEY]
    cols = ["record_status", "created_at", "created_by",
            "updated_at", "updated_by"] + keys
    vals = [record_status, _ts(), actor, _ts(), actor] + \
           [values[k] for k in keys]
    if pdpa_consent:
        cols.append("pdpa_consent_at"); vals.append(_ts())
    if token:
        cols.append("candidate_token"); vals.append(token)
    sql = (f"INSERT INTO employees ({','.join(cols)}) "
           f"VALUES ({','.join([PH]*len(vals))})")
    if IS_POSTGRES:
        sql += " RETURNING id"
        cur.execute(sql, vals); new_id = cur.fetchone()[0]
    else:
        cur.execute(sql, vals); new_id = cur.lastrowid
    _audit(conn, actor, "create", new_id, values.get("emp_no"),
           {k: [None, values[k]] for k in keys})
    conn.commit()
    return new_id


def update_record(employee_id: int, changes: dict, actor: str):
    """Direct update (admin path). Audited field-by-field."""
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM employees WHERE id={PH}", (employee_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"employee id {employee_id} not found")
    old = dict(row) if not IS_POSTGRES else \
        dict(zip([d[0] for d in cur.description], row))
    diff = {k: [old.get(k), v] for k, v in changes.items()
            if k in BY_KEY and str(old.get(k) or "") != str(v or "")}
    if not diff:
        return {}
    sets = ", ".join(f"{k}={PH}" for k in diff)
    cur.execute(
        f"UPDATE employees SET {sets}, updated_at={PH}, updated_by={PH} "
        f"WHERE id={PH}",
        [diff[k][1] for k in diff] + [_ts(), actor, employee_id])
    _audit(conn, actor, "update", employee_id, old.get("emp_no"), diff)
    conn.commit()
    return diff


def set_status(employee_id: int, new_status: str, actor: str):
    assert new_status in RECORD_STATUSES
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT record_status, emp_no FROM employees WHERE id={PH}",
                (employee_id,))
    r = cur.fetchone()
    cur.execute(f"UPDATE employees SET record_status={PH}, updated_at={PH}, "
                f"updated_by={PH} WHERE id={PH}",
                (new_status, _ts(), actor, employee_id))
    _audit(conn, actor, f"status:{r[0]}->{new_status}", employee_id, r[1])
    conn.commit()


def promote_candidate(employee_id: int, emp_no: str, org_values: dict,
                      actor: str):
    """Requirement 1: qualified candidate -> transfer into employee master.
    Assigns Emp No. + org fields (dept, cost centre, title, joined date...)
    then flips record_status to 'upcoming' (start date in future) or 'active'.
    """
    changes = dict(org_values); changes["emp_no"] = emp_no
    diff = update_record(employee_id, changes, actor)
    status = "upcoming"
    jd = changes.get("joined_date")
    if jd and str(jd) <= dt.date.today().isoformat():
        status = "active"
    set_status(employee_id, status, actor)
    conn = get_conn()
    _audit(conn, actor, "promote", employee_id, emp_no, diff)
    conn.commit()
    return status


def get_record(employee_id=None, emp_no=None, token=None):
    conn = get_conn(); cur = conn.cursor()
    if employee_id:
        cur.execute(f"SELECT * FROM employees WHERE id={PH}", (employee_id,))
    elif emp_no:
        cur.execute(f"SELECT * FROM employees WHERE emp_no={PH}", (emp_no,))
    elif token:
        cur.execute(f"SELECT * FROM employees WHERE candidate_token={PH}",
                    (token,))
    else:
        return None
    row = cur.fetchone()
    if row is None:
        return None
    return dict(zip([d[0] for d in cur.description],
                    row)) if IS_POSTGRES else dict(row)


def list_records(record_status=None):
    conn = get_conn(); cur = conn.cursor()
    if record_status:
        cur.execute(f"""SELECT * FROM employees WHERE record_status={PH}
                        ORDER BY emp_no""", (record_status,))
    else:
        cur.execute("SELECT * FROM employees ORDER BY record_status, emp_no")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


# ---------------------------------------------------------------- photos
def save_photo(employee_id: int, raw_bytes: bytes, actor: str):
    """Same processing rules as the previous org-chart photo system:
    EXIF-rotate -> centre-crop square -> 200x200 -> JPEG q85, <=100 KB."""
    import io
    from PIL import Image, ImageOps
    img = Image.open(io.BytesIO(raw_bytes))
    img = ImageOps.exif_transpose(img).convert("RGB")
    w, h = img.size; m = min(w, h)
    img = img.crop(((w - m)//2, (h - m)//2, (w + m)//2, (h + m)//2))
    img = img.resize((200, 200), Image.LANCZOS)
    q = 85
    while True:
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=q)
        if buf.tell() <= 100_000 or q <= 40:
            break
        q -= 10
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"UPDATE employees SET photo={PH}, photo_mime={PH}, "
                f"updated_at={PH}, updated_by={PH} WHERE id={PH}",
                (buf.getvalue(), "image/jpeg", _ts(), actor, employee_id))
    _audit(conn, actor, "photo_upload", employee_id)
    conn.commit()


def photos_as_data_uris():
    """{exact org-chart node name: data URI} for injection into
    AMS-org-chart.html at the /*__PHOTOS_JSON__*/ marker.
    Node names look like 'Nicholas Doyle  (Nicky)' (two spaces + nickname)."""
    import base64
    out = {}
    for r in list_records("active"):
        if not r.get("photo"):
            continue
        name = (r.get("emp_name_en") or "")
        # strip title prefix the way the chart generator did
        for t in ("Mr.", "Ms.", "Mrs.", "Miss"):
            name = name.replace(t, "").strip()
        nick = (r.get("nickname") or "").strip()
        key = f"{name}  ({nick})" if nick else name
        b = r["photo"]
        b = bytes(b) if not isinstance(b, bytes) else b
        out[key] = ("data:image/jpeg;base64," +
                    base64.b64encode(b).decode())
    return out


def orgchart_emp_map():
    """{exact org-chart node name: {emp_no, nickname, dept, phone, email,
    manager}} for the profile bubble. Only non-sensitive preview fields —
    salary/PDPA fields are never included here; they stay server-side and
    role-gated on the profile page."""
    out = {}
    for r in list_records("active"):
        name = (r.get("emp_name_en") or "")
        for t in ("Mr.", "Ms.", "Mrs.", "Miss"):
            name = name.replace(t, "").strip()
        nick = (r.get("nickname") or "").strip()
        key = f"{name}  ({nick})" if nick else name
        out[key] = {
            "emp_no": r.get("emp_no") or "",
            "nickname": nick,
            "dept": r.get("dept_location") or "",
            "phone": r.get("mobile") or "",
            "email": r.get("personal_email") or "",
            "manager": (r.get("mgr_name") or "").replace("Mr.", "")
                       .replace("Ms.", "").replace("Mrs.", "")
                       .replace("Miss", "").strip(),
        }
    return out


# ---------------------------------------------------------------- change requests (requirement 2)
def submit_change_request(employee_id, field_key, new_value, actor):
    rec = get_record(employee_id=employee_id)
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        f"""INSERT INTO employee_change_requests
            (employee_id, field_key, old_value, new_value,
             requested_by, requested_at)
            VALUES ({PH},{PH},{PH},{PH},{PH},{PH})""",
        (employee_id, field_key, str(rec.get(field_key) or ""),
         str(new_value), actor, _ts()))
    _audit(conn, actor, "change_request", employee_id, rec.get("emp_no"),
           {field_key: [rec.get(field_key), new_value]})
    conn.commit()


def pending_change_requests():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""SELECT cr.*, e.emp_no AS e_emp_no,
                          e.emp_name_en AS e_name
                   FROM employee_change_requests cr
                   JOIN employees e ON e.id = cr.employee_id
                   WHERE cr.status='pending' ORDER BY cr.id""")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


def review_change_request(req_id, approve: bool, reviewer: str, note=""):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM employee_change_requests WHERE id={PH}",
                (req_id,))
    row = cur.fetchone()
    req = dict(zip([d[0] for d in cur.description],
                   row)) if IS_POSTGRES else dict(row)
    status = "approved" if approve else "rejected"
    cur.execute(f"""UPDATE employee_change_requests
                    SET status={PH}, reviewed_by={PH}, reviewed_at={PH},
                        review_note={PH} WHERE id={PH}""",
                (status, reviewer, _ts(), note, req_id))
    conn.commit()
    if approve:  # requirement 2: only applied once admin approves
        update_record(req["employee_id"], {req["field_key"]:
                                           req["new_value"]}, reviewer)
    conn = get_conn()
    _audit(conn, reviewer, f"{status}_change", req["employee_id"],
           detail={req["field_key"]: [req["old_value"], req["new_value"]]})
    conn.commit()


# ---------------------------------------------------------------- leave / OT (requirement 5)
def submit_leave(employee_id, emp_no, leave_type, date_from, date_to,
                 period, days, reason, actor, unit="day", hours=None,
                 evidence=None):
    conn = get_conn(); cur = conn.cursor()
    from lib import doc_numbers
    doc = doc_numbers.issue("leave", "leave_requests", None, actor)
    ev = evidence or {}
    cur.execute(
        f"""INSERT INTO leave_requests (employee_id, emp_no, leave_type,
            date_from, date_to, period, days, reason, requested_by,
            requested_at, doc_no, unit, hours, evidence_name, evidence_mime,
            evidence_data)
            VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
        (employee_id, emp_no, leave_type, date_from, date_to, period,
         days, reason, actor, _ts(), doc, unit, hours, ev.get("name"),
         ev.get("mime"), ev.get("data")))
    _audit(conn, actor, "leave_submit", employee_id, emp_no,
           {"type": leave_type, "from": str(date_from), "to": str(date_to),
            "days": days, "unit": unit, "hours": hours, "doc_no": doc,
            "evidence": bool(ev.get("data"))})
    conn.commit()
    doc_numbers.link(doc, "leave_requests")
    return doc


def submit_ot(employee_id, emp_no, ot_date, time_from, time_to, hours,
              rate, reason, actor, ot_type=None, work_order_no=None,
              shift=None):
    conn = get_conn(); cur = conn.cursor()
    from lib import doc_numbers
    doc = doc_numbers.issue("ot", "ot_requests", None, actor)
    cur.execute(
        f"""INSERT INTO ot_requests (employee_id, emp_no, ot_date, time_from,
            time_to, hours, rate, ot_type, work_order_no, shift, reason,
            requested_by, requested_at, doc_no)
            VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
        (employee_id, emp_no, str(ot_date), str(time_from), str(time_to),
         hours, rate, ot_type, work_order_no, shift, reason, actor, _ts(),
         doc))
    _audit(conn, actor, "ot_submit", employee_id, emp_no,
           {"date": str(ot_date), "hours": hours, "rate": rate,
            "ot_type": ot_type, "wo": work_order_no, "doc_no": doc})
    conn.commit()
    doc_numbers.link(doc, "ot_requests")
    return doc


def submit_shift_change(employee_id, emp_no, requester_name, current_shift,
                        requested_shift, date_from, date_to, reason, actor):
    conn = get_conn(); cur = conn.cursor()
    from lib import doc_numbers
    doc = doc_numbers.issue("shift", "shift_change_requests", None, actor)
    cur.execute(
        f"""INSERT INTO shift_change_requests (employee_id, emp_no,
            requester_emp_no, requester_name, current_shift, requested_shift,
            date_from, date_to, reason, requested_by, requested_at, doc_no)
            VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
        (employee_id, emp_no, str(emp_no), requester_name, current_shift,
         requested_shift, str(date_from),
         str(date_to) if date_to else None, reason, actor, _ts(), doc))
    _audit(conn, actor, "shift_submit", employee_id, emp_no,
           {"from": current_shift, "to": requested_shift,
            "eff": str(date_from), "doc_no": doc})
    conn.commit()
    doc_numbers.link(doc, "shift_change_requests")
    return doc


def submit_time_edit(employee_id, emp_no, requester_name, work_date, shift,
                     doc_type, original_scans, req_time_in, req_time_out,
                     reason, actor):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        f"""INSERT INTO time_edit_requests (employee_id, emp_no,
            requester_emp_no, requester_name, work_date, shift, doc_type,
            original_scans, req_time_in, req_time_out, reason, requested_by,
            requested_at)
            VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
        (employee_id, emp_no, str(emp_no), requester_name, str(work_date),
         shift, doc_type, original_scans, req_time_in, req_time_out, reason,
         actor, _ts()))
    _audit(conn, actor, "timeedit_submit", employee_id, emp_no,
           {"date": str(work_date), "in": req_time_in, "out": req_time_out})
    conn.commit()


def pending_requests(kind):  # kind: 'leave' | 'ot'
    table = "leave_requests" if kind == "leave" else "ot_requests"
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT r.*, e.emp_name_en AS e_name, e.dept_location
                    FROM {table} r JOIN employees e ON e.id=r.employee_id
                    WHERE r.status='pending' ORDER BY r.id""")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


def my_requests(kind, employee_id, limit=50):
    table = {"leave": "leave_requests", "ot": "ot_requests",
             "shift": "shift_change_requests",
             "timeedit": "time_edit_requests"}[kind]
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT * FROM {table} WHERE employee_id={PH}
                    ORDER BY id DESC LIMIT {int(limit)}""", (employee_id,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


def review_request(kind, req_id, approve, reviewer, note=""):
    table = "leave_requests" if kind == "leave" else "ot_requests"
    status = "approved" if approve else "rejected"
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""UPDATE {table} SET status={PH}, approver={PH},
                    approved_at={PH}, approve_note={PH} WHERE id={PH}""",
                (status, reviewer, _ts(), note, req_id))
    _audit(conn, reviewer, f"{kind}_{status}", detail={"request_id": req_id,
                                                       "note": note})
    conn.commit()
