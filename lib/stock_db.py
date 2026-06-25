# lib/stock_db.py
# ============================================================================
# STATIONERY STOCK & ISSUE (§4)
# Your real flow: admin forecasts and buys fast-movers (paper, pens) INTO
# STOCK first; departments then draw them instantly — no purchase cycle wait.
#   receipt  -> on_hand + qty, moving-average unit cost updated
#   issue    -> staff request from IN-STOCK list -> L1 approve (kind="stock")
#               -> admin hands over -> on_hand - qty, cost charged to the
#               requester's department (the allocation ledger = stock_moves)
#   adjust   -> physical count variance (audited)
# Reorder alert: on_hand < min_level.
# ============================================================================
import datetime as dt

from lib.db import get_conn, IS_POSTGRES, PH
from lib import employee_db as edb

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"


def _ts():
    return dt.datetime.now().isoformat(timespec="seconds")


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS stock_items (
        id {SERIAL},
        product_code TEXT UNIQUE,
        description TEXT NOT NULL,
        unit TEXT DEFAULT 'ชิ้น',
        on_hand REAL NOT NULL DEFAULT 0,
        min_level REAL NOT NULL DEFAULT 0,
        avg_cost REAL NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS stock_moves (
        id {SERIAL},
        item_id INTEGER NOT NULL,
        move_type TEXT NOT NULL,          -- receipt | issue | adjust
        qty REAL NOT NULL,                -- signed (+in / -out)
        unit_cost REAL DEFAULT 0,
        department TEXT, emp_no TEXT, emp_name TEXT,
        ref TEXT, note TEXT,
        actor TEXT, created_at TEXT)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS stock_issues (
        id {SERIAL},
        doc_no TEXT UNIQUE,
        requester_emp_no TEXT, requester_name TEXT, department TEXT,
        purpose TEXT,
        status TEXT NOT NULL DEFAULT 'submitted',
        approver TEXT, approved_at TEXT, approve_note TEXT,
        handed_over_at TEXT, handed_by TEXT,
        created_by TEXT, created_at TEXT)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS stock_issue_lines (
        id {SERIAL},
        issue_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        qty REAL NOT NULL)""")
    conn.commit()


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


# ---------------------------------------------------------------- items
def list_items(active_only=True, in_stock_only=False):
    conn = get_conn(); cur = conn.cursor()
    sql = "SELECT * FROM stock_items WHERE 1=1"
    if active_only:
        sql += " AND active=1"
    if in_stock_only:
        sql += " AND on_hand > 0"
    cur.execute(sql + " ORDER BY description")
    return _rows(cur)


def get_item(item_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM stock_items WHERE id={PH}", (item_id,))
    r = cur.fetchone()
    if not r:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r)) if IS_POSTGRES else dict(r)


def upsert_item(product_code, description, unit, min_level, actor):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT id FROM stock_items WHERE product_code={PH} "
                f"OR (product_code IS NULL AND description={PH})",
                (product_code or "", description))
    row = cur.fetchone()
    if row:
        cur.execute(f"""UPDATE stock_items SET description={PH}, unit={PH},
                        min_level={PH} WHERE id={PH}""",
                    (description, unit, min_level, row[0]))
    else:
        cur.execute(f"""INSERT INTO stock_items (product_code, description,
                        unit, min_level) VALUES ({PH},{PH},{PH},{PH})""",
                    (product_code or None, description, unit, min_level))
    conn.commit()
    edb._audit(conn, actor, "stock_item_upsert",
               detail={"code": product_code, "desc": description[:40]})
    conn.commit()


# ---------------------------------------------------------------- receipt
def receive(item_id, qty, unit_cost, ref, actor):
    """+stock with MOVING-AVERAGE cost update."""
    it = get_item(item_id)
    qty = float(qty); unit_cost = float(unit_cost or 0)
    old_val = (it["on_hand"] or 0) * (it["avg_cost"] or 0)
    new_qty = (it["on_hand"] or 0) + qty
    new_avg = ((old_val + qty * unit_cost) / new_qty) if new_qty > 0 \
        else unit_cost
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"UPDATE stock_items SET on_hand={PH}, avg_cost={PH} "
                f"WHERE id={PH}", (new_qty, round(new_avg, 4), item_id))
    cur.execute(f"""INSERT INTO stock_moves (item_id, move_type, qty,
                    unit_cost, ref, actor, created_at)
                    VALUES ({PH},'receipt',{PH},{PH},{PH},{PH},{PH})""",
                (item_id, qty, unit_cost, ref, actor, _ts()))
    conn.commit()
    edb._audit(conn, actor, "stock_receive",
               detail={"item_id": item_id, "qty": qty, "cost": unit_cost})
    conn.commit()


def adjust(item_id, counted_qty, note, actor):
    """Physical count -> variance adjust move (audited)."""
    it = get_item(item_id)
    diff = float(counted_qty) - float(it["on_hand"] or 0)
    if abs(diff) < 1e-9:
        return 0.0
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"UPDATE stock_items SET on_hand={PH} WHERE id={PH}",
                (float(counted_qty), item_id))
    cur.execute(f"""INSERT INTO stock_moves (item_id, move_type, qty,
                    unit_cost, note, actor, created_at)
                    VALUES ({PH},'adjust',{PH},{PH},{PH},{PH},{PH})""",
                (item_id, diff, it["avg_cost"] or 0, note, actor, _ts()))
    conn.commit()
    edb._audit(conn, actor, "stock_adjust",
               detail={"item_id": item_id, "diff": diff, "note": note[:60]})
    conn.commit()
    return diff


# ---------------------------------------------------------------- issues
def _next_doc():
    conn = get_conn(); cur = conn.cursor()
    ym = dt.date.today().strftime("%y%m")
    cur.execute(f"SELECT COUNT(*) FROM stock_issues WHERE doc_no LIKE {PH}",
                (f"ISS-{ym}-%",))
    return f"ISS-{ym}-{cur.fetchone()[0] + 1:03d}"


def create_issue(requester, lines, purpose, actor):
    """lines: [{item_id, qty}] — qty validated against on_hand at handover,
    not here (others may draw first)."""
    conn = get_conn(); cur = conn.cursor()
    doc = _next_doc()
    cur.execute(f"""INSERT INTO stock_issues (doc_no, requester_emp_no,
                    requester_name, department, purpose, status,
                    created_by, created_at)
                    VALUES ({PH},{PH},{PH},{PH},{PH},'submitted',{PH},{PH})""",
                (doc, requester.get("emp_no"), requester.get("emp_name_en"),
                 requester.get("dept_location"), purpose, actor, _ts()))
    if IS_POSTGRES:
        cur.execute("SELECT id FROM stock_issues WHERE doc_no=%s", (doc,))
        iid = cur.fetchone()[0]
    else:
        iid = cur.lastrowid
    for l in lines:
        cur.execute(f"""INSERT INTO stock_issue_lines (issue_id, item_id,
                        qty) VALUES ({PH},{PH},{PH})""",
                    (iid, l["item_id"], float(l["qty"])))
    conn.commit()
    edb._audit(conn, actor, "stock_issue_create", detail={"doc_no": doc})
    conn.commit()
    return iid, doc


def get_issue(iid):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM stock_issues WHERE id={PH}", (iid,))
    r = cur.fetchone()
    if not r:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r)) if IS_POSTGRES else dict(r)


def issue_lines(iid):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT l.*, i.description, i.unit, i.on_hand, i.avg_cost
                    FROM stock_issue_lines l JOIN stock_items i
                    ON i.id = l.item_id WHERE l.issue_id={PH}""", (iid,))
    return _rows(cur)


