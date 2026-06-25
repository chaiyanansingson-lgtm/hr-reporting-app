# KPI Dashboard — Management module function (req. 2.1)
# Split out of K Attendance. Monthly view = the org KPI/absenteeism/OT analysis
# (parity with the old tab) with a fixed Headcount-by-Function chart. Weekly view
# = the standard HR weekly metrics (built in the next step).
import streamlit as st

from lib import theme as _theme
from lib.auth import require_capability, has_capability
from lib import attendance_db as att

_theme.inject()
require_capability("attend.view_team")
_theme.header("แดชบอร์ด KPI", "KPI Dashboard",
              "ภาพรวมการขาดงาน · OT · กำลังคน — รายเดือน และ รายสัปดาห์")

_view = st.radio("มุมมอง · View",
                 ["📅 รายเดือน · Monthly", "📆 รายสัปดาห์ · Weekly metrics"],
                 horizontal=True, key="kpi_view")
_monthly = _view.startswith("📅")

if _monthly:
    import plotly.graph_objects as go
    import plotly.express as px
    from lib import kpi_calc as _kpi, timesheet_db as _tdb
    st.markdown("### 📈 แดชบอร์ด KPI · KPI Dashboard")
    st.caption("คำนวณจากไฟล์บันทึกเวลา (face-scan) โดยตรง — ไม่ต้องอัปโหลดไฟล์ "
               "ชั่วโมงทำงานแยก · derived directly from the timesheet, no separate "
               "working-hours upload.")
    _up = _tdb.latest_upload()
    if not _up:
        st.info("ยังไม่มีข้อมูลบันทึกเวลา — อัปโหลดไฟล์ที่หน้า '📊 รายงาน' ก่อน · "
                "upload the face-scan timesheet on the Report page first.")
    else:
        _df = _kpi.load(_up["id"])
        _pers = _kpi.periods(_df)
        if not _pers:
            st.warning("ไม่พบข้อมูลในไฟล์ · no rows in the timesheet.")
        else:
            _tg = _kpi.get_targets()
            f1, f2, f3 = st.columns([2, 2, 3])
            sel_p = f1.selectbox("เดือน (กราฟเดือนเดียว) · Period", _pers[::-1])
            last_n = f2.slider("จำนวนเดือนในกราฟแนวโน้ม · Months in trend", 3, 36,
                               min(12, max(3, len(_pers))))
            gv = f3.radio("จัดกลุ่มแนวโน้ม · Trend grouping",
                          ["SG&A / MANU", "ตามหน้าที่ · By Function"],
                          horizontal=True)
            use_top = gv.startswith("SG&A")
            with st.expander("🎯 เป้าหมาย KPI · Targets (แก้ไข แล้วกดบันทึก)"):
                tc = st.columns(6)
                nt = {}
                nt["absenteeism_total"] = tc[0].number_input(
                    "ขาดงานรวม % · Absence", 0.0, 100.0,
                    _tg["absenteeism_total"] * 100, 0.1) / 100
                nt["sick_leave"] = tc[1].number_input(
                    "ลาป่วย % · Sick", 0.0, 100.0, _tg["sick_leave"] * 100, 0.1) / 100
                nt["business_leave"] = tc[2].number_input(
                    "ลากิจ % · Business", 0.0, 100.0,
                    _tg["business_leave"] * 100, 0.1) / 100
                nt["without_pay"] = tc[3].number_input(
                    "ไม่จ่าย % · W/Pay", 0.0, 100.0,
                    _tg["without_pay"] * 100, 0.1) / 100
                nt["annual_leave"] = tc[4].number_input(
                    "พักร้อน % · Annual", 0.0, 100.0,
                    _tg["annual_leave"] * 100, 0.1) / 100
                nt["ot_total"] = tc[5].number_input(
                    "OT %", 0.0, 200.0, _tg["ot_total"] * 100, 1.0) / 100
                if st.button("💾 บันทึกเป้าหมาย · Save targets"):
                    _kpi.set_targets(nt); st.rerun()
            if len(_pers) < 3:
                st.info(f"มีข้อมูล {len(_pers)} เดือน — กราฟแนวโน้มจะเป็นจุดจนกว่าจะ"
                        "อัปโหลดไฟล์เดือนย้อนหลังเพิ่ม.")
            st.markdown("---")

            st.markdown("#### 🩺 การขาดงาน · Absenteeism — Actual vs Target")
            abx = _kpi.absenteeism_breakdown_by_month(_df, last_n)

            def _trend(dd, col, title, tgt, color, h=340):
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=dd["period"], y=dd[col], mode="lines+markers+text",
                    text=dd[col].apply(lambda v: f"{v:.2f}%"),
                    textposition="top center", line=dict(width=3, color=color),
                    marker=dict(size=8), name="Actual"))
                fig.add_trace(go.Scatter(
                    x=dd["period"], y=[tgt] * len(dd), mode="lines",
                    line=dict(width=2, color="#D62728", dash="dash"),
                    name=f"Target {tgt:.2f}%"))
                fig.update_layout(title=title, height=h,
                    margin=dict(t=46, b=8, l=8, r=8),
                    legend=dict(orientation="h", y=-0.28, x=0.5,
                                xanchor="center"),
                    yaxis_title="%", yaxis=dict(rangemode="tozero"),
                    xaxis_title="")
                return fig

            st.plotly_chart(_trend(abx, "total_absent_pct",
                "Total Absenteeism % (excl AL) vs Target",
                _tg["absenteeism_total"] * 100, "#C96342", 360),
                use_container_width=True)
            LV = {"ลาป่วย · Sick Leave": ("sick_pct", _tg["sick_leave"] * 100, "#D08560"),
                  "ลากิจ · Business/Personal": ("business_pct", _tg["business_leave"] * 100, "#9B7F4A"),
                  "ไม่จ่าย · Without Pay": ("without_pay_pct", _tg["without_pay"] * 100, "#A23B3B"),
                  "พักร้อน · Annual Leave": ("annual_pct", _tg["annual_leave"] * 100, "#5E479F")}
            picks = st.multiselect("เลือกกราฟประเภทการลา · Leave-type charts",
                                   list(LV), default=list(LV))
            cc = st.columns(2)
            for i, nm in enumerate(picks):
                col, tgt, color = LV[nm]
                cc[i % 2].plotly_chart(_trend(abx, col, nm + " %", tgt, color),
                                       use_container_width=True)

            st.markdown("---")
            st.markdown(f"#### 🏷️ การขาดงานรายเดือน · Monthly Absenteeism — {gv}")
            ag = _kpi.absenteeism_by_group_by_month(_df, last_n, use_top)
            if not ag.empty:
                fig = px.line(ag, x="period", y="absenteeism_pct", color="group",
                              markers=True, height=400, text="absenteeism_pct")
                fig.update_traces(texttemplate="%{text:.2f}%",
                                  textposition="top center",
                                  mode="lines+markers+text")
                fig.add_hline(y=_tg["absenteeism_total"] * 100, line_dash="dash",
                    line_color="#D62728",
                    annotation_text=f"Target {_tg['absenteeism_total']*100:.2f}%")
                fig.update_layout(margin=dict(t=16, b=8), xaxis_title="",
                                  yaxis_title="Absenteeism %", legend_title="")
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.markdown(f"#### ⏱️ OT รายเดือน · Monthly Overtime — {gv}")
            og = _kpi.ot_by_group_by_month(_df, last_n, use_top)
            if not og.empty:
                fig = px.line(og, x="period", y="ot_pct", color="group",
                              markers=True, height=400, text="ot_pct")
                fig.update_traces(texttemplate="%{text:.1f}%",
                                  textposition="top center",
                                  mode="lines+markers+text")
                fig.add_hline(y=_tg["ot_total"] * 100, line_dash="dash",
                    line_color="#D62728",
                    annotation_text=f"Target {_tg['ot_total']*100:.1f}%")
                fig.update_layout(margin=dict(t=16, b=8), xaxis_title="",
                                  yaxis_title="OT %", legend_title="")
                st.plotly_chart(fig, use_container_width=True)
            st.markdown("##### OT แยกอัตรา (เดือนเดียว) · OT breakdown by multiplier")
            otp = st.multiselect("อัตรา OT · multipliers",
                ["OT*1", "OT*1.5", "OT*2", "OT*3"],
                default=["OT*1", "OT*1.5", "OT*2", "OT*3"])
            smt = _kpi.single_month_table(_df, sel_p)
            if not smt.empty and otp:
                ol = smt.melt(id_vars=["group", "function"], value_vars=otp,
                              var_name="OT Type", value_name="Hours")
                fig = px.bar(ol, x="function", y="Hours", color="OT Type",
                    barmode="stack", height=400, text="Hours",
                    color_discrete_sequence=["#FFE699", "#F4B183", "#C00000",
                                             "#7030A0"],
                    title=f"OT hours by multiplier — {sel_p}")
                fig.update_traces(texttemplate="%{text:,.0f}",
                                  textposition="inside",
                                  insidetextanchor="middle")
                fig.update_layout(xaxis_tickangle=-30, margin=dict(t=46, b=8),
                    uniformtext_minsize=7, uniformtext_mode="hide",
                    legend=dict(orientation="h", y=-0.3, x=0.5,
                                xanchor="center"))
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.markdown(f"#### 📊 รายละเอียดเดือนเดียว · Single-month detail — {sel_p}")
            wt = _kpi.working_vs_ot_by_function(_df, sel_p)
            if not wt.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(name="Working Hours", x=wt["function"],
                    y=wt["working_hrs"], marker_color="#2C5AA0",
                    text=wt["working_hrs"].apply(lambda v: f"{v:,.0f}"),
                    textposition="outside"))
                fig.add_trace(go.Bar(name="OT Hours", x=wt["function"],
                    y=wt["ot_hrs"], marker_color="#D67D2C",
                    text=wt["ot_hrs"].apply(lambda v: f"{v:,.0f}"),
                    textposition="outside"))
                fig.update_layout(title=f"Working Hours vs OT by Function — {sel_p}",
                    barmode="group", height=430, xaxis_tickangle=-30,
                    margin=dict(t=46, b=8),
                    legend=dict(orientation="h", y=-0.3, x=0.5,
                                xanchor="center"))
                st.plotly_chart(fig, use_container_width=True)
            if not smt.empty:
                hl = smt.melt(id_vars=["group", "function"],
                    value_vars=["Permanent HC", "Contract HC", "TP HC"],
                    var_name="Type", value_name="HC")
                hl["Type"] = hl["Type"].str.replace(" HC", "")
                hl = hl[hl["HC"] > 0]            # only contract types present
                _h = max(360, 30 * hl["function"].nunique() + 130)
                fig = px.bar(hl, y="function", x="HC", color="Type",
                    orientation="h", barmode="group", height=_h,
                    title=f"Headcount by Function — {sel_p}", text="HC",
                    color_discrete_map={"Permanent": "#2C5AA0",
                                        "Contract": "#D67D2C", "TP": "#7C9444"},
                    category_orders={"Type": ["Permanent", "Contract", "TP"]})
                fig.update_traces(texttemplate="%{text:,.0f}",
                                  textposition="outside", cliponaxis=False,
                                  textfont_size=12)
                fig.update_layout(margin=dict(t=46, b=8, l=8, r=34),
                    xaxis_title="Headcount (คน)", yaxis_title="",
                    bargap=0.28, bargroupgap=0.06,
                    legend=dict(orientation="h", y=-0.12, x=0.5,
                                xanchor="center", title=""))
                st.plotly_chart(fig, use_container_width=True)
