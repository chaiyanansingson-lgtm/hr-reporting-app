# lib/approval_db.py
# ============================================================================
# 3-LEVEL REPORTING-LINE APPROVAL for Leave & OT  (requirement, 12 Jun)
#
# The chain comes straight from the employee master's Mgr column (the same
# data that builds the org chart):
#     L1 = the requester's direct manager
#     L2 = L1's manager
#     L3 = L2's manager
# If the chain is shorter (e.g. a GM direct-report has only 1-2 levels up),
# approval simply completes at the last available level — no dead ends.
#
# Status flow on the request:  pending_l1 -> pending_l2 -> pending_l3
#                              -> approved   (or 'rejected' at any level)
# Each level is one row in request_approvals; every action is audited and
# triggers an email to the next approver (lib/notify.py).
# ============================================================================
import datetime as dt

from lib.db import get_conn, IS_POSTGRES, PH
from lib import employee_db as edb

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"

MAX_LEVELS = 3

# kind -> backing request table (each table has columns: id, status,
# approver, approved_at, approve_note). Adding a new approvable module is
# one registry line + its table.
REQUEST_TABLES = {
    "leave": "leave_requests",
    "ot": "ot_requests",
    "po": "erp_purchase_orders",
    "car": "car_bookings",
    "permit_out": "permit_takeouts",
    "permit_entry": "permit_entries",
    "stock": "stock_issues",
    "resign": "resignations",
    "shift": "shift_change_requests",
    "timeedit": "time_edit_requests",
}


def _table(kind):
    return REQUEST_TABLES[kind]


def _ts():
    return dt.datetime.now().isoformat(timespec="seconds")


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS request_approvals (
        id {SERIAL},
        request_kind TEXT NOT NULL,      -- 'leave' | 'ot'
        request_id INTEGER NOT NULL,
        level INTEGER NOT NULL,          -- 1 / 2 / 3
        approver_emp_no TEXT, approver_name TEXT, approver_email TEXT,
        status TEXT NOT NULL DEFAULT 'waiting',
            -- waiting (earlier level not done) / pending (its turn) /
            -- approved / rejected / skipped
        acted_by TEXT, acted_at TEXT, note TEXT,
        last_reminded_at TEXT)""")
    conn.commit()


# ---------------------------------------------------------------- chain
def _clean_name(name):
    s = str(name or "").strip()
    for t in ("Mr.", "Ms.", "Mrs.", "Miss"):
        s = s.replace(t, "")
    return " ".join(s.split())


def _find_by_name(name):
    """Match a Mgr-column name against the active employee master."""
    target = _clean_name(name).lower()
    if not target:
        return None
    for r in edb.list_records("active"):
        if _clean_name(r.get("emp_name_en")).lower() == target:
            return r
    return None


def resolve_chain(employee_rec, max_levels=MAX_LEVELS):
    """[ (level, approver_record), ... ] walking up the Mgr column.
    Stops early at the top of the tree or on a broken link, and never lets
    someone approve their own request."""
    chain, seen = [], {str(employee_rec.get("emp_no"))}
    cur = employee_rec
    for lvl in range(1, max_levels + 1):
        mgr = _find_by_name(cur.get("mgr_name"))
        if not mgr or str(mgr.get("emp_no")) in seen:
            break
        chain.append((lvl, mgr))
        seen.add(str(mgr.get("emp_no")))
        cur = mgr
    return chain


def resolve_chain_for(kind, employee_rec, max_levels=MAX_LEVELS):
    """Approval chain for a request: use the admin-configured approval line for
    this kind/scope if one exists, otherwise fall back to the manager-walk."""
    try:
        from lib import approval_rules as ar
        configured = ar.resolve_configured_chain(kind, employee_rec,
                                                 max_levels)
        if configured:
            return configured
    except Exception:
        pass
    return resolve_chain(employee_rec, max_levels)


def _approver_email(emp_no):
    """users.email first (the login the manager actually uses), then the
    employee master's work/personal email."""
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT email FROM users WHERE emp_no={PH}", (str(emp_no),))
    r = cur.fetchone()
    if r and r[0]:
        return r[0]
    rec = edb.get_record(emp_no=str(emp_no))
    return (rec or {}).get("personal_email")


# ---------------------------------------------------------------- lifecycle
def open_approvals(kind, request_id, requester_rec, chain=None):
    """Create the approval rows for a fresh request. Returns the L1 row
    (so the caller can fire the first email) or None if no chain exists
    (then the request auto-approves — flagged for HR in the admin view).
    chain: optional pre-resolved [(level, emp_record), ...] — used by modules
    with their own approval-line config (e.g. ERP purchase lines)."""
    if chain is None:
        chain = resolve_chain_for(kind, requester_rec)
    conn = get_conn(); cur = conn.cursor()
    first = None
    for lvl, mgr in chain:
        status = "pending" if lvl == 1 else "waiting"
        email = _approver_email(mgr["emp_no"])
        cur.execute(
            f"""INSERT INTO request_approvals (request_kind, request_id,
                level, approver_emp_no, approver_name, approver_email,
                status) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
            (kind, request_id, lvl, str(mgr["emp_no"]),
             _clean_name(mgr.get("emp_name_en")), email, status))
        if lvl == 1:
            first = {"level": 1, "approver_emp_no": str(mgr["emp_no"]),
                     "approver_name": _clean_name(mgr.get("emp_name_en")),
                     "approver_email": email}
    table = _table(kind)
    new_status = "pending_l1" if chain else "approved"
    cur.execute(f"UPDATE {table} SET status={PH} WHERE id={PH}",
                (new_status, request_id))
    conn.commit()
    return first


def rows_for(kind, request_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT * FROM request_approvals
                    WHERE request_kind={PH} AND request_id={PH}
                    ORDER BY level""", (kind, request_id))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


