# lib/permit_db.py
# ============================================================================
# ENTRANCE PERMITS (§10) — two forms, faithful to the originals you sent:
#   FM-HR-034 Rev.00  ใบขออนุญาตผ่านเข้า-ออก / ENTRY-CARD
#       visitor entry: name/surname, address/company, contact person,
#       purpose, car number, motorcycle + M/F ticks, goods-in,
#       signatures (visitor + host), security in/out times.
#       Printed TWO CARDS PER A4 exactly like the master file.
#   FM-HR-035 Rev.00  ใบขออนุญาตนำของออกนอกบริเวณโรงงาน (take goods out)
#       department ticks, personal/company property, 10-row items table,
#       notes 1-4, แจ้งโดย/รับทราบโดย + รปภ. block, ANCA footer.
# Flow: request -> host / dept-head approval (unified engine) ->
#       admin & security daily list -> print in original format.
# ============================================================================
import datetime as dt
import html as H

from lib.db import get_conn, IS_POSTGRES, PH
from lib import employee_db as edb

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"

FM035_DEPTS = ["Laser/เลเซอร์", "Folding/พับ", "Welding/เชื่อม",
               "Painting/สี", "Assembly/ประกอบ", "Store/สโตร์",
               "Office/สำนักงาน", "Maintenance/ซ่อมบำรุง", "Other/อื่นๆ"]


