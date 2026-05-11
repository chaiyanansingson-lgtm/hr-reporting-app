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
require_login(capability="orgchart.view")
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


# ── Visual Chart view (graphviz - Visio-style with photos, dept headers, color schemes) ──
with tab_visual:
    import os, tempfile, html as _html
    import subprocess, base64, mimetypes, re as _re
    st.markdown("#### 🎨 Visual organizational chart")

    # ── Render helper: inline photos as data: URIs so the browser can display them ──
    # The default `st.graphviz_chart` leaves <image xlink:href="/tmp/..."/> references
    # pointing at server-side file paths, which the browser cannot load. We call the
    # `dot` binary ourselves, then post-process the SVG to replace each absolute file
    # path with a base64-encoded data URI of the file's bytes.
    def _render_dot_with_inline_photos(dot_source: str) -> str:
        proc = subprocess.run(
            ["dot", "-Tsvg"],
            input=dot_source.encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=30,
        )
        svg = proc.stdout.decode("utf-8", errors="replace")

        def _inline(match):
            attr_quote = match.group(1)
            href = match.group(2)
            if href.startswith(("http://", "https://", "data:")):
                return match.group(0)
            if not os.path.isabs(href) or not os.path.exists(href):
                return match.group(0)
            try:
                with open(href, "rb") as f:
                    data = f.read()
                mime = mimetypes.guess_type(href)[0] or "image/jpeg"
                b64 = base64.b64encode(data).decode("ascii")
                return f'xlink:href={attr_quote}data:{mime};base64,{b64}{attr_quote}'
            except Exception:
                return match.group(0)

        svg = _re.sub(r'xlink:href=(["\'])([^"\']+)\1', _inline, svg)
        # Strip explicit width/height so CSS can make the SVG responsive
        svg = _re.sub(r'<svg([^>]*?)\swidth="[^"]+"', r'<svg\1', svg, count=1)
        svg = _re.sub(r'<svg([^>]*?)\sheight="[^"]+"', r'<svg\1', svg, count=1)
        return svg

    st.caption(
        "Visio-style top-down hierarchy with employee photos, name (Surname + first letter), "
        "position, level, and reporting lines (solid = direct, dashed = dotted-line). "
        "Boxes are color-coded — switch the color scheme below to view by **role** or **department**. "
        "Admin can customize the colors in **⚙️ Settings → 🎨 Org Chart Style**."
    )

    # ------ Helper: format short name "Nicholas D. (Nicky)"
    def _format_short_name(emp_name: str, nickname: str) -> str:
        # Strip prefix
        nm = (emp_name or "").strip()
        for px in ("Mr.", "Ms.", "Mrs.", "Miss "):
            if nm.startswith(px):
                nm = nm[len(px):].strip()
                break
        parts = nm.split()
        if len(parts) >= 2:
            first = " ".join(parts[:-1])  # everything except last word
            last_initial = parts[-1][0].upper() + "."
            short = f"{first} {last_initial}"
        else:
            short = nm
        nick = (nickname or "").strip()
        if nick:
            short = f"{short} ({nick})"
        return short

    # ------ Filters
    fc1, fc2, fc3 = st.columns([2, 2, 2])
    root_picker_options = {f"⭐ Whole company ({len(employees)} people)": None}
    for r in sorted(roots, key=lambda x: -(x.get("level") or 0)):
        root_picker_options[f"{r['emp_name']} — {r.get('title') or '?'}"] = r["emp_no"]
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

    chart_max_depth = fc2.slider("Levels deep", 1, 10, 5)

    color_scheme = fc3.selectbox(
        "Color scheme",
        ["By role (Mgr/Sup/Leader)", "By department"],
        help="Pick how box colors are assigned. Admin defines the colors in Settings.",
    )

    # ------ Display options
    co1, co2, co3 = st.columns(3)
    show_photos = co1.toggle("Show photos", value=True,
                              help="Embed employee photos in each box (uploaded by admin in Employees page)")
    show_titles = co2.toggle("Show titles", value=True)
    show_dept_headers = co3.toggle("Show department headers", value=True,
                                    help="Wrap employees in same dept inside a labeled cluster (Visio-style)")

    # ------ Compute visible set (root + descendants up to depth)
    def _walk_down(emp_no: str, depth: int, max_d: int, accumulator: set):
        if depth > max_d or emp_no in accumulator:
            return
        accumulator.add(emp_no)
        for child in children_of.get(emp_no, []):
            _walk_down(child["emp_no"], depth + 1, max_d, accumulator)

    visible: set[str] = set()
    if chart_root is None:
        for r in roots:
            _walk_down(r["emp_no"], 0, chart_max_depth, visible)
    else:
        _walk_down(chart_root, 0, chart_max_depth, visible)

    visible_emps = [e for e in employees if e["emp_no"] in visible]

    if not visible_emps:
        st.warning("No employees to display with current filters.")
    else:
        st.caption(f"Rendering **{len(visible_emps)}** employees, max **{chart_max_depth}** levels deep.")

        # ------ Resolve color rules
        ROLE_DEFAULTS = {
            "Mgr.":     {"fill": "#715091", "font": "#FFFFFF", "border": "#4A2F62"},
            "Sup.":     {"fill": "#009ADE", "font": "#FFFFFF", "border": "#0073A8"},
            "Leader":   {"fill": "#E31D93", "font": "#FFFFFF", "border": "#A8126B"},
            "(staff)":  {"fill": "#F3F4F6", "font": "#1F2937", "border": "#D1D5DB"},
        }
        admin_role_colors = db.get_org_chart_colors("role")
        admin_dept_colors = db.get_org_chart_colors("dept")

        DEFAULT_DEPT_PALETTE = [
            "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899",
            "#14B8A6", "#F97316", "#6366F1", "#84CC16", "#06B6D4", "#A855F7",
        ]

        def _color_for_emp(e: dict) -> dict:
            """Return {fill, font, border} for an employee, based on the active scheme."""
            if color_scheme.startswith("By role"):
                role = e.get("is_mgr_role") or "(staff)"
                if role in admin_role_colors and admin_role_colors[role].get("fill"):
                    return admin_role_colors[role]
                return ROLE_DEFAULTS.get(role, ROLE_DEFAULTS["(staff)"])
            else:
                # By department
                dept = (e.get("dept_by_location") or "").strip() or "(no dept)"
                if dept in admin_dept_colors and admin_dept_colors[dept].get("fill"):
                    return admin_dept_colors[dept]
                # Auto-assign from palette
                idx = sum(ord(c) for c in dept) % len(DEFAULT_DEPT_PALETTE)
                fill = DEFAULT_DEPT_PALETTE[idx]
                # Compute readable text color
                h = fill.lstrip("#")
                lum = (0.299 * int(h[0:2], 16) + 0.587 * int(h[2:4], 16) + 0.114 * int(h[4:6], 16)) / 255
                return {"fill": fill, "font": "#FFFFFF" if lum < 0.6 else "#1F2937", "border": fill}

        # ------ Write photos to a temp directory (graphviz needs file paths)
        photo_paths: dict[str, str] = {}
        temp_dir = None
        if show_photos:
            temp_dir = tempfile.mkdtemp(prefix="orgphotos_")
            for e in visible_emps:
                blob = db.get_employee_photo(e["emp_no"])
                if blob:
                    p = os.path.join(temp_dir, f"emp_{e['emp_no']}.jpg")
                    try:
                        with open(p, "wb") as f:
                            f.write(blob)
                        photo_paths[e["emp_no"]] = p
                    except Exception:
                        pass

        # ------ Build the DOT
        dot_lines = [
            'digraph OrgChart {',
            '  rankdir=TB;',
            '  graph [splines=ortho, nodesep=0.35, ranksep=0.55, bgcolor="transparent", fontname="Arial"];',
            '  node [shape=box, style="filled,rounded", fontname="Arial", margin="0.10,0.08", penwidth=1.5];',
            '  edge [color="#6B7280", arrowsize=0.6, penwidth=1.2];',
            '  compound=true;',
            '',
        ]

        def _node_label(e: dict) -> str:
            """Build an HTML-like graphviz label with photo + name + title + level."""
            short_name = _format_short_name(e.get("emp_name") or "?", e.get("nickname") or "")
            title = e.get("title") or ""
            level = e.get("level")
            role = e.get("is_mgr_role") or ""

            # Use HTML label syntax (graphviz supports <TABLE>...</TABLE>)
            rows = []
            # Photo row (if available)
            if show_photos and e["emp_no"] in photo_paths:
                p = photo_paths[e["emp_no"]].replace("\\", "/")
                rows.append(
                    f'<TR><TD FIXEDSIZE="TRUE" WIDTH="62" HEIGHT="62" '
                    f'CELLPADDING="0"><IMG SRC="{p}" SCALE="TRUE"/></TD></TR>'
                )
            # Name row
            rows.append(
                f'<TR><TD CELLPADDING="2"><FONT POINT-SIZE="10"><B>'
                f'{_html.escape(short_name)}</B></FONT></TD></TR>'
            )
            # Title row
            if show_titles and title:
                rows.append(
                    f'<TR><TD CELLPADDING="1"><FONT POINT-SIZE="9">'
                    f'{_html.escape(title)}</FONT></TD></TR>'
                )
            # Level + role row (small subtle line)
            badge_bits = []
            if level is not None and level != "":
                badge_bits.append(f"L{level}")
            if role:
                badge_bits.append(role)
            if badge_bits:
                rows.append(
                    f'<TR><TD CELLPADDING="1"><FONT POINT-SIZE="8" COLOR="#666666">'
                    f'{_html.escape(" · ".join(str(b) for b in badge_bits))}</FONT></TD></TR>'
                )
            html_label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">{"".join(rows)}</TABLE>>'
            return html_label

        def _emit_node(e: dict, indent: str = "  ") -> str:
            colors = _color_for_emp(e)
            return (
                f'{indent}"{e["emp_no"]}" [label={_node_label(e)}, '
                f'fillcolor="{colors["fill"]}", color="{colors["border"]}", '
                f'fontcolor="{colors["font"]}"];'
            )

        # Decide layout: clusters by department or flat
        if show_dept_headers:
            # Group visible employees by department
            by_dept: dict[str, list[dict]] = {}
            for e in visible_emps:
                d = (e.get("dept_by_location") or "").strip() or "(no dept)"
                by_dept.setdefault(d, []).append(e)

            for i, (dept, members) in enumerate(sorted(by_dept.items())):
                # Cluster header
                dept_color = admin_dept_colors.get(dept, {}).get("fill", "#F3F4F6")
                dept_font = admin_dept_colors.get(dept, {}).get("font", "#1F2937")
                # Use a slightly darker variant for the cluster bg if main is light
                dot_lines.append(f'  subgraph cluster_dept_{i} {{')
                dot_lines.append(f'    label=<<B>{_html.escape(dept)}</B>>;')
                dot_lines.append(f'    style="rounded,filled";')
                dot_lines.append(f'    fillcolor="#FAFBFC";')
                dot_lines.append(f'    color="{dept_color}";')
                dot_lines.append(f'    fontcolor="{dept_font}";')
                dot_lines.append(f'    fontsize=12;')
                dot_lines.append(f'    margin=12;')
                for emp in members:
                    dot_lines.append(_emit_node(emp, indent="    "))
                dot_lines.append('  }')
        else:
            for emp in visible_emps:
                dot_lines.append(_emit_node(emp))

        # ------ Edges: solid lines for direct manager, dashed for dotted-line
        for e in visible_emps:
            mgr = e.get("manager_emp_no")
            if mgr and mgr in visible:
                dot_lines.append(f'  "{mgr}" -> "{e["emp_no"]}";')
            # Dotted-line managers
            dotted = db.get_dotted_managers(e["emp_no"])
            for dm in dotted:
                if dm and dm in visible:
                    dot_lines.append(
                        f'  "{dm}" -> "{e["emp_no"]}" '
                        f'[style=dashed, color="#9CA3AF", arrowsize=0.5, '
                        f'constraint=false, penwidth=1.0];'
                    )

        dot_lines.append("}")
        dot_source = "\n".join(dot_lines)

        try:
            svg = _render_dot_with_inline_photos(dot_source)
            # Wrap in a responsive container so wide charts can scroll horizontally
            st.markdown(
                f'<div style="overflow-x:auto; width:100%;">{svg}</div>',
                unsafe_allow_html=True,
            )
        except subprocess.TimeoutExpired:
            st.error("⏱️ The chart took too long to render. Try narrowing the branch or reducing depth.")
            with st.expander("Show DOT source (for debugging)"):
                st.code(dot_source, language="dot")
        except subprocess.CalledProcessError as ex:
            st.error(
                f"Could not render the visual chart: dot returned {ex.returncode}. "
                "The Tree and Table views above still work."
            )
            with st.expander("Show DOT source (for debugging)"):
                st.code(dot_source, language="dot")
            if ex.stderr:
                with st.expander("Show dot stderr"):
                    st.code(ex.stderr.decode("utf-8", errors="replace"))
        except FileNotFoundError:
            # graphviz binary missing — fall back to Streamlit's built-in renderer
            # (loses photos but keeps the chart)
            st.warning("⚠️ Graphviz binary not found on this server. Falling back to the default renderer — photos may not display.")
            st.graphviz_chart(dot_source, use_container_width=True)
        except Exception as ex:
            st.error(
                f"Could not render the visual chart: {ex}. "
                "The Tree and Table views above still work."
            )
            with st.expander("Show DOT source (for debugging)"):
                st.code(dot_source, language="dot")

        # Legend
        st.markdown("---")
        leg1, leg2 = st.columns(2)
        with leg1:
            st.markdown("**Line types / ประเภทเส้นเชื่อม:**")
            st.markdown("- **Solid line** ─── Direct report (รายงานตรง)")
            st.markdown("- **Dashed line** ╌╌╌ Dotted-line / matrix report (รายงานสายประ)")
        with leg2:
            if color_scheme.startswith("By role"):
                st.markdown("**Color by role / สีตามบทบาท:**")
                for role in ["Mgr.", "Sup.", "Leader", "(staff)"]:
                    c = admin_role_colors.get(role, {}).get("fill") or ROLE_DEFAULTS[role]["fill"]
                    st.markdown(
                        f"<span style='display:inline-block;width:14px;height:14px;"
                        f"background:{c};border-radius:3px;margin-right:6px;vertical-align:middle'></span>"
                        f"**{role}**", unsafe_allow_html=True,
                    )
            else:
                st.markdown("**Color by department / สีตามแผนก:**")
                st.caption("Each department has its own color — admin sets these in Settings.")

        # Download as DOT file
        st.download_button(
            "⬇️ Download chart as DOT file",
            data=dot_source.encode("utf-8"),
            file_name=f"org_chart_{chart_root or 'all'}.dot",
            mime="text/vnd.graphviz",
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
