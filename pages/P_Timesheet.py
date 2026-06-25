# pages/P_Timesheet.py — employee self-service timesheet (req. 9, 5 panels)
# ============================================================================
# 1) Face-scan records (+ a time-edit / time-record request, printable)
# 2) Pending OT          (your in-app OT awaiting approval)
# 3) Unsubmitted OT      (face-scan shows OT you have not yet submitted)
# 4) Pending leave       (your in-app leave awaiting approval)
# 5) Absent vs leave     (absent days reconciled against approved leave)
# Own data only — scoped to the signed-in user's emp_no.
# ============================================================================
import datetime as dt
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme
from lib.auth import require_capability, current_user
from lib import payroll_cycle as pc
from lib import employee_db as edb
from lib import attendance_db as adb_att
from lib import approval_db as adb
from lib import notify
from lib import print_docs
from lib import ot_rules as otr

require_capability("self.view_profile")
_theme.inject()
st.title("🗓️ ไทม์ชีทของฉัน / My Timesheet")

u = current_user() or {}
emp_no = u.get("emp_no")
me = u.get("username", "system")
rec = edb.get_record(emp_no=emp_no) if emp_no else None
if not emp_no or not rec:
    st.warning("บัญชีของคุณยังไม่ได้ผูกกับรหัสพนักงาน — โปรดให้ผู้ดูแลระบบผูกบัญชีใน "
               "โมดูล Admin ก่อน · Your account isn't linked to an employee "
               "number yet; ask an admin to link it in the Admin module.")
    st.stop()

# ---------------------------------------------------------------- cycle
cycles = pc.recent_cycles(12)
idx = st.selectbox("รอบเงินเดือน / Payroll cycle", list(range(len(cycles))),
                   format_func=lambda i: pc.cycle_label(*cycles[i]))
year, month = cycles[idx]
w = pc.payroll_windows(year, month)
s0, s1 = w["scan_start"].isoformat(), w["scan_end"].isoformat()
st.caption(f"หน้าต่างสแกนหน้า / Face-scan window: {w['scan_start']:%d %b %Y} → "
           f"{w['scan_end']:%d %b %Y}")


# ---------------------------------------------------------------- helpers
def _is_pending(s):
    s = str(s or "").lower()
    return s.startswith("pending") or ("รอ" in s)


def _is_approved(s):
    s = str(s or "")
    return ("อนุมัติ" in s and "ไม่อนุมัติ" not in s) or \
        str(s).lower().startswith("approve")


def _approved_leave_days():
    """Set of ISO dates covered by the user's APPROVED leave (in-app)."""
    out = set()
    for r in edb.my_requests("leave", rec["id"], limit=300):
        if not _is_approved(r.get("status")):
            continue
        try:
            d = dt.date.fromisoformat(str(r["date_from"])[:10])
            d1 = dt.date.fromisoformat(str(r["date_to"])[:10])
        except Exception:
            continue
        while d <= d1:
            out.add(d.isoformat())
            d += dt.timedelta(days=1)
    return out


def _in_app_ot_dates():
    out = set()
    for r in edb.my_requests("ot", rec["id"], limit=300):
        if "reject" in str(r.get("status", "")).lower() or \
                "ไม่อนุมัติ" in str(r.get("status", "")):
            continue
        out.add(str(r.get("ot_date", ""))[:10])
    return out


def _emit_print(html, name):
    pdf = print_docs.html_to_pdf(html)
    if pdf:
        st.download_button("⬇️ ดาวน์โหลด PDF / Download PDF", pdf,
                           file_name=name + ".pdf", mime="application/pdf",
                           key="dl_" + name, use_container_width=True)
    else:
        st.download_button("⬇️ ดาวน์โหลด HTML (Ctrl+P → PDF)",
                           html.encode("utf-8"), file_name=name + ".html",
                           mime="text/html", key="dlh_" + name,
                           use_container_width=True)


# face-scan rows for this person within the scan window
try:
    _ts_all = adb_att.timesheet_rows({str(emp_no)})
except Exception:
    _ts_all = []
ts = sorted([r for r in _ts_all if s0 <= str(r.get("work_date", "")) <= s1],
            key=lambda r: r.get("work_date", ""))
_have_scan = bool(_ts_all)

_TRAIL = {"approved": "✅", "rejected": "❌", "pending": "⏳",
          "waiting": "·", "skipped": "—"}


def _trail(kind, rid):
    steps = adb.rows_for(kind, rid)
    return " → ".join(f"L{s['level']} {s['approver_name']} "
                      f"{_TRAIL.get(s['status'], s['status'])}"
                      for s in steps) or "อนุมัติอัตโนมัติ"