else:
    from lib import weekly_metrics as wm
    import plotly.graph_objects as _go
    import plotly.express as _px
    from plotly.subplots import make_subplots as _msub

    st.subheader("📆 ตัวชี้วัดรายสัปดาห์ · Weekly metrics")
    _cmsg = st.session_state.pop("wm_compute_msg", None)
    if _cmsg:
        (st.success if _cmsg[0] == "ok" else st.error)(_cmsg[1])
    _ot_t, _ab_t = wm.targets()
    _weeks = wm.weeks()
    # apply a pending auto-select from "Compute a week" — MUST be set before the
    # wm_week widget below is instantiated (Streamlit forbids changing it after).
    _goto = st.session_state.pop("wm_goto_week", None)
    if _goto and _goto in _weeks:
        st.session_state["wm_week"] = _goto

    if not _weeks:
        st.info("ยังไม่มีข้อมูลรายสัปดาห์ · no weekly data yet — seed ประวัติจาก "
                "ไฟล์ Weekly Metric Report หรือคำนวณสัปดาห์จาก 3 รายงาน "
                "ที่แผง 'ตั้งค่า & นำเข้า' ด้านล่าง.")
    else:
        _sel = st.selectbox("สัปดาห์ที่แสดง · Week", _weeks[::-1], key="wm_week")
        _prev = wm.prev_week_of(_sel)
        _rows = wm.week_data(_sel)
        _depts = [r["dept"] for r in _rows]
        _ov = wm.overall(_sel)
        m = st.columns(4)
        m[0].metric("OT รวม · Overall OT %",
                    f"{(_ov['ot_pct'] or 0) * 100:.1f}%",
                    f"เป้า {_ot_t * 100:.0f}%", delta_color="off")
        m[1].metric("ขาดงานรวม · Overall Absent %",
                    f"{(_ov['absent_pct'] or 0) * 100:.2f}%",
                    f"เป้า {_ab_t * 100:.1f}%", delta_color="off")
        m[2].metric("ชม.ทำงาน · Working hrs", f"{_ov['working']:,.0f}")
        m[3].metric("ชม. OT · OT hrs", f"{_ov['ot']:,.0f}")
        _src = {r["source"] for r in _rows}
        st.caption(f"แหล่งข้อมูล · source: {', '.join(sorted(_src))} • "
                   f"{len(_depts)} แผนก")

        _pmap = {r["dept"]: r for r in wm.week_data(_prev)} if _prev else {}

        # ----- presentation charts (matplotlib, match the Excel look) -----
        from lib import weekly_charts as _wc
        _ot100, _ab100 = _ot_t * 100, _ab_t * 100
        _work = [r.get("working") or 0 for r in _rows]
        _othr = [r.get("ot") or 0 for r in _rows]
        _lvhr = [r.get("leave") or 0 for r in _rows]

        def _ser(k):
            return [(r.get(k) or 0) * 100 for r in _rows]

        def _pser(k):
            return ([(_pmap.get(d, {}).get(k) or 0) * 100 for d in _depts]
                    if _prev else None)

        _pl = f"Prev wk ({_prev})" if _prev else "Prev wk"
        _tl = f"This wk ({_sel})"

        st.markdown("##### \u23f1\ufe0f OT \u0e23\u0e32\u0e22\u0e2a\u0e31\u0e1b\u0e14\u0e32\u0e2b\u0e4c \u00b7 OT this week")
        _fig = _wc.combo_chart(_depts, _work, _othr, _ser("ot_pct"),
                               _pser("ot_pct"), _ot100, f"OT % \u2014 {_sel}",
                               "OT Hrs", _pl, _tl)
        _png = _wc.png_bytes(_fig)
        st.image(_png, use_container_width=True)
        st.download_button("\u2b07\ufe0f \u0e14\u0e32\u0e27\u0e19\u0e4c\u0e42\u0e2b\u0e25\u0e14\u0e23\u0e39\u0e1b OT \u00b7 Download OT chart (PNG)",
                           _png, file_name=f"OT_{_sel.replace(' ', '_')}.png",
                           mime="image/png", key="dl_ot")

        st.markdown("##### \U0001fa7a \u0e01\u0e32\u0e23\u0e02\u0e32\u0e14\u0e07\u0e32\u0e19\u0e23\u0e32\u0e22\u0e2a\u0e31\u0e1b\u0e14\u0e32\u0e2b\u0e4c \u00b7 Absenteeism this week")
        _fig = _wc.combo_chart(_depts, _work, _lvhr, _ser("absent_pct"),
                               _pser("absent_pct"), _ab100,
                               f"Absenteeism % \u2014 {_sel}", "Leave Hrs",
                               _pl, _tl)
        _png = _wc.png_bytes(_fig)
        st.image(_png, use_container_width=True)
        st.download_button("\u2b07\ufe0f \u0e14\u0e32\u0e27\u0e19\u0e4c\u0e42\u0e2b\u0e25\u0e14\u0e23\u0e39\u0e1b\u0e02\u0e32\u0e14\u0e07\u0e32\u0e19 \u00b7 Download absenteeism chart (PNG)",
                           _png,
                           file_name=f"Absenteeism_{_sel.replace(' ', '_')}.png",
                           mime="image/png", key="dl_ab")

        # ----- per-organisation small charts (separate per dept) -----
        if len(_weeks) > 2:
            _nw = st.slider("\u0e08\u0e33\u0e19\u0e27\u0e19\u0e2a\u0e31\u0e1b\u0e14\u0e32\u0e2b\u0e4c\u0e41\u0e22\u0e01\u0e41\u0e1c\u0e19\u0e01 \u00b7 Weeks per dept",
                            2, len(_weeks), min(4, len(_weeks)), key="wm_nw")
        else:
            _nw = len(_weeks)
            st.caption(f"\u0e41\u0e2a\u0e14\u0e07 {_nw} \u0e2a\u0e31\u0e1b\u0e14\u0e32\u0e2b\u0e4c\u0e17\u0e35\u0e48\u0e21\u0e35 \u00b7 showing the {_nw} week(s) "
                       "available.")
        _ws, _td = wm.trend(_nw)
        _tdepts = [d for d in wm.DEPT_ORDER if d in _td] + \
                  [d for d in _td if d not in wm.DEPT_ORDER]

        def _dser(k):
            return {d: [(_td.get(d, {}).get(w, {}).get(k) or 0) * 100
                        for w in _ws] for d in _tdepts}

        st.markdown(f"##### \U0001f4c8 OT% \u0e41\u0e22\u0e01\u0e41\u0e1c\u0e19\u0e01 \u00b7 OT% by department ({_nw} wk)")
        _fig = _wc.per_org_grid(_ws, _dser("ot_pct"), _ot100,
                                f"OT % by department \u2014 last {_nw} weeks")
        _png = _wc.png_bytes(_fig)
        st.image(_png, use_container_width=True)
        st.download_button("\u2b07\ufe0f Download OT-by-dept (PNG)", _png,
                           file_name=f"OT_by_dept_{_sel.replace(' ', '_')}.png",
                           mime="image/png", key="dl_g1")

        st.markdown(f"##### \U0001f4c9 \u0e01\u0e32\u0e23\u0e02\u0e32\u0e14\u0e07\u0e32\u0e19% \u0e41\u0e22\u0e01\u0e41\u0e1c\u0e19\u0e01 \u00b7 Absenteeism% by department ({_nw} wk)")
        _fig = _wc.per_org_grid(_ws, _dser("absent_pct"), _ab100,
                                f"Absenteeism % by department \u2014 last {_nw} weeks")
        _png = _wc.png_bytes(_fig)
        st.image(_png, use_container_width=True)
        st.download_button("\u2b07\ufe0f Download absenteeism-by-dept (PNG)",
                           _png,
                           file_name=f"Absent_by_dept_{_sel.replace(' ', '_')}.png",
                           mime="image/png", key="dl_g2")

    # ----------------------- seed / settings / compute -----------------------
    _wm_admin = has_capability("system.users")
    with st.expander("⚙️ ตั้งค่า & นำเข้า · Settings & data" + ("" if _wm_admin else " — เฉพาะแอดมิน · admin only")):
      if not _wm_admin:
        st.info("เฉพาะผู้ดูแลระบบ/ซูเปอร์แอดมินเท่านั้นจึงนำเข้าหรือตั้งค่าได้ · Only Admin/Superadmin can import data or change settings here.")
      else:
            _s = wm.get_settings()
            cc = st.columns(4)
            _dh = cc[0].number_input("ชม./วัน · Daily hrs", 1.0, 24.0,
                                     float(_s["daily_hours"]), 0.5)
            _wd = cc[1].number_input("วันทำงาน/สัปดาห์ · Days/wk", 1.0, 7.0,
                                     float(_s["working_days"]), 0.5)
            _ott = cc[2].number_input("เป้า OT %", 0.0, 100.0,
                                      float(_s["ot_target"]) * 100, 0.5) / 100
            _abt = cc[3].number_input("เป้า Absent %", 0.0, 100.0,
                                      float(_s["absent_target"]) * 100, 0.1) / 100
            if st.button("💾 บันทึกค่าตั้ง · Save settings"):
                wm.set_setting("daily_hours", _dh)
                wm.set_setting("working_days", _wd)
                wm.set_setting("ot_target", _ott)
                wm.set_setting("absent_target", _abt)
                st.success("บันทึกแล้ว · saved."); st.rerun()

            st.divider()
            st.markdown("**📥 Seed ประวัติจากไฟล์ · Seed history** — รองรับทั้ง "
                        "Weekly-Metric-Report และ FY tracker (.xlsx) "
                        "(ระบบตรวจชนิดไฟล์อัตโนมัติ)")
            _up = st.file_uploader("ไฟล์ .xlsx", type=["xlsx"], key="wm_seed")
            if _up and st.button("🚀 Seed จากไฟล์นี้ · Seed now"):
                try:
                    res = wm.seed_file(_up.read())
                    kind = res[0]
                    if kind == "fy":
                        _, fwk, lwk, nn = res
                        st.success(f"Seed FY history สำเร็จ • {fwk} → {lwk} • "
                                   f"{nn} แถว."); st.rerun()
                    else:
                        _, cw, nn = res
                        st.success(f"Seed สำเร็จ • สัปดาห์ล่าสุด {cw} • "
                                   f"{nn} แถว."); st.rerun()
                except Exception as e:
                    st.error(f"อ่านไฟล์ไม่สำเร็จ: {e}")

            st.divider()
            st.markdown("**🧮 คำนวณสัปดาห์จาก 3 รายงาน · Compute a week from the "
                        "uploaded HR reports** (ใช้รหัสต้นทุน column G แมปแผนก)")
            import datetime as _dt
            cc2 = st.columns([1.4, 1.2, 1.2])
            _wl = cc2[0].text_input("ป้ายสัปดาห์ · Week label (เช่น Jun 26-W3)",
                                    key="wm_wl")
            _df = cc2[1].date_input("ตั้งแต่ · From", _dt.date.today(), key="wm_df")
            _dt_ = cc2[2].date_input("ถึง · To", _dt.date.today(), key="wm_dt")
            if st.button("คำนวณ & บันทึก · Compute & store"):
                if not _wl.strip():
                    st.warning("กรอกป้ายสัปดาห์ก่อน · enter a week label.")
                elif not att.active_upload("timesheet"):
                    st.warning("ยังไม่มีไฟล์เวลาทำงาน — อัปโหลดไฟล์บันทึกเวลาที่ "
                               "ผู้ดูแลระบบ → ข้อมูล & อัปโหลด ก่อน · upload a "
                               "timesheet first.")
                else:
                    nn = wm.compute_week(_wl.strip(), _df.isoformat(),
                                         _dt_.isoformat())
                    if nn == 0:
                        st.session_state["wm_compute_msg"] = (
                            "error", "\u0e04\u0e33\u0e19\u0e27\u0e13\u0e44\u0e14\u0e49 0 \u0e41\u0e1c\u0e19\u0e01 \u2014 \u0e2d\u0e32\u0e08\u0e40\u0e1e\u0e23\u0e32\u0e30 (1) "
                            "\u0e0a\u0e48\u0e27\u0e07\u0e27\u0e31\u0e19\u0e17\u0e35\u0e48\u0e44\u0e21\u0e48\u0e04\u0e23\u0e2d\u0e1a\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e43\u0e19\u0e44\u0e1f\u0e25\u0e4c\u0e40\u0e27\u0e25\u0e32 (\u0e15\u0e31\u0e49\u0e07\u0e41\u0e15\u0e48/\u0e16\u0e36\u0e07 "
                            "\u0e14\u0e49\u0e32\u0e19\u0e1a\u0e19) \u0e2b\u0e23\u0e37\u0e2d (2) \u0e23\u0e2b\u0e31\u0e2a\u0e15\u0e49\u0e19\u0e17\u0e38\u0e19 (column G) \u0e02\u0e2d\u0e07\u0e1e\u0e19\u0e31\u0e01\u0e07\u0e32\u0e19"
                            "\u0e44\u0e21\u0e48\u0e15\u0e23\u0e07\u0e01\u0e31\u0e1a 'MAP \u0e23\u0e2b\u0e31\u0e2a\u0e15\u0e49\u0e19\u0e17\u0e38\u0e19 \u2192 \u0e41\u0e1c\u0e19\u0e01' \u0e14\u0e49\u0e32\u0e19\u0e25\u0e48\u0e32\u0e07. "
                            "\u0e15\u0e23\u0e27\u0e08\u0e0a\u0e48\u0e27\u0e07\u0e27\u0e31\u0e19\u0e17\u0e35\u0e48\u0e41\u0e25\u0e30\u0e41\u0e1c\u0e19\u0e1c\u0e31\u0e07\u0e41\u0e25\u0e49\u0e27\u0e25\u0e2d\u0e07\u0e43\u0e2b\u0e21\u0e48 \u00b7 0 departments "
                            "\u2014 either the From/To dates don't overlap the "
                            "timesheet, or the employees' cost-centre codes "
                            "don't match the cost-centre\u2192department map below. "
                            "Check both and retry.")
                    else:
                        _norm = wm._norm_week(_wl.strip())
                        st.session_state["wm_goto_week"] = _norm
                        st.session_state["wm_compute_msg"] = (
                            "ok", f"✅ คำนวณ {nn} แผนกสำหรับ '{_norm}' แล้ว และเลือก "
                            "ให้อัตโนมัติด้านบน — เลื่อนขึ้นเพื่อดูกราฟ · computed "
                            f"{nn} departments for '{_norm}'; it's now selected "
                            "above — scroll up to see the charts.")
                    st.rerun()

            st.divider()
            st.markdown("**🗺️ แผนผังรหัสต้นทุน → แผนก (ใช้ตอนคำนวณสด) · "
                        "Cost-centre → department map**")
            st.caption("คีย์ = รหัสต้นทุน 3 หลัก (MASTER คอลัมน์ G), ค่า = ชื่อแผนก "
                       "ใน 11 แผนกมาตรฐาน. แก้เป็น JSON แล้วบันทึก.")
            import json as _json
            _cc_now = _json.dumps(wm.get_cc_map(), ensure_ascii=False, indent=2)
            _cc_txt = st.text_area("cc_map (JSON)", _cc_now, height=200,
                                   key="wm_ccmap")
            if st.button("💾 บันทึกแผนผัง · Save map"):
                try:
                    _m = _json.loads(_cc_txt)
                    assert isinstance(_m, dict) and _m
                    wm.set_cc_map(_m)
                    st.success(f"บันทึก {len(_m)} รหัสแล้ว · saved."); st.rerun()
                except Exception as e:
                    st.error(f"JSON ไม่ถูกต้อง · invalid JSON: {e}")
