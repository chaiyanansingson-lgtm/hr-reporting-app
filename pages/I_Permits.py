# pages/I_Permits.py — Entrance permits (§10)
# FM-HR-034 ENTRY-CARD (visitor entry, host approves) and
# FM-HR-035 take-goods-out permit (dept-head approves via Mgr chain).
# Both print in the ORIGINAL form layout via the direct-print popup.
import datetime as dt
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme
import streamlit.components.v1 as components

from lib.auth import require_capability, current_user, has_capability
from lib import employee_db as edb
from lib import approval_db as adb
from lib import permit_db as pdb
from lib import notify

_theme.inject()
require_capability("permit.request")

user = current_user(); me = user["username"]
rec = edb.get_record(emp_no=str(user.get("emp_no") or "")) or {}

st.title("🪪 ใบอนุญาตผ่านเข้า-ออก & นำของออก / Entrance & Take-out Permits")

tabs = st.tabs(["🚪 ENTRY-CARD (FM-HR-034)",
                "📦 นำของออกโรงงาน (FM-HR-035)",
                "✅ อนุมัติ / Approvals",
                "🛡️ รปภ. & Admin / Security"])


def _print_button(html, key):
    if st.button("🖨️ พิมพ์ / Print", key=key):
        components.html(
            f"<script>var w=window.open('','_blank');"
            f"w.document.write({html!r});w.document.close();</script>",
            height=0)


# ============================================== FM-HR-034 entry card
with tabs[0]:
    st.caption("ขอบัตรผ่านเข้า-ออกให้ผู้มาติดต่อ — พิมพ์ตามแบบฟอร์ม "
               "FM-HR-034 Rev.00 (2 ใบ/หน้า A4) / Entry card for a visitor, "
               "printed exactly per the original form.")
    with st.form("ent_form"):
        c1, c2, c3 = st.columns(3)
        vd = c1.date_input("วันที่เข้า / Visit date", dt.date.today())
        vn = c2.text_input("ชื่อ / NAME *")
        vs = c3.text_input("นามสกุล / SURNAME *")
        comp = st.text_input("ที่อยู่/บริษัท / ADDRESS-Company *")
        c4, c5 = st.columns(2)
        contact = c4.text_input("บุคคลที่ต้องการติดต่อ / CONTACT PERSON",
                                value=rec.get("emp_name_en") or "")
        purpose = c5.text_input("วัตถุประสงค์ / PURPOSE *")
        c6, c7, c8 = st.columns(3)
        carno = c6.text_input("ทะเบียนรถ / CAR NUMBER")
        moto = c7.checkbox("มอเตอร์ไซค์ / Motorcycle")
        sex = c8.radio("เพศ / Sex", ["", "M", "F"], horizontal=True,
                       format_func=lambda x: {"": "-", "M": "ชาย",
                                              "F": "หญิง"}[x])
        goods = st.text_input("สิ่งของ/อุปกรณ์ที่นำเข้า / Goods-tools in")
        go = st.form_submit_button("📨 ขอบัตร / Submit", type="primary")
    if go:
        if not (vn.strip() and vs.strip() and comp.strip()
                and purpose.strip()):
            st.error("กรุณากรอกช่องที่มี *")
        else:
            pid, doc = pdb.create_entry(rec, vd, vn, vs, comp, contact,
                                        purpose, carno, moto, sex, goods, me)
            # host (the requester) approval is implicit; route to their L1
            chain = adb.resolve_chain(rec, max_levels=1) if rec else []
            p = pdb.get_permit("permit_entry", pid)
            p["summary"] = f"ผู้มาติดต่อ {vn} {vs} ({comp}) วันที่ {vd}"
            first = adb.open_approvals("permit_entry", pid, rec,
                                       chain=chain or None)
            if first:
                notify.notify_approver("permit_entry", p, first)
                st.success(f"ส่งคำขอแล้ว **{doc}** → รออนุมัติ "
                           f"{first['approver_name']}")
            else:
                st.success(f"บันทึกแล้ว **{doc}** — พิมพ์ได้ที่แท็บ รปภ. & "
                           f"Admin")
    st.divider()
    st.markdown("**บัตรของฉัน / My entry cards**")
    for p in pdb.list_permits("permit_entry",
                              requester_emp_no=rec.get("emp_no"))[:10]:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{p['doc_no']}** {p['visit_date']} — {p['v_name']} "
                 f"{p['v_surname']} ({p['v_company']}) • {p['status']}")
        if p["status"] in ("approved", "Request"):
            with c2:
                _print_button(pdb.entry_card_html(p), f"pe{p['id']}")

