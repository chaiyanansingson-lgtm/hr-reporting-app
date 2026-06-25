# pages/N_OT_Report.py
# ============================================================================
# OT-by-department comparison report (§8).
#   - Managers (salary.ot_report) compare any two saved months: summary cards,
#     interactive grouped bar chart, comparison table, and a downloadable
#     ANCA infographic (PNG / PDF) like the level-meeting deck.
#   - Uploading raw salary data, viewing per-employee OT detail, and
#     downloading the original file are STRICTLY Super-Admin only
#     (gated on employee.view_salary).
# ============================================================================
import datetime as dt

import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme

from lib.auth import require_capability, has_capability, current_user
from lib import ot_salary_db as osd
from lib import ot_report_render as orr

_theme.inject()
require_capability("salary.ot_report")

is_super = has_capability("employee.view_salary")        # raw salary gate
me = current_user()
actor = (me or {}).get("username", "system")

st.title("💰 รายงานเปรียบเทียบ OT ตามแผนก / OT by Department")
st.caption("เปรียบเทียบค่าล่วงเวลา (OT จ่ายจริง, บาท) ระหว่างสองเดือน แยกตาม "
           "18 แผนก · Compare overtime paid (THB) between two months across "
           "the 18 expanded departments.")

# ============================================================ UPLOAD (super)
if is_super:
    with st.expander("📤 อัปโหลดข้อมูลเงินเดือน (เฉพาะ Super Admin) / "
                     "Upload monthly salary data (Super Admin only)",
                     expanded=False):
        st.caption("ไฟล์รายงานเงินเดือนรายเดือน (.csv / .xls / .xlsx) — ระบบจะ"
                   "อ่านเฉพาะคอลัมน์ OT และสรุปยอดตามแผนก ข้อมูลรายบุคคลจะถูกเก็บ"
                   "อย่างปลอดภัยและเห็นได้เฉพาะ Super Admin · The monthly salary "
                   "export; only the OT column is summed, per department. Raw "
                   "rows stay Super-Admin-only.")
        up = st.file_uploader("เลือกไฟล์ / Choose file",
                              type=["csv", "xls", "xlsx"], key="ot_up")
        if up is not None:
            raw = up.getvalue()
            try:
                parsed = osd.parse_salary(raw, up.name)
            except Exception as e:
                st.error(f"อ่านไฟล์ไม่สำเร็จ / could not parse file: {e}")
                parsed = None
            if parsed:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("OT รวม / Total OT (THB)",
                          f"{parsed['grand_total']:,.2f}")
                m2.metric("พนักงาน / Employees", parsed["n_emp"])
                m3.metric("Cost centres", parsed["n_cc"])
                ok = parsed["reconciled"]
                m4.metric("กระทบยอด / Reconciled",
                          "✓ ตรง / OK" if ok else "✗ ไม่ตรง / check")
                if not ok:
                    st.warning(f"ผลรวมรายบุคคล ({parsed['grand_total']:,.2f}) "
                               f"ไม่เท่ากับแถว Total Dept "
                               f"({parsed['total_dept']:,.2f}). ตรวจไฟล์อีกครั้ง "
                               f"· Employee OT sum does not match the Total "
                               f"Dept rows — please check the file.")
                if parsed["unmapped"]:
                    rows = ", ".join(f"{c} ({nm}) ฿{ot:,.0f}"
                                     for c, nm, ot in parsed["unmapped"])
                    st.warning("⚠️ Cost centre ที่ยังไม่ได้แมปแผนก / unmapped "
                               f"cost centres (ไม่ถูกนับ / excluded): {rows}")
                # per-department preview
                import pandas as pd
                prev = pd.DataFrame(
                    [(d, parsed["dept_totals"][d]) for d in osd.DEPT_ORDER],
                    columns=["แผนก / Department", "OT (THB)"])
                st.dataframe(prev, use_container_width=True, hide_index=True,
                             column_config={"OT (THB)": st.column_config.
                                            NumberColumn(format="%.2f")})

                st.markdown("**บันทึกเป็นเดือน / Save as a month snapshot**")
                _guess = up.name
                _def_lbl = ""
                for mon in ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
                            "Aug", "Sep", "Oct", "Nov", "Dec"):
                    if mon.lower() in _guess.lower():
                        _def_lbl = f"{mon} {dt.date.today():%Y}"
                        break
                s1, s2 = st.columns([2, 3])
                label = s1.text_input("ชื่อเดือน / Month label",
                                      value=_def_lbl,
                                      placeholder="เช่น April 2026", key="ot_lbl")
                cyc = s2.text_input("รอบการจ่าย (แสดงบนรายงาน) / Pay cycle "
                                    "(shown on report)",
                                    placeholder="เช่น 21 Mar – 20 Apr 2026",
                                    key="ot_cyc")
                exists = any(m["label"] == label.strip()
                             for m in osd.list_months())
                if exists and label.strip():
                    st.info(f"มีเดือน “{label.strip()}” อยู่แล้ว — บันทึกจะเขียน"
                            "ทับ · a snapshot with this label exists; saving "
                            "overwrites it.")
                if st.button("💾 บันทึกเดือนนี้ / Save this month",
                             type="primary", disabled=not label.strip()):
                    osd.save_month(label.strip(), cyc.strip(), cyc.strip(),
                                   parsed, raw, up.name, actor)
                    st.success(f"บันทึกแล้ว / saved: {label.strip()}")
                    st.rerun()
