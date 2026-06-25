# pages/F_Leave_OT.py  (v3 — Leave + OT + Shift-change, 3-level approval + email)
# ============================================================================
# Flow: staff submits -> L1 (direct manager) -> L2 -> L3 -> approved.
# Each handover emails the next approver; final decision emails the staff.
# HR (leave.admin) sees the whole pipeline and can fire reminder emails.
# v3 (req. 5/6): OT in 0.5h steps with shift-aware start times (16:55 after a
# day shift), Work Order No. + OT-type columns, FM-HR-031 print, and a new
# Shift-change request (คำขอเปลี่ยนกะ) showing each shift's standard hours.
# ============================================================================
import datetime as dt
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme

from lib.auth import require_capability, current_user, has_capability
from lib import employee_db as edb
from lib import approval_db as adb
from lib import notify
from lib import print_docs
from lib import approver_tools
from lib import ot_rules as otr

_theme.inject()
require_capability("leave.submit")

user = current_user()
me = user["username"]

st.title("🗓️ Leave & OT / การลาและโอที")

emp_no = (user or {}).get("emp_no")
rec = edb.get_record(emp_no=str(emp_no)) if emp_no else None
if not rec:
    st.warning("บัญชีของคุณยังไม่ผูกรหัสพนักงาน — แจ้ง HR / Your login is "
               "not linked to an Emp. No. yet (System Admin → Users).")
    st.stop()

from lib import leave_config

# All leave-type labels (active + legacy) for display; the picker uses active.
LEAVE_TYPES = leave_config.labels(active_only=False)

STATUS_TH = {"pending_l1": "รอผู้อนุมัติระดับ 1", "pending_l2":
             "รอผู้อนุมัติระดับ 2", "pending_l3": "รอผู้อนุมัติระดับ 3",
             "approved": "อนุมัติแล้ว ✅", "rejected": "ไม่อนุมัติ ❌",
             "pending": "รออนุมัติ"}

_TRAIL_ICON = {"approved": "✅", "rejected": "❌", "pending": "⏳",
               "waiting": "·", "skipped": "—"}


def _trail(kind, req_id):
    steps = adb.rows_for(kind, req_id)
    return " → ".join(f"L{s['level']} {s['approver_name']} "
                      f"{_TRAIL_ICON.get(s['status'], s['status'])}"
                      for s in steps) or "อนุมัติอัตโนมัติ"


def _emit_print(html, name):
    """Offer the filled form as PDF (WeasyPrint) or HTML (browser Ctrl+P)."""
    pdf = print_docs.html_to_pdf(html)
    if pdf:
        st.download_button("⬇️ ดาวน์โหลด PDF / Download PDF", pdf,
                           file_name=name + ".pdf", mime="application/pdf",
                           key="dl_" + name, use_container_width=True)
    else:
        st.download_button("⬇️ ดาวน์โหลด HTML (Ctrl+P → Save as PDF)",
                           html.encode("utf-8"), file_name=name + ".html",
                           mime="text/html", key="dlh_" + name,
                           use_container_width=True)
        st.caption("WeasyPrint ไม่พร้อมในเครื่องนี้ — เปิดไฟล์แล้วกด Ctrl+P "
                   "เพื่อบันทึกเป็น PDF (A4).")


def _notify_first(kind, req, first):
    if first:
        try:
            _, msg = notify.notify_approver(kind, req, first)
        except Exception:
            msg = "—"
        st.success(f"ส่งคำขอแล้ว → รอ L1: {first['approver_name']} • {msg}")
    else:
        st.success("ส่งคำขอแล้ว (ไม่มีสายอนุมัติ → อนุมัติอัตโนมัติ)")


# approval chain (transparency)
chain = adb.resolve_chain(rec)
if chain:
    st.caption("สายอนุมัติของคุณ / Your approval chain: " + " → ".join(
        f"L{lvl}: {adb._clean_name(m.get('emp_name_en'))}"
        for lvl, m in chain))