def my_queue(kind, approver_emp_no):
    """Requests whose CURRENT pending level belongs to this approver.
    leave/ot join the employee master; other kinds carry their own
    requester columns."""
    conn = get_conn(); cur = conn.cursor()
    table = _table(kind)
    if kind in ("leave", "ot"):
        cur.execute(f"""
            SELECT r.*, a.level AS my_level, a.id AS approval_id,
                   e.emp_name_en AS e_name, e.dept_location
            FROM request_approvals a
            JOIN {table} r ON r.id = a.request_id
            JOIN employees e ON e.id = r.employee_id
            WHERE a.request_kind={PH} AND a.approver_emp_no={PH}
              AND a.status='pending'
            ORDER BY r.id""", (kind, str(approver_emp_no)))
    else:
        cur.execute(f"""
            SELECT r.*, a.level AS my_level, a.id AS approval_id
            FROM request_approvals a
            JOIN {table} r ON r.id = a.request_id
            WHERE a.request_kind={PH} AND a.approver_emp_no={PH}
              AND a.status='pending'
            ORDER BY r.id""", (kind, str(approver_emp_no)))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


def act(kind, approval_id, approve: bool, actor_username, note=""):
    """Approve/reject one level. Returns dict describing what happened:
    {'final': bool, 'rejected': bool, 'next': next-approver-row or None,
     'request_id': int}"""
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM request_approvals WHERE id={PH}",
                (approval_id,))
    row = cur.fetchone()
    a = dict(zip([d[0] for d in cur.description], row)) if IS_POSTGRES \
        else dict(row)
    kind, req_id, lvl = a["request_kind"], a["request_id"], a["level"]
    table = _table(kind)
    status = "approved" if approve else "rejected"
    cur.execute(f"""UPDATE request_approvals SET status={PH}, acted_by={PH},
                    acted_at={PH}, note={PH} WHERE id={PH}""",
                (status, actor_username, _ts(), note, approval_id))
    result = {"final": False, "rejected": False, "next": None,
              "request_id": req_id}
    if not approve:
        cur.execute(f"""UPDATE request_approvals SET status='skipped'
                        WHERE request_kind={PH} AND request_id={PH}
                        AND status IN ('waiting','pending') AND id<>{PH}""",
                    (kind, req_id, approval_id))
        cur.execute(f"""UPDATE {table} SET status='rejected', approver={PH},
                        approved_at={PH}, approve_note={PH} WHERE id={PH}""",
                    (actor_username, _ts(), note, req_id))
        result["rejected"] = True
    else:
        cur.execute(f"""SELECT * FROM request_approvals
                        WHERE request_kind={PH} AND request_id={PH}
                        AND level={PH}""", (kind, req_id, lvl + 1))
        nxt = cur.fetchone()
        if nxt:
            n = dict(zip([d[0] for d in cur.description], nxt)) \
                if IS_POSTGRES else dict(nxt)
            cur.execute(f"""UPDATE request_approvals SET status='pending'
                            WHERE id={PH}""", (n["id"],))
            cur.execute(f"UPDATE {table} SET status={PH} WHERE id={PH}",
                        (f"pending_l{lvl + 1}", req_id))
            result["next"] = n
        else:
            cur.execute(f"""UPDATE {table} SET status='approved',
                            approver={PH}, approved_at={PH},
                            approve_note={PH} WHERE id={PH}""",
                        (actor_username, _ts(), note, req_id))
            result["final"] = True
    conn.commit()
    edb._audit(conn, actor_username,
               f"{kind}_L{lvl}_{status}", detail={"request_id": req_id,
                                                  "note": note})
    conn.commit()
    return result


def pending_overview():
    """All open approvals (for HR admin + the reminder job)."""
    conn = get_conn(); cur = conn.cursor()
    out = []
    for kind, table in REQUEST_TABLES.items():
        try:
            if kind in ("leave", "ot"):
                cur.execute(f"""
                    SELECT a.*, r.emp_no AS req_emp_no,
                           e.emp_name_en AS req_name
                    FROM request_approvals a
                    JOIN {table} r ON r.id = a.request_id
                    JOIN employees e ON e.id = r.employee_id
                    WHERE a.status='pending' AND a.request_kind={PH}""",
                    (kind,))
            else:
                cur.execute(f"""
                    SELECT a.*, r.requester_emp_no AS req_emp_no,
                           r.requester_name AS req_name
                    FROM request_approvals a
                    JOIN {table} r ON r.id = a.request_id
                    WHERE a.status='pending' AND a.request_kind={PH}""",
                    (kind,))
            cols = [d[0] for d in cur.description]
            out += [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
                    for r in cur.fetchall()]
        except Exception:
            conn.rollback() if IS_POSTGRES else None
    return out


def mark_reminded(approval_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"UPDATE request_approvals SET last_reminded_at={PH} "
                f"WHERE id={PH}", (_ts(), approval_id))
    conn.commit()