# ================================================ Panel 1: face-scan records
st.markdown("### 🕘 1) บันทึกสแกนหน้า / Face-scan records")
if not _have_scan:
    st.info("ยังไม่มีไฟล์สแกนหน้าที่อัปโหลด — ผู้ดูแลระบบอัปโหลดที่ Admin → ข้อมูล & "
            "อัปโหลด · No face-scan file uploaded yet (Admin → Data & Uploads).")
elif not ts:
    st.caption("ไม่มีบันทึกในรอบนี้ · No records in this cycle window.")
else:
    st.dataframe(
        [{"วันที่ · Date": r.get("work_date"),
          "กะ · Shift": r.get("shift_code") or "",
          "สแกน · Scans": r.get("scans") or "",
          "ชม.งาน · Work h": r.get("normal_hours") or 0,
          "สาย · Late m": r.get("late_min") or 0,
          "ออกก่อน · Early m": r.get("early_min") or 0,
          "OT (h)": round(sum(r.get(k) or 0
                              for k in ("ot1", "ot15", "ot2", "ot3")), 2),
          "ขาด · Absent": "✔" if (r.get("absent") or 0) > 0 else ""}
         for r in ts], use_container_width=True, hide_index=True)

# --- time-edit / time-record request (printable) ---
with st.expander("✏️ ขอแก้ไข / บันทึกเวลาทำงาน · Request a time edit / record"):
    st.caption("ใช้เมื่อสแกนผิดพลาด ลืมสแกน หรือเวลาที่บันทึกไม่ถูกต้อง — "
               "ส่งให้ผู้บังคับบัญชาอนุมัติ และพิมพ์เป็นแบบฟอร์มได้ · For a missed "
               "or wrong scan; routed for approval and printable.")
    _date_opts = [r["work_date"] for r in ts] or [dt.date.today().isoformat()]
    c1, c2 = st.columns(2)
    te_date = c1.selectbox("วันที่ทำงาน / Work date", _date_opts, key="te_date")
    te_shift = c2.text_input("รหัสกะ / Shift",
                             value=next((r.get("shift_code") or "" for r in ts
                                         if r["work_date"] == te_date), ""),
                             key="te_shift")
    _orig = next((r.get("scans") or "" for r in ts
                  if r["work_date"] == te_date), "")
    st.caption(f"เวลาที่ระบบบันทึกไว้ · Currently recorded: **{_orig or '—'}**")
    te_type = st.radio("ประเภท / Type",
                       ["edit", "record"], horizontal=True,
                       format_func=lambda k: {"edit": "ขอแก้ไขเวลา · Edit time",
                                              "record": "ขอบันทึกลงเวลา · "
                                              "Record time"}[k], key="te_type")
    c3, c4 = st.columns(2)
    te_in = c3.time_input("เวลาเข้าที่ขอ / Time in", dt.time(7, 45),
                          step=dt.timedelta(minutes=5), key="te_in")
    te_out = c4.time_input("เวลาออกที่ขอ / Time out", dt.time(16, 25),
                           step=dt.timedelta(minutes=5), key="te_out")
    te_reason = st.text_area("เหตุผล / Reason", height=68, key="te_reason")
    if st.button("ส่งคำขอแก้ไขเวลา / Submit", type="primary", key="te_submit"):
        if not te_reason.strip():
            st.error("กรุณาระบุเหตุผล / Please give a reason.")
        else:
            nm = (adb._clean_name(rec.get("emp_name_en"))
                  or rec.get("emp_name_th") or me)
            edb.submit_time_edit(rec["id"], rec["emp_no"], nm, te_date,
                                 te_shift, te_type, _orig,
                                 te_in.strftime("%H:%M"),
                                 te_out.strftime("%H:%M"), te_reason, me)
            req = edb.my_requests("timeedit", rec["id"], limit=1)[0]
            first = adb.open_approvals("timeedit", req["id"], rec)
            if first:
                try:
                    _, msg = notify.notify_approver("timeedit", req, first)
                except Exception:
                    msg = "—"
                st.success(f"ส่งคำขอแล้ว → รอ L1: {first['approver_name']} • {msg}")
            else:
                st.success("ส่งคำขอแล้ว (ไม่มีสายอนุมัติ → อนุมัติอัตโนมัติ)")
            st.rerun()

    _mine = edb.my_requests("timeedit", rec["id"], limit=50)
    if _mine:
        st.markdown("**คำขอแก้ไขเวลาของฉัน · My time-edit requests**")
        for r in _mine:
            st.markdown(
                f"- {r['work_date']} · {r.get('req_time_in') or '—'}–"
                f"{r.get('req_time_out') or '—'} — "
                f"{r['status']}  <span style='color:#888;font-size:12px'>"
                f"{_trail('timeedit', r['id'])}</span>",
                unsafe_allow_html=True)
            if st.button("🖨️ พิมพ์แบบแก้ไขเวลา / Print", key=f"prte{r['id']}"):
                _emit_print(print_docs.render_time_edit(rec, r),
                            f"TimeEdit_{r['id']}")

