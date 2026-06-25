# pages/T_On_Behalf.py — Management ▸ คำขออนุมัติแทน (submit on behalf, req. 7)
# ============================================================================
# A manager files Leave / OT / Shift-change / Resignation FOR a subordinate.
# Because the submitting manager is themselves an approver in the subordinate's
# line, their submission stands in for their own approval — so the request is
# routed as a SHORTCUT to the upper approval levels (the manager is removed
# from the chain, and the remaining ≤2 levels approve).
# ============================================================================
import datetime as dt
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme
from lib.auth import require_capability, current_user
from lib import employee_db as edb
from lib import approval_db as adb
from lib import attendance_db as adb_att
from lib import notify
from lib import ot_rules as otr
from lib import resign_db as rdb
from lib import print_docs

require_capability("leave.approve")          # supervisors / managers / admins
_theme.inject()
st.title("🤝 คำขออนุมัติแทน / Submit on behalf")
st.caption("หัวหน้างานยื่นคำขอ (ลา / โอที / เปลี่ยนกะ / ลาออก) แทนผู้ใต้บังคับบัญชา — "
           "ระบบจะข้ามระดับของคุณ และส่งตรงไปยังผู้อนุมัติระดับเหนือขึ้นไป · A manager "
           "files a request for a subordinate; it skips your level and routes to "
           "the approver(s) above you.")

mgr = current_user() or {}
me = mgr.get("username", "system")
mgr_rec = edb.get_record(emp_no=mgr.get("emp_no")) if mgr.get("emp_no") else None
if not mgr_rec:
    st.warning("บัญชีของคุณยังไม่ได้ผูกกับรหัสพนักงาน — โปรดให้ผู้ดูแลระบบผูกบัญชีก่อน · "
               "Your account isn't linked to an employee number yet.")
    st.stop()

# --- subordinates (reporting subtree, excluding self) ---
try:
    sub_nos = adb_att.subordinate_emp_nos(mgr_rec, include_self=False)
except Exception:
    sub_nos = set()
subs = [r for r in edb.list_records("active")
        if str(r.get("emp_no")) in {str(x) for x in sub_nos}]
subs.sort(key=lambda r: str(r.get("emp_name_en") or ""))
if not subs:
    st.info("ไม่พบผู้ใต้บังคับบัญชาในสายงานของคุณ (ตามคอลัมน์ Mgr ใน Employee List) · "
            "No subordinates found in your reporting line.")
    st.stop()


def _label(r):
    return f"{r.get('emp_no')} · {adb._clean_name(r.get('emp_name_en'))}"


sidx = st.selectbox("เลือกผู้ใต้บังคับบัญชา / Subordinate", list(range(len(subs))),
                    format_func=lambda i: _label(subs[i]))
subject = subs[sidx]
subject_id = subject["id"]
subject_no = subject["emp_no"]
subject_nm = (adb._clean_name(subject.get("emp_name_en"))
              or subject.get("emp_name_th") or subject_no)


def _onbehalf_chain():
    """Subject's chain with the submitting manager removed, re-numbered,
    capped at the upper 2 levels."""
    chain = adb.resolve_chain(subject)
    chain = [(l, r) for (l, r) in chain
             if str(r.get("emp_no")) != str(mgr_rec.get("emp_no"))]
    return [(i + 1, r) for i, (_, r) in enumerate(chain)][:2]


_chain = _onbehalf_chain()
if _chain:
    st.caption("จะส่งไปยัง / Will route to: " + " → ".join(
        f"L{l}: {adb._clean_name(r.get('emp_name_en'))}" for l, r in _chain))
else:
    st.caption("ไม่มีผู้อนุมัติเหนือคุณสำหรับพนักงานคนนี้ → อนุมัติอัตโนมัติและแจ้ง HR · "
               "No approver above you for this person → auto-approves, flagged to HR.")


def _route(kind, req_id, success_label):
    first = adb.open_approvals(kind, req_id, subject, chain=_chain or None)
    if first:
        try:
            req = edb.my_requests(kind, subject_id, limit=1)[0] \
                if kind != "resign" else {"emp_no": subject_no,
                                          "doc_no": "", "summary": success_label}
            _, msg = notify.notify_approver(kind, req, first)
        except Exception:
            msg = "—"
        st.success(f"ยื่นแทน {subject_nm} แล้ว → รอ {first['approver_name']} • {msg}")
    else:
        st.success(f"ยื่นแทน {subject_nm} แล้ว (อนุมัติอัตโนมัติ) · submitted (auto-approved).")
    st.rerun()


