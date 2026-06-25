# pages/K_Attendance.py — Team attendance & abnormalities (§5)
# HR uploads the 3 standard files -> managers see ONLY their reporting
# subtree: working-hours summary, R1-R6 abnormality chase lists, Excel
# export. HR/admin sees the whole company.
import datetime as dt
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme

from lib.auth import require_capability, current_user, has_capability
from lib import employee_db as edb
from lib import attendance_db as att

_theme.inject()
require_capability("attend.view_team")

user = current_user(); me = user["username"]
rec = edb.get_record(emp_no=str(user.get("emp_no") or "")) or {}

_theme.header("เวลาทำงาน — ทีมของฉัน", "Attendance — My team",
              "เวลาทำงาน • OT • การขาดงาน ของทีม จากข้อมูลล่าสุดที่อัปโหลด "
              "(ภาพรวมองค์กรอยู่ที่ แดชบอร์ด KPI)")

is_hr = has_capability("attend.upload")
tabs = st.tabs(["👥 ทีมของฉัน / My team",
                "🚨 ความผิดปกติ / Abnormalities"])

# scope
if is_hr:
    scope = None
    scope_label = "ทั้งบริษัท / whole company (HR)"
elif rec:
    scope = att.subordinate_emp_nos(rec)
    scope_label = f"สายบังคับบัญชาของคุณ ({len(scope)} คน)"
else:
    scope = set()
    scope_label = "ยังไม่ผูกรหัสพนักงาน"

ups = {k: att.active_upload(k) for k in ("timesheet", "leave", "ot")}
have_data = any(ups.values())

def _kpi_cards(cards):
    """ANCA-style infographic cards (in-system, no download needed)."""
    cols = "".join(
        f"""<div style="flex:1;min-width:150px;border-radius:14px;padding:14px 16px;
        color:#fff;background:linear-gradient(135deg,{c1},{c2});
        box-shadow:0 2px 8px rgba(15,23,42,.12)">
        <div style="font-size:11.5px;opacity:.92;font-weight:600">{lb}</div>
        <div style="font-size:26px;font-weight:800;line-height:1.2">{v}</div>
        <div style="font-size:10.5px;opacity:.85">{sub}</div></div>"""
        for lb, v, sub, c1, c2 in cards)
    st.markdown(f'<div style="display:flex;gap:12px;flex-wrap:wrap;'
                f'margin:6px 0 14px">{cols}</div>', unsafe_allow_html=True)


