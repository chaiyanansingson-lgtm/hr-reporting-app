"""
📊 Report page - the main HR report.
Renders the same table shape as the user's screenshot, with filters, unit toggle,
optional Annual Leave columns, and Excel/PNG download buttons.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import db, calculations as calc, exports
from lib.page_utils import require_login, page_header

st.set_page_config(page_title="Report", page_icon="📊", layout="wide")
require_login()
page_header(title_key="report_title", subtitle_key="report_subtitle")

# ---------- filters ----------
periods = db.list_periods()
if not periods:
    st.warning(
        "No data loaded yet. An admin needs to upload a Timesheet on the **📤 Upload Data** page first."
    )
    st.stop()

cgs = db.list_cost_groups()
unique_top = sorted({c["sg_a_manu"] for c in cgs if c["sg_a_manu"]})
unique_dept = sorted({c["department"] for c in cgs if c["department"]})

with st.expander("🔧 Filters & calculation settings (click to collapse for more table room)",
                  expanded=True):
    f1, f2, f3, f4 = st.columns([2, 1.2, 2.5, 2.5])
    period = f1.selectbox("Reporting period", periods, index=0)
    unit = f2.radio("Unit", ["Hours", "Days"], horizontal=True)
    top_filter = f3.multiselect("Top group", unique_top,
                                default=unique_top, placeholder="(all)",
                                help="Whatever group names you've defined in Configuration → Cost Groups")
    dept_filter = f4.multiselect("Function (department)", unique_dept,
                                 default=[], placeholder="(all)")

    # Working-hours mode
    wh_mode_label = st.radio(
        "Working Hours mode",
        ["Actual (from Timesheet)", "Standard (HC × Working Days × Daily Std Hrs)"],
        horizontal=False,
        help="**Actual** sums the work_hours column from the Timesheet. "
             "**Standard** computes the expected hours: number of working days in the period "
             "(from Holidays + per-weekday rules in Configuration) × daily standard hours × headcount.",
    )
    wh_mode = "actual" if wh_mode_label.startswith("Actual") else "standard"

    # Deduction toggles — separate row, all per-leave-type
    st.markdown("**Deduct from Working Hours:**")
    d1, d2, d3, d4, d5 = st.columns(5)
    deduct_al = d1.toggle("Annual Leave", value=False, key="ded_al",
                           help="Subtract Annual Leave hours from Working Hours.")
    deduct_sick = d2.toggle("Sick Leave", value=False, key="ded_sick",
                             help="Subtract Sick Leave hours from Working Hours.")
    deduct_business = d3.toggle("Business Leave", value=False, key="ded_bus",
                                 help="Subtract Business Leave hours from Working Hours.")
    deduct_without_pay = d4.toggle("Without Pay", value=False, key="ded_wp",
                                    help="Subtract Without-Pay hours from Working Hours.")
    include_al_in_pct = d5.toggle("Include AL in %Absent", value=False, key="inc_al",
                                   help="Add Annual Leave hours to the Absent numerator and denominator.")

    # Second filter row: column toggles
    g1, g2 = st.columns([3, 5])
    include_al = g1.toggle("Show Annual Leave columns", value=True,
                           help="The red-box columns from the original screenshot")
    leave_breakdown = g2.multiselect(
        "Add leave-type breakdown columns",
        ["Sick Leave", "Business Leave", "Without Pay"],
        default=[],
        help="Each adds Total / Permanent / Contract columns for that leave type. "
             "These are subsets of the lumped 'Total Absent (Excl AL)' columns.",
    )
    include_sick = "Sick Leave" in leave_breakdown
    include_business = "Business Leave" in leave_breakdown
    include_without_pay = "Without Pay" in leave_breakdown

# Translate dept filter -> cost code list
cost_codes_filter = None
if dept_filter:
    cost_codes_filter = [c["code"] for c in cgs if c["department"] in dept_filter]

# Personal-overrides toggle — when ON, calculations use this user's overrides
# instead of (or on top of) the master settings.
from lib.page_utils import is_admin
me = st.session_state.get("username") or ""
user_has_overrides = bool(me) and bool(db.list_user_overrides(me))

if user_has_overrides:
    use_personal = st.toggle(
        f"👤 Apply my personal calculation settings to this report",
        value=not is_admin(),  # default ON for non-admin, OFF for admin
        help="When ON, this report uses YOUR personal Holiday / Hour-rule / "
             "Cost-group / Period overrides. When OFF, uses the master settings. "
             "Either way, the master DB and other users are unaffected.",
    )
    effective_user = me if use_personal else None
else:
    effective_user = None

# Build report
report = calc.build_report(
    period=period,
    unit=unit,
    include_annual_leave_cols=include_al,
    cost_codes_filter=cost_codes_filter,
    wh_mode=wh_mode,
    deduct_al_from_wh=deduct_al,
    deduct_sick_from_wh=deduct_sick,
    deduct_business_from_wh=deduct_business,
    deduct_without_pay_from_wh=deduct_without_pay,
    include_al_in_absent_pct=include_al_in_pct,
    username=effective_user,
)

# Show banner if personal overrides are in effect
if effective_user:
    summary = db.get_user_override_summary(effective_user)
    with st.expander(
        f"🎛️ Personal calculation settings ACTIVE — {len(summary)} difference(s) from master",
        expanded=False,
    ):
        if summary:
            st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
        st.caption(
            "These overrides only affect what YOU see. Manage them on the "
            "**Settings** page (toggle to 'My Personal Settings' mode)."
        )

# If standard mode, show the resolved working days info
if wh_mode == "standard":
    wd = report["meta"].get("standard_work_days")
    sh = report["meta"].get("standard_hrs_per_emp")
    if wd is not None:
        unit_factor = 1.0 if unit == "Hours" else 1.0 / db.get_hour_config().get("hours_per_day", 8.0)
        st.caption(
            f"📐 **Standard mode active** — {period} has **{wd} working days** "
            f"× **{sh:.2f} hrs/day** = **{sh*unit_factor:.2f} {unit.lower()}/employee**. "
            f"Adjust holidays or per-weekday hours in Configuration if these don't match your expectation."
        )

# Optional top-level filter applied client-side
if top_filter and report["rows"]:
    report["rows"] = [r for r in report["rows"] if r["sg_a_manu"] in top_filter]

# ---------- rendering: build the display dataframe like the screenshot ----------
st.markdown("---")

if not report["rows"]:
    st.info("No data matches these filters.")
    st.stop()

# ============================================================================
# Viewing controls — density, table height, collapsible filters
# ============================================================================
st.markdown("---")

with st.container():
    v1, v2, v3, v4 = st.columns([2, 2, 3, 1.2])
    density = v1.radio(
        "📐 Density",
        ["Compact", "Normal", "Spacious"], index=1, horizontal=True,
        help="Affects row height and font size of the report table below."
    )
    table_height = v2.slider(
        "📏 Table height (px)", min_value=300, max_value=1400, value=700, step=50,
        help="Drag to make the table shorter or taller."
    )
    v3.caption(
        "💡 **Tip:** hover over the top-right of the table to reveal Streamlit's built-in "
        "**search**, **download CSV**, and **fullscreen** buttons. "
        "You can also press **Ctrl + +** / **Ctrl + −** to zoom the whole page."
    )
    full_width = v4.toggle("🔍 Full width", value=False,
                            help="Hide the sidebar to give the table the entire screen width.")

# CSS for density + optional sidebar collapse
density_css = {
    "Compact":   {"font_size": "0.78rem", "row_height": "26px"},
    "Normal":    {"font_size": "0.88rem", "row_height": "32px"},
    "Spacious":  {"font_size": "0.98rem", "row_height": "40px"},
}[density]
extra_css = f"""
<style>
[data-testid="stDataFrame"] table {{ font-size: {density_css['font_size']}; }}
[data-testid="stDataFrame"] tbody tr td,
[data-testid="stDataFrame"] thead tr th {{
    padding-top: 4px; padding-bottom: 4px; height: {density_css['row_height']};
}}
/* Make sure Streamlit's native dataframe toolbar (search/download/expand) is visible */
[data-testid="stElementToolbar"] {{
    opacity: 0.85 !important;
    background: rgba(255,255,255,0.95) !important;
    border-radius: 8px !important;
    border: 1px solid rgba(15,23,42,0.10) !important;
}}
[data-testid="stElementToolbar"]:hover {{
    opacity: 1 !important;
}}
"""
if full_width:
    extra_css += """