else:
    st.caption("ไม่พบผู้บังคับบัญชาในระบบ — คำขอจะอนุมัติอัตโนมัติและแจ้ง HR / "
               "No manager found in the employee master; requests "
               "auto-approve and are flagged to HR.")

t_submit, t_my, t_approve, t_admin = st.tabs(
    ["📨 Submit", "🧾 My requests", "✅ My approvals", "🛠️ HR admin"])

# ---------------------------------------------------------------- submit
with t_submit:
    kind = st.radio("ประเภทคำขอ / Request type",
                    ["Leave / การลา", "OT / โอที", "Shift change / เปลี่ยนกะ"],
                    horizontal=True)

    # ---- Leave ----
    if kind.startswith("Leave"):
        _active = leave_config.labels(active_only=True)
        _hour_ok = leave_config.hour_unit_enabled()
        with st.form("leave_form"):
            lt = st.selectbox("ประเภทการลา / Leave type", list(_active),
                              format_func=lambda k: _active[k])
            if leave_config.requires_evidence(lt):
                st.caption("📎 ประเภทนี้ต้องแนบหลักฐาน · this type requires "
                           "evidence to submit.")
            _unit = "day"
            _hours = None
            if _hour_ok:
                _unit = st.radio("หน่วย / Unit", ["day", "hour"],
                                 horizontal=True,
                                 format_func=lambda u: ("วัน · Day" if u == "day"
                                                        else "ชั่วโมง · Hour"))
            c1, c2 = st.columns(2)
            d1 = c1.date_input("จากวันที่ / From", dt.date.today())
            d2 = c2.date_input("ถึงวันที่ / To", dt.date.today())
            if _unit == "hour":
                _hcol = st.columns(2)
                _hours = _hcol[0].number_input("จำนวนชั่วโมง / Hours", 0.5, 24.0,
                                               1.0, 0.5)
                period = "hourly"
            else:
                period = st.radio(
                    "ช่วงเวลา / Period", ["full", "half_am", "half_pm"],
                    horizontal=True,
                    format_func=lambda p: {"full": "เต็มวัน",
                                           "half_am": "ครึ่งเช้า",
                                           "half_pm": "ครึ่งบ่าย"}[p])
            reason = st.text_area("เหตุผล / Reason", height=70)
            _ev = st.file_uploader(
                "แนบหลักฐาน (รูป/ไฟล์) / Evidence (photo or file)",
                type=["png", "jpg", "jpeg", "pdf", "doc", "docx"],
                key="leave_ev")
            go = st.form_submit_button("ส่งคำขอลา / Submit", type="primary")
        if go:
            _need_ev = (leave_config.requires_evidence(lt)
                        or leave_config.mandatory_evidence_global())
            if d2 < d1:
                st.error("วันที่สิ้นสุดต้องไม่ก่อนวันเริ่ม · end date can't be "
                         "before start date.")
            elif leave_config.mandatory_reason() and not reason.strip():
                st.error("⛔ กรุณากรอกเหตุผล · reason is required.")
            elif _need_ev and _ev is None:
                st.error("⛔ ประเภทการลานี้ต้องแนบหลักฐานก่อนส่ง · this leave "
                         "type requires an evidence file before you can submit.")
            else:
                if _unit == "hour":
                    days = round((_hours or 0) / 8.0, 3)
                else:
                    days = (d2 - d1).days + 1
                    if period != "full":
                        days = 0.5 if d1 == d2 else days - 0.5
                _evd = None
                if _ev is not None:
                    import base64 as _b64
                    _evd = {"name": _ev.name, "mime": _ev.type,
                            "data": _b64.b64encode(_ev.read()).decode("ascii")}
                edb.submit_leave(rec["id"], rec["emp_no"], lt,
                                 d1.isoformat(), d2.isoformat(), period,
                                 days, reason, me, unit=_unit, hours=_hours,
                                 evidence=_evd)
                req = edb.my_requests("leave", rec["id"], limit=1)[0]
                first = adb.open_approvals("leave", req["id"], rec)
                _notify_first("leave", req, first)

    # ---- OT (req. 5: 0.5h steps, shift-aware start, OT type, Work Order No.) ----
    elif kind.startswith("OT"):
        od = st.date_input("วันที่ทำโอที / OT date", dt.date.today(),
                           key="ot_date")
        c1, c2 = st.columns(2)
        shift = c1.selectbox("กะ / Shift", list(otr.SHIFTS), key="ot_shift",
                             format_func=lambda k: otr.shift_label(k))
        ot_type = c2.selectbox("ประเภท OT / OT type", list(otr.OT_TYPES),
                               key="ot_type",
                               format_func=lambda k: otr.ot_type_label(k))
        mode = otr.OT_TYPES[ot_type]["mode"]
        c3, c4 = st.columns(2)
        hours = c3.number_input("จำนวนชั่วโมง / Hours (ทวีคูณ 0.5)",
                                min_value=0.5, max_value=12.0, value=2.0,
                                step=0.5, key="ot_hours")
        if mode == "free":
            fs = c4.time_input("เวลาเริ่ม (วันหยุด) / Start (holiday)",
                               dt.time(8, 0),
                               step=dt.timedelta(minutes=30), key="ot_fs")
            free_start = fs.strftime("%H:%M")
        else:
            free_start = "08:00"
            c4.markdown("&nbsp;")
            c4.caption("⏱️ เวลาเริ่ม–สิ้นสุด คำนวณจากกะอัตโนมัติ / "
                       "Start–end auto-derived from the shift.")
        tf, tt = otr.ot_window(shift, ot_type, hours, free_start)
        rate = otr.multiplier(ot_type)
        st.info(f"⏱️ ช่วงเวลา OT / OT window: **{tf} – {tt}**  ·  "
                f"{hours:g} ชม. × **{rate}**")
        wo = st.text_input("Work Order No. / เลขที่ใบสั่งงาน", key="ot_wo")
        reason = st.text_area("งาน/เหตุผล / Work detail", height=70,
                              key="ot_reason")
        if st.button("ส่งคำขอโอที / Submit", type="primary", key="ot_submit"):
            edb.submit_ot(rec["id"], rec["emp_no"], od, tf, tt, hours, rate,
                          reason, me, ot_type=ot_type, work_order_no=wo,
                          shift=shift)
            req = edb.my_requests("ot", rec["id"], limit=1)[0]
            first = adb.open_approvals("ot", req["id"], rec)
            _notify_first("ot", req, first)
            st.rerun()

    # ---- Shift change (req. 6) ----
    else:
        st.caption("กะมาตรฐาน / Standard shifts:  " +
                   "   ·   ".join(otr.shift_label(k) for k in otr.SHIFTS))
        c1, c2 = st.columns(2)
        cur_shift = c1.selectbox("กะปัจจุบัน / Current shift", list(otr.SHIFTS),
                                 key="sc_cur",
                                 format_func=lambda k: otr.shift_label(k))
        req_shift = c2.selectbox("กะที่ขอเปลี่ยนเป็น / Requested shift",
                                 list(otr.SHIFTS), index=1, key="sc_req",
                                 format_func=lambda k: otr.shift_label(k))
        c3, c4 = st.columns(2)
        df = c3.date_input("มีผลตั้งแต่ / Effective from", dt.date.today(),
                           key="sc_df")
        use_to = c4.checkbox("ระบุวันสิ้นสุด / Set end date", key="sc_useto")
        d_to = c4.date_input("ถึง / To", dt.date.today(), key="sc_dt") \
            if use_to else None
        reason = st.text_area("เหตุผล / Reason", height=70, key="sc_reason")
        if st.button("ส่งคำขอเปลี่ยนกะ / Submit", type="primary",
                     key="sc_submit"):
            if cur_shift == req_shift:
                st.error("กะปัจจุบันและกะที่ขอต้องไม่เหมือนกัน / Current and "
                         "requested shift must differ.")
            else:
                nm = (adb._clean_name(rec.get("emp_name_en"))
                      or rec.get("emp_name_th") or me)
                edb.submit_shift_change(
                    rec["id"], rec["emp_no"], nm, cur_shift, req_shift,
                    df.isoformat(), d_to.isoformat() if d_to else None,
                    reason, me)
                req = edb.my_requests("shift", rec["id"], limit=1)[0]
                first = adb.open_approvals("shift", req["id"], rec)
                _notify_first("shift", req, first)
                st.rerun()