# ===================================================== HR DASHBOARD (ASM)
import pandas as _pd
import altair as alt
# ------------------------------------------------------------------ team
with tabs[0]:
    st.caption(f"ขอบเขต / Scope: **{scope_label}**")
    if not ups["timesheet"]:
        st.info("ยังไม่มีไฟล์เวลาทำงาน — ผู้ดูแลระบบอัปโหลดที่ ผู้ดูแลระบบ → "
                "ข้อมูล & อัปโหลด / No timesheet snapshot yet.")
    else:
        import datetime as _dt
        import calendar as _cal
        u = ups["timesheet"]
        st.caption(f"ข้อมูลช่วง {u['period_from']} → {u['period_to']} • "
                   f"อัปโหลด {str(u['uploaded_at'])[:16]} โดย "
                   f"{u['uploaded_by']}")

        # ---------- period + leave-type filters (req. 2.3) ----------
        _pf = _dt.date.fromisoformat(u["period_from"])
        _pt = _dt.date.fromisoformat(u["period_to"])
        fc1, fc2, fc3 = st.columns([1.1, 1.8, 2.3])
        _mode = fc1.radio("ช่วงเวลา · Period",
                          ["รายเดือน · Monthly", "รายสัปดาห์ · Weekly"],
                          key="mt_mode")
        if _mode.startswith("รายเดือน"):
            _months = []
            _d = _pf.replace(day=1)
            while _d <= _pt:
                _months.append(_d.strftime("%Y-%m"))
                _d = (_d.replace(day=28) + _dt.timedelta(days=4)).replace(day=1)
            _sel = fc2.selectbox("เดือน · Month", _months,
                                 index=len(_months) - 1, key="mt_month")
            _y, _mo = map(int, _sel.split("-"))
            d_from = f"{_y:04d}-{_mo:02d}-01"
            d_to = f"{_y:04d}-{_mo:02d}-{_cal.monthrange(_y, _mo)[1]:02d}"
            _plabel = _sel
        else:
            _weeks = []
            _wk = _pf - _dt.timedelta(days=_pf.weekday())     # back to Monday
            while _wk <= _pt:
                _weeks.append(_wk)
                _wk += _dt.timedelta(days=7)
            _selw = fc2.selectbox(
                "สัปดาห์ · Week", _weeks, index=len(_weeks) - 1,
                format_func=lambda w: f"{w:%d %b}–"
                f"{(w + _dt.timedelta(days=6)):%d %b %Y}", key="mt_week")
            d_from = _selw.isoformat()
            d_to = (_selw + _dt.timedelta(days=6)).isoformat()
            _plabel = f"{_selw:%d %b}–{(_selw + _dt.timedelta(days=6)):%d %b}"
        _lv = fc3.multiselect("ประเภทลาที่นับ · Leave types counted",
                              ["Sick", "Personal", "Annual"],
                              default=["Sick", "Personal", "Annual"],
                              key="mt_lv")
        st.caption(f"แสดงช่วง · Showing **{_plabel}**  ({d_from} → {d_to})")

        summary = att.team_summary(scope, date_from=d_from, date_to=d_to)
        if not summary:
            st.caption("ไม่มีข้อมูลในช่วง/ขอบเขตนี้ / no rows in this window")
        else:
            tot_h = sum(r["Hours"] for r in summary)
            tot_ot = sum(r["OT h"] for r in summary)
            tot_ab = sum(r["Absent"] for r in summary)
            tot_lv = sum(sum(r[t] for t in _lv) for r in summary)
            _kpi_cards([
                ("พนักงานในทีม / Team", len(summary), "คน",
                 "#009ADE", "#0b78ab"),
                ("ชม.งานรวม / Worked", f"{tot_h:,.0f}", "ชั่วโมง",
                 "#715091", "#4d3566"),
                ("ชม. OT รวม / OT", f"{tot_ot:,.0f}",
                 f"เฉลี่ย {tot_ot/max(len(summary),1):,.0f} ชม./คน",
                 "#E31D93", "#a31368"),
                ("ขาดงาน / Absent", f"{tot_ab:g}", "วัน (สะสม)",
                 "#f59e0b", "#b97708"),
                ("วันลารวม / Leave", f"{tot_lv:g}",
                 "+".join(_lv) or "—", "#16a34a", "#0e7a36")])

            # ---- top rankings: sortable tables with values (item 11) ----
            rk = att.rankings(scope, date_from=d_from, date_to=d_to)
            import pandas as _pd
            _rcols = st.columns(3)
            for _col, _key, _ttl, _unit in (
                (_rcols[0], "ot", "🏆 OT สูงสุด / Top OT", "OT (ชม.)"),
                (_rcols[1], "late", "⏰ สายสะสม / Top late", "นาที · min"),
                (_rcols[2], "absent", "🚫 ขาดงาน / Top absence",
                 "วัน · days")):
                _col.markdown(f"**{_ttl}**")
                _d = rk[_key]
                if _d:
                    _col.dataframe(
                        _pd.DataFrame([{"#": i + 1, "ชื่อ · Name": n, _unit: v}
                                       for i, (n, v) in enumerate(_d.items())]),
                        use_container_width=True, hide_index=True)
                    _col.caption("คลิกหัวคอลัมน์เพื่อจัดเรียง (มาก→น้อย) · click a "
                                 "column header to re-sort")
                else:
                    _col.caption("— ไม่มีข้อมูล · no data")

            # ---- per-person table (filter-aware; hides unticked leave cols) ----
            with st.expander("📋 ตารางรายคน / Per-person table", expanded=True):
                _hide = [t for t in ("Sick", "Personal", "Annual")
                         if t not in _lv]
                _disp = [{k: v for k, v in r.items() if k not in _hide}
                         for r in summary]
                st.dataframe(_disp, use_container_width=True, height=380)

            # ---- consecutive no-show watchdog (req. 2.6 — your team only) ----
            st.markdown("**🚨 ขาดงานต่อเนื่อง / Consecutive no-show "
                        "(ทีมของคุณ · your team)**")
            st.caption("นับเฉพาะวันทำงาน (วันหยุด/วันลาไม่ตัดความต่อเนื่อง) • "
                       "ครบ 3 วัน = เงื่อนไขเลิกจ้างตาม พ.ร.บ.คุ้มครองแรงงาน "
                       "พ.ศ.2541 ม.119(5).")
            _runs = att.noshow_runs(scope, min_days=2)
            _open = [r for r in _runs if r["open"]]
            _hist = [r for r in _runs if not r["open"] and r["days"] >= 3]
            k1, k2 = st.columns(2)
            k1.metric("⚠️ กำลังขาดงานอยู่ (≥2 วัน)", len(_open))
            k2.metric("ประวัติขาด ≥3 วัน (ในช่วงไฟล์)", len(_hist))
            if _open:
                st.dataframe([{
                    "Emp": r["emp_no"], "ชื่อ / Name": r["emp_name"],
                    "ตั้งแต่ / From": r["start"], "ถึง / To": r["end"],
                    "วันที่ขาด / Days": r["days"],
                    "สถานะ / Status": ("🔴 ครบ ม.119(5)" if r["days"] >= 3
                                       else "⚠️ เตือนวันที่ 2")}
                    for r in _open], use_container_width=True)
                st.caption("ดำเนินการเลิกจ้าง/ยื่นแทนได้ที่หน้า อนุมัติแทน · "
                           "process via Submit-on-behalf.")
            elif not _hist:
                st.success("ไม่พบการขาดงานต่อเนื่องในทีม · none in your team.")
            if _hist:
                with st.expander(f"ประวัติ (ปิดแล้ว) — {len(_hist)} ราย"):
                    st.dataframe([{
                        "Emp": r["emp_no"], "ชื่อ / Name": r["emp_name"],
                        "ตั้งแต่ / From": r["start"], "ถึง / To": r["end"],
                        "วัน / Days": r["days"]} for r in _hist],
                        use_container_width=True)

