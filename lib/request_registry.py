# lib/request_registry.py
# ---------------------------------------------------------------------------
# Unifies every request kind (leave, OT, shift, time-edit, resignation) into a
# single list with: document number, requester, submitted date, status, and —
# for pending items — which approver it is waiting on. Powers the Request
# Register page and the raw-data export.
# ---------------------------------------------------------------------------
from lib.db import get_conn, IS_POSTGRES, PH

KINDS = ["leave", "ot", "shift", "time_edit", "resign"]
TABLE = {
    "leave": "leave_requests",
    "ot": "ot_requests",
    "shift": "shift_change_requests",
    "time_edit": "time_edit_requests",
    "resign": "resignations",
}
TYPE_LABEL = {
    "leave": "ใบลา · Leave",
    "ot": "OT · OT",
    "shift": "เปลี่ยนกะ · Shift",
    "time_edit": "แก้เวลา · Time edit",
    "resign": "ลาออก · Resign",
}
STATUS_LABEL = {
    "pending": "⏳ รออนุมัติ · Pending",
    "approved": "✅ อนุมัติแล้ว · Approved",
    "rejected": "⛔ ไม่อนุมัติ · Rejected",
    "cancelled": "🚫 ยกเลิก · Cancelled",
}


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


_name_cache = {}


def _name_for(emp_no):
    if not emp_no:
        return ""
    key = str(emp_no)
    if key in _name_cache:
        return _name_cache[key]
    conn = get_conn(); cur = conn.cursor()
    nm = ""
    try:
        cur.execute(f"SELECT emp_name_en, emp_name_th FROM employees "
                    f"WHERE emp_no={PH}", (key,))
        r = cur.fetchone()
        if r:
            nm = r[0] or r[1] or ""
    except Exception:
        nm = ""
    _name_cache[key] = nm
    return nm


def current_approver(kind, request_id):
    """(name, emp_no) of the approver a pending request is waiting on, if any."""
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute(f"""SELECT approver_name, approver_emp_no
            FROM request_approvals
            WHERE request_kind={PH} AND request_id={PH} AND status='pending'
            ORDER BY level LIMIT 1""", (kind, request_id))
        r = cur.fetchone()
        return (r[0], r[1]) if r else (None, None)
    except Exception:
        return (None, None)


def _status_norm(st):
    s = (st or "").lower()
    if s.startswith("pending") or s in ("submitted", "waiting", "open"):
        return "pending"
    if s in ("approved", "completed", "done"):
        return "approved"
    if s in ("rejected", "declined"):
        return "rejected"
    if s in ("cancelled", "canceled", "void"):
        return "cancelled"
    return s or "pending"


def _summary(kind, r):
    if kind == "leave":
        return (f"{r.get('leave_type', '')} {r.get('date_from', '')}"
                f"→{r.get('date_to', '')} ({r.get('days', '')}d)")
    if kind == "ot":
        return (f"{r.get('ot_date', '')} {r.get('time_from', '')}-"
                f"{r.get('time_to', '')} ({r.get('hours', '')}h ×"
                f"{r.get('rate', '')})")
    if kind == "shift":
        return (f"{r.get('current_shift', '')}→{r.get('requested_shift', '')} "
                f"{r.get('date_from', '')}")
    if kind == "time_edit":
        return (f"{r.get('work_date', '')} in {r.get('req_time_in', '')} / "
                f"out {r.get('req_time_out', '')}")
    return f"{r.get('subject_name', '')} · LWD {r.get('last_working_day', '')}"


def all_requests(kinds=None, status=None, q=None):
    out = []
    for kind in (kinds or KINDS):
        tbl = TABLE[kind]
        conn = get_conn(); cur = conn.cursor()
        try:
            cur.execute(f"SELECT * FROM {tbl}")
            rows = _rows(cur)
        except Exception:
            continue
        for r in rows:
            emp_no = (r.get("emp_no") or r.get("requester_emp_no")
                      or r.get("subject_emp_no") or "")
            name = r.get("requester_name") or _name_for(emp_no)
            submitted = r.get("requested_at") or r.get("created_at") or ""
            sn = _status_norm(r.get("status"))
            appr_name = appr_no = None
            if sn == "pending":
                appr_name, appr_no = current_approver(kind, r.get("id"))
            out.append(dict(
                kind=kind, type_label=TYPE_LABEL[kind],
                doc_no=r.get("doc_no") or "—", emp_no=str(emp_no),
                requester=name, submitted=submitted, status=sn,
                status_label=STATUS_LABEL.get(sn, sn),
                waiting_on=(appr_name or "—"),
                summary=_summary(kind, r), id=r.get("id")))
    if status and status != "all":
        out = [o for o in out if o["status"] == status]
    if q:
        ql = q.lower().strip()
        out = [o for o in out if ql in (o["requester"] or "").lower()
               or ql in str(o["emp_no"]).lower()
               or ql in (o["doc_no"] or "").lower()]
    out.sort(key=lambda o: (o["submitted"] or ""), reverse=True)
    return out


def counts():
    """Status tallies across all requests (for the header metrics)."""
    c = {"pending": 0, "approved": 0, "rejected": 0, "cancelled": 0,
         "total": 0}
    for o in all_requests():
        c["total"] += 1
        c[o["status"]] = c.get(o["status"], 0) + 1
    return c


def raw_frame(kinds=None):
    """One DataFrame of every raw request column, with a request_type column."""
    import pandas as pd
    frames = []
    for kind in (kinds or KINDS):
        tbl = TABLE[kind]
        conn = get_conn(); cur = conn.cursor()
        try:
            cur.execute(f"SELECT * FROM {tbl}")
            rows = _rows(cur)
        except Exception:
            continue
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df.insert(0, "request_type", kind)
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)
