# Employee drill-down — Management module (req. 2.4)
# Per-subordinate face-scan review: pick an employee + period (weekly/monthly),
# see summary stats (work hrs / total hrs / absent / leave hrs / late) plus the
# daily series and the leave/OT requests in that window.
import datetime as dt
import calendar as cal
import streamlit as st

from lib import theme as _theme
from lib.auth import require_capability, current_user, has_capability
from lib import employee_db as edb
from lib import attendance_db as att

_theme.inject()
require_capability("attend.view_team")
user = current_user()
rec = edb.get_record(emp_no=str(user.get("emp_no") or "")) or {}
is_hr = has_capability("attend.upload")

_theme.header("เจาะรายคน", "Employee drill-down",
              "ทบทวนบันทึกเวลา (face-scan) ของผู้ใต้บังคับบัญชา ตามรายสัปดาห์/รายเดือน")

if is_hr:
    scope = None
    scope_label = "ทั้งบริษัท / whole company (HR)"
elif rec.get("emp_no"):
    scope = att.subordinate_emp_nos(rec)
    scope_label = f"สายบังคับบัญชาของคุณ ({len(scope)} คน)"
else:
    scope = set()
    scope_label = "ยังไม่ผูกรหัสพนักงาน / no emp_no linked"
st.caption(f"ขอบเขต / Scope: **{scope_label}**")

up = att.active_upload("timesheet")
if not up:
    st.info("ยังไม่มีไฟล์เวลาทำงาน — ผู้ดูแลระบบอัปโหลดที่ **ผู้ดูแลระบบ → "
            "ข้อมูล & อัปโหลด** / No timesheet snapshot yet.")
    st.stop()

summary = att.team_summary(scope)
if not summary:
    st.caption("ไม่มีพนักงานในขอบเขตนี้ / no employees in scope")
    st.stop()

# -------------------------- employee + period filter -----------------------
c0, c1, c2 = st.columns([2.4, 1.1, 1.8])
opts = {f"{r['Emp']} • {r['Name']}": r["Emp"] for r in summary}
pick = c0.selectbox("เลือกพนักงาน (พิมพ์ชื่อ/รหัสเพื่อค้นหา) · Employee "
                    "(type name or ID to search)", list(opts), key="dd_emp")
_pf = dt.date.fromisoformat(up["period_from"])
_pt = dt.date.fromisoformat(up["period_to"])
mode = c1.radio("ช่วง · Period", ["รายเดือน · Monthly", "รายสัปดาห์ · Weekly"],
                key="dd_mode")
if mode.startswith("รายเดือน"):
    months = []
    d = _pf.replace(day=1)
    while d <= _pt:
        months.append(d.strftime("%Y-%m"))
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    sel = c2.selectbox("เดือน · Month", months, index=len(months) - 1,
                       key="dd_month")
    y, mo = map(int, sel.split("-"))
    d_from = f"{y:04d}-{mo:02d}-01"
    d_to = f"{y:04d}-{mo:02d}-{cal.monthrange(y, mo)[1]:02d}"
    plabel = sel
else:
    weeks = []
    wk = _pf - dt.timedelta(days=_pf.weekday())          # back to Monday
    while wk <= _pt:
        weeks.append(wk)
        wk += dt.timedelta(days=7)
    selw = c2.selectbox(
        "สัปดาห์ · Week", weeks, index=len(weeks) - 1,
        format_func=lambda w: f"{w:%d %b}–"
        f"{(w + dt.timedelta(days=6)):%d %b %Y}", key="dd_week")
    d_from = selw.isoformat()
    d_to = (selw + dt.timedelta(days=6)).isoformat()
    plabel = f"{selw:%d %b}–{(selw + dt.timedelta(days=6)):%d %b}"

emp_no = opts[pick]
ts_e, daily, leaves, ots_e = att.employee_daily(emp_no, date_from=d_from,
                                                date_to=d_to)
st.divider()
st.markdown(f"### 🔍 {pick}")
st.caption(f"ช่วง · Period {plabel} ({d_from} → {d_to})")

# -------------------- selected person: summary stats (TOP) -----------------
STD = 8.0
work_h = sum(r["normal_hours"] or 0 for r in ts_e)
ot_h = sum(sum(r[k] or 0 for k in ("ot1", "ot15", "ot2", "ot3"))
           for r in ts_e)
absent_d = sum(r["absent"] or 0 for r in ts_e)
leave_d = sum((r["sick"] or 0) + (r["personal"] or 0) + (r["annual"] or 0)
              for r in ts_e)
late_m = sum(r["late_min"] or 0 for r in ts_e)
m = st.columns(5)
m[0].metric("ชม.งานรวม / Worked", f"{work_h:,.1f}")
m[1].metric("ชม.รวม / Total hrs", f"{work_h + ot_h:,.1f}", f"+OT {ot_h:,.1f}")
m[2].metric("ขาดงาน / Absent", f"{absent_d:g}", "วัน")
m[3].metric("ชม.การลา / Leave hrs", f"{leave_d * STD:,.1f}",
            f"{leave_d:g} วัน × {STD:g}")