def list_issues(status=None, requester_emp_no=None, limit=200):
    conn = get_conn(); cur = conn.cursor()
    sql = "SELECT * FROM stock_issues WHERE 1=1"
    args = []
    if status:
        sql += f" AND status={PH}"; args.append(status)
    if requester_emp_no:
        sql += f" AND requester_emp_no={PH}"
        args.append(str(requester_emp_no))
    sql += f" ORDER BY id DESC LIMIT {int(limit)}"
    cur.execute(sql, args)
    return _rows(cur)


def hand_over(iid, actor):
    """Admin hands the goods over: stock -qty, cost charged to the
    requester's department in the moves ledger. Returns (ok, msg)."""
    iss = get_issue(iid)
    if not iss or iss["status"] != "approved":
        return False, "ต้องอนุมัติก่อน / must be approved first"
    lines = issue_lines(iid)
    short = [l for l in lines if (l["on_hand"] or 0) < l["qty"]]
    if short:
        return False, ("ของไม่พอ / insufficient stock: " +
                       ", ".join(f"{l['description']} (มี {l['on_hand']:g})"
                                 for l in short))
    conn = get_conn(); cur = conn.cursor()
    for l in lines:
        cur.execute(f"UPDATE stock_items SET on_hand=on_hand-{PH} "
                    f"WHERE id={PH}", (l["qty"], l["item_id"]))
        cur.execute(f"""INSERT INTO stock_moves (item_id, move_type, qty,
                        unit_cost, department, emp_no, emp_name, ref, actor,
                        created_at) VALUES ({PH},'issue',{PH},{PH},{PH},
                        {PH},{PH},{PH},{PH},{PH})""",
                    (l["item_id"], -l["qty"], l["avg_cost"] or 0,
                     iss["department"], iss["requester_emp_no"],
                     iss["requester_name"], iss["doc_no"], actor, _ts()))
    cur.execute(f"""UPDATE stock_issues SET status='handed_over',
                    handed_over_at={PH}, handed_by={PH} WHERE id={PH}""",
                (_ts(), actor, iid))
    conn.commit()
    edb._audit(conn, actor, "stock_handover", detail={"doc_no": iss["doc_no"]})
    conn.commit()
    return True, "จ่ายของแล้ว / handed over"


