# pages/L_Resignation.py — Resignation & no-show watchdog (§6)
# self-submit -> full L1..L3 chain (email+LINE) | manager delegate-submit
# for no-show subordinates | watchdog: day-2 alert, day-3 escalation per
# LPA s.119(5) | HR checklist -> record flips to resigned + printable
# bilingual notice.
import datetime as dt
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme
import streamlit.components.v1 as components

from lib.auth import require_capability, current_user, has_capability
from lib import employee_db as edb
from lib import approval_db as adb
from lib import attendance_db as att
from lib import resign_db as rdb
from lib import notify

_theme.inject()
require_capability("resign.submit")

user = current_user(); me = user["username"]
rec = edb.get_record(emp_no=str(user.get("emp_no") or "")) or {}

st.title("📤 การลาออก / Resignation")

is_hr = has_capability("resign.admin")
tabs = st.tabs(["✍️ ยื่นลาออก / Resign", "✅ อนุมัติ / Approvals",
                "🗂️ HR Admin"])


def _print(html, key):
    if st.button("🖨️ พิมพ์หนังสือ / Print notice", key=key):
        components.html(
            f"<script>var w=window.open('','_blank');"
            f"w.document.write({html!r});w.document.close();</script>",
            height=0)


def _submit(requester, subject, kind, last_day, reason,
            noshow_from=None, noshow_days=None):
    rid, doc = rdb.create(requester, subject, kind, last_day, reason, me,
                          noshow_from, noshow_days)
    # chain of the SUBJECT's reporting line (full 3 levels like leave)
    chain = adb.resolve_chain(subject)
    # delegate case: skip the requester themselves if they are L1
    chain = [(l, r) for (l, r) in chain
             if str(r.get("emp_no")) != str(requester.get("emp_no"))] \
        if kind == "delegate" else chain
    chain = [(i + 1, r) for i, (_, r) in enumerate(chain)]
    r0 = rdb.get(rid)
    r0["summary"] = (f"{doc} • {subject.get('emp_name_en')} • "
                     f"วันสุดท้าย {last_day}")
    r0["doc_no"] = doc
    first = adb.open_approvals("resign", rid, subject, chain=chain or None)
    if first:
        notify.notify_approver("resign", r0, first)
        return doc, first["approver_name"]
    return doc, None

# ------------------------------------------------------------------ self
with tabs[0]:
    if not rec:
        st.warning("บัญชียังไม่ผูกรหัสพนักงาน / account not linked")
    else:
        st.caption("ยื่นลาออกด้วยตนเอง — เข้าสายอนุมัติ 3 ระดับเหมือนใบลา "
                   "พร้อมแจ้งเตือนอีเมล/LINE ทุกขั้น แนะนำแจ้งล่วงหน้าอย่าง"
                   "น้อย 30 วันตามระเบียบบริษัท")
        with st.form("self_resign"):
            last_day = st.date_input("วันทำงานวันสุดท้าย / Last working day",
                                     dt.date.today() + dt.timedelta(days=30))
            reason = st.text_area("เหตุผล / Reason *")
            ok = st.form_submit_button("📨 ยื่นใบลาออก / Submit",
                                       type="primary")
        if ok:
            if not reason.strip():
                st.error("กรุณาระบุเหตุผล")
            else:
                doc, ap = _submit(rec, rec, "self", last_day, reason)
                st.success(f"ยื่นแล้ว **{doc}**"
                           + (f" → รออนุมัติ {ap}" if ap else ""))
        mine = rdb.list_resignations(subject_emp_no=rec.get("emp_no"))
        for r in mine[:5]:
            st.write(f"- **{r['doc_no']}** วันสุดท้าย "
                     f"{r['last_working_day']} — **{r['status']}**")

# ------------------------------------------------------------------ approvals
with tabs[1]:
    q = adb.my_queue("resign", rec.get("emp_no")) if rec else []
    if not q:
        st.caption("ไม่มีรายการรออนุมัติ / nothing waiting")
    for r in q:
        kind_lb = ("เลิกจ้าง (no-show)" if r["kind"] == "delegate"
                   else "ลาออก")
        st.markdown(f"**[L{r['my_level']}] {r['doc_no']}** ({kind_lb}) — "
                    f"{r['subject_name']} ({r['department']})<br>"
                    f"วันสุดท้าย/มีผล: {r['last_working_day']}<br>"
                    f"เหตุผล: {r['reason']}", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 1, 3])
        note = c3.text_input("Note", key=f"rn{r['approval_id']}",
                             label_visibility="collapsed")
        if c1.button("✅", key=f"ra{r['approval_id']}"):
            res = adb.act("resign", r["approval_id"], True, me, note)
            if res["final"]:
                subj = edb.get_record(emp_no=r["subject_emp_no"])
                notify.notify_requester(
                    "resign", {"summary": r["doc_no"]},
                    (subj or {}).get("personal_email"), "approved", note,
                    requester_emp_no=r["subject_emp_no"])
            st.rerun()
        if c2.button("❌", key=f"rr{r['approval_id']}"):
            adb.act("resign", r["approval_id"], False, me, note)
            st.rerun()

# ------------------------------------------------------------------ HR admin
with tabs[2]:
    if not is_hr:
        st.info("Requires resign.admin")
    else:
        st.subheader("เช็คลิสต์ปิดเรื่อง / Completion checklist")
        for r in rdb.list_resignations(status="approved"):
            with st.container(border=True):
                st.markdown(f"**{r['doc_no']}** {r['subject_name']} "
                            f"({r['department']}) • วันสุดท้าย "
                            f"{r['last_working_day']} • "
                            f"{'เลิกจ้าง no-show' if r['kind']=='delegate' else 'ลาออกเอง'}")
                c1, c2, c3, c4, c5 = st.columns(5)
                a = c1.checkbox("คืนทรัพย์สิน", bool(r["chk_assets"]),
                                key=f"ka{r['id']}")
                b = c2.checkbox("แจ้งออก สปส.", bool(r["chk_sso"]),
                                key=f"kb{r['id']}")
                c = c3.checkbox("เงินงวดสุดท้าย", bool(r["chk_finalpay"]),
                                key=f"kc{r['id']}")
                if (a, b, c) != (bool(r["chk_assets"]), bool(r["chk_sso"]),
                                 bool(r["chk_finalpay"])):
                    rdb.set_checklist(r["id"], a, b, c, me)
                    st.rerun()
                if c4.button("✅ ปิดเรื่อง", key=f"kd{r['id']}"):
                    ok, msg = rdb.complete(r["id"], me)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
                with c5:
                    _print(rdb.notice_html(r), f"np{r['id']}")
        st.subheader("ปิดเรื่องแล้ว / Completed")
        for r in rdb.list_resignations(status="completed")[:10]:
            c1, c2 = st.columns([4, 1])
            c1.write(f"✅ **{r['doc_no']}** {r['subject_name']} — มีผล "
                     f"{r['last_working_day']}")
            with c2:
                _print(rdb.notice_html(r), f"npc{r['id']}")