[data-testid="stSidebar"] { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: block !important; }
.block-container { max-width: 100% !important; padding-left: 2rem; padding-right: 2rem; }
"""
extra_css += "</style>"
st.markdown(extra_css, unsafe_allow_html=True)

# Display table (with subtotals interleaved) -----------------------------------
ID_COLS = exports.ID_COLS
HC_COLS = exports.HC_COLS
WORK_COLS = exports.WORK_COLS
ABSENT_COLS = exports.ABSENT_COLS
PCT_ABSENT_COLS = exports.PCT_ABSENT_COLS
OT_COLS = exports.OT_COLS
AL_COLS = exports.AL_COLS
SICK_COLS = exports.SICK_COLS
BUSINESS_COLS = exports.BUSINESS_COLS
WITHOUT_PAY_COLS = exports.WITHOUT_PAY_COLS

cols = ID_COLS + HC_COLS + WORK_COLS + ABSENT_COLS + PCT_ABSENT_COLS + OT_COLS
if include_sick:
    cols += SICK_COLS
if include_business:
    cols += BUSINESS_COLS
if include_without_pay:
    cols += WITHOUT_PAY_COLS
if include_al:
    cols += AL_COLS

groups_by_top = {g["sg_a_manu"]: g for g in report["groups"]}

display_rows = []
row_kinds = []
last_top = None
for r in report["rows"]:
    top = r.get("sg_a_manu", "")
    if last_top is not None and top != last_top:
        if last_top in groups_by_top:
            sub = dict(groups_by_top[last_top])
            sub["sg_a_manu"] = f"⮕ Total {last_top}"
            sub["department"] = ""
            display_rows.append(sub)
            row_kinds.append("sub")
    last_top = top
    display_rows.append(r)
    row_kinds.append("data")
if last_top is not None and last_top in groups_by_top:
    sub = dict(groups_by_top[last_top])
    sub["sg_a_manu"] = f"⮕ Total {last_top}"
    sub["department"] = ""
    display_rows.append(sub)
    row_kinds.append("sub")
g = dict(report["grand_total"])
g["sg_a_manu"] = "GRAND TOTAL"
g["department"] = ""
display_rows.append(g)
row_kinds.append("grand")

display_df = pd.DataFrame(display_rows)[cols].rename(
    columns={"sg_a_manu": "SG&A / MANU", "department": "Function"}
)

# Style: highlight subtotal/grand rows
def _row_style(row):
    idx = row.name
    kind = row_kinds[idx] if idx < len(row_kinds) else "data"
    if kind == "grand":
        return ["background-color:#1F3864; color:white; font-weight:bold;"] * len(row)
    if kind == "sub":
        return ["background-color:#305496; color:white; font-weight:bold;"] * len(row)
    return [""] * len(row)


# Number formatting per column
fmt = {}
for c in cols:
    if c in HC_COLS:
        fmt[c] = "{:,.0f}"
    elif c in PCT_ABSENT_COLS or c == "% OT":
        fmt[c] = "{:.2f}%"
    elif c not in ID_COLS:
        fmt[c] = "{:,.1f}"

styler = (
    display_df.style
    .format({k.replace("sg_a_manu", "SG&A / MANU").replace("department", "Function"): v
             for k, v in fmt.items()})
    .apply(_row_style, axis=1)
)

st.dataframe(styler, use_container_width=True, hide_index=True, height=table_height)

# ---------- summary metrics ----------
gt = report["grand_total"]
st.markdown("### Summary")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Headcount (Total)", int(gt.get("Total HC", 0)),
          help=f'PER {int(gt.get("Permanent HC",0))} + SUB {int(gt.get("Contract HC",0))} + TEM {int(gt.get("TP HC",0))}')
m2.metric(f"Working ({unit})", f'{gt.get("Total Working Hrs",0):,.1f}')
m3.metric(f"Absent excl AL ({unit})", f'{gt.get("Total Absent Hrs",0):,.1f}',
          delta=f'{gt.get("% Total Absent",0):.2f}%', delta_color="off")
m4.metric(f"OT total ({unit})", f'{gt.get("Total OT",0):,.1f}',
          delta=f'{gt.get("% OT",0):.2f}%', delta_color="off")
m5.metric(f"Annual Leave ({unit})", f'{gt.get("Total AL",0):,.1f}')

# ---------- exports ----------
st.markdown("---")
st.markdown("### Export")
e1, e2, e3 = st.columns([1, 1, 4])

xls_bytes = exports.to_excel_bytes(
    report, include_al=include_al,
    include_sick=include_sick, include_business=include_business,
    include_without_pay=include_without_pay,
    username=effective_user,
)
e1.download_button(
    label="⬇️ Excel (.xlsx)",
    data=xls_bytes,
    file_name=f"HR_Report_{period}_{unit}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

png_bytes = exports.to_png_bytes(
    report, include_al=include_al,
    include_sick=include_sick, include_business=include_business,
    include_without_pay=include_without_pay,
)
if png_bytes:
    e2.download_button(
        label="🖼️ PNG image",
        data=png_bytes,
        file_name=f"HR_Report_{period}_{unit}.png",
        mime="image/png",
        use_container_width=True,
    )
else:
    e2.button("🖼️ PNG image", disabled=True, use_container_width=True,
              help="PNG export needs `kaleido` installed (see requirements.txt)")