else:
    st.info("🔒 การอัปโหลดและข้อมูลเงินเดือนดิบสงวนสิทธิ์เฉพาะ Super Admin — "
            "ผู้จัดการดูได้เฉพาะยอด OT รวมตามแผนก · Raw salary upload and "
            "per-employee detail are restricted to Super Admin. Managers see "
            "department-level OT totals only.")

st.divider()

# ============================================================ COMPARISON
months = osd.list_months()
if len(months) < 2:
    have = ", ".join(m["label"] for m in months) or "—"
    st.warning("ต้องมีอย่างน้อย 2 เดือนเพื่อเปรียบเทียบ · Need at least two "
               f"saved months to compare. ขณะนี้มี / currently saved: {have}")
    st.stop()

labels = [m["label"] for m in months]


def _mkey(lbl):
    """(year, month_index) parsed from a label like 'April 2026'; (0,0) if not."""
    import re as _re
    s = str(lbl).lower()
    mo = 0
    for i, name in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul",
                              "aug", "sep", "oct", "nov", "dec"], 1):
        if name in s:
            mo = i
            break
    ym = _re.search(r"(20\d{2})", s)
    return (int(ym.group(1)) if ym else 0, mo)


_keyed = [(_mkey(l), l) for l in labels]
if all(k != (0, 0) for k, _ in _keyed):
    _srt = [l for _, l in sorted(_keyed)]          # oldest -> newest
    default_b = _srt[-1]                            # newest calendar month
    default_a = _srt[-2] if len(_srt) >= 2 else _srt[0]
else:
    default_b = labels[0]                           # newest upload
    default_a = labels[1]                           # previous upload

c1, c2 = st.columns(2)
la = c1.selectbox("เดือน A / Month A (ฐาน / base)", labels,
                  index=labels.index(default_a), key="ot_cmp_a")
lb = c2.selectbox("เดือน B / Month B (เทียบ / compare)", labels,
                  index=labels.index(default_b), key="ot_cmp_b")
if la == lb:
    st.warning("เลือกคนละเดือน / pick two different months.")
    st.stop()

da = osd.get_month(la)
db = osd.get_month(lb)
ta = da["dept_totals"]
tb = db["dept_totals"]
A = {d: float(ta.get(d, 0) or 0) for d in osd.DEPT_ORDER}
B = {d: float(tb.get(d, 0) or 0) for d in osd.DEPT_ORDER}
tot_a = sum(A.values()); tot_b = sum(B.values())
delta = tot_b - tot_a
pct = (delta / tot_a * 100) if tot_a else 0.0

mc1, mc2, mc3 = st.columns(3)
mc1.metric(f"{la} · OT รวม / Total", f"฿{tot_a:,.0f}")
mc2.metric(f"{lb} · OT รวม / Total", f"฿{tot_b:,.0f}")
mc3.metric("เปลี่ยนแปลง / Change", f"฿{delta:,.0f}",
           f"{pct:+.1f}% vs {la}")

# ---- interactive grouped bar chart ----
import plotly.graph_objects as go
order_top = list(osd.DEPT_ORDER)[::-1]          # first dept on top in barh
fig = go.Figure()
fig.add_trace(go.Bar(
    y=order_top, x=[A[d] for d in order_top], name=la, orientation="h",
    marker_color="#009ADE",
    text=[f"฿{A[d]:,.0f}" for d in order_top], textposition="outside",
    cliponaxis=False))
fig.add_trace(go.Bar(
    y=order_top, x=[B[d] for d in order_top], name=lb, orientation="h",
    marker_color="#E31D93",
    text=[f"฿{B[d]:,.0f}" for d in order_top], textposition="outside",
    cliponaxis=False))