st.divider()

# ================================================ Panel 2: pending OT
st.markdown("### ⏰ 2) โอทีที่รออนุมัติ / Pending OT")
_ot = [r for r in edb.my_requests("ot", rec["id"], limit=200)
       if _is_pending(r.get("status"))]
if not _ot:
    st.caption("ไม่มีโอทีที่รออนุมัติ · No pending OT.")
else:
    st.dataframe(
        [{"วันที่ · Date": r.get("ot_date"),
          "เวลา · Time": f"{r.get('time_from','')}–{r.get('time_to','')}",
          "ชม. · Hrs": r.get("hours"),
          "ประเภท · Type": otr.ot_type_label(r["ot_type"])
          if r.get("ot_type") else f"×{r.get('rate','')}",
          "WO": r.get("work_order_no") or "",
          "สถานะ · Status": r.get("status")} for r in _ot],
        use_container_width=True, hide_index=True)

# ================================================ Panel 3: unsubmitted OT
st.markdown("### 🚩 3) โอทีที่ตรวจพบแต่ยังไม่ได้ยื่น / OT detected, not submitted")
st.caption("ระบบสแกนหน้าพบว่าคุณทำงานล่วงเวลาในวันเหล่านี้ แต่ยังไม่มีคำขอ OT ในระบบ "
           "— กรุณายื่นที่เมนู ลา/โอที · The face-scan shows OT on these days with "
           "no OT request yet — please submit one in Leave & OT.")
_app_ot = _in_app_ot_dates()
_missing = []
for r in ts:
    done = round(sum(r.get(k) or 0 for k in ("ot1", "ot15", "ot2", "ot3")), 2)
    if done > 0 and str(r.get("work_date", ""))[:10] not in _app_ot:
        _missing.append({"วันที่ · Date": r.get("work_date"),
                         "กะ · Shift": r.get("shift_code") or "",
                         "สแกน · Scans": r.get("scans") or "",
                         "OT ที่ตรวจพบ · Detected (h)": done})
if not _have_scan:
    st.caption("— (ต้องมีไฟล์สแกนหน้าก่อน · needs a face-scan upload)")
elif not _missing:
    st.success("ไม่มีโอทีค้างยื่นในรอบนี้ · No unsubmitted OT this cycle. 👍")
else:
    st.dataframe(_missing, use_container_width=True, hide_index=True)

# ================================================ Panel 4: pending leave
st.markdown("### 🌴 4) การลาที่รออนุมัติ / Pending leave")
_lv = [r for r in edb.my_requests("leave", rec["id"], limit=200)
       if _is_pending(r.get("status"))]
if not _lv:
    st.caption("ไม่มีการลาที่รออนุมัติ · No pending leave.")
else:
    st.dataframe(
        [{"ประเภท · Type": r.get("leave_type"),
          "ตั้งแต่ · From": r.get("date_from"), "ถึง · To": r.get("date_to"),
          "วัน · Days": r.get("days"),
          "สถานะ · Status": r.get("status")} for r in _lv],
        use_container_width=True, hide_index=True)

# ================================================ Panel 5: absent vs leave
st.markdown("### 📛 5) วันขาดงาน (เทียบกับใบลา) / Absent — reconciled vs leave")
_appr_days = _approved_leave_days()
try:
    _appr_days |= {d for (e, d) in adb_att._approved_leave_dates({str(emp_no)})}
except Exception:
    pass
_absent_rows = [r for r in ts if (r.get("absent") or 0) > 0]
if not _have_scan:
    st.caption("— (ต้องมีไฟล์สแกนหน้าก่อน · needs a face-scan upload)")
elif not _absent_rows:
    st.success("ไม่มีวันขาดงานในรอบนี้ · No absent days this cycle. 👍")
else:
    st.dataframe(
        [{"วันที่ · Date": r.get("work_date"),
          "กะ · Shift": r.get("shift_code") or "",
          "สถานะ · Status": ("✅ มีใบลาอนุมัติแล้ว · covered by approved leave"
                             if str(r.get("work_date", "")) in _appr_days
                             else "❌ ขาดงานไม่มีใบลา · unexcused absence")}
         for r in _absent_rows], use_container_width=True, hide_index=True)