# ---------------------------------------------------------------- my requests
with t_my:
    # Leave
    st.subheader("การลา / Leave")
    items = edb.my_requests("leave", rec["id"])
    if not items:
        st.caption("ยังไม่มีคำขอ / none yet")
    for r in items:
        head = (f"{LEAVE_TYPES.get(r['leave_type'], r['leave_type'])}"
                f" {r['date_from']}→{r['date_to']} ({r['days']} วัน)")
        st.markdown(f"**{head}** — {STATUS_TH.get(r['status'], r['status'])}<br>"
                    f"<span style='color:#777;font-size:13px'>"
                    f"{_trail('leave', r['id'])}</span>", unsafe_allow_html=True)

    # OT (with OT type + Work Order No. + FM-HR-031 print)
    st.subheader("โอที / OT")
    items = edb.my_requests("ot", rec["id"])
    if not items:
        st.caption("ยังไม่มีคำขอ / none yet")
    for r in items:
        extra = []
        if r.get("ot_type"):
            extra.append(otr.ot_type_label(r["ot_type"]))
        if r.get("work_order_no"):
            extra.append(f"WO: {r['work_order_no']}")
        extra_html = (" · ".join(extra)) if extra else ""
        head = (f"{r['ot_date']} {r['time_from']}–{r['time_to']} "
                f"({r['hours']:g} ชม. ×{r['rate']})")
        st.markdown(f"**{head}** — {STATUS_TH.get(r['status'], r['status'])}<br>"
                    f"<span style='color:#777;font-size:13px'>{extra_html}"
                    f"{'  •  ' if extra_html else ''}{_trail('ot', r['id'])}"
                    f"</span>", unsafe_allow_html=True)
        if st.button("🖨️ พิมพ์ FM-HR-031 / Print", key=f"prot{r['id']}"):
            _emit_print(print_docs.render_ot_requisition(rec, r),
                        f"OT_FM-HR-031_{r['id']}")

    # Shift change
    st.subheader("เปลี่ยนกะ / Shift change")
    items = edb.my_requests("shift", rec["id"])
    if not items:
        st.caption("ยังไม่มีคำขอ / none yet")
    for r in items:
        rng = r['date_from'] + (f" → {r['date_to']}" if r.get('date_to') else "")
        head = (f"{otr.shift_label(r['current_shift'])}  →  "
                f"{otr.shift_label(r['requested_shift'])}  ({rng})")
        st.markdown(f"**{head}** — {STATUS_TH.get(r['status'], r['status'])}<br>"
                    f"<span style='color:#777;font-size:13px'>"
                    f"{_trail('shift', r['id'])}</span>", unsafe_allow_html=True)
        if st.button("🖨️ พิมพ์แบบเปลี่ยนกะ / Print", key=f"prsc{r['id']}"):
            _emit_print(print_docs.render_shift_change(rec, r),
                        f"ShiftChange_{r['id']}")

