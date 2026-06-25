# lib/resign_db.py
# ============================================================================
# RESIGNATION + NO-SHOW TERMINATION (§6)
#   self      : staff submits own resignation -> full L1..L3 chain
#   delegate  : manager files FOR a no-show subordinate (reason pre-set)
#   The no-show watchdog (attendance_db.noshow_runs) feeds the delegate
#   path: day-2 alert, day-3 escalation citing LPA s.119(5) —
#   ลูกจ้างละทิ้งหน้าที่เป็นเวลาสามวันทำงานติดต่อกันโดยไม่มีเหตุอันสมควร.
# After approval, HR completes a checklist (asset return, SSO-out,
# final pay) and the employee record flips to 'resigned' on the date.
# ============================================================================
import datetime as dt
import html as H

from lib.db import get_conn, IS_POSTGRES, PH
from lib import employee_db as edb

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"


def _ts():
    return dt.datetime.now().isoformat(timespec="seconds")


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS resignations (
        id {SERIAL},
        doc_no TEXT UNIQUE,
        requester_emp_no TEXT, requester_name TEXT, department TEXT,
        subject_emp_no TEXT NOT NULL,      -- the employee leaving
        subject_name TEXT,
        kind TEXT NOT NULL DEFAULT 'self', -- self | delegate
        last_working_day TEXT,
        reason TEXT,
        noshow_from TEXT, noshow_days INTEGER,
        status TEXT NOT NULL DEFAULT 'submitted',
        approver TEXT, approved_at TEXT, approve_note TEXT,
        chk_assets INTEGER DEFAULT 0, chk_sso INTEGER DEFAULT 0,
        chk_finalpay INTEGER DEFAULT 0,
        completed_at TEXT, completed_by TEXT,
        created_by TEXT, created_at TEXT)""")
    conn.commit()


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


def _next_doc():
    conn = get_conn(); cur = conn.cursor()
    ym = dt.date.today().strftime("%y%m")
    cur.execute(f"SELECT COUNT(*) FROM resignations WHERE doc_no LIKE {PH}",
                (f"RSN-{ym}-%",))
    return f"RSN-{ym}-{cur.fetchone()[0] + 1:03d}"


def create(requester, subject_rec, kind, last_working_day, reason, actor,
           noshow_from=None, noshow_days=None):
    conn = get_conn(); cur = conn.cursor()
    doc = _next_doc()
    cur.execute(
        f"""INSERT INTO resignations (doc_no, requester_emp_no,
            requester_name, department, subject_emp_no, subject_name, kind,
            last_working_day, reason, noshow_from, noshow_days, status,
            created_by, created_at)
            VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},
            'submitted',{PH},{PH})""",
        (doc, requester.get("emp_no"), requester.get("emp_name_en"),
         subject_rec.get("dept_location"), str(subject_rec.get("emp_no")),
         subject_rec.get("emp_name_en"), kind, str(last_working_day),
         reason, noshow_from, noshow_days, actor, _ts()))
    if IS_POSTGRES:
        cur.execute("SELECT id FROM resignations WHERE doc_no=%s", (doc,))
        rid = cur.fetchone()[0]
    else:
        rid = cur.lastrowid
    conn.commit()
    edb._audit(conn, actor, f"resignation_create_{kind}",
               detail={"doc_no": doc, "subject": subject_rec.get("emp_no")})
    conn.commit()
    return rid, doc


def get(rid):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM resignations WHERE id={PH}", (rid,))
    r = cur.fetchone()
    if not r:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r)) if IS_POSTGRES else dict(r)


def list_resignations(status=None, subject_emp_no=None,
                      requester_emp_no=None, limit=200):
    conn = get_conn(); cur = conn.cursor()
    sql = "SELECT * FROM resignations WHERE 1=1"
    args = []
    if status:
        sql += f" AND status={PH}"; args.append(status)
    if subject_emp_no:
        sql += f" AND subject_emp_no={PH}"; args.append(str(subject_emp_no))
    if requester_emp_no:
        sql += f" AND requester_emp_no={PH}"
        args.append(str(requester_emp_no))
    sql += f" ORDER BY id DESC LIMIT {int(limit)}"
    cur.execute(sql, args)
    return _rows(cur)


def set_checklist(rid, assets=None, sso=None, finalpay=None, actor=""):
    conn = get_conn(); cur = conn.cursor()
    sets, args = [], []
    for col, v in (("chk_assets", assets), ("chk_sso", sso),
                   ("chk_finalpay", finalpay)):
        if v is not None:
            sets.append(f"{col}={PH}")
            args.append(1 if v else 0)
    if not sets:
        return
    args.append(rid)
    cur.execute(f"UPDATE resignations SET {', '.join(sets)} WHERE id={PH}",
                args)
    conn.commit()


def complete(rid, actor):
    """Checklist done -> employee record flips to resigned on the date.
    Returns (ok, msg)."""
    r = get(rid)
    if not r or r["status"] != "approved":
        return False, "ต้องผ่านการอนุมัติก่อน / must be approved first"
    if not (r["chk_assets"] and r["chk_sso"] and r["chk_finalpay"]):
        return False, ("เช็คลิสต์ยังไม่ครบ (ทรัพย์สิน/สปส./เงินสุดท้าย) / "
                       "checklist incomplete")
    emp = edb.get_record(emp_no=r["subject_emp_no"])
    if emp:
        # effective date lives on the resignation record (last_working_day);
        # the employee master only carries the status flip (audited).
        edb.set_status(emp["id"], "resigned", actor)
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""UPDATE resignations SET status='completed',
                    completed_at={PH}, completed_by={PH} WHERE id={PH}""",
                (_ts(), actor, rid))
    conn.commit()
    edb._audit(conn, actor, "resignation_complete",
               detail={"doc_no": r["doc_no"]})
    conn.commit()
    return True, "ปิดเรื่องแล้ว — สถานะพนักงานเปลี่ยนเป็น resigned"