from lib import leave_config

# Active leave types for the on-behalf picker (single source of truth).
LEAVE_TYPES = leave_config.labels(active_only=True)

st.divider()
rtype = st.radio("ประเภทคำขอ / Request type",
                 ["Leave / ลา", "OT / โอที", "Shift / เปลี่ยนกะ",
                  "Resignation / ลาออก"], horizontal=True)

# -------------------------------------------------------------------- Leave
if rtype.startswith("Leave"):
    lt = st.selectbox("ประเภทการลา / Leave type", list(LEAVE_TYPES),
                      format_func=lambda k: LEAVE_TYPES[k], key="ob_lt")
    c1, c2 = st.columns(2)
    d1 = c1.date_input("จากวันที่ / From", dt.date.today(), key="ob_d1")
    d2 = c2.date_input("ถึงวันที่ / To", dt.date.today(), key="ob_d2")
    period = st.radio("ช่วงเวลา / Period", ["full", "half_am", "half_pm"],
                      horizontal=True, key="ob_per",
                      format_func=lambda p: {"full": "เต็มวัน", "half_am":
                                             "ครึ่งเช้า", "half_pm": "ครึ่งบ่าย"}[p])
    reason = st.text_area("เหตุผล / Reason", height=68, key="ob_lr")
    if st.button("ยื่นคำขอลาแทน / Submit leave", type="primary", key="ob_lsub"):
        if d2 < d1:
            st.error("วันที่สิ้นสุดต้องไม่ก่อนวันเริ่ม")
        else:
            days = (d2 - d1).days + 1
            if period != "full":
                days = 0.5 if d1 == d2 else days - 0.5
            edb.submit_leave(subject_id, subject_no, lt, d1.isoformat(),
                             d2.isoformat(), period, days, reason, me)
            req = edb.my_requests("leave", subject_id, limit=1)[0]
            _route("leave", req["id"], "leave")

# -------------------------------------------------------------------- OT
elif rtype.startswith("OT"):
    od = st.date_input("วันที่ทำโอที / OT date", dt.date.today(), key="ob_od")
    c1, c2 = st.columns(2)
    shift = c1.selectbox("กะ / Shift", list(otr.SHIFTS), key="ob_sh",
                         format_func=lambda k: otr.shift_label(k))
    ot_type = c2.selectbox("ประเภท OT / OT type", list(otr.OT_TYPES), key="ob_ot",
                           format_func=lambda k: otr.ot_type_label(k))
    mode = otr.OT_TYPES[ot_type]["mode"]
    c3, c4 = st.columns(2)
    hours = c3.number_input("จำนวนชั่วโมง / Hours (×0.5)", 0.5, 12.0, 2.0, 0.5,
                            key="ob_hr")
    if mode == "free":
        fs = c4.time_input("เวลาเริ่ม (วันหยุด) / Start", dt.time(8, 0),
                           step=dt.timedelta(minutes=30), key="ob_fs")
        free_start = fs.strftime("%H:%M")
    else:
        free_start = "08:00"
        c4.caption("⏱️ เวลาเริ่ม–สิ้นสุด คำนวณจากกะ · auto from shift")
    tf, tt = otr.ot_window(shift, ot_type, hours, free_start)
    rate = otr.multiplier(ot_type)
    st.info(f"⏱️ {tf} – {tt} · {hours:g} ชม. × {rate}")
    wo = st.text_input("Work Order No.", key="ob_wo")
    reason = st.text_area("งาน/เหตุผล / Work detail", height=68, key="ob_or")
    if st.button("ยื่นคำขอโอทีแทน / Submit OT", type="primary", key="ob_osub"):
        edb.submit_ot(subject_id, subject_no, od, tf, tt, hours, rate, reason,
                      me, ot_type=ot_type, work_order_no=wo, shift=shift)
        req = edb.my_requests("ot", subject_id, limit=1)[0]
        _route("ot", req["id"], "ot")