# ============================================== FM-HR-035 take-out
with tabs[1]:
    st.caption("ใบขออนุญาตนำของออกนอกบริเวณโรงงาน — อนุมัติโดยหัวหน้าแผนก "
               "(สายบังคับบัญชา L1) แล้วยื่น รปภ. / printed per FM-HR-035 "
               "Rev.00.")
    with st.form("out_form"):
        c1, c2, c3 = st.columns(3)
        od = c1.date_input("วันที่ / Date", dt.date.today())
        dept = c2.selectbox("แผนก / Department", pdb.FM035_DEPTS)
        dept_other = c3.text_input("ระบุ (ถ้าเลือก Other)")
        prop = st.radio("ของ / Property of", ["company", "personal"],
                        horizontal=True,
                        format_func=lambda x: "ของบริษัท" if x == "company"
                        else "ของส่วนตัว")
        st.markdown("**รายการ (สูงสุด 10 แถวตามฟอร์ม) / Items (max 10)**")
        lines = []
        for i in range(1, 6):
            c1, c2, c3, c4 = st.columns([4, 1, 1, 3])
            it = c1.text_input(f"รายการ {i}", key=f"oi{i}",
                               label_visibility="collapsed",
                               placeholder=f"{i}. รายการ / item")
            qy = c2.text_input("จำนวน", key=f"oq{i}",
                               label_visibility="collapsed",
                               placeholder="จำนวน")
            un = c3.text_input("หน่วย", key=f"ou{i}",
                               label_visibility="collapsed",
                               placeholder="หน่วย")
            rs = c4.text_input("วัตถุประสงค์", key=f"or{i}",
                               label_visibility="collapsed",
                               placeholder="วัตถุประสงค์ที่นำออก")
            if it.strip():
                lines.append({"item": it, "qty": qy, "unit": un,
                              "reason": rs})
        go = st.form_submit_button("📨 ส่งคำขอ / Submit", type="primary")
    if go:
        if not lines:
            st.error("กรุณาใส่อย่างน้อย 1 รายการ")
        elif not rec:
            st.error("บัญชียังไม่ผูกรหัสพนักงาน")
        else:
            pid, doc = pdb.create_takeout(rec, od, dept, dept_other, prop,
                                          lines, me)
            chain = adb.resolve_chain(rec, max_levels=1)
            p = pdb.get_permit("permit_out", pid)
            p["summary"] = (f"นำของออก {len(lines)} รายการ ({dept}) "
                            f"วันที่ {od}")
            first = adb.open_approvals("permit_out", pid, rec,
                                       chain=chain or None)
            if first:
                notify.notify_approver("permit_out", p, first)
                st.success(f"ส่งแล้ว **{doc}** → รออนุมัติ "
                           f"{first['approver_name']}")
            else:
                st.success(f"บันทึกแล้ว **{doc}**")
    st.divider()
    st.markdown("**คำขอของฉัน / My take-out permits**")
    for p in pdb.list_permits("permit_out",
                              requester_emp_no=rec.get("emp_no"))[:10]:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{p['doc_no']}** {p['out_date']} — {p['department']} • "
                 f"{p['status']}")
        if p["status"] == "approved":
            with c2:
                _print_button(pdb.takeout_html(
                    p, pdb.takeout_lines(p["id"])), f"po{p['id']}")