def _ts():
    return dt.datetime.now().isoformat(timespec="seconds")


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS permit_entries (
        id {SERIAL},
        doc_no TEXT UNIQUE,
        requester_emp_no TEXT, requester_name TEXT,   -- host staff
        visit_date TEXT,
        v_name TEXT, v_surname TEXT, v_company TEXT,
        contact_person TEXT, purpose TEXT,
        car_number TEXT, motorcycle INTEGER DEFAULT 0,
        sex TEXT,                                       -- M / F / ''
        goods_in TEXT,
        status TEXT NOT NULL DEFAULT 'Request',
        approver TEXT, approved_at TEXT, approve_note TEXT,
        time_in TEXT, time_out TEXT, guard_name TEXT,
        created_by TEXT, created_at TEXT)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS permit_takeouts (
        id {SERIAL},
        doc_no TEXT UNIQUE,
        requester_emp_no TEXT, requester_name TEXT, requester_title TEXT,
        out_date TEXT,
        department TEXT,                                 -- one of FM035_DEPTS
        dept_other TEXT,
        property_of TEXT NOT NULL DEFAULT 'company',     -- personal|company
        status TEXT NOT NULL DEFAULT 'Request',
        approver TEXT, approved_at TEXT, approve_note TEXT,
        ack_by TEXT, ack_title TEXT,                     -- รับทราบโดย
        guard_name TEXT, time_out TEXT, guard_date TEXT,
        created_by TEXT, created_at TEXT)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS permit_takeout_lines (
        id {SERIAL},
        permit_id INTEGER NOT NULL,
        seq INTEGER, item TEXT, qty TEXT, unit TEXT, reason TEXT)""")
    conn.commit()


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


def _next_doc(prefix, table):
    conn = get_conn(); cur = conn.cursor()
    ym = dt.date.today().strftime("%y%m")
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE doc_no LIKE {PH}",
                (f"{prefix}-{ym}-%",))
    return f"{prefix}-{ym}-{cur.fetchone()[0] + 1:03d}"


# ---------------------------------------------------------------- entry card
def create_entry(host, visit_date, v_name, v_surname, v_company,
                 contact_person, purpose, car_number, motorcycle, sex,
                 goods_in, actor):
    conn = get_conn(); cur = conn.cursor()
    doc = _next_doc("ENT", "permit_entries")
    cur.execute(
        f"""INSERT INTO permit_entries (doc_no, requester_emp_no,
            requester_name, visit_date, v_name, v_surname, v_company,
            contact_person, purpose, car_number, motorcycle, sex, goods_in,
            status, created_by, created_at)
            VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},
            {PH},{PH},'Request',{PH},{PH})""",
        (doc, (host or {}).get("emp_no"), (host or {}).get("emp_name_en"),
         str(visit_date), v_name, v_surname, v_company, contact_person,
         purpose, car_number, 1 if motorcycle else 0, sex, goods_in,
         actor, _ts()))
    if IS_POSTGRES:
        cur.execute("SELECT id FROM permit_entries WHERE doc_no=%s", (doc,))
        pid = cur.fetchone()[0]
    else:
        pid = cur.lastrowid
    conn.commit()
    edb._audit(conn, actor, "permit_entry_create", detail={"doc_no": doc})
    conn.commit()
    return pid, doc


def create_takeout(requester, out_date, department, dept_other, property_of,
                   lines, actor):
    """lines: [{item, qty, unit, reason}] max 10 (the form has 10 rows)."""
    conn = get_conn(); cur = conn.cursor()
    doc = _next_doc("OUT", "permit_takeouts")
    cur.execute(
        f"""INSERT INTO permit_takeouts (doc_no, requester_emp_no,
            requester_name, requester_title, out_date, department,
            dept_other, property_of, status, created_by, created_at)
            VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},'Request',
            {PH},{PH})""",
        (doc, requester.get("emp_no"), requester.get("emp_name_en"),
         requester.get("title"), str(out_date), department, dept_other,
         property_of, actor, _ts()))
    if IS_POSTGRES:
        cur.execute("SELECT id FROM permit_takeouts WHERE doc_no=%s", (doc,))
        pid = cur.fetchone()[0]
    else:
        pid = cur.lastrowid
    for i, l in enumerate(lines[:10], 1):
        cur.execute(f"""INSERT INTO permit_takeout_lines (permit_id, seq,
                        item, qty, unit, reason)
                        VALUES ({PH},{PH},{PH},{PH},{PH},{PH})""",
                    (pid, i, l.get("item"), l.get("qty"), l.get("unit"),
                     l.get("reason")))
    conn.commit()
    edb._audit(conn, actor, "permit_takeout_create", detail={"doc_no": doc})
    conn.commit()
    return pid, doc


def get_permit(kind, pid):
    table = "permit_entries" if kind == "permit_entry" else "permit_takeouts"
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table} WHERE id={PH}", (pid,))
    r = cur.fetchone()
    if not r:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r)) if IS_POSTGRES else dict(r)


def takeout_lines(pid):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM permit_takeout_lines WHERE permit_id={PH} "
                f"ORDER BY seq", (pid,))
    return _rows(cur)


def list_permits(kind, status=None, date=None, requester_emp_no=None):
    table = "permit_entries" if kind == "permit_entry" else "permit_takeouts"
    dcol = "visit_date" if kind == "permit_entry" else "out_date"
    conn = get_conn(); cur = conn.cursor()
    sql = f"SELECT * FROM {table} WHERE 1=1"
    args = []
    if status:
        sql += f" AND status={PH}"; args.append(status)
    if date:
        sql += f" AND {dcol}={PH}"; args.append(str(date))
    if requester_emp_no:
        sql += f" AND requester_emp_no={PH}"
        args.append(str(requester_emp_no))
    sql += " ORDER BY id DESC LIMIT 300"
    cur.execute(sql, args)
    return _rows(cur)


def security_log(kind, pid, time_in=None, time_out=None, guard_name=None,
                 actor=""):
    table = "permit_entries" if kind == "permit_entry" else "permit_takeouts"
    conn = get_conn(); cur = conn.cursor()
    sets, args = [], []
    if time_in is not None and kind == "permit_entry":
        sets.append(f"time_in={PH}"); args.append(str(time_in)[:5])
    if time_out is not None:
        sets.append(f"time_out={PH}"); args.append(str(time_out)[:5])
    if guard_name is not None:
        sets.append(f"guard_name={PH}"); args.append(guard_name)
    if kind == "permit_out":
        sets.append(f"guard_date={PH}")
        args.append(dt.date.today().isoformat())
    if not sets:
        return
    args.append(pid)
    cur.execute(f"UPDATE {table} SET {', '.join(sets)} WHERE id={PH}", args)
    conn.commit()
    edb._audit(conn, actor, f"{kind}_security_log", detail={"id": pid})
    conn.commit()


# ============================================================ PRINT (originals)
_ANCA_LOGO = """<div style="display:flex;justify-content:flex-end">
 <div style="display:flex;gap:8px;align-items:center">
  <div style="width:34px;height:34px;border-radius:7px;display:grid;
   place-items:center;color:#fff;font-weight:800;font-size:18px;
   background:linear-gradient(135deg,#009ADE,#715091 55%,#E31D93)">A</div>
  <div style="font-weight:800;color:#1d2a55;font-size:12px;line-height:1.1">
   ANCA<br>MANUFACTURING<br>SOLUTIONS</div></div></div>"""

_FOOTER = """<div class="ftr">
 <div><b>ANCA Manufacturing Solutions (Thailand) Ltd.</b><br>
 Eastern Seaboard Industrial Estate<br>
 109/14 M.4 T.Pluakdaeng A.Pluakdaeng Rayong 21140 Thailand</div>
 <div style="text-align:right"><b>Tel:+66(0)38-959-223-5<br>
 Fax:+66(0)38959-226</b></div></div>"""


def _dots(v, width):
    v = H.escape(str(v or ""))
    return (f'<span class="fill" style="min-width:{width}px">{v}</span>')


def _th_date(iso):
    try:
        d = dt.date.fromisoformat(str(iso)[:10])
        return d.day, ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน",
                       "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
                       "กันยายน", "ตุลาคม", "พฤศจิกายน",
                       "ธันวาคม"][d.month], d.year + 543
    except Exception:
        return "", "", ""


def entry_card_html(rec):
    """FM-HR-034: TWO identical cards per A4 (like the master file)."""
    d, m, y = _th_date(rec.get("visit_date"))
    moto = "☑" if rec.get("motorcycle") else "☐"
    male = "☑" if rec.get("sex") == "M" else "☐"
    female = "☑" if rec.get("sex") == "F" else "☐"

    def card():
        return f"""<div class="card">
 <div class="c" style="font-weight:700">ANCA Manufacturing Solutions
 (Thailand) Ltd.</div>
 <div class="c">บริษัท แอนคา แมนูแฟคเจอริ่ง โซลูชั่นส์ (ประเทศไทย) จำกัด</div>
 <div class="c" style="font-weight:800;font-size:15px;margin-top:2px">
 ใบขออนุญาตผ่านเข้า-ออก</div>
 <div class="c" style="font-weight:700">ENTRY – CARD</div>
 <div class="c" style="margin:4px 0">วันที่ {_dots(d, 36)} เดือน
 {_dots(m, 90)} พ.ศ. {_dots(y, 50)}</div>
 <div class="ln">ชื่อ / NAME {_dots(rec.get('v_name'), 180)}
  นามสกุล / SURNAME {_dots(rec.get('v_surname'), 160)}</div>
 <div class="ln">ที่อยู่/บริษัท / ADDRESS
  {_dots(rec.get('v_company'), 420)}</div>
 <div class="ln">บุคคลที่ต้องการติดต่อ / CONTACT PERSON
  {_dots(rec.get('contact_person'), 330)}</div>
 <div class="ln">วัตถุประสงค์ / PURPOSE {_dots(rec.get('purpose'), 400)}</div>
 <div class="ln">ทะเบียนรถ / CAR NUMBER {_dots(rec.get('car_number'), 180)}
  &nbsp;&nbsp;&nbsp;{moto} มอเตอร์ไซค์ &nbsp;&nbsp;{male} ชาย
  &nbsp;&nbsp;{female} หญิง</div>
 <div class="ln">สิ่งของ/อุปกรณ์ เครื่องมือที่นำเข้า / GOOD/ACCESSORIES TOOL
  TO BE IN {_dots(rec.get('goods_in'), 250)}</div>
 <div class="ln" style="margin-top:8px">ลงชื่อผู้มาติดต่อ
  {_dots('', 150)} ลงชื่อผู้รับการติดต่อ
  {_dots(rec.get('requester_name'), 150)}</div>
 <div class="ln">เวลาเข้า {_dots(rec.get('time_in'), 70)}
  ลงชื่อรปภ. {_dots(rec.get('guard_name'), 130)}
  เวลาออก {_dots(rec.get('time_out'), 70)}</div>
 <div style="font-size:9px;color:#555;margin-top:4px">FM-HR-034&nbsp;
  Rev.00 &nbsp;•&nbsp; เลขที่ระบบ / Ref: {H.escape(rec.get('doc_no') or '')}
 </div></div>"""

    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<title>{H.escape(rec.get('doc_no') or 'ENTRY-CARD')}</title><style>
@page{{size:A4 portrait;margin:10mm}}
body{{font-family:'Sarabun','Leelawadee UI',Tahoma,sans-serif;font-size:12px;
 color:#111;margin:0}}
.card{{border:1px dashed #999;padding:12px 16px;margin-bottom:10mm;
 page-break-inside:avoid}}
.c{{text-align:center}} .ln{{margin:5px 0}}
.fill{{display:inline-block;border-bottom:1px dotted #555;padding:0 4px;
 text-align:center;font-weight:600}}
.noprint{{position:fixed;top:8px;right:10px}}
.noprint button{{padding:8px 16px;border:0;border-radius:8px;color:#fff;
 font-weight:700;cursor:pointer;
 background:linear-gradient(135deg,#009ADE,#715091)}}
@media print{{.noprint{{display:none}}}}
</style></head><body onload="window.print()">
<div class="noprint"><button onclick="window.print()">🖨️ Print</button></div>
{card()}{card()}
</body></html>"""


def takeout_html(rec, lines):
    """FM-HR-035 ใบขออนุญาตนำของออกนอกบริเวณโรงงาน — original layout."""
    d_, m_, y_ = _th_date(rec.get("out_date"))
    dept = rec.get("department") or ""

    def tick(label):
        on = "☑" if dept == label else "☐"
        extra = ""
        if label.startswith("Other") and rec.get("dept_other"):
            extra = f" โปรดระบุ {_dots(rec.get('dept_other'), 140)}"
        elif label.startswith("Other"):
            extra = " โปรดระบุ " + _dots("", 140)
        return f"<span class='tk'>{on} {H.escape(label)}{extra}</span>"

    rows = ""
    by_seq = {l["seq"]: l for l in lines}
    for i in range(1, 11):
        l = by_seq.get(i, {})
        rows += (f"<tr><td class='c'>{i}</td>"
                 f"<td>{H.escape(str(l.get('item') or ''))}</td>"
                 f"<td class='c'>{H.escape(str(l.get('qty') or ''))}</td>"
                 f"<td class='c'>{H.escape(str(l.get('unit') or ''))}</td>"
                 f"<td>{H.escape(str(l.get('reason') or ''))}</td></tr>")
    pp = "☑" if rec.get("property_of") == "personal" else "☐"
    pc = "☑" if rec.get("property_of") == "company" else "☐"
    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<title>{H.escape(rec.get('doc_no') or 'FM-HR-035')}</title><style>
@page{{size:A4 portrait;margin:12mm 14mm 16mm}}
body{{font-family:'Sarabun','Leelawadee UI',Tahoma,sans-serif;font-size:13px;
 color:#111;margin:0;position:relative;min-height:255mm}}
h1{{text-align:center;font-size:19px;margin:10px 0 6px}}
.fill{{display:inline-block;border-bottom:1px dotted #555;padding:0 4px;
 text-align:center;font-weight:600}}
.tk{{display:inline-block;min-width:31%;margin:3px 0;font-size:13px}}
table{{border-collapse:collapse;width:100%;margin:6px 0}}
th,td{{border:1.4px solid #111;padding:4px 6px;font-size:12.5px}}
th{{font-weight:700;text-align:center}}
td.c{{text-align:center}}
.note{{font-size:12px;margin:3px 0}}
.sig{{display:flex;justify-content:space-between;margin-top:12px;
 font-size:12.5px}}
.sig>div{{width:48%}}
.ftr{{position:absolute;bottom:0;left:0;right:0;display:flex;
 justify-content:space-between;border-top:2.5px solid #1d2a55;
 padding-top:4px;font-size:10px;color:#1d2a55}}
.rev{{position:absolute;bottom:-13mm;left:0;font-size:9.5px;color:#444}}
.noprint{{position:fixed;top:8px;right:10px}}
.noprint button{{padding:8px 16px;border:0;border-radius:8px;color:#fff;
 font-weight:700;cursor:pointer;
 background:linear-gradient(135deg,#009ADE,#715091)}}
@media print{{.noprint{{display:none}}}}
</style></head><body onload="window.print()">
<div class="noprint"><button onclick="window.print()">🖨️ Print</button></div>
{_ANCA_LOGO}
<h1>ใบขออนุญาตนำของออกนอกบริเวณโรงงาน</h1>
<div style="text-align:center;margin-bottom:8px">วันที่ {_dots(d_, 40)} /
 {_dots(m_, 110)} / {_dots(y_, 56)}</div>
<div>
 {tick('Laser/เลเซอร์')}{tick('Folding/พับ')}{tick('Welding/เชื่อม')}
 {tick('Painting/สี')}{tick('Assembly/ประกอบ')}{tick('Store/สโตร์')}
 {tick('Office/สำนักงาน')}{tick('Maintenance/ซ่อมบำรุง')}{tick('Other/อื่นๆ')}
</div>
<div style="margin:6px 0">มีความประสงค์นำของออกบริเวณโรงงาน
 &nbsp;&nbsp;{pp} ของส่วนตัว &nbsp;&nbsp;{pc} ของบริษัท</div>
<div style="text-align:center;font-weight:700">
 รายการวัสดุ/อุปกรณ์ที่นำเข้า/ออกบริเวณโรงงานมีดังต่อไปนี้</div>
<table><tr><th style="width:7%">ลำดับ</th><th>รายการ</th>
 <th style="width:13%">ปริมาณ/จำนวน</th><th style="width:9%">หน่วย</th>
 <th style="width:26%">วัตถุประสงค์ที่นำออก</th></tr>{rows}</table>
<div class="note"><b>หมายเหตุ</b> 1. ผู้นำของ ออกบริเวณโรงงาน
 (บุคคลภายในและภายนอกบริษัทฯ) กรอกเอกสารรายการดังกล่าวข้างต้น</div>
<div class="note" style="padding-left:52px">2. ส่งให้ผู้แจ้งนำของ ออก
 (บุคคลในบริษัทฯเท่านั้น) และหัวหน้าแผนก/ผู้มีอำนาจ เซ็นอนุมัตินำของ
 ออกบริเวณโรงงาน</div>
<div class="note" style="padding-left:52px">3. นำเอกสารนี้
 ยื่นที่รปภ.เพื่อใช้เป็นหลักฐานการอนุญาตให้นำของ เข้า/ออกนอกโรงงานได้</div>
<div class="note" style="padding-left:52px">4. รปภ.รวบรวมส่งให้
 จป.วิชาชีพทุกเช้าของวันถัดไป</div>
<div class="sig">
 <div>แจ้งโดย(ตัวบรรจง) {_dots(rec.get('requester_name'), 170)}<br><br>
  ตำแหน่ง {_dots(rec.get('requester_title'), 190)}</div>
 <div>รับทราบโดย {_dots(rec.get('ack_by') or rec.get('approver'), 165)}
  <br><br>ตำแหน่ง {_dots(rec.get('ack_title'), 185)}</div>
</div>
<div class="sig">
 <div>ผู้บันทึก {_dots(rec.get('guard_name'), 190)}<br>
  <span style="padding-left:26px">เจ้าหน้าที่รักษาความปลอดภัย</span></div>
 <div>เวลานำของออก {_dots(rec.get('time_out'), 110)}<br>
  วันที่ {_dots(rec.get('guard_date'), 170)}</div>
</div>
<div style="font-size:10px;color:#555;margin-top:8px">เลขที่ระบบ / Ref:
 {H.escape(rec.get('doc_no') or '')} • สถานะ: {H.escape(rec.get('status')
 or '')} • อนุมัติโดย: {H.escape(rec.get('approver') or '-')}</div>
{_FOOTER}
<div class="rev">FM-HR-035&nbsp; Rev.00</div>
</body></html>"""