# ---------------------------------------------------------------- approvals
with t_approve:
    if not has_capability("leave.approve"):
        st.info("หน้าสำหรับผู้อนุมัติ / Requires leave.approve")
    else:
        any_item = False
        for kind, label in (("leave", "การลา / Leave"), ("ot", "โอที / OT"),
                            ("shift", "เปลี่ยนกะ / Shift change"),
                            ("timeedit", "แก้ไขเวลา / Time edit")):
            queue = adb.my_queue(kind, rec["emp_no"])
            if queue:
                st.subheader(f"{label} — {len(queue)} pending")
            for r in queue:
                any_item = True
                if kind == "leave":
                    head = (f"{r['emp_no']} • {r['e_name']} "
                            f"({r['dept_location']}) — "
                            f"{LEAVE_TYPES.get(r['leave_type'])} "
                            f"{r['date_from']}→{r['date_to']} "
                            f"({r['days']} วัน)")
                    why = r.get("reason") or "—"
                elif kind == "ot":
                    extra = otr.ot_type_label(r["ot_type"]) if r.get("ot_type") \
                        else f"×{r['rate']}"
                    wo = f" • WO:{r['work_order_no']}" if r.get("work_order_no") \
                        else ""
                    head = (f"{r['emp_no']} • {r['e_name']} "
                            f"({r['dept_location']}) — {r['ot_date']} "
                            f"{r['time_from']}–{r['time_to']} "
                            f"({r['hours']:g} ชม. · {extra}{wo})")
                    why = r.get("reason") or "—"
                elif kind == "shift":
                    rng = r['date_from'] + (f"→{r['date_to']}"
                                            if r.get('date_to') else "")
                    head = (f"{r['emp_no']} • {r.get('requester_name', '')} — "
                            f"{otr.shift_label(r['current_shift'])} → "
                            f"{otr.shift_label(r['requested_shift'])} ({rng})")
                    why = r.get("reason") or "—"
                else:  # timeedit
                    head = (f"{r['emp_no']} • {r.get('requester_name', '')} — "
                            f"แก้ไขเวลา {r.get('work_date')} "
                            f"({r.get('req_time_in') or '-'}–"
                            f"{r.get('req_time_out') or '-'})")
                    why = (f"เดิม/was: {r.get('original_scans') or '—'} · "
                           f"{r.get('reason') or '—'}")
                st.markdown(f"**[L{r['my_level']}]** {head}<br>"
                            f"เหตุผล: {why}", unsafe_allow_html=True)
                with st.expander("🔎 ตรวจรายละเอียด & เครื่องมือผู้อนุมัติ · "
                                 "Review details & tools"):
                    _reqr = (edb.get_record(employee_id=r.get("employee_id"))
                             or edb.get_record(
                                 emp_no=str(r.get("emp_no") or "")) or {})
                    _det = {
                        "leave": print_docs.render_leave_requisition,
                        "ot": print_docs.render_ot_requisition,
                        "shift": print_docs.render_shift_change,
                        "timeedit": print_docs.render_time_edit,
                    }.get(kind)
                    _nm = (_reqr.get("emp_name_en") or r.get("e_name")
                           or r.get("requester_name") or "")
                    st.caption(f"เอกสาร · Doc: {r.get('doc_no') or '—'}  ·  "
                               f"ผู้ขอ · Requester: {r.get('emp_no')} {_nm}  ·  "
                               f"แผนก · Dept: "
                               f"{_reqr.get('dept_location') or r.get('dept_location') or '—'}")
                    if kind == "leave" and r.get("evidence_data"):
                        import base64 as _b64
                        try:
                            st.download_button(
                                "📎 ดูหลักฐานแนบ · Download evidence",
                                _b64.b64decode(r["evidence_data"]),
                                file_name=r.get("evidence_name") or "evidence",
                                mime=(r.get("evidence_mime")
                                      or "application/octet-stream"),
                                key=f"ev{kind}{r['approval_id']}",
                                use_container_width=True)
                        except Exception:
                            pass
                    elif kind == "leave":
                        st.caption("📎 ไม่มีไฟล์แนบ · no evidence attached.")
                    _pk = f"{kind}{r['approval_id']}"
                    _pc = st.columns(2)
                    if _pc[0].button("🖨️ พิมพ์เพื่อเซ็น · Print to sign",
                                     key=f"pr{_pk}", use_container_width=True):
                        st.session_state[f"shpr_{_pk}"] = True
                    if st.session_state.get(f"shpr_{_pk}") and _det:
                        _emit_print(
                            _det(_reqr, r),
                            f"{kind}_{r.get('doc_no') or r['approval_id']}")
                    _to = (_reqr.get("personal_email")
                           or _reqr.get("email") or "")
                    _subj, _body = approver_tools.reminder_text(kind, r, _nm)
                    _pc[1].link_button(
                        "📧 เปิด Outlook แจ้งเตือน · Outlook reminder",
                        approver_tools.outlook_mailto(_to, _subj, _body),
                        use_container_width=True)
                    if not _to:
                        _pc[1].caption("ไม่พบอีเมลผู้ขอ — ตั้งผู้รับใน Outlook · "
                                       "no email on file; set recipient in "
                                       "Outlook.")
                c1, c2, c3 = st.columns([1, 1, 3])
                note = c3.text_input("Note", key=f"n{kind}{r['approval_id']}",
                                     label_visibility="collapsed")
                if c1.button("✅ Approve", key=f"a{kind}{r['approval_id']}"):
                    res = adb.act(kind, r["approval_id"], True, me, note)
                    if res["next"]:
                        try:
                            _, msg = notify.notify_approver(kind, r, res["next"])
                        except Exception:
                            msg = "—"
                        st.toast(f"→ L{res['next']['level']} "
                                 f"{res['next']['approver_name']} • {msg}")
                    elif res["final"]:
                        reqr = edb.get_record(employee_id=r["employee_id"])
                        try:
                            notify.notify_requester(
                                kind, r, (reqr or {}).get("personal_email"),
                                "approved", note)
                        except Exception:
                            pass
                    st.rerun()
                if c2.button("❌ Reject", key=f"r{kind}{r['approval_id']}"):
                    adb.act(kind, r["approval_id"], False, me, note)
                    reqr = edb.get_record(employee_id=r["employee_id"])
                    try:
                        notify.notify_requester(
                            kind, r, (reqr or {}).get("personal_email"),
                            "rejected", note)
                    except Exception:
                        pass
                    st.rerun()
        if not any_item:
            st.caption("ไม่มีรายการรออนุมัติของคุณ / Nothing waiting for you "
                       "right now.")