# ------------------------------------------------------------------ abnormal
with tabs[1]:
    if not have_data:
        st.info("ต้องอัปโหลดไฟล์ก่อน / upload the files first")
    else:
        run_d = (ups["timesheet"] or {}).get("period_to")
        abn = att.abnormalities(scope, run_date=run_d)
        # visual overview: abnormality mix + by department
        mix = {"มาสาย/กลับก่อน": len(abn["late_early"]),
               "ขาดงาน": len(abn["noshow"]),
               "ใบลารออนุมัติ": len(abn["leave_pending"]),
               "OTไม่ยื่นใบ": len(abn["ot_not_submitted"]),
               "ใบOTรออนุมัติ": len(abn["ot_pending"]),
               "OTซ้ำซ้อน": len(abn["ot_duplicate"])}
        c1, c2 = st.columns(2)
        c1.markdown("**ภาพรวมความผิดปกติ / Abnormality mix**")
        c1.bar_chart(mix, horizontal=True)
        from collections import Counter as _C
        by_emp_dept = {str(r.get("emp_no")): (r.get("dept_location") or "—")
                       for r in edb.list_records("active")}
        dept_cnt = _C()
        for k in ("late_early", "noshow", "ot_not_submitted",
                  "ot_duplicate"):
            for row in abn[k]:
                dept_cnt[by_emp_dept.get(str(row.get("Emp")), "—")] += 1
        if dept_cnt:
            c2.markdown("**ตามแผนก / By department**")
            c2.bar_chart(dict(dept_cnt.most_common(12)), horizontal=True)
        labels = [("late_early", "🕐 มาสาย/กลับก่อน (R1)"),
                  ("noshow", "🔴 ขาดงาน/ไม่มีใบลา (R2)"),
                  ("leave_pending", "🟡 ใบลารออนุมัติ (R3)"),
                  ("ot_not_submitted", "🟠 ทำ OT แต่ไม่ยื่นใบ (R4)"),
                  ("ot_pending", "🟡 ใบ OT รออนุมัติ (R5)"),
                  ("ot_duplicate", "🔁 ใบ OT ซ้ำซ้อน (R6)")]
        c = st.columns(6)
        for col, (k, lb) in zip(c, labels):
            col.metric(lb.split(" ")[1].split("(")[0][:12], len(abn[k]))
        for k, lb in labels:
            with st.expander(f"{lb} — {len(abn[k])} รายการ",
                             expanded=(k == "noshow" and bool(abn[k]))):
                if abn[k]:
                    st.dataframe(abn[k], use_container_width=True)
                else:
                    st.caption("ไม่มี / none 🎉")
        summary = att.team_summary(scope)
        st.download_button(
            "⬇️ ดาวน์โหลดรายงาน Excel / Download Excel",
            att.export_xlsx(abn, summary),
            file_name=f"Attendance_abnormality_{dt.date.today()}.xlsx")
        st.caption("หมายเหตุ: วันที่ดึงข้อมูล (วันสุดท้ายของไฟล์) ไม่ถูกนับ "
                   "ขาดงาน เพื่อกันการแจ้งเตือนผิดระหว่างกะยังไม่จบ / The "
                   "pull date is excluded from no-show to avoid mid-shift "
                   "false positives.")