# -------------------------------------------------------------------- Shift
elif rtype.startswith("Shift"):
    st.caption("กะมาตรฐาน: " + "  ·  ".join(otr.shift_label(k)
                                            for k in otr.SHIFTS))
    c1, c2 = st.columns(2)
    cur_sh = c1.selectbox("กะปัจจุบัน / Current", list(otr.SHIFTS), key="ob_cs",
                          format_func=lambda k: otr.shift_label(k))
    req_sh = c2.selectbox("กะที่ขอ / Requested", list(otr.SHIFTS), index=1,
                          key="ob_rs", format_func=lambda k: otr.shift_label(k))
    c3, c4 = st.columns(2)
    df = c3.date_input("มีผลตั้งแต่ / From", dt.date.today(), key="ob_sf")
    use_to = c4.checkbox("ระบุวันสิ้นสุด / End date", key="ob_ut")
    d_to = c4.date_input("ถึง / To", dt.date.today(), key="ob_st") \
        if use_to else None
    reason = st.text_area("เหตุผล / Reason", height=68, key="ob_sr")
    if st.button("ยื่นเปลี่ยนกะแทน / Submit shift change", type="primary",
                 key="ob_ssub"):
        if cur_sh == req_sh:
            st.error("กะปัจจุบันและกะที่ขอต้องไม่เหมือนกัน")
        else:
            edb.submit_shift_change(subject_id, subject_no, subject_nm, cur_sh,
                                    req_sh, df.isoformat(),
                                    d_to.isoformat() if d_to else None,
                                    reason, me)
            req = edb.my_requests("shift", subject_id, limit=1)[0]
            _route("shift", req["id"], "shift")

# -------------------------------------------------------------------- Resign
else:
    st.caption("ยื่นใบลาออก/เลิกจ้างแทนพนักงาน (เช่น กรณีขาดงานติดต่อกัน) · File a "
               "resignation/termination for the employee.")
    last_day = st.date_input("วันทำงานสุดท้าย / Last working day",
                             dt.date.today(), key="ob_ld")
    reason = st.text_area("เหตุผล / Reason", height=68, key="ob_rr")
    if st.button("ยื่นลาออกแทน / Submit resignation", type="primary",
                 key="ob_rsub"):
        rid, doc = rdb.create(mgr_rec, subject, "delegate",
                              last_day.isoformat(), reason, me)
        _route("resign", rid, f"{doc} • {subject_nm} • {last_day.isoformat()}")

# -------------------------------------------------- my on-behalf submissions
st.divider()
def _emit_print(html, name):
    """Offer the filled form as PDF (WeasyPrint) or printable HTML (Ctrl+P)."""
    pdf = print_docs.html_to_pdf(html)
    if pdf:
        st.download_button("⬇️ ดาวน์โหลด PDF / Download PDF", pdf,
                           file_name=name + ".pdf", mime="application/pdf",
                           key="dl_" + name, use_container_width=True)
    else:
        st.download_button("⬇️ ดาวน์โหลด HTML (เปิดแล้วกด Ctrl+P เพื่อพิมพ์)",
                           html.encode("utf-8"), file_name=name + ".html",
                           mime="text/html", key="dlh_" + name,
                           use_container_width=True)


with st.expander("📋 คำขอที่ฉันยื่นแทน · Requests I submitted on behalf"):
    found = False
    for kind, lbl in (("leave", "ลา"), ("ot", "โอที"), ("shift", "เปลี่ยนกะ")):
        for r in edb.my_requests(kind, subject_id, limit=50):
            if str(r.get("requested_by")) != str(me):
                continue
            found = True
            _when = r.get("date_from") or r.get("ot_date") or ""
            c1, c2 = st.columns([5, 2])
            c1.markdown(f"**{lbl}** · {subject_nm} · {_when} — {r.get('status')}")
            if c2.button("🖨️ พิมพ์ · Print", key=f"prob_{kind}_{r['id']}"):
                if kind == "leave":
                    _emit_print(print_docs.render_leave_requisition(subject, r),
                                f"Leave_{subject_no}_{r['id']}")
                elif kind == "ot":
                    _emit_print(print_docs.render_ot_requisition(subject, r),
                                f"OT_{subject_no}_{r['id']}")
                else:
                    _emit_print(print_docs.render_shift_change(subject, r),
                                f"Shift_{subject_no}_{r['id']}")
    for r in rdb.list_resignations(requester_emp_no=mgr_rec.get("emp_no")):
        found = True
        c1, c2 = st.columns([5, 2])
        c1.markdown(f"**ลาออก** · {r.get('subject_name')} · "
                    f"{r.get('last_working_day')} — {r.get('status')}")
        if c2.button("🖨️ พิมพ์ · Print", key=f"prob_rsn_{r['id']}"):
            _emit_print(rdb.notice_html(r), f"Resignation_{r.get('id')}")
    if not found:
        st.caption("ยังไม่มี · none yet")