# ---------------------------------------------------------------- reports
def reorder_alerts():
    return [i for i in list_items()
            if (i["min_level"] or 0) > 0 and
            (i["on_hand"] or 0) < i["min_level"]]


def stock_value():
    return sum((i["on_hand"] or 0) * (i["avg_cost"] or 0)
               for i in list_items())


def issue_cost_by(group="department"):
    """Allocation ledger pivots from issue moves (cost = qty*avg at issue).
    group: department | month | item"""
    conn = get_conn(); cur = conn.cursor()
    if group == "month":
        key = "substr(m.created_at,1,7)"
    elif group == "item":
        key = "i.description"
    else:
        key = "m.department"
    cur.execute(f"""SELECT {key} AS k,
                    SUM(-m.qty * m.unit_cost) AS cost,
                    SUM(-m.qty) AS qty
                    FROM stock_moves m JOIN stock_items i ON i.id=m.item_id
                    WHERE m.move_type='issue'
                    GROUP BY {key} ORDER BY cost DESC""")
    return [{"key": r[0] or "—", "cost_thb": round(float(r[1] or 0), 2),
             "qty": float(r[2] or 0)}
            for r in cur.fetchall()]


def usage_monthly_avg(item_id, months=3):
    """Average monthly issue qty (for the reorder suggestion)."""
    conn = get_conn(); cur = conn.cursor()
    since = (dt.date.today() - dt.timedelta(days=months * 30)).isoformat()
    cur.execute(f"""SELECT SUM(-qty) FROM stock_moves
                    WHERE item_id={PH} AND move_type='issue'
                    AND created_at >= {PH}""", (item_id, since))
    total = float(cur.fetchone()[0] or 0)
    return round(total / months, 1)
