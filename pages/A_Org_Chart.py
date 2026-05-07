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

tab_tree, tab_visual, tab_table, tab_dept = st.tabs([
    f"🌳 {t('org_view_tree')}",
    f"🎨 Visual Chart",
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


# ── Visual Chart view (graphviz - Visio-style box-and-line layout) ──
with tab_visual:
    st.markdown("#### 🎨 Visual organizational chart")
    st.caption(
        "Top-down hierarchy with boxes and connecting lines — like the Visio "
        "format. Boxes are color-coded by role: 🟪 Manager, 🟦 Supervisor, "
        "🟥 Leader, ⬜ regular staff. Use mouse wheel to zoom, drag to pan."
    )

    # Filters
    fc1, fc2, fc3 = st.columns([2, 2, 2])
    # Pick a root (top of branch to display)
    root_picker_options = {f"⭐ Whole company ({len(employees)} people)": None}
    for r in sorted(roots, key=lambda x: -(x.get("level") or 0)):
        root_picker_options[f"{r['emp_name']} — {r.get('title') or '?'}"] = r["emp_no"]
    # Also add managers as possible starting points
    for e in sorted(employees, key=lambda x: x.get("emp_name") or ""):
        if e.get("is_mgr_role") in ("Mgr.", "Sup."):
            label = f"  ↳ {e['emp_name']} — {e.get('title') or '?'} ({e.get('is_mgr_role')})"
            if e["emp_no"] not in [v for v in root_picker_options.values() if v]:
                root_picker_options[label] = e["emp_no"]

    chart_root_label = fc1.selectbox(
        "Show branch starting from", list(root_picker_options.keys()),
        help="Pick the company root or a specific manager to show only their team.",
    )
    chart_root = root_picker_options[chart_root_label]

    chart_max_depth = fc2.slider("Levels deep", 1, 10, 5,
                                  help="How many levels of reports to show below the root")
    show_titles = fc3.toggle("Show titles", value=True,
                              help="Include job titles in each box (turn off for compact view)")

    # Build the set of employees to render (chart_root + descendants up to max depth)
    def _collect_descendants(root_emp_no: str | None, max_d: int) -> set[str]:
        if root_emp_no is None:
            # Whole company — start from all roots
            collected = set()
            for r in roots:
                _walk_down(r["emp_no"], 0, max_d, collected)
            return collected
        else:
            collected = set()
            _walk_down(root_emp_no, 0, max_d, collected)
            return collected

    def _walk_down(emp_no: str, depth: int, max_d: int, accumulator: set[str]):
        if depth > max_d or emp_no in accumulator:
            return
        accumulator.add(emp_no)
        for child in children_of.get(emp_no, []):
            _walk_down(child["emp_no"], depth + 1, max_d, accumulator)

    visible = _collect_descendants(chart_root, chart_max_depth)
    visible_emps = [e for e in employees if e["emp_no"] in visible]

    if not visible_emps:
        st.warning("No employees to display with current filters.")
    else:
        st.caption(f"Rendering **{len(visible_emps)}** employees, max **{chart_max_depth}** levels deep.")

        # Color scheme: matches the Anca CI palette
        ROLE_COLORS = {
            "Mgr.":   {"fill": "#715091", "font": "white", "border": "#4A2F62"},
            "Sup.":   {"fill": "#009ADE", "font": "white", "border": "#0073A8"},
            "Leader": {"fill": "#E31D93", "font": "white", "border": "#A8126B"},
            "":       {"fill": "#F3F4F6", "font": "#1F2937", "border": "#D1D5DB"},
        }

        # Build DOT graph
        dot_lines = [
            'digraph OrgChart {',
            '  rankdir=TB;',  # Top to Bottom
            '  graph [splines=ortho, nodesep=0.35, ranksep=0.55, bgcolor="transparent"];',
            '  node [shape=box, style="filled,rounded", fontname="Arial", fontsize=10, '
                  'margin="0.18,0.10", penwidth=1.5];',
            '  edge [color="#9CA3AF", arrowsize=0.6, penwidth=1.0];',
            '',
        ]

        for e in visible_emps:
            role = e.get("is_mgr_role") or ""
            colors = ROLE_COLORS.get(role, ROLE_COLORS[""])
            name = (e.get("emp_name") or "?").replace('"', "'")
            # Strip Mr./Ms./Mrs. prefix for compactness
            for px in ("Mr.", "Ms.", "Mrs.", "Miss "):
                if name.startswith(px):
                    name = name[len(px):].strip()
                    break
            nick = e.get("nickname") or ""
            title = e.get("title") or ""

            # Build label: Name (Nick)\nTitle\n[Role badge]
            parts = [name]
            if nick:
                parts[0] += f" ({nick})"
            if show_titles and title:
                # Word-wrap long titles
                if len(title) > 22:
                    words = title.split()
                    lines, cur = [], ""
                    for w in words:
                        if len(cur) + len(w) + 1 > 22:
                            lines.append(cur.strip())
                            cur = w + " "
                        else:
                            cur += w + " "
                    if cur.strip():
                        lines.append(cur.strip())
                    title = "\\n".join(lines)
                parts.append(title)
            label = "\\n".join(parts).replace('"', "'")

            dot_lines.append(
                f'  "{e["emp_no"]}" [label="{label}", '
                f'fillcolor="{colors["fill"]}", fontcolor="{colors["font"]}", '
                f'color="{colors["border"]}"];'
            )

        # Add edges (manager -> employee)
        for e in visible_emps:
            mgr = e.get("manager_emp_no")
            if mgr and mgr in visible:
                dot_lines.append(f'  "{mgr}" -> "{e["emp_no"]}";')

        dot_lines.append("}")
        dot_source = "\n".join(dot_lines)

        try:
            st.graphviz_chart(dot_source, use_container_width=True)
        except Exception as ex:
            st.error(
                "Could not render the visual chart. Streamlit Cloud may not have "
                "graphviz installed. The Tree and Table views above still work."
            )
            with st.expander("Show DOT source (for debugging)"):
                st.code(dot_source, language="dot")

        # Download as DOT file (can be opened in Visio/Graphviz/draw.io)
        st.download_button(
            "⬇️ Download chart as DOT file",
            data=dot_source.encode("utf-8"),
            file_name=f"org_chart_{chart_root or 'all'}.dot",
            mime="text/vnd.graphviz",
            help="Open in Graphviz, draw.io, or any DOT-compatible tool to print or edit.",
        )


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
