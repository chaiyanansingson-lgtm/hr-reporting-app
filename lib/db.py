"""
Database layer.  SQLite for the prototype; swap DATABASE_URL to Postgres
(e.g. Supabase) for production with no other code changes.
"""
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "hr.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def cursor():
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS employees (
    emp_no TEXT PRIMARY KEY,
    emp_name TEXT,
    emp_type TEXT,        -- PER / SUB / TEM
    cost_code TEXT,
    level INTEGER,
    d_in TEXT,            -- Direct / Indirect
    is_active INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS managers (
    emp_no TEXT PRIMARY KEY,
    title TEXT,
    is_manager INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cost_groups (
    code TEXT PRIMARY KEY,
    department TEXT,            -- mid level (Function), e.g. 'Admin', 'CNC'
    sg_a_manu TEXT,             -- top level: 'SG&A' / 'MANU' / 'MANU Support'
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS holidays (
    holiday_date TEXT PRIMARY KEY,
    holiday_name TEXT
);

CREATE TABLE IF NOT EXISTS hour_config (
    config_key TEXT PRIMARY KEY,
    config_value REAL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS targets (
    target_key TEXT PRIMARY KEY,
    target_value REAL,                -- as decimal (0.025 = 2.5%)
    description TEXT
);

CREATE TABLE IF NOT EXISTS timesheet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_no TEXT NOT NULL,
    work_date TEXT NOT NULL,
    period TEXT NOT NULL,         -- YYYY-MM
    shift_code TEXT,
    work_hours REAL DEFAULT 0,
    late_hours REAL DEFAULT 0,
    early_hours REAL DEFAULT 0,
    ot1_hours REAL DEFAULT 0,
    ot15_hours REAL DEFAULT 0,
    ot2_hours REAL DEFAULT 0,
    ot3_hours REAL DEFAULT 0,
    absent_hours REAL DEFAULT 0,
    sick_hours REAL DEFAULT 0,
    personal_hours REAL DEFAULT 0,
    annual_hours REAL DEFAULT 0,
    UNIQUE(emp_no, work_date)
);
CREATE INDEX IF NOT EXISTS idx_timesheet_period ON timesheet(period);
CREATE INDEX IF NOT EXISTS idx_timesheet_empno ON timesheet(emp_no);

-- Detailed OT entries: one row per OT occurrence with proper date
-- When this table has data for a period, it overrides the timesheet OT columns
-- so monthly aggregation is always correct regardless of timesheet date range.
CREATE TABLE IF NOT EXISTS ot_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_no TEXT NOT NULL,
    work_date TEXT NOT NULL,
    period TEXT NOT NULL,
    multiplier REAL NOT NULL,
    hours REAL NOT NULL,
    ot_type TEXT,
    ot_period TEXT
);
CREATE INDEX IF NOT EXISTS idx_ot_entries_period ON ot_entries(period);
CREATE INDEX IF NOT EXISTS idx_ot_entries_empdate ON ot_entries(emp_no, work_date);

CREATE TABLE IF NOT EXISTS upload_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_type TEXT,
    file_name TEXT,
    period TEXT,
    rows_inserted INTEGER,
    uploaded_by TEXT,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Per-month override for working days / daily std hours.  When a row exists for
-- a period, its values are used in Standard-mode WH calculation instead of the
-- holiday + weekday-hours auto-computation.  (Matches cells F36/F37 in the
-- existing Excel report's per-month Notes section.)
CREATE TABLE IF NOT EXISTS period_overrides (
    period TEXT PRIMARY KEY,            -- YYYY-MM
    working_days INTEGER,               -- override; NULL = auto
    daily_std_hours REAL,               -- override; NULL = auto (avg of weekday hours)
    notes TEXT
);

-- Manager-submitted requests to change employee data.  Admin reviews and
-- approves/rejects.  Approved changes are applied to the employees table.
CREATE TABLE IF NOT EXISTS change_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_no TEXT NOT NULL,
    field_name TEXT NOT NULL,           -- cost_code, emp_type, d_in, level
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    status TEXT DEFAULT 'pending',      -- pending, approved, rejected
    submitted_by TEXT,
    submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_change_requests_status ON change_requests(status);
CREATE INDEX IF NOT EXISTS idx_change_requests_emp ON change_requests(emp_no);

-- Sign-up requests submitted by users via the sign-up screen.
-- Admin reviews and approves -> creates the actual user account.
CREATE TABLE IF NOT EXISTS signup_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requested_username TEXT NOT NULL,
    requested_email TEXT NOT NULL,
    requested_full_name TEXT,
    requested_emp_no TEXT,             -- optional: link to an existing employee
    requested_role TEXT DEFAULT 'viewer',  -- desired role: viewer/manager
    reason TEXT,                        -- why they need access
    password_hash TEXT NOT NULL,        -- bcrypt hash of their chosen password
    status TEXT DEFAULT 'pending',      -- pending / approved / rejected
    request_ip TEXT,
    request_user_agent TEXT,
    submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_notes TEXT,
    granted_role TEXT                   -- role admin actually granted (may differ from requested)
);
CREATE INDEX IF NOT EXISTS idx_signup_status ON signup_requests(status);

-- Audit log: every sign-in attempt (success and failure) with IP + user agent.
CREATE TABLE IF NOT EXISTS login_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,                      -- attempted username (may not exist)
    success INTEGER NOT NULL,           -- 1 = login succeeded, 0 = failed
    ip_address TEXT,
    user_agent TEXT,
    role_at_login TEXT,                 -- role of the user (if login succeeded)
    failure_reason TEXT,                -- "wrong password", "user not found", etc.
    occurred_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_login_audit_user ON login_audit(username);
CREATE INDEX IF NOT EXISTS idx_login_audit_when ON login_audit(occurred_at);

-- Extended employee fields (so we can show org chart, dept, manager, etc.)
-- Augments the basic employees table with the richer fields from MASTER list.
CREATE TABLE IF NOT EXISTS employees_extended (
    emp_no TEXT PRIMARY KEY,
    nickname TEXT,
    name_th TEXT,
    dept_by_location TEXT,              -- "Admin", "HR", "Engineer", etc.
    cost_centre_name TEXT,              -- "354 - Finance&HR&Admin&Safety Department"
    title TEXT,
    manager_name TEXT,                  -- the "Mgr" column - text name of manager (may be empty)
    manager_emp_no TEXT,                -- resolved employee number of manager (FK if found)
    is_mgr_role TEXT,                   -- "Mgr." / "Sup." / "Leader" / NULL
    thai_or_expat TEXT,                 -- "Thai" / "Expat"
    joined_date TEXT,                   -- ISO date
    status TEXT,                        -- "AMS" / "SUB" / "Guard" / "CNK"
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (emp_no) REFERENCES employees(emp_no) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_emp_ext_mgr ON employees_extended(manager_emp_no);
CREATE INDEX IF NOT EXISTS idx_emp_ext_dept ON employees_extended(dept_by_location);

-- Personal user overrides — each user can have their own copy of holidays,
-- hour config, period overrides, cost-group top assignments. These NEVER
-- affect the master DB; they only change what THIS user sees in Reports/Charts
-- when the "Use my personal settings" toggle is on.
CREATE TABLE IF NOT EXISTS user_overrides (
    username TEXT NOT NULL,
    setting_type TEXT NOT NULL,
    setting_data TEXT NOT NULL,         -- JSON-encoded
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (username, setting_type)
);
CREATE INDEX IF NOT EXISTS idx_user_overrides ON user_overrides(username);
"""


def init_db():
    with cursor() as cur:
        cur.executescript(SCHEMA_SQL)
        # Seed default hour_config if empty
        cur.execute("SELECT COUNT(*) AS c FROM hour_config")
        if cur.fetchone()["c"] == 0:
            defaults = [
                ("monday_hours", 8.0, "Standard working hours on Monday"),
                ("tuesday_hours", 8.0, "Standard working hours on Tuesday"),
                ("wednesday_hours", 8.0, "Standard working hours on Wednesday"),
                ("thursday_hours", 8.0, "Standard working hours on Thursday"),
                ("friday_hours", 8.0, "Standard working hours on Friday"),
                ("saturday_hours", 0.0, "Standard working hours on Saturday"),
                ("sunday_hours", 0.0, "Standard working hours on Sunday"),
                ("hours_per_day", 8.0, "Hours <-> day conversion factor"),
                ("ot1_multiplier", 1.0, "OT*1 multiplier"),
                ("ot15_multiplier", 1.5, "OT*1.5 multiplier"),
                ("ot2_multiplier", 2.0, "OT*2 multiplier"),
                ("ot3_multiplier", 3.0, "OT*3 multiplier"),
            ]
            cur.executemany(
                "INSERT INTO hour_config(config_key, config_value, description) VALUES (?,?,?)",
                defaults,
            )
        # Seed default KPI targets (decimals: 0.025 = 2.5%)
        cur.execute("SELECT COUNT(*) AS c FROM targets")
        if cur.fetchone()["c"] == 0:
            target_defaults = [
                ("absenteeism_total", 0.025, "Total Absenteeism % target (2.5%)"),
                ("sick_leave",      0.0440, "Sick Leave % target (4.4%)"),
                ("business_leave",  0.0189, "Business Leave % target (1.9%)"),
                ("other_leaves",    0.0151, "Other Leaves % target (1.5%)"),
                ("without_pay",     0.0000, "Without Pay % target (0%)"),
                ("annual_leave",    0.0692, "Annual Leave % target (6.9%)"),
                ("ot_total",        0.2800, "OT % target (28%)"),
                ("turnover",        0.0200, "Turnover rate target (2%)"),
            ]
            cur.executemany(
                "INSERT INTO targets(target_key, target_value, description) VALUES (?,?,?)",
                target_defaults,
            )


# ---------- helper accessors used across pages ----------

def get_hour_config():
    with cursor() as cur:
        cur.execute("SELECT config_key, config_value FROM hour_config")
        return {r["config_key"]: r["config_value"] for r in cur.fetchall()}


def update_hour_config(key, value):
    with cursor() as cur:
        cur.execute(
            "UPDATE hour_config SET config_value = ? WHERE config_key = ?",
            (float(value), key),
        )


def get_targets():
    """Return all KPI targets as {key: decimal_value}."""
    with cursor() as cur:
        cur.execute("SELECT target_key, target_value FROM targets")
        return {r["target_key"]: r["target_value"] for r in cur.fetchall()}


def update_target(key, value):
    with cursor() as cur:
        cur.execute(
            "UPDATE targets SET target_value = ? WHERE target_key = ?",
            (float(value), key),
        )


def list_holidays():
    with cursor() as cur:
        cur.execute("SELECT holiday_date, holiday_name FROM holidays ORDER BY holiday_date")
        return [dict(r) for r in cur.fetchall()]


def upsert_holiday(date_str, name):
    with cursor() as cur:
        cur.execute(
            "INSERT OR REPLACE INTO holidays(holiday_date, holiday_name) VALUES (?,?)",
            (date_str, name),
        )


def delete_holiday(date_str):
    with cursor() as cur:
        cur.execute("DELETE FROM holidays WHERE holiday_date = ?", (date_str,))


def list_cost_groups():
    with cursor() as cur:
        cur.execute("""SELECT code, department, sg_a_manu, sort_order
                       FROM cost_groups ORDER BY sort_order, department, code""")
        return [dict(r) for r in cur.fetchall()]


def upsert_cost_group(code, department, sg_a_manu, sort_order=0):
    with cursor() as cur:
        cur.execute(
            """INSERT OR REPLACE INTO cost_groups(code, department, sg_a_manu, sort_order)
               VALUES (?,?,?,?)""",
            (str(code), department, sg_a_manu, int(sort_order)),
        )


def delete_cost_group(code):
    with cursor() as cur:
        cur.execute("DELETE FROM cost_groups WHERE code = ?", (str(code),))


def list_employees(active_only=True):
    sql = "SELECT * FROM employees"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY emp_no"
    with cursor() as cur:
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]


def list_periods():
    """Distinct periods present in timesheet data."""
    with cursor() as cur:
        cur.execute("SELECT DISTINCT period FROM timesheet ORDER BY period DESC")
        return [r["period"] for r in cur.fetchall()]


def get_period_summary():
    """Per-period summary for the upload page."""
    with cursor() as cur:
        cur.execute(
            """SELECT period, COUNT(DISTINCT emp_no) AS employees,
                      COUNT(*) AS rows, MAX(work_date) AS last_date
                 FROM timesheet GROUP BY period ORDER BY period DESC"""
        )
        return [dict(r) for r in cur.fetchall()]


def log_upload(file_type, file_name, period, rows, user, notes=""):
    with cursor() as cur:
        cur.execute(
            """INSERT INTO upload_log(file_type, file_name, period, rows_inserted, uploaded_by, notes)
               VALUES (?,?,?,?,?,?)""",
            (file_type, file_name, period, rows, user, notes),
        )


def get_upload_log(limit=50):
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM upload_log ORDER BY uploaded_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in cur.fetchall()]


def period_has_ot_detail(period: str) -> bool:
    """Return True if ot_entries table has any rows for this period."""
    with cursor() as cur:
        cur.execute("SELECT 1 FROM ot_entries WHERE period = ? LIMIT 1", (period,))
        return cur.fetchone() is not None


def get_periods_with_ot_detail() -> list[str]:
    with cursor() as cur:
        cur.execute("SELECT DISTINCT period FROM ot_entries ORDER BY period DESC")
        return [r["period"] for r in cur.fetchall()]


# ---------- Period overrides (working days / daily std hours per month) ----------

def get_period_override(period: str) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM period_overrides WHERE period = ?", (period,))
        r = cur.fetchone()
        return dict(r) if r else None


def list_period_overrides() -> list[dict]:
    with cursor() as cur:
        cur.execute("SELECT * FROM period_overrides ORDER BY period DESC")
        return [dict(r) for r in cur.fetchall()]


def upsert_period_override(period: str, working_days=None, daily_std_hours=None, notes=""):
    with cursor() as cur:
        cur.execute(
            """INSERT INTO period_overrides(period, working_days, daily_std_hours, notes)
                 VALUES (?,?,?,?)
               ON CONFLICT(period) DO UPDATE SET
                 working_days = excluded.working_days,
                 daily_std_hours = excluded.daily_std_hours,
                 notes = excluded.notes""",
            (period,
             int(working_days) if working_days not in (None, "") else None,
             float(daily_std_hours) if daily_std_hours not in (None, "") else None,
             notes or ""),
        )


def delete_period_override(period: str):
    with cursor() as cur:
        cur.execute("DELETE FROM period_overrides WHERE period = ?", (period,))


# ---------- Change requests ----------

def submit_change_request(emp_no: str, field_name: str, old_value: str,
                          new_value: str, reason: str, submitted_by: str) -> int:
    with cursor() as cur:
        cur.execute(
            """INSERT INTO change_requests(emp_no, field_name, old_value, new_value,
                                            reason, status, submitted_by)
               VALUES (?,?,?,?,?,'pending',?)""",
            (emp_no, field_name, str(old_value or ""), str(new_value or ""),
             reason or "", submitted_by),
        )
        return cur.lastrowid


def list_change_requests(status: str | None = None,
                         submitted_by: str | None = None) -> list[dict]:
    sql = """SELECT cr.*, e.emp_name FROM change_requests cr
               LEFT JOIN employees e ON e.emp_no = cr.emp_no"""
    where = []
    params = []
    if status:
        where.append("cr.status = ?"); params.append(status)
    if submitted_by:
        where.append("cr.submitted_by = ?"); params.append(submitted_by)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY cr.submitted_at DESC"
    with cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def approve_change_request(request_id: int, reviewer: str, notes: str = "") -> bool:
    """Apply the change to the employees table and mark request approved."""
    with cursor() as cur:
        cur.execute("SELECT * FROM change_requests WHERE id = ? AND status = 'pending'",
                    (request_id,))
        r = cur.fetchone()
        if not r:
            return False
        # Whitelist of editable fields -> column in employees
        FIELD_MAP = {
            "cost_code": "cost_code",
            "emp_type":  "emp_type",
            "d_in":      "d_in",
            "level":     "level",
            "emp_name":  "emp_name",
        }
        col = FIELD_MAP.get(r["field_name"])
        if not col:
            return False
        new_val = r["new_value"]
        if col == "level":
            try:
                new_val = int(new_val)
            except (ValueError, TypeError):
                return False
        cur.execute(f"UPDATE employees SET {col} = ?, updated_at = CURRENT_TIMESTAMP WHERE emp_no = ?",
                    (new_val, r["emp_no"]))
        cur.execute(
            """UPDATE change_requests
                 SET status='approved', reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP, review_notes=?
               WHERE id=?""",
            (reviewer, notes or "", request_id),
        )
    return True


def reject_change_request(request_id: int, reviewer: str, notes: str = "") -> bool:
    with cursor() as cur:
        cur.execute(
            """UPDATE change_requests
                 SET status='rejected', reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP, review_notes=?
               WHERE id=? AND status='pending'""",
            (reviewer, notes or "", request_id),
        )
        return cur.rowcount > 0


# ============================================================================
# Sign-up requests
# ============================================================================

def submit_signup_request(username: str, email: str, full_name: str,
                          password_hash: str, requested_role: str = "viewer",
                          emp_no: str = "", reason: str = "",
                          ip: str = "", user_agent: str = "") -> int:
    """A new user requests an account. Admin must approve before they can sign in."""
    with cursor() as cur:
        cur.execute(
            """INSERT INTO signup_requests
                (requested_username, requested_email, requested_full_name,
                 requested_emp_no, requested_role, reason, password_hash,
                 status, request_ip, request_user_agent)
               VALUES (?,?,?,?,?,?,?,'pending',?,?)""",
            (username.strip(), email.strip(), full_name.strip(),
             emp_no.strip(), requested_role, reason.strip(), password_hash,
             ip[:64] if ip else "", (user_agent or "")[:200]),
        )
        return cur.lastrowid


def list_signup_requests(status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM signup_requests"
    params = []
    if status:
        sql += " WHERE status = ?"; params.append(status)
    sql += " ORDER BY submitted_at DESC"
    with cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def get_signup_request(request_id: int) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM signup_requests WHERE id = ?", (request_id,))
        r = cur.fetchone()
        return dict(r) if r else None


def signup_username_already_exists_or_pending(username: str) -> str:
    """Return reason string if username conflicts; empty if available."""
    username = username.strip().lower()
    with cursor() as cur:
        cur.execute("SELECT 1 FROM signup_requests WHERE LOWER(requested_username) = ? AND status = 'pending'",
                    (username,))
        if cur.fetchone():
            return "A signup request with this username is already pending review."
    return ""


def mark_signup_reviewed(request_id: int, reviewer: str, decision: str,
                         granted_role: str = "", notes: str = "") -> bool:
    """decision = 'approved' or 'rejected'. Caller is responsible for actually
    creating the user account in auth.yaml when approved."""
    if decision not in ("approved", "rejected"):
        return False
    with cursor() as cur:
        cur.execute(
            """UPDATE signup_requests
                 SET status=?, reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP,
                     review_notes=?, granted_role=?
               WHERE id=? AND status='pending'""",
            (decision, reviewer, notes or "", granted_role or "", request_id),
        )
        return cur.rowcount > 0


# ============================================================================
# Login audit log
# ============================================================================

def log_login_attempt(username: str, success: bool, ip: str = "",
                      user_agent: str = "", role: str = "",
                      failure_reason: str = ""):
    with cursor() as cur:
        cur.execute(
            """INSERT INTO login_audit
                (username, success, ip_address, user_agent, role_at_login, failure_reason)
               VALUES (?,?,?,?,?,?)""",
            (username, 1 if success else 0,
             (ip or "")[:64], (user_agent or "")[:200],
             role, failure_reason),
        )


def get_login_audit(limit: int = 200, username: str | None = None,
                    only_admin: bool = False, only_failures: bool = False) -> list[dict]:
    sql = "SELECT * FROM login_audit"
    where = []
    params = []
    if username:
        where.append("username = ?"); params.append(username)
    if only_admin:
        where.append("role_at_login = 'admin'")
    if only_failures:
        where.append("success = 0")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY occurred_at DESC LIMIT ?"
    params.append(int(limit))
    with cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


# ============================================================================
# Extended employee data (org chart support)
# ============================================================================

def upsert_employee_extended(emp_no: str, **fields):
    """Insert or update an employees_extended row. Pass keyword args for fields to set."""
    allowed = {"nickname", "name_th", "dept_by_location", "cost_centre_name",
               "title", "manager_name", "manager_emp_no", "is_mgr_role",
               "thai_or_expat", "joined_date", "status"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    placeholders = ", ".join("?" for _ in cols)
    with cursor() as cur:
        cur.execute(f"""INSERT INTO employees_extended (emp_no, {', '.join(cols)})
                          VALUES (?, {placeholders})
                        ON CONFLICT(emp_no) DO UPDATE SET
                          {', '.join(f'{c}=excluded.{c}' for c in cols)},
                          updated_at = CURRENT_TIMESTAMP""",
                    [emp_no] + [fields[c] for c in cols])


def list_employees_with_extended() -> list[dict]:
    """Return all active employees joined with their extended data + manager info."""
    with cursor() as cur:
        cur.execute("""
            SELECT e.emp_no, e.emp_name, e.emp_type, e.cost_code, e.level, e.d_in,
                   e.is_active,
                   ex.nickname, ex.name_th, ex.dept_by_location, ex.cost_centre_name,
                   ex.title, ex.manager_name, ex.manager_emp_no, ex.is_mgr_role,
                   ex.thai_or_expat, ex.joined_date, ex.status
              FROM employees e
              LEFT JOIN employees_extended ex ON ex.emp_no = e.emp_no
             WHERE e.is_active = 1
             ORDER BY e.emp_no
        """)
        return [dict(r) for r in cur.fetchall()]


def get_employee_extended(emp_no: str) -> dict | None:
    with cursor() as cur:
        cur.execute("""
            SELECT e.*, ex.nickname, ex.name_th, ex.dept_by_location,
                   ex.cost_centre_name, ex.title, ex.manager_name,
                   ex.manager_emp_no, ex.is_mgr_role, ex.thai_or_expat,
                   ex.joined_date, ex.status
              FROM employees e
              LEFT JOIN employees_extended ex ON ex.emp_no = e.emp_no
             WHERE e.emp_no = ?
        """, (emp_no,))
        r = cur.fetchone()
        return dict(r) if r else None


def get_direct_reports(manager_emp_no: str) -> list[dict]:
    """Return all employees whose manager_emp_no = the given emp_no."""
    with cursor() as cur:
        cur.execute("""
            SELECT e.emp_no, e.emp_name, ex.title, ex.dept_by_location,
                   ex.is_mgr_role, ex.nickname
              FROM employees e
              JOIN employees_extended ex ON ex.emp_no = e.emp_no
             WHERE ex.manager_emp_no = ? AND e.is_active = 1
             ORDER BY e.emp_name
        """, (manager_emp_no,))
        return [dict(r) for r in cur.fetchall()]


# ============================================================================
# Personal user overrides (per-user calculation settings)
# ============================================================================
import json as _json

# Recognised setting types stored under user_overrides:
#   'holidays'         -> list of {date, name}
#   'hour_config'      -> dict of weekday hours + hours_per_day
#   'period_overrides' -> dict period -> {working_days, daily_std_hours, notes}
#   'cost_group_tops'  -> dict code -> {sg_a_manu, sort_order} (only top group is overridable)


def get_user_override(username: str, setting_type: str):
    """Return parsed JSON of a user's override, or None if not set."""
    if not username:
        return None
    with cursor() as cur:
        cur.execute(
            "SELECT setting_data FROM user_overrides WHERE username = ? AND setting_type = ?",
            (username, setting_type),
        )
        r = cur.fetchone()
        if not r:
            return None
        try:
            return _json.loads(r["setting_data"])
        except (TypeError, ValueError):
            return None


def set_user_override(username: str, setting_type: str, data) -> None:
    """Replace (or insert) a user's override. data is JSON-serialisable."""
    payload = _json.dumps(data, ensure_ascii=False, default=str)
    with cursor() as cur:
        cur.execute(
            """INSERT INTO user_overrides(username, setting_type, setting_data)
                 VALUES(?,?,?)
               ON CONFLICT(username, setting_type) DO UPDATE SET
                 setting_data = excluded.setting_data,
                 updated_at = CURRENT_TIMESTAMP""",
            (username, setting_type, payload),
        )


def clear_user_override(username: str, setting_type: str) -> None:
    """Delete a user's override (revert to master values)."""
    with cursor() as cur:
        cur.execute(
            "DELETE FROM user_overrides WHERE username = ? AND setting_type = ?",
            (username, setting_type),
        )


def list_user_overrides(username: str) -> list[str]:
    """Return list of setting_types this user has personal overrides for."""
    if not username:
        return []
    with cursor() as cur:
        cur.execute(
            "SELECT setting_type FROM user_overrides WHERE username = ?",
            (username,),
        )
        return [r["setting_type"] for r in cur.fetchall()]


# --- Effective accessors: return user's override if set, else fall back to master ---

def effective_holidays(username: str | None = None) -> list[dict]:
    """Holidays for the given user (or master if no override / no username)."""
    if username:
        ov = get_user_override(username, "holidays")
        if ov is not None:
            return ov
    return list_holidays()


def effective_hour_config(username: str | None = None) -> dict:
    if username:
        ov = get_user_override(username, "hour_config")
        if ov is not None:
            # Merge: user's overrides on top of master defaults
            base = get_hour_config()
            base.update(ov)
            return base
    return get_hour_config()


def effective_period_override(period: str, username: str | None = None) -> dict | None:
    if username:
        ov = get_user_override(username, "period_overrides") or {}
        if period in ov:
            return ov[period]
    return get_period_override(period)


def effective_cost_groups(username: str | None = None) -> list[dict]:
    """Cost groups with the user's top-group reassignments applied (if any)."""
    base = list_cost_groups()
    if not username:
        return base
    ov = get_user_override(username, "cost_group_tops") or {}
    if not ov:
        return base
    # Apply user's overrides for top group + sort_order
    out = []
    for cg in base:
        cg2 = dict(cg)
        if cg["code"] in ov:
            user_cg = ov[cg["code"]]
            if "sg_a_manu" in user_cg:
                cg2["sg_a_manu"] = user_cg["sg_a_manu"]
            if "sort_order" in user_cg:
                cg2["sort_order"] = user_cg["sort_order"]
        out.append(cg2)
    return out


def get_user_override_summary(username: str) -> list[dict]:
    """Return a human-readable summary of differences between user's overrides and master.
    Used in export memos.
    """
    if not username:
        return []
    diffs = []
    overrides = list_user_overrides(username)
    if "holidays" not in overrides and "hour_config" not in overrides \
            and "period_overrides" not in overrides and "cost_group_tops" not in overrides:
        return []

    if "holidays" in overrides:
        u = get_user_override(username, "holidays") or []
        m = list_holidays()
        u_dates = {h.get("holiday_date") for h in u}
        m_dates = {h["holiday_date"] for h in m}
        added = u_dates - m_dates
        removed = m_dates - u_dates
        if added or removed:
            diffs.append({"setting": "Holidays",
                           "detail": f"Added {len(added)}, removed {len(removed)} vs master"})

    if "hour_config" in overrides:
        u = get_user_override(username, "hour_config") or {}
        m = get_hour_config()
        for k, v in u.items():
            if abs(float(m.get(k, 0)) - float(v)) > 1e-6:
                diffs.append({"setting": f"Hour rule: {k}",
                               "detail": f"Master={m.get(k)}, Yours={v}"})

    if "period_overrides" in overrides:
        u = get_user_override(username, "period_overrides") or {}
        for period, vals in u.items():
            wd = vals.get("working_days")
            dh = vals.get("daily_std_hours")
            diffs.append({"setting": f"Period override {period}",
                           "detail": f"working_days={wd}, daily_std={dh}"})

    if "cost_group_tops" in overrides:
        u = get_user_override(username, "cost_group_tops") or {}
        for code, vals in u.items():
            diffs.append({"setting": f"Cost code {code}",
                           "detail": f"top_group={vals.get('sg_a_manu')}"})

    return diffs
