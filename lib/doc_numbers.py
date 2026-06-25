# lib/doc_numbers.py
# ---------------------------------------------------------------------------
# Central, single-source-of-truth document numbering for every request that
# becomes a document in the HRM. Each issued number is recorded in one table
# (doc_registry) so Admin/Superadmin can list, track and export every document
# from one place, and so numbers never collide.
#
# Scheme:  <TT>-<YYYYMMDD>-<NNNN>
#   TT     two-letter request-type code (LV, OT, SH, TE, RS, …)
#   YYYYMMDD  the calendar date the document was issued
#   NNNN   a per-type, per-day running counter, zero-padded to 4 digits
#
#   e.g.  OT-20260624-0001   →  1st OT document issued on 24 Jun 2026
#         LV-20260624-0007   →  7th Leave document issued the same day
#
# Why this shape (vs a raw timestamp like OT2026062423420000):
#   • sortable      – plain text sort = chronological within a type
#   • parseable     – split on "-" → type / date / sequence (clean Excel cols)
#   • human-readable– an approver can read the type and date at a glance
#   • countable     – the running number tells you "the Nth OT that day"
#   • collision-safe– reserved in doc_registry with a UNIQUE constraint + retry
# ---------------------------------------------------------------------------
import datetime as dt

from lib.db import get_conn, IS_POSTGRES, PH

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
    "INTEGER PRIMARY KEY AUTOINCREMENT"

# request kind  ->  two-letter prefix
PREFIX = {
    "leave": "LV",
    "ot": "OT",
    "shift": "SH",
    "time_edit": "TE",
    "resign": "RS",
    "po": "PO",
    "car": "CB",
    "permit_out": "PT",
    "permit_entry": "PE",
    "stock": "ST",
}

# request kind  ->  bilingual label (for the register & the Excel spec)
LABEL = {
    "leave": "Leave request · ใบลา",
    "ot": "OT request · ใบขอทำงานล่วงเวลา",
    "shift": "Shift change · ขอเปลี่ยนกะ",
    "time_edit": "Time adjustment · ขอแก้ไขเวลา",
    "resign": "Resignation · การลาออก",
    "po": "Purchase order · ใบสั่งซื้อ",
    "car": "Car booking · จองรถ",
    "permit_out": "Permit to take out · ใบนำของออก",
    "permit_entry": "Permit to enter · ใบนำเข้า",
    "stock": "Stock issue · เบิกของ",
}

# request kind  ->  backing request table (so the register can join in status)
REQUEST_TABLE = {
    "leave": "leave_requests",
    "ot": "ot_requests",
    "shift": "shift_change_requests",
    "time_edit": "time_edit_requests",
    "resign": "resignations",
}


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS doc_registry (
        id {SERIAL},
        doc_no TEXT UNIQUE NOT NULL,
        kind TEXT NOT NULL,
        request_table TEXT,
        request_id INTEGER,
        issued_by TEXT,
        issued_at TEXT
    )""")
    conn.commit()


def _now_iso():
    return dt.datetime.now().isoformat(timespec="seconds")


def next_no(kind, when=None):
    """Compute (but do not record) the next number for a kind on a given day."""
    when = when or dt.datetime.now()
    pre = PREFIX.get(kind, "DC")
    base = f"{pre}-{when.strftime('%Y%m%d')}-"
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM doc_registry WHERE doc_no LIKE {PH}",
                (base + "%",))
    n = (cur.fetchone()[0] or 0) + 1
    while True:                                   # collision-safe
        cand = f"{base}{n:04d}"
        cur.execute(f"SELECT 1 FROM doc_registry WHERE doc_no={PH}", (cand,))
        if not cur.fetchone():
            return cand
        n += 1


def issue(kind, request_table=None, request_id=None, actor="system",
          when=None):
    """Reserve and record the next document number; returns the number."""
    doc = next_no(kind, when)
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""INSERT INTO doc_registry
        (doc_no, kind, request_table, request_id, issued_by, issued_at)
        VALUES ({PH},{PH},{PH},{PH},{PH},{PH})""",
                (doc, kind, request_table or REQUEST_TABLE.get(kind),
                 request_id, actor, _now_iso()))
    conn.commit()
    return doc


def link(doc_no, request_table):
    """After the request row exists, back-fill its id into the registry by
    matching the doc_no stored on the request row (doc_no is unique → safe)."""
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute(f"SELECT id FROM {request_table} WHERE doc_no={PH}",
                    (doc_no,))
        row = cur.fetchone()
    except Exception:
        row = None
    if row:
        cur.execute(f"UPDATE doc_registry SET request_id={PH} WHERE doc_no={PH}",
                    (row[0], doc_no))
        conn.commit()


def get_for(request_table, request_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT doc_no FROM doc_registry
        WHERE request_table={PH} AND request_id={PH}
        ORDER BY id DESC""", (request_table, request_id))
    r = cur.fetchone()
    return r[0] if r else None


def registry(kind=None):
    """All issued documents (newest first) for the admin register / export."""
    conn = get_conn(); cur = conn.cursor()
    q = ("SELECT doc_no, kind, request_table, request_id, issued_by, issued_at "
         "FROM doc_registry")
    args = []
    if kind:
        q += f" WHERE kind={PH}"; args.append(kind)
    q += " ORDER BY issued_at DESC, doc_no DESC"
    cur.execute(q, tuple(args))
    cols = ["doc_no", "kind", "request_table", "request_id", "issued_by",
            "issued_at"]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
