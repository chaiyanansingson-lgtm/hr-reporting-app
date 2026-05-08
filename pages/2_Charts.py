"""
📈 Charts page — KPI dashboard matching the FY2026_HR_Metric_Update Chart sheet.

Mirrors the 13 charts in the existing dashboard:
    - Total Absenteeism % vs target line (monthly)
    - Per leave-type % vs per-target line (Sick, Business, Without-Pay, Annual)
    - Absenteeism by Department/Group (multi-line)
    - OT by Department/Group (multi-line)
    - Single-month: Working Hours vs OT bar chart by Department, Headcount stacked
    - (Turnover requires resignation tracking — placeholder card included)
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import db, calculations as calc
from lib.page_utils import require_login, page_header

st.set_page_config(page_title="Charts", page_icon="📈", layout="wide")
require_login(capability="report.view_charts")
page_header(title_key="charts_title", subtitle_key="charts_subtitle")

periods = db.list_periods()
if not periods:
    st.warning("No data loaded yet. Upload a Timesheet from Upload Data first.")
    st.stop()

targets = db.get_targets()

# ---------- Top filter row ----------
f1, f2, f3 = st.columns([2, 2, 3])
sel_period = f1.selectbox("Period (single-month charts)", periods, index=0)
last_n = f2.slider("Months in trend charts", 3, 36, value=min(12, max(3, len(periods))))
group_view = f3.radio(
    "Trend grouping", ["By SG&A / MANU (top)", "By Function (detail)"],
    horizontal=True, index=0,
)
use_top = group_view.startswith("By SG&A")

if len(periods) < 3:
    st.info(
        f"📅 You currently have **{len(periods)} month** of data loaded. "
        "Trend charts will show single dots until you upload more historical Timesheets. "
        "Upload past months from the **📤 Upload Data** page — each period is stored separately."
    )

st.markdown("---")

# ============================================================================
# SECTION 1 — Absenteeism breakdown vs target lines
# ============================================================================
st.markdown("## 🩺 Absenteeism — Actual vs Target")

abs_df = calc.absenteeism_breakdown_by_month(last_n_periods=last_n)


def _trend_with_target(df: pd.DataFrame, value_col: str, title: str,
                        target_pct: float, color: str = "#1F77B4",
                        height: int = 320) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["period"], y=df[value_col],
        mode="lines+markers+text",
        text=df[value_col].apply(lambda v: f"{v:.2f}%"),
        textposition="top center",
        line=dict(width=3, color=color),
        marker=dict(size=9),
        name="Actual",
    ))
    if not df.empty:
        fig.add_trace(go.Scatter(
            x=df["period"], y=[target_pct] * len(df),
            mode="lines",
            line=dict(width=2, color="#D62728", dash="dash"),
            name=f"Target {target_pct:.2f}%",
        ))
    fig.update_layout(
        title=title, height=height,
        margin=dict(t=50, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        xaxis_title="", yaxis_title="%",
        yaxis=dict(rangemode="tozero"),
    )
    return fig


# Total Absenteeism % vs target
fig1 = _trend_with_target(abs_df, "total_absent_pct",
                          "Total Absenteeism % (excl AL) vs Target",
                          targets["absenteeism_total"] * 100, color="#C96342", height=360)
st.plotly_chart(fig1, use_container_width=True)

# User chooses which leave-type charts to display
LEAVE_CHART_DEFS = {
    "Sick Leave":             ("sick_pct",        targets["sick_leave"] * 100,    "#D08560"),
    "Business / Personal Leave": ("business_pct",  targets["business_leave"] * 100,"#9B7F4A"),
    "Without Pay":            ("without_pay_pct", targets["without_pay"] * 100,   "#A23B3B"),
    "Annual Leave":           ("annual_pct",      targets["annual_leave"] * 100,  "#5E479F"),
}
selected_leaves = st.multiselect(
    "Leave-type charts to display",
    list(LEAVE_CHART_DEFS.keys()),
    default=list(LEAVE_CHART_DEFS.keys()),
    help="Pick which leave-type trend charts to show below.",
)

if selected_leaves:
    cols = st.columns(2)
    for i, name in enumerate(selected_leaves):
        col_field, tgt, color = LEAVE_CHART_DEFS[name]
        with cols[i % 2]:
            st.plotly_chart(_trend_with_target(
                abs_df, col_field, f"{name} %", tgt, color=color),
                use_container_width=True)


# ============================================================================
# SECTION 2 — Absenteeism by Department/Group
# ============================================================================
st.markdown("---")
st.markdown(f"## 🏷️ Monthly Absenteeism — {group_view}")

abs_dept = calc.absenteeism_by_department_by_month(last_n_periods=last_n, use_top_level=use_top)
if abs_dept.empty:
    st.info("No data for this view.")
else:
    fig = px.line(
        abs_dept, x="period", y="absenteeism_pct", color="group",
        markers=True, height=420,
    )
    fig.add_hline(y=targets["absenteeism_total"] * 100,
                  line_dash="dash", line_color="#D62728",
                  annotation_text=f"Target {targets['absenteeism_total']*100:.2f}%",
                  annotation_position="top right")
    fig.update_layout(
        margin=dict(t=20, b=10),
        xaxis_title="", yaxis_title="Absenteeism %",
        legend_title="",
    )
    st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# SECTION 3 — OT by Department/Group
# ============================================================================
st.markdown("---")
st.markdown(f"## ⏱️ Monthly Overtime — {group_view}")

ot_dept = calc.ot_by_department_by_month(last_n_periods=last_n, use_top_level=use_top)
if ot_dept.empty:
    st.info("No data for this view.")
else:
    fig = px.line(
        ot_dept, x="period", y="ot_pct", color="group",
        markers=True, height=420,
    )
    fig.add_hline(y=targets["ot_total"] * 100,
                  line_dash="dash", line_color="#D62728",
                  annotation_text=f"Target {targets['ot_total']*100:.2f}%",
                  annotation_position="top right")
    fig.update_layout(
        margin=dict(t=20, b=10),
        xaxis_title="", yaxis_title="OT %",
        legend_title="",
    )
    st.plotly_chart(fig, use_container_width=True)

# OT-by-multiplier single-month chart with selectable multipliers
st.markdown("##### OT breakdown by multiplier — single month")
ot_mult_pick = st.multiselect(
    "OT multipliers to display",
    ["OT*1", "OT*1.5", "OT*2", "OT*3"],
    default=["OT*1", "OT*1.5", "OT*2", "OT*3"],
    help="Pick which OT multipliers appear in the breakdown bars below.",
)
report_for_ot = calc.build_report(period=sel_period, unit="Hours")
rows_df_ot = pd.DataFrame(report_for_ot["rows"])
if not rows_df_ot.empty and ot_mult_pick:
    ot_long = rows_df_ot.melt(
        id_vars=["sg_a_manu", "department"],
        value_vars=ot_mult_pick,
        var_name="OT Type", value_name="Hours",
    )
    fig_ot_mult = px.bar(
        ot_long, x="department", y="Hours", color="OT Type",
        color_discrete_sequence=["#FFE699", "#F4B183", "#C00000", "#7030A0"],
        height=400, barmode="stack",
        title=f"OT hours by multiplier — {sel_period}",
    )
    fig_ot_mult.update_layout(
        xaxis_tickangle=-30, margin=dict(t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
    )
    st.plotly_chart(fig_ot_mult, use_container_width=True)


# ============================================================================
# SECTION 4 — Single-month detail
# ============================================================================
st.markdown("---")
st.markdown(f"## 📊 Single-month detail — {sel_period}")

wt = calc.working_vs_ot_by_department(sel_period)
if not wt.empty:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Working Hours", x=wt["department"], y=wt["working_hrs"],
        marker_color="#2C5AA0",
        text=wt["working_hrs"].apply(lambda v: f"{v:,.0f}"),
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="OT Hours", x=wt["department"], y=wt["ot_hrs"],
        marker_color="#D67D2C",
        text=wt["ot_hrs"].apply(lambda v: f"{v:,.0f}"),
        textposition="outside",
    ))
    fig.update_layout(
        title=f"Working Hours vs OT by Function — {sel_period}",
        barmode="group", height=440,
        xaxis_tickangle=-30,
        margin=dict(t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
    )
    st.plotly_chart(fig, use_container_width=True)

    report = calc.build_report(period=sel_period, unit="Hours")
    rows_df = pd.DataFrame(report["rows"])
    if not rows_df.empty:
        hc_long = rows_df.melt(
            id_vars=["sg_a_manu", "department"],
            value_vars=["Permanent HC", "Contract HC", "TP HC"],
            var_name="Type", value_name="HC",
        )
        hc_long["Type"] = hc_long["Type"].str.replace(" HC", "")
        fig_hc = px.bar(
            hc_long, x="department", y="HC", color="Type",
            color_discrete_map={"Permanent": "#2C5AA0", "Contract": "#D67D2C", "TP": "#7C9444"},
            height=380, title=f"Headcount by Function — {sel_period}",
        )
        fig_hc.update_layout(
            xaxis_tickangle=-30, margin=dict(t=50, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        )
        st.plotly_chart(fig_hc, use_container_width=True)


# ============================================================================
# SECTION 5 — Turnover (placeholder)
# ============================================================================
st.markdown("---")
st.markdown("## 🔄 Turnover")
st.info(
    f"**Target {targets['turnover']*100:.1f}%** — "
    "Turnover tracking requires recording resignations and new hires each month. "
    "This is **not yet built** — the prototype only tracks the current employee snapshot. "
    "Tell me when you want this and I'll add a Turnover events page where admin can log "
    "monthly Resigned/New entries to drive this chart."
)
