# lib/auth.py
# ============================================================================
# Users + 7-role RBAC.
# Roles (rank order): visitor < viewer < supervisor < manager < finance
#                     < admin < super_admin
# A user gets capabilities from their role (role_capabilities table) plus any
# personal grants (user_capabilities). Pages call require_capability(cap);
# inline checks call has_capability(cap); identity via current_user()
# which includes emp_no — the link between a login and the employee master.
# ============================================================================
import hashlib
import hmac
import os
import datetime as dt

import streamlit as st

from lib.db import get_conn, IS_POSTGRES, PH

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"

ROLES = ["visitor", "viewer", "supervisor", "manager", "finance",
         "admin", "super_admin"]


def _hash(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(),
                               120_000).hex()


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS users (
        id {SERIAL},
        username TEXT UNIQUE NOT NULL,
        pw_salt TEXT NOT NULL, pw_hash TEXT NOT NULL,
        role_key TEXT NOT NULL DEFAULT 'viewer',
        emp_no TEXT,                       -- link to employees.emp_no
        email TEXT,                        -- for notifications
        active INTEGER NOT NULL DEFAULT 1,
        must_change_pw INTEGER NOT NULL DEFAULT 0,
        created_at TEXT)""")
    # additive migrations (idempotent AND Postgres-safe: on PG a failed
    # statement aborts the whole transaction, so commit on success and
    # rollback on "column already exists" before the next statement runs)
    for _col in ("line_user_id TEXT",
                 "must_change_pw INTEGER NOT NULL DEFAULT 0"):
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN {_col}")
            conn.commit()
        except Exception:
            conn.rollback() if IS_POSTGRES else None
    cur.execute(f"""CREATE TABLE IF NOT EXISTS roles (
        role_key TEXT PRIMARY KEY, name_en TEXT, name_th TEXT,
        rank INTEGER)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS modules (
        module_key TEXT PRIMARY KEY, name_en TEXT, name_th TEXT,
        active INTEGER NOT NULL DEFAULT 1)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS capabilities (
        cap_key TEXT PRIMARY KEY, name_en TEXT, name_th TEXT,
        module_key TEXT)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS role_capabilities (
        role_key TEXT NOT NULL, cap_key TEXT NOT NULL,
        PRIMARY KEY (role_key, cap_key))""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS user_capabilities (
        username TEXT NOT NULL, cap_key TEXT NOT NULL,
        PRIMARY KEY (username, cap_key))""")

    # --- ported from v11.5: login audit + self-service signup (req. 4) ---
    cur.execute(f"""CREATE TABLE IF NOT EXISTS login_audit (
        id {SERIAL},
        username TEXT,
        success INTEGER NOT NULL,           -- 1 success / 0 failure
        ip_address TEXT, user_agent TEXT,
        role_at_login TEXT, failure_reason TEXT,
        occurred_at TEXT)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS signup_requests (
        id {SERIAL},
        req_username TEXT NOT NULL, req_email TEXT, req_full_name TEXT,
        req_emp_no TEXT, req_role TEXT DEFAULT 'viewer', reason TEXT,
        pw_salt TEXT NOT NULL, pw_hash TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',   -- pending/approved/rejected
        request_ip TEXT, request_user_agent TEXT,
        submitted_at TEXT,
        reviewed_by TEXT, reviewed_at TEXT, review_notes TEXT,
        granted_role TEXT)""")
    conn.commit()


def create_user(username, password, role_key="viewer", emp_no=None,
                email=None, must_change=False):
    salt = os.urandom(16).hex()
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""INSERT INTO users (username, pw_salt, pw_hash, role_key,
                    emp_no, email, created_at, must_change_pw)
                    VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
                (username, salt, _hash(password, salt), role_key, emp_no,
                 email, dt.datetime.now().isoformat(timespec="seconds"),
                 1 if must_change else 0))
    conn.commit()


def set_password(username, new_password):
    """Set a new password (new salt) and clear the must-change flag."""
    salt = os.urandom(16).hex()
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""UPDATE users SET pw_salt={PH}, pw_hash={PH},
                    must_change_pw=0 WHERE username={PH}""",
                (salt, _hash(new_password, salt), username))
    conn.commit()