# ---------------------------------------------------------------- notices
def notice_html(r):
    """Bilingual acceptance (self) or termination notice (delegate /
    no-show, citing LPA s.119(5))."""
    is_noshow = r["kind"] == "delegate"
    title_th = ("หนังสือเลิกจ้าง" if is_noshow
                else "หนังสือตอบรับการลาออก")
    title_en = ("Notice of Termination of Employment" if is_noshow
                else "Acceptance of Resignation")
    body_th = (
        f"ตามที่ นาย/นาง/นางสาว {H.escape(r['subject_name'] or '')} "
        f"(รหัสพนักงาน {H.escape(r['subject_emp_no'])}) "
        + (f"ได้ละทิ้งหน้าที่เป็นเวลา {r['noshow_days'] or 3} วันทำงาน"
           f"ติดต่อกันตั้งแต่วันที่ {H.escape(r['noshow_from'] or '-')} "
           f"โดยไม่มีเหตุอันสมควร บริษัทฯ จึงขอเลิกจ้างโดยไม่จ่ายค่าชดเชย "
           f"ตามพระราชบัญญัติคุ้มครองแรงงาน พ.ศ. 2541 มาตรา 119(5) "
           f"โดยมีผลตั้งแต่วันที่ {H.escape(r['last_working_day'] or '')}"
           if is_noshow else
           f"ได้ยื่นความประสงค์ขอลาออกจากการเป็นพนักงาน บริษัทฯ "
           f"ขอตอบรับการลาออกดังกล่าว โดยให้มีผลวันสุดท้ายของการทำงานคือ "
           f"วันที่ {H.escape(r['last_working_day'] or '')}"))
    body_en = (
        f"This is to confirm that the employment of "
        f"{H.escape(r['subject_name'] or '')} (Emp. No. "
        f"{H.escape(r['subject_emp_no'])}) "
        + ("is terminated without severance pay pursuant to Section 119(5) "
           "of the Labour Protection Act B.E. 2541, due to abandonment of "
           f"duty for {r['noshow_days'] or 3} consecutive working days "
           f"from {H.escape(r['noshow_from'] or '-')} without reasonable "
           f"cause, effective {H.escape(r['last_working_day'] or '')}."
           if is_noshow else
           f"ends by resignation, with the last working day on "
           f"{H.escape(r['last_working_day'] or '')}. The company accepts "
           "the resignation with thanks for the services rendered."))
    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<title>{H.escape(r['doc_no'])}</title><style>
@page{{size:A4 portrait;margin:22mm 20mm}}
body{{font-family:'Sarabun','Leelawadee UI',Tahoma,sans-serif;font-size:14px;
 color:#111;line-height:1.8}}
.head{{display:flex;justify-content:space-between;align-items:center;
 border-bottom:3px solid #715091;padding-bottom:8px}}
.logo{{width:40px;height:40px;border-radius:9px;display:grid;
 place-items:center;color:#fff;font-weight:800;font-size:20px;
 background:linear-gradient(135deg,#009ADE,#715091 55%,#E31D93)}}
h1{{font-size:19px;text-align:center;margin:24px 0 4px}}
h2{{font-size:14px;text-align:center;margin:0 0 18px;color:#555;
 font-weight:600}}
.sig{{margin-top:60px;display:flex;justify-content:space-around;
 text-align:center}}
.sig div{{width:40%}}
.line{{border-bottom:1px dotted #555;height:34px;margin-bottom:6px}}
.noprint{{position:fixed;top:8px;right:10px}}
.noprint button{{padding:8px 16px;border:0;border-radius:8px;color:#fff;
 font-weight:700;cursor:pointer;
 background:linear-gradient(135deg,#009ADE,#715091)}}
@media print{{.noprint{{display:none}}}}
</style></head><body onload="window.print()">
<div class="noprint"><button onclick="window.print()">🖨️ Print</button></div>
<div class="head"><div style="display:flex;gap:10px;align-items:center">
<div class="logo">A</div><b>ANCA Manufacturing Solutions (Thailand) Ltd.</b>
</div><div>เลขที่ {H.escape(r['doc_no'])}<br>วันที่
{dt.date.today():%d/%m/%Y}</div></div>
<h1>{title_th}</h1><h2>{title_en}</h2>
<p>{body_th}</p>
<p style="color:#444">{body_en}</p>
<p>ทั้งนี้ ขอให้พนักงานดำเนินการคืนทรัพย์สินของบริษัทฯ ให้ครบถ้วน
และติดต่อฝ่ายทรัพยากรบุคคลเรื่องสิทธิประโยชน์และเอกสารที่เกี่ยวข้อง /
Please return all company property and contact HR regarding final
entitlements and documents.</p>
<div class="sig">
<div><div class="line"></div>ฝ่ายทรัพยากรบุคคล / HR Department</div>
<div><div class="line"></div>ผู้จัดการทั่วไป / General Manager</div>
</div>
<p style="font-size:10px;color:#888;margin-top:40px">เอกสารออกโดยระบบ AMS
HRM • สถานะ: {H.escape(r['status'])} • ผู้อนุมัติ:
{H.escape(r['approver'] or '-')}</p>
</body></html>"""