m[4].metric("มาสาย / Late", f"{late_m:,.0f}", "นาที")

# -------------------- selected person: daily scan table --------------------
import pandas as _pd
_pdet = []
for r in ts_e:
    _pdet.append({
        "วันที่ · Date": r.get("work_date"),
        "กะ · Shift": r.get("shift_code") or "—",
        "สแกนเข้า-ออก · Scan in/out": r.get("scans") or "—",
        "ชม.งาน · Hrs": r.get("normal_hours") or 0,
        "OT": round(sum(r.get(k) or 0 for k in ("ot1", "ot15", "ot2", "ot3")),
                    2),
        "สาย · Late(m)": r.get("late_min") or 0,
        "ขาด · Absent": r.get("absent") or 0,
    })
if _pdet:
    st.markdown("**🗓️ บันทึกรายวัน (สแกนเข้า/ออก) · Daily record**")
    st.dataframe(_pd.DataFrame(_pdet), use_container_width=True,
                 hide_index=True, height=300)
else:
    st.caption("ไม่มีบันทึกเวลาในช่วงนี้ · no scans in this window.")

# -------------------- selected person: leave & OT requests -----------------
cc1, cc2 = st.columns(2)
with cc1:
    st.markdown(f"**ใบลา / Leave ({len(leaves)})**")
    if leaves:
        st.dataframe([{"Doc": l["doc_no"], "Type": l["req_type"],
                       "From": l["date_start"], "Days": l["days"],
                       "Status": l["status"]} for l in leaves],
                     use_container_width=True, height=240)
with cc2:
    st.markdown(f"**ใบ OT / OT ({len(ots_e)})**")
    if ots_e:
        st.dataframe([{"Doc": o["doc_no"], "Date": o["date_start"],
                       "Time": o["time_range"], "Hrs": o["hours"],
                       "Status": o["status"]} for o in ots_e],
                     use_container_width=True, height=240)

# ======================= whole-team attendance sheet =======================
st.divider()
with st.expander("📋 ตารางเวลาทั้งทีม (ทุกคนในสายงาน) · Whole-team attendance "
                 "sheet — คลิกเพื่อเปิด", expanded=False):
    import io as _io
    _tsum = att.team_summary(scope, d_from, d_to)
    if not _tsum:
        st.caption("ไม่มีข้อมูลในช่วงนี้ · no attendance in this window.")
    else:
        st.markdown(f"**สรุปรายคน · Per-person summary** — {plabel}")
        _sdf = _pd.DataFrame(_tsum)
        st.dataframe(_sdf, use_container_width=True, hide_index=True)
        _det = []
        for r in att.timesheet_rows(scope):
            if d_from <= r["work_date"] <= d_to:
                _det.append({
                    "รหัส · Emp": r["emp_no"], "ชื่อ · Name": r["emp_name"],
                    "วันที่ · Date": r["work_date"],
                    "กะ · Shift": r.get("shift_code") or "—",
                    "สแกนเข้า-ออก · Scan in/out": r.get("scans") or "—",
                    "ชม.งาน · Hrs": r.get("normal_hours") or 0,
                    "OT": round(sum(r.get(k) or 0
                                    for k in ("ot1", "ot15", "ot2", "ot3")), 2),
                    "สาย · Late(m)": r.get("late_min") or 0,
                    "ขาด · Absent": r.get("absent") or 0,
                })
        _det.sort(key=lambda x: (x["รหัส · Emp"], x["วันที่ · Date"]))
        st.markdown("**รายวัน: สแกนเข้า/ออก · กะ · สาย · ขาด · OT — Daily scan "
                    f"sheet** ({len(_det)} แถว)")
        if _det:
            st.dataframe(_pd.DataFrame(_det), use_container_width=True,
                         hide_index=True, height=360)
        _buf = _io.BytesIO()
        with _pd.ExcelWriter(_buf, engine="openpyxl") as _xw:
            _sdf.to_excel(_xw, sheet_name="Summary", index=False)
            if _det:
                _pd.DataFrame(_det).to_excel(_xw, sheet_name="Daily",
                                             index=False)
        _buf.seek(0)
        _dc = st.columns(2)
        _dc[0].download_button(
            "📊 ดาวน์โหลด Excel · Download Excel", _buf.getvalue(),
            file_name=f"team_attendance_{d_from}_{d_to}.xlsx",
            mime=("application/vnd.openxmlformats-officedocument."
                  "spreadsheetml.sheet"), use_container_width=True)
        if _det:
            _dc[1].download_button(
                "📄 CSV (รายวัน) · Daily CSV",
                _pd.DataFrame(_det).to_csv(index=False).encode("utf-8-sig"),
                file_name=f"team_attendance_daily_{d_from}_{d_to}.csv",
                mime="text/csv", use_container_width=True)