def verify_login(username, password):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT username, pw_salt, pw_hash, role_key, emp_no,
                    email, must_change_pw FROM users
                    WHERE username={PH} AND active=1""",
                (username,))
    r = cur.fetchone()
    if not r:
        return None
    row = dict(zip([d[0] for d in cur.description], r)) if IS_POSTGRES \
        else dict(r)
    if hmac.compare_digest(row["pw_hash"], _hash(password, row["pw_salt"])):
        return row
    return None


def _caps_for(username, role_key):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT cap_key FROM role_capabilities WHERE role_key={PH}",
                (role_key,))
    caps = {r[0] for r in cur.fetchall()}
    cur.execute(f"SELECT cap_key FROM user_capabilities WHERE username={PH}",
                (username,))
    caps |= {r[0] for r in cur.fetchall()}
    return caps


def login(username, password):
    row = verify_login(username, password)
    if not row:
        try:
            log_login_attempt(username, False, "",
                              "wrong password" if user_exists(username)
                              else "user not found")
        except Exception:
            pass
        return False
    st.session_state["user"] = {
        "username": row["username"], "role": row["role_key"],
        "emp_no": row["emp_no"], "email": row["email"],
        "must_change_pw": row.get("must_change_pw", 0),
        "caps": _caps_for(row["username"], row["role_key"])}
    try:
        log_login_attempt(row["username"], True, row["role_key"], "")
    except Exception:
        pass
    return True


def logout():
    st.session_state.pop("user", None)


def current_user():
    return st.session_state.get("user")


def has_capability(cap):
    u = current_user()
    return bool(u and cap in u["caps"])


def require_capability(cap):
    u = current_user()
    if not u:
        st.warning("กรุณาเข้าสู่ระบบก่อน / Please sign in to continue.")
        st.page_link("app.py", label="🔐 ไปหน้าเข้าสู่ระบบ · Go to sign-in",
                     use_container_width=True)
        st.stop()
    if cap not in u["caps"]:
        st.error(f"🚫 สิทธิ์ไม่เพียงพอ / Your role ({u['role']}) lacks the "
                 f"'{cap}' capability. Ask a Super Admin.")
        st.stop()
    return u


def set_user_emp_no(username, emp_no):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"UPDATE users SET emp_no={PH} WHERE username={PH}",
                (emp_no, username))
    conn.commit()


def set_user_line_id(username, line_user_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"UPDATE users SET line_user_id={PH} WHERE username={PH}",
                (line_user_id, username))
    conn.commit()


def line_id_for_emp(emp_no):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT line_user_id FROM users WHERE emp_no={PH}",
                (str(emp_no),))
    r = cur.fetchone()
    return r[0] if r and r[0] else None


def set_user_email(username, email):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"UPDATE users SET email={PH} WHERE username={PH}",
                (email, username))
    conn.commit()


def list_users():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""SELECT username, role_key, emp_no, email, line_user_id,
                   active FROM users ORDER BY username""")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


# ============================================================================
# v11.5 port (req. 4): login audit + self-service signup & review.
# ============================================================================
def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


def _client_meta():
    """Best-effort client IP + user-agent from the request headers."""
    ip = ""
    ua = ""
    try:
        h = dict(st.context.headers or {})
        ua = (h.get("User-Agent") or h.get("user-agent") or "")[:200]
        xff = (h.get("X-Forwarded-For") or h.get("x-forwarded-for") or "")
        ip = (xff.split(",")[0].strip() if xff else "")[:64]
    except Exception:
        pass
    return ip, ua


def user_exists(username):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT 1 FROM users WHERE LOWER(username)={PH}",
                (str(username).strip().lower(),))
    return cur.fetchone() is not None


# ---- login audit ----------------------------------------------------------
def log_login_attempt(username, success, role="", failure_reason=""):
    ip, ua = _client_meta()
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""INSERT INTO login_audit (username, success, ip_address,
                    user_agent, role_at_login, failure_reason, occurred_at)
                    VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
                (username, 1 if success else 0, ip, ua, role or "",
                 failure_reason or "", _now()))
    conn.commit()