fig.update_layout(
    barmode="group", height=760, bargap=0.25, bargroupgap=0.08,
    title=f"OT จ่ายตามแผนก / OT paid by department — {la} vs {lb}",
    margin=dict(l=10, r=40, t=50, b=10),
    legend=dict(orientation="h", y=1.04, x=0),
    xaxis_title="OT (THB)", yaxis_title="")
st.plotly_chart(fig, use_container_width=True)

# ---- comparison table ----
import pandas as pd
rows = []
for d in osd.DEPT_ORDER:
    ch = B[d] - A[d]
    cp = (ch / A[d] * 100) if A[d] else (100.0 if B[d] else 0.0)
    rows.append({"แผนก / Department": d, f"{la} (THB)": A[d],
                 f"{lb} (THB)": B[d], "เปลี่ยน / Change": ch,
                 "% เปลี่ยน / Change %": cp})
rows.append({"แผนก / Department": "TOTAL", f"{la} (THB)": tot_a,
             f"{lb} (THB)": tot_b, "เปลี่ยน / Change": delta,
             "% เปลี่ยน / Change %": pct})
df = pd.DataFrame(rows)
st.dataframe(
    df, use_container_width=True, hide_index=True,
    column_config={
        f"{la} (THB)": st.column_config.NumberColumn(format="%.0f"),
        f"{lb} (THB)": st.column_config.NumberColumn(format="%.0f"),
        "เปลี่ยน / Change": st.column_config.NumberColumn(format="%.0f"),
        "% เปลี่ยน / Change %": st.column_config.NumberColumn(format="%.1f%%")})

# ---- downloadable infographic ----
st.markdown("#### 🖼️ ส่งออกอินโฟกราฟิก / Export infographic")
if st.button("สร้างอินโฟกราฟิก ANCA (PNG / PDF) / Generate ANCA infographic",
             type="primary", key="ot_gen"):
    with st.spinner("กำลังวาด / rendering…"):
        try:
            out = orr.render_comparison(
                la, A, lb, B, osd.DEPT_ORDER,
                period_a=da.get("period_from") or "",
                period_b=db.get("period_from") or "")
            st.session_state["_ot_info"] = out
            st.session_state["_ot_info_name"] = (
                f"OT_by_Department_{la}_vs_{lb}".replace(" ", "_")
                .replace("/", "-"))
        except Exception as e:
            st.session_state["_ot_info"] = None
            st.error(f"เกิดข้อผิดพลาด / error: {e}")

_info = st.session_state.get("_ot_info")
if _info:
    nm = st.session_state.get("_ot_info_name", "OT_by_Department")
    st.image(_info["png"], use_container_width=True)
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ PNG", _info["png"], file_name=f"{nm}.png",
                       mime="image/png", use_container_width=True)
    d2.download_button("⬇️ PDF", _info["pdf"], file_name=f"{nm}.pdf",
                       mime="application/pdf", use_container_width=True)

# ============================================================ RAW (super)
if is_super:
    st.divider()
    with st.expander("🔒 ข้อมูลรายบุคคล & ไฟล์ต้นฉบับ (เฉพาะ Super Admin) / "
                     "Per-employee detail & original file (Super Admin only)",
                     expanded=False):
        rlabel = st.selectbox("เลือกเดือน / Month", labels, key="ot_raw_lbl")
        raw_m = osd.get_month(rlabel, with_raw=True)
        if raw_m:
            import pandas as pd
            erows = raw_m.get("emp_rows", [])
            st.caption(f"{len(erows)} รายการ · uploaded "
                       f"{raw_m['uploaded_at']} by {raw_m['uploaded_by']} · "
                       f"file: {raw_m.get('raw_filename') or '—'}")
            if erows:
                edf = pd.DataFrame(erows, columns=["Emp No", "Cost Centre",
                                                   "แผนก / Department",
                                                   "OT (THB)"])
                st.dataframe(edf, use_container_width=True, hide_index=True,
                             height=360,
                             column_config={"OT (THB)": st.column_config.
                                            NumberColumn(format="%.2f")})
            if raw_m.get("raw_file"):
                fn = raw_m.get("raw_filename") or f"{rlabel}.dat"
                st.download_button("⬇️ ดาวน์โหลดไฟล์ต้นฉบับ / Download original "
                                   "file", raw_m["raw_file"], file_name=fn,
                                   use_container_width=True)
            st.markdown("---")
            if st.button(f"🗑️ ลบเดือน “{rlabel}” / Delete this month",
                         key="ot_del"):
                osd.delete_month(rlabel)
                st.success(f"ลบแล้ว / deleted: {rlabel}")
                st.rerun()