# ---------------------------------------------------------------- HR admin
with t_admin:
    if not has_capability("leave.admin"):
        st.info("Requires leave.admin (HR)")
    else:
        pend = adb.pending_overview()
        st.subheader(f"ภาพรวมที่ค้างอนุมัติ / Pipeline — {len(pend)} pending "
                     f"level(s)")
        if pend:
            st.dataframe(
                [{"Kind": p["request_kind"], "Requester":
                  f"{p['req_emp_no']} {p['req_name']}",
                  "Level": f"L{p['level']}", "Approver": p["approver_name"],
                  "Approver email": p["approver_email"] or "⚠️ none",
                  "Last reminded": p["last_reminded_at"] or "never"}
                 for p in pend], use_container_width=True)
        st.divider()
        st.subheader("⏰ Reminder emails")
        if not notify.smtp_configured():
            st.warning("SMTP ยังไม่ได้ตั้งค่าใน secrets — อีเมลจะถูกข้าม / "
                       "SMTP is not configured in "
                       ".streamlit/secrets.toml [smtp]; see manual §9.")
        age = st.number_input("เตือนรายการที่ค้างเกิน (ชั่วโมง) / Remind "
                              "items pending longer than (hours)",
                              min_value=1, value=24)
        if st.button("📧 Send reminders now", type="primary"):
            rep = notify.send_pending_reminders(min_age_hours=age)
            if rep:
                for r in rep:
                    st.write(f"- {r['approver']} ({r['email']}): "
                             f"{r['items']} item(s) → {r['result']}")
            else:
                st.info("ไม่มีรายการที่ถึงเกณฑ์เตือน / Nothing due for a "
                        "reminder.")
        st.caption("ตั้งเตือนอัตโนมัติรายวันได้ด้วย GitHub Actions cron — "
                   "ดูคู่มือ §9 / For automatic daily reminders use the "
                   "GitHub Actions cron in scripts/send_reminders.py "
                   "(manual §9).")