def get_login_audit(limit=200, username=None, only_admin=False,
                    only_failures=False):
    conn = get_conn(); cur = conn.cursor()
    sql = "SELECT * FROM login_audit"
    where = []
    params = []
    if username:
        where.append(f"username={PH}"); params.append(username)
    if only_admin:
        where.append("role_at_login LIKE '%admin%'")
    if only_failures:
        where.append("success=0")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY id DESC LIMIT {int(limit)}"
    cur.execute(sql, tuple(params))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


# ---- self-service signup --------------------------------------------------
def submit_signup_request(username, email, full_name, password,
                          role="viewer", emp_no="", reason=""):
    salt = os.urandom(16).hex()
    pwh = _hash(password, salt)
    ip, ua = _client_meta()
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""INSERT INTO signup_requests (req_username, req_email,
                    req_full_name, req_emp_no, req_role, reason, pw_salt,
                    pw_hash, status, request_ip, request_user_agent,
                    submitted_at)
                    VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},'pending',
                    {PH},{PH},{PH})""",
                (str(username).strip(), (email or "").strip(),
                 (full_name or "").strip(), (emp_no or "").strip(),
                 role or "viewer", (reason or "").strip(), salt, pwh,
                 ip, ua, _now()))
    conn.commit()


def signup_pending_exists(username):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT 1 FROM signup_requests
                    WHERE LOWER(req_username)={PH} AND status='pending'""",
                (str(username).strip().lower(),))
    return cur.fetchone() is not None


def list_signup_requests(status=None):
    conn = get_conn(); cur = conn.cursor()
    if status:
        cur.execute(f"""SELECT * FROM signup_requests WHERE status={PH}
                        ORDER BY id DESC""", (status,))
    else:
        cur.execute("SELECT * FROM signup_requests ORDER BY id DESC")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


def approve_signup(req_id, reviewer, granted_role=None, emp_no=None, notes=""):
    """Create the user account from a pending request, then mark it approved.
    The applicant keeps the password they chose at sign-up."""
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM signup_requests WHERE id={PH}", (req_id,))
    r = cur.fetchone()
    if not r:
        return (False, "ไม่พบคำขอ / request not found")
    row = dict(zip([d[0] for d in cur.description], r)) if IS_POSTGRES \
        else dict(r)
    if row["status"] != "pending":
        return (False, "คำขอนี้ถูกดำเนินการแล้ว / already handled")
    uname = row["req_username"]
    if user_exists(uname):
        return (False, f"มีชื่อผู้ใช้ '{uname}' อยู่แล้ว / username exists")
    role = granted_role or row.get("req_role") or "viewer"
    eno = (emp_no if emp_no not in (None, "") else (row.get("req_emp_no") or None))
    cur.execute(f"""INSERT INTO users (username, pw_salt, pw_hash, role_key,
                    emp_no, email, active, must_change_pw, created_at)
                    VALUES ({PH},{PH},{PH},{PH},{PH},{PH},1,0,{PH})""",
                (uname, row["pw_salt"], row["pw_hash"], role, eno or None,
                 row.get("req_email") or None, _now()))
    cur.execute(f"""UPDATE signup_requests SET status='approved',
                    reviewed_by={PH}, reviewed_at={PH}, review_notes={PH},
                    granted_role={PH} WHERE id={PH}""",
                (reviewer, _now(), notes or "", role, req_id))
    conn.commit()
    return (True, f"อนุมัติและสร้างผู้ใช้ '{uname}' (บทบาท {role}) แล้ว / "
                  f"user created")


def reject_signup(req_id, reviewer, notes=""):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""UPDATE signup_requests SET status='rejected',
                    reviewed_by={PH}, reviewed_at={PH}, review_notes={PH}
                    WHERE id={PH} AND status='pending'""",
                (reviewer, _now(), notes or "", req_id))
    n = cur.rowcount
    conn.commit()
    return n > 0