# ============================================== approvals
with tabs[2]:
    if not has_capability("permit.approve"):
        st.info("Requires permit.approve")
    else:
        any_q = False
        for kind, label in (("permit_entry", "ENTRY-CARD"),
                            ("permit_out", "นำของออก / Take-out")):
            q = adb.my_queue(kind, rec.get("emp_no"))
            if q:
                st.subheader(f"{label} — {len(q)}")
            for r in q:
                any_q = True
                if kind == "permit_entry":
                    head = (f"{r['doc_no']} • {r['v_name']} "
                            f"{r['v_surname']} ({r['v_company']}) "
                            f"{r['visit_date']} — {r['purpose']}")
                else:
                    ls = pdb.takeout_lines(r["id"])
                    head = (f"{r['doc_no']} • {r['requester_name']} "
                            f"({r['department']}) {r['out_date']} — "
                            + "; ".join(f"{l['item']}×{l['qty'] or 1}"
                                        for l in ls[:4]))
                st.markdown(f"**[L{r['my_level']}]** {head}")
                c1, c2, c3 = st.columns([1, 1, 3])
                note = c3.text_input("Note", key=f"pn{kind}{r['approval_id']}",
                                     label_visibility="collapsed")
                if c1.button("✅", key=f"pa{kind}{r['approval_id']}"):
                    adb.act(kind, r["approval_id"], True, me, note)
                    st.rerun()
                if c2.button("❌", key=f"pr{kind}{r['approval_id']}"):
                    adb.act(kind, r["approval_id"], False, me, note)
                    st.rerun()
        if not any_q:
            st.caption("ไม่มีรายการรออนุมัติ / nothing waiting")

# ============================================== security / admin
with tabs[3]:
    if not has_capability("permit.admin"):
        st.info("Requires permit.admin (HR/Security)")
    else:
        day = st.date_input("วันที่ / Date", dt.date.today(), key="sec_day")
        st.subheader("ENTRY-CARD วันนี้ / today")
        for p in pdb.list_permits("permit_entry", date=str(day)):
            c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
            c1.write(f"**{p['doc_no']}** {p['v_name']} {p['v_surname']} "
                     f"({p['v_company']}) • {p['status']}"
                     + (f" • เข้า {p['time_in']}" if p['time_in'] else "")
                     + (f" • ออก {p['time_out']}" if p['time_out'] else ""))
            tin = c2.text_input("เข้า", key=f"ti{p['id']}",
                                label_visibility="collapsed",
                                placeholder="HH:MM เข้า")
            tout = c3.text_input("ออก", key=f"to{p['id']}",
                                 label_visibility="collapsed",
                                 placeholder="HH:MM ออก")
            if c4.button("💾", key=f"sv{p['id']}"):
                pdb.security_log("permit_entry", p["id"],
                                 time_in=tin or None, time_out=tout or None,
                                 guard_name=me, actor=me)
                st.rerun()
            with c5:
                _print_button(pdb.entry_card_html(p), f"spe{p['id']}")
        st.subheader("นำของออกวันนี้ / Take-out today")
        for p in pdb.list_permits("permit_out", date=str(day)):
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.write(f"**{p['doc_no']}** {p['requester_name']} "
                     f"({p['department']}) • {p['status']}")
            tout = c2.text_input("เวลาออก", key=f"oto{p['id']}",
                                 label_visibility="collapsed",
                                 placeholder="HH:MM นำออก")
            if c3.button("💾", key=f"osv{p['id']}"):
                pdb.security_log("permit_out", p["id"], time_out=tout or
                                 None, guard_name=me, actor=me)
                st.rerun()
            with c4:
                _print_button(pdb.takeout_html(
                    p, pdb.takeout_lines(p["id"])), f"spo{p['id']}")
