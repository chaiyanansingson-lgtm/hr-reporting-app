"""
Org Chart page — visualize the company structure.

Three views:
- Tree view (interactive expandable): traverse from a chosen root downward
- Table view: flat list with a "reports to" column, easy to filter
- By department: group employees by Dept by Location

Built from the `employees_extended` table populated by the Employee MASTER
import. Uses the manager_emp_no column to resolve hierarchy.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import db
from lib.page_utils import require_login, page_header
from lib.i18n import t

st.set_page_config(page_title="Org Chart", page_icon="🌳", layout="wide")
require_login()
page_header(title_key="org_chart_title", subtitle_key="org_chart_subtitle")

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
employees = db.list_employees_with_extended()
if not employees:
    st.warning(t("no_org_data"))
    st.stop()

# Build lookup tables
by_no = {e["emp_no"]: e for e in employees}
children_of: dict[str, list[dict]] = {}
for e in employees:
    mgr = e.get("manager_emp_no") or ""
    children_of.setdefault(mgr, []).append(e)
# Sort children by emp_name
for k in children_of:
    children_of[k].sort(key=lambda x: (x.get("emp_name") or ""))

# Roots = anyone whose manager_emp_no is empty or doesn't resolve to a known emp
roots = []
for e in employees:
    mgr = e.get("manager_emp_no") or ""
    if not mgr or mgr not in by_no:
        roots.append(e)
roots.sort(key=lambda x: (-(x.get("level") or 0), x.get("emp_name") or ""))


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _emp_chip(e: dict) -> str:
    """Inline 1-line summary of an employee."""
    nick = f" ({e['nickname']})" if e.get("nickname") else ""
    title = e.get("title") or ""
    role_badge = ""
    if e.get("is_mgr_role"):
        color = {"Mgr.": "#715091", "Sup.": "#009ADE", "Leader": "#E31D93"}.get(
            e.get("is_mgr_role", ""), "#6B7280")
        role_badge = (f"&nbsp;<span style='background:{color};color:white;"
                       f"padding:1px 8px;border-radius:4px;font-size:0.75rem;'>"
                       f"{e['is_mgr_role']}</span>")
    return (f"<b>{e.get('emp_name','')}</b>{nick}{role_badge}"
             f"<br><small style='color:#6B7280'>{title} · "
             f"{e.get('dept_by_location') or ''} · #{e['emp_no']}</small>")


def _render_tree_branch(emp: dict, depth: int = 0, max_depth: int = 8):
    """Render an expandable branch starting at this employee."""
    if depth > max_depth:
        return

    reports = children_of.get(emp["emp_no"], [])
    label_html = _emp_chip(emp)
    n_reports = len(reports)

    # Use expander when there are reports; otherwise just render the chip
    if n_reports:
        with st.expander(f"  {emp.get('emp_name','')}  ·  {emp.get('title') or ''}  "
                          f"({n_reports} {t('direct_reports')})",
                          expanded=(depth == 0)):
            st.markdown(label_html, unsafe_allow_html=True)
            st.markdown("")
            for child in reports:
                _render_tree_branch(child, depth + 1, max_depth)
    else:
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• {label_html}", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# View tabs
# ---------------------------------------------------------------------------

tab_tree, tab_table, tab_dept = st.tabs([
    f"🌳 {t('org_view_tree')}",
    f"📋 {t('org_view_table')}",
    f"🏢 {t('org_view_dept')}",
])

# ── Tree view ──
with tab_tree:
    st.markdown(f"#### Top-of-org / starting points")
    if not roots:
        st.info("No org tree root found (every employee has a manager who is also an employee).")
    else:
        # Let user pick which root to expand
        root_options = {f"{r['emp_name']} — {r.get('title') or '?'}  (#{r['emp_no']})": r["emp_no"]
                         for r in roots}
        # Also offer "all roots"
        all_roots_label = f"⭐  All {len(roots)} top-level people"
        pick = st.selectbox("Start from", [all_roots_label] + list(root_options.keys()))

        starts = roots if pick == all_roots_label else [by_no[root_options[pick]]]

        max_depth = st.slider("Maximum depth to expand", 1, 8, 4)

        for r in starts:
            _render_tree_branch(r, depth=0, max_depth=max_depth)

# ── Table view ──
with tab_table:
    rows = []
    for e in employees:
        mgr_no = e.get("manager_emp_no") or ""
        mgr = by_no.get(mgr_no)
        rows.append({
            "Emp #": e["emp_no"],
            "Name": e.get("emp_name", ""),
            "Nickname": e.get("nickname") or "",
            "Title": e.get("title") or "",
            "Department": e.get("dept_by_location") or "",
            "Cost Centre": e.get("cost_centre_name") or "",
            "Level": e.get("level") or "",
            "Direct/Indirect": e.get("d_in") or "",
            "Mgr role": e.get("is_mgr_role") or "",
            t("reports_to"): mgr.get("emp_name", "") if mgr else (e.get("manager_name") or ""),
            "Mgr Emp #": mgr_no,
            "Status": e.get("status") or "",
            "Joined": e.get("joined_date") or "",
        })
    df = pd.DataFrame(rows)

    f1, f2, f3 = st.columns(3)
    dept_filter = f1.multiselect("Filter by department",
                                   sorted(df["Department"].dropna().unique().tolist()))
    role_filter = f2.multiselect("Filter by Mgr role",
                                   sorted(df["Mgr role"].dropna().unique().tolist()))
    name_filter = f3.text_input("Search name / title", "")

    fdf = df.copy()
    if dept_filter:
        fdf = fdf[fdf["Department"].isin(dept_filter)]
    if role_filter:
        fdf = fdf[fdf["Mgr role"].isin(role_filter)]
    if name_filter:
        nf = name_filter.lower()
        fdf = fdf[
            fdf["Name"].str.lower().str.contains(nf, na=False)
            | fdf["Title"].str.lower().str.contains(nf, na=False)
            | fdf["Nickname"].str.lower().str.contains(nf, na=False)
        ]

    st.caption(f"Showing {len(fdf):,} of {len(df):,} employees")
    st.dataframe(fdf, use_container_width=True, hide_index=True, height=600)

    csv = fdf.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv,
                        file_name="org_chart.csv", mime="text/csv")

# ── By department ──
with tab_dept:
    by_dept: dict[str, list[dict]] = {}
    for e in employees:
        d = e.get("dept_by_location") or "(no department)"
        by_dept.setdefault(d, []).append(e)

    sorted_depts = sorted(by_dept.keys())

    # Summary metrics
    st.markdown(f"#### {len(sorted_depts)} departments, {len(employees)} employees")
    mcols = st.columns(4)
    for i, d in enumerate(sorted_depts[:4]):
        mcols[i].metric(d, len(by_dept[d]))

    # Each dept as an expander
    for d in sorted_depts:
        members = by_dept[d]
        members.sort(key=lambda x: (-(x.get("level") or 0), x.get("emp_name") or ""))
        with st.expander(f"🏢 **{d}** — {len(members)} people", expanded=False):
            tdf = pd.DataFrame([{
                "Emp #": m["emp_no"],
                "Name": m.get("emp_name", ""),
                "Nick": m.get("nickname") or "",
                "Title": m.get("title") or "",
                "Level": m.get("level") or "",
                "Mgr role": m.get("is_mgr_role") or "",
                t("reports_to"): m.get("manager_name") or "",
            } for m in members])
            st.dataframe(tdf, use_container_width=True, hide_index=True)
