"""
Configuration page — accessible to ALL logged-in users.

Two edit modes:
  - "Master Settings" (admin only): edits affect the main DB and ALL users.
  - "My Personal Settings" (everyone): edits go to user_overrides table and
    only affect THIS user's calculations. Master DB is untouched.

The same UI tabs (Holidays / Cost Groups / Hour Rules / KPI Targets /
Per-Month Overrides) work in either mode; saves route to the right place.

Non-admin users can ONLY use Personal Mode (the Master toggle is hidden).
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import db, parsers
from lib.page_utils import require_login, page_header, is_admin

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
require_login(capability="report.edit_config")  # any logged-in user (admin or non-admin) can access
page_header(title_key="config_title", subtitle_key="config_subtitle")

USERNAME = st.session_state.get("username", "")
ADMIN = is_admin()

# ---------------------------------------------------------------------------
# Top-level mode toggle: Master vs Personal
# ---------------------------------------------------------------------------
if ADMIN:
    mode = st.radio(
        "📌 Edit mode",
        ["🌐  Master Settings (affects ALL users)",
         "👤  My Personal Settings (only affects my view)"],
        horizontal=True,
        help="Master = edits the company-wide defaults stored in the database. "
             "Personal = edits a per-user override; the master DB stays untouched.",
    )
    PERSONAL_MODE = mode.startswith("👤")
else:
    PERSONAL_MODE = True
    st.info(
        "👤 You are editing **your personal settings**. Changes here only affect "
        "what YOU see in Reports & Charts. The master database (and other users) "
        "are unaffected. Admins can switch to Master Settings mode."
    )

if PERSONAL_MODE and USERNAME:
    # Show what overrides this user already has
    existing = db.list_user_overrides(USERNAME)
    if existing:
        chips = " ".join(f"`{e}`" for e in existing)
        st.caption(f"You currently have personal overrides for: {chips}")

st.markdown("---")

periods = db.list_periods()

t1, t2, t3, t4, t5, t6 = st.tabs(
    ["📅 Holidays", "🗂️ Cost Groups", "⏱️ Hour rules", "🎯 KPI Targets",
     "📆 Per-Month Overrides", "🎨 Org Chart Style"]
)


# ============================================================================
# Helpers
# ============================================================================

def _personal_save_msg():
    return ("✅ Saved to **your personal overrides**. Master database is unchanged. "
            "Refresh the Report or Charts page to see the effect.")


# ============================================================================
# 📅 Holidays tab
# ============================================================================
with t1:
    st.markdown("### Holidays")

    if PERSONAL_MODE:
        st.caption(
            "📝 **You can freely edit your personal holiday list below.** "
            "Add new rows by typing in the bottom blank row. "
            "Delete by selecting a row and pressing Delete. "
            "Click 'Save changes' when done."
        )
        # Source data: user's override if exists, else copy of master as starting point
        ov = db.get_user_override(USERNAME, "holidays")
        if ov is None:
            holidays = db.list_holidays()
            st.caption("(Starting from the master holiday list — your edits will be saved separately.)")
        else:
            holidays = ov
    else:
        st.caption(
            "Master holidays affect every user's working-day calculation. "
            "Add rows by typing in the bottom blank line, delete by selecting + Delete key."
        )
        holidays = db.list_holidays()

    df = pd.DataFrame(holidays) if holidays else pd.DataFrame(
        columns=["holiday_date", "holiday_name"])
    if not df.empty:
        df["holiday_date"] = pd.to_datetime(df["holiday_date"]).dt.date

    edited = st.data_editor(
        df.rename(columns={"holiday_date": "Date", "holiday_name": "Name"}),
        num_rows="dynamic",
        use_container_width=True,
        key=f"holiday_editor_{'p' if PERSONAL_MODE else 'm'}",
        column_config={
            "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD",
                                                 required=True),
            "Name": st.column_config.TextColumn("Name", required=False,
                                                 help="Holiday name (Thai or English)"),
        },
        hide_index=True,
    )

    cA, cB, cC = st.columns([1.5, 1.5, 4])
    if cA.button("💾 Save changes", type="primary", key=f"hd_save_{PERSONAL_MODE}"):
        new_list = []
        for _, row in edited.iterrows():
            d = row["Date"]
            if pd.isna(d):
                continue
            if hasattr(d, "isoformat"):
                d = d.isoformat()
            new_list.append({
                "holiday_date": str(d),
                "holiday_name": (str(row["Name"]) if not pd.isna(row["Name"]) else "")
            })
        if PERSONAL_MODE:
            db.set_user_override(USERNAME, "holidays", new_list)
            st.success(_personal_save_msg())
        else:
            old = {h["holiday_date"]: h["holiday_name"] for h in holidays}
            new = {h["holiday_date"]: h["holiday_name"] for h in new_list}
            for d in old:
                if d not in new:
                    db.delete_holiday(d)
            for d, n in new.items():
                db.upsert_holiday(d, n)
            st.success("✅ Master holidays saved.")
        st.rerun()

    if PERSONAL_MODE and db.get_user_override(USERNAME, "holidays") is not None:
        if cB.button("↺ Reset to master", key="hd_reset"):
            db.clear_user_override(USERNAME, "holidays")
            st.success("Your personal holiday override removed — using master list now.")
            st.rerun()

    if not PERSONAL_MODE:
        with st.expander("Bulk import from Excel"):
            f = st.file_uploader("Upload holidays .xlsx", type=["xlsx"], key="bulk_hd")
            if f and st.button("Import", key="hd_bulk_btn"):
                n = parsers.import_holidays(f)
                st.success(f"Imported / updated {n} holidays.")
                st.rerun()


# ============================================================================
# 🗂️ Cost Groups tab
# ============================================================================
with t2:
    st.markdown("### Cost-Group mapping")

    cgs_master = db.list_cost_groups()

    if PERSONAL_MODE:
        st.caption(
            "📝 **Personally reassign cost codes to different top groups** for your "
            "own view. Useful when you want to see a different rollup (e.g. group "
            "all production codes together). Cost code and Function name come from "
            "the master list and cannot be changed here."
        )
        ov = db.get_user_override(USERNAME, "cost_group_tops") or {}
        # Build display: master CG with user's overrides applied
        view_rows = []
        for cg in cgs_master:
            user_top = ov.get(cg["code"], {}).get("sg_a_manu", cg["sg_a_manu"])
            user_sort = ov.get(cg["code"], {}).get("sort_order", cg["sort_order"])
            view_rows.append({
                "Cost Code": cg["code"],
                "Function": cg["department"],
                "Top Group (yours)": user_top,
                "Sort": user_sort,
                "Master Top Group": cg["sg_a_manu"],
            })
        df_view = pd.DataFrame(view_rows)
        edited = st.data_editor(
            df_view, use_container_width=True, hide_index=True, key="cg_editor_p",
            disabled=["Cost Code", "Function", "Master Top Group"],
            column_config={
                "Top Group (yours)": st.column_config.TextColumn(
                    "Top Group (yours)",
                    help="Type any name. Master Top Group column shows what admin set."),
                "Sort": st.column_config.NumberColumn(
                    "Sort", default=0, step=1,
                    help="Lower = appears first in report."),
            },
        )
        if st.button("💾 Save my cost-group overrides", type="primary", key="cg_save_p"):
            new_ov = {}
            for _, r in edited.iterrows():
                code = str(r["Cost Code"])
                user_top = str(r["Top Group (yours)"]) if not pd.isna(r["Top Group (yours)"]) else ""
                user_sort = int(r["Sort"]) if not pd.isna(r["Sort"]) else 0
                master_top = str(r["Master Top Group"]) if not pd.isna(r["Master Top Group"]) else ""
                # Only store as override if it actually differs from master
                master_cg = next((c for c in cgs_master if c["code"] == code), None)
                if not master_cg:
                    continue
                if user_top != master_cg["sg_a_manu"] or user_sort != master_cg["sort_order"]:
                    new_ov[code] = {"sg_a_manu": user_top, "sort_order": user_sort}
            db.set_user_override(USERNAME, "cost_group_tops", new_ov)
            st.success(_personal_save_msg())
            st.rerun()
        if db.get_user_override(USERNAME, "cost_group_tops"):
            if st.button("↺ Reset to master", key="cg_reset"):
                db.clear_user_override(USERNAME, "cost_group_tops")
                st.success("Your personal cost-group override removed.")
                st.rerun()
    else:
        st.caption(
            "Map each cost code to its mid-level **Function** and a top-level **Group**. "
            "Free text fields — use any group names you like."
        )
        cg_df = pd.DataFrame(cgs_master) if cgs_master else pd.DataFrame(
            columns=["code", "department", "sg_a_manu", "sort_order"])
        if not cg_df.empty:
            used_groups = sorted(cg_df["sg_a_manu"].dropna().unique().tolist())
            if used_groups:
                chips = " ".join(f"`{g}`" for g in used_groups)
                st.caption(f"**Top groups currently in use:** {chips}")

        edited = st.data_editor(
            cg_df.rename(columns={"code": "Cost Code", "department": "Function",
                                   "sg_a_manu": "Top Group", "sort_order": "Sort"}),
            num_rows="dynamic",
            use_container_width=True,
            key="cg_editor_m",
            hide_index=True,
            column_config={
                "Cost Code": st.column_config.TextColumn("Cost Code", required=True),
                "Function": st.column_config.TextColumn("Function (Department)", required=True),
                "Top Group": st.column_config.TextColumn("Top Group", required=True),
                "Sort": st.column_config.NumberColumn("Sort", default=0, step=1),
            },
        )
        if st.button("💾 Save mapping", type="primary", key="cg_save_m"):
            old_codes = {c["code"] for c in cgs_master}
            new_codes = set()
            for _, r in edited.iterrows():
                code = r["Cost Code"]
                if pd.isna(code) or str(code).strip() == "":
                    continue
                db.upsert_cost_group(
                    str(code).strip(),
                    r["Function"] or "",
                    r["Top Group"] or "(Ungrouped)",
                    int(r["Sort"]) if not pd.isna(r["Sort"]) else 0,
                )
                new_codes.add(str(code).strip())
            for c in old_codes - new_codes:
                db.delete_cost_group(c)
            st.success("✅ Cost-group mapping saved.")
            st.rerun()


# ============================================================================
# ⏱️ Hour rules tab
# ============================================================================
with t3:
    st.markdown("### Hour rules")

    if PERSONAL_MODE:
        st.caption(
            "📝 **Override the default daily standard hours per weekday.** "
            "Useful if you want to model a different work schedule for your view. "
            "Leave blank / unchanged to keep the master value."
        )
        ov = db.get_user_override(USERNAME, "hour_config") or {}
        master_cfg = db.get_hour_config()
    else:
        st.caption(
            "These values control how the report converts between days and hours. "
            "They affect ALL users."
        )
        master_cfg = db.get_hour_config()
        ov = master_cfg

    colA, colB = st.columns(2)
    weekdays = ["monday_hours", "tuesday_hours", "wednesday_hours", "thursday_hours",
                "friday_hours", "saturday_hours", "sunday_hours"]
    labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    new_vals = {}
    with colA:
        st.markdown("#### Standard hours per weekday")
        for k, lbl in zip(weekdays, labels):
            current = ov.get(k, master_cfg.get(k, 8.0))
            help_text = (f"Master value: {master_cfg.get(k, 8.0)}" if PERSONAL_MODE
                         else "Standard hours expected on this weekday")
            new_vals[k] = st.number_input(
                lbl, min_value=0.0, max_value=24.0, value=float(current),
                step=0.5, key=f"in_{k}_{PERSONAL_MODE}", help=help_text,
            )

        st.markdown("#### Day ↔ Hour conversion")
        new_vals["hours_per_day"] = st.number_input(
            "Hours per day (when displaying in 'Days' unit)",
            min_value=0.5, max_value=24.0,
            value=float(ov.get("hours_per_day", master_cfg.get("hours_per_day", 8.0))),
            step=0.5, key=f"in_hpd_{PERSONAL_MODE}",
            help=(f"Master: {master_cfg.get('hours_per_day', 8.0)}" if PERSONAL_MODE else None),
        )

    with colB:
        st.markdown("#### OT multipliers")
        for k, lbl in [("ot1_multiplier", "OT × 1"), ("ot15_multiplier", "OT × 1.5"),
                        ("ot2_multiplier", "OT × 2"), ("ot3_multiplier", "OT × 3")]:
            new_vals[k] = st.number_input(
                lbl, min_value=0.0,
                value=float(ov.get(k, master_cfg.get(k, 1.0))),
                step=0.1, key=f"in_{k}_{PERSONAL_MODE}",
                help=(f"Master: {master_cfg.get(k, 1.0)}" if PERSONAL_MODE else None),
            )

    st.markdown("---")
    cA, cB, _ = st.columns([1.5, 1.5, 4])
    if cA.button("💾 Save hour rules", type="primary", key=f"hr_save_{PERSONAL_MODE}"):
        if PERSONAL_MODE:
            # Only save values that differ from master
            diffs = {k: v for k, v in new_vals.items()
                     if abs(float(master_cfg.get(k, 0)) - float(v)) > 1e-6}
            if diffs:
                db.set_user_override(USERNAME, "hour_config", diffs)
                st.success(_personal_save_msg())
            else:
                db.clear_user_override(USERNAME, "hour_config")
                st.info("All values match master — your override has been removed.")
        else:
            for k, v in new_vals.items():
                db.update_hour_config(k, v)
            st.success("✅ Master hour rules saved.")
        st.rerun()

    if PERSONAL_MODE and db.get_user_override(USERNAME, "hour_config"):
        if cB.button("↺ Reset to master", key="hr_reset"):
            db.clear_user_override(USERNAME, "hour_config")
            st.success("Your personal hour-config override removed.")
            st.rerun()


# ============================================================================
# 🎯 KPI Targets tab (master-only — targets are display-only metadata)
# ============================================================================
with t4:
    st.markdown("### KPI Targets")
    if PERSONAL_MODE:
        st.info(
            "KPI targets are display-only (the dashed reference lines on charts) "
            "and are managed at the master level only. Switch to Master Settings "
            "(if you're an admin) to change them."
        )
    else:
        st.caption(
            "These percentages drive the dashed target lines on Charts. "
            "Stored as decimals (0.025 = 2.5%); enter whole-number percentages here."
        )
        targets = db.get_targets()
        target_meta = [
            ("absenteeism_total", "Total Absenteeism % (excl AL)"),
            ("sick_leave",        "Sick Leave %"),
            ("business_leave",    "Business / Personal Leave %"),
            ("other_leaves",      "Other Leaves %"),
            ("without_pay",       "Without Pay %"),
            ("annual_leave",      "Annual Leave %"),
            ("ot_total",          "OT %"),
            ("turnover",          "Turnover %"),
        ]
        new_vals = {}
        c1, c2 = st.columns(2)
        for i, (k, lbl) in enumerate(target_meta):
            current_pct = float(targets.get(k, 0)) * 100
            new_vals[k] = (c1 if i % 2 == 0 else c2).number_input(
                f"{lbl}", min_value=0.0, max_value=100.0,
                value=current_pct, step=0.1, key=f"tgt_{k}",
            )
        if st.button("💾 Save targets", type="primary"):
            for k, v in new_vals.items():
                db.update_target(k, v / 100)
            st.success("✅ Targets saved.")
            st.rerun()


# ============================================================================
# 📆 Per-Month Overrides tab
# ============================================================================
with t5:
    st.markdown("### Per-Month Overrides — Working Days & Daily Std Hours")

    if PERSONAL_MODE:
        st.caption(
            "📝 **Personally override the working days / daily standard hours for "
            "specific months.** Matches cells F36/F37 in your Excel report's Notes "
            "section. Affects only YOUR Standard-mode WH calculation."
        )
        existing = db.get_user_override(USERNAME, "period_overrides") or {}
        master_overrides = {p["period"]: p for p in db.list_period_overrides()}
        rows_for_editor = []
        for period, vals in existing.items():
            rows_for_editor.append({
                "Period": period,
                "Working Days": vals.get("working_days"),
                "Daily Std Hours": vals.get("daily_std_hours"),
                "Notes": vals.get("notes", ""),
            })
        if not rows_for_editor:
            rows_for_editor = [{"Period": "", "Working Days": None,
                                "Daily Std Hours": None, "Notes": ""}]

        edited = st.data_editor(
            pd.DataFrame(rows_for_editor),
            num_rows="dynamic", use_container_width=True, hide_index=True,
            key="ov_editor_p",
            column_config={
                "Period": st.column_config.TextColumn("Period (YYYY-MM)", required=True,
                                                       help="e.g. 2026-04"),
                "Working Days": st.column_config.NumberColumn(
                    "Working Days", min_value=0, max_value=31, step=1),
                "Daily Std Hours": st.column_config.NumberColumn(
                    "Daily Std Hours", min_value=0.0, max_value=24.0,
                    step=0.01, format="%.2f"),
                "Notes": st.column_config.TextColumn("Notes"),
            },
        )

        cA, cB, _ = st.columns([1.5, 1.5, 4])
        if cA.button("💾 Save my overrides", type="primary", key="ov_save_p"):
            new_overrides = {}
            for _, r in edited.iterrows():
                p = r["Period"]
                if pd.isna(p) or str(p).strip() == "":
                    continue
                p = str(p).strip()
                wd = r["Working Days"] if not pd.isna(r["Working Days"]) else None
                dh = r["Daily Std Hours"] if not pd.isna(r["Daily Std Hours"]) else None
                notes = r["Notes"] if not pd.isna(r["Notes"]) else ""
                if wd is None and dh is None:
                    continue
                new_overrides[p] = {
                    "working_days": int(wd) if wd is not None else None,
                    "daily_std_hours": float(dh) if dh is not None else None,
                    "notes": str(notes),
                }
            if new_overrides:
                db.set_user_override(USERNAME, "period_overrides", new_overrides)
            else:
                db.clear_user_override(USERNAME, "period_overrides")
            st.success(_personal_save_msg())
            st.rerun()

        if existing:
            if cB.button("↺ Reset to master", key="ov_reset"):
                db.clear_user_override(USERNAME, "period_overrides")
                st.success("Your personal period overrides removed.")
                st.rerun()

        # Show what master has, for context
        if master_overrides:
            st.caption("---")
            st.caption("**Master overrides** (applied if you have no personal override for the same period):")
            mdf = pd.DataFrame([{
                "Period": p, "Working Days": v.get("working_days"),
                "Daily Std Hours": v.get("daily_std_hours"), "Notes": v.get("notes", "")
            } for p, v in master_overrides.items()])
            st.dataframe(mdf, use_container_width=True, hide_index=True)
    else:
        # Admin / master mode
        st.caption(
            "Override the auto-computed standard working days and/or daily standard "
            "hours for a specific month. Matches cells F36/F37 in the Excel report's "
            "Notes section. Affects every user (unless they have a personal override)."
        )
        overrides = db.list_period_overrides()
        ov_df = pd.DataFrame(overrides) if overrides else pd.DataFrame(
            columns=["period", "working_days", "daily_std_hours", "notes"])

        edited_ov = st.data_editor(
            ov_df.rename(columns={"period": "Period", "working_days": "Working Days",
                                   "daily_std_hours": "Daily Std Hours", "notes": "Notes"}),
            num_rows="dynamic", use_container_width=True, hide_index=True,
            key="ov_editor_m",
            column_config={
                "Period": st.column_config.TextColumn("Period (YYYY-MM)", required=True),
                "Working Days": st.column_config.NumberColumn(
                    "Working Days", min_value=0, max_value=31, step=1),
                "Daily Std Hours": st.column_config.NumberColumn(
                    "Daily Std Hours", min_value=0.0, max_value=24.0,
                    step=0.01, format="%.2f"),
                "Notes": st.column_config.TextColumn("Notes"),
            },
        )
        if st.button("💾 Save overrides", type="primary", key="ov_save_m"):
            old_periods = {o["period"] for o in overrides}
            new_periods = set()
            for _, r in edited_ov.iterrows():
                p = r["Period"]
                if pd.isna(p) or str(p).strip() == "":
                    continue
                p = str(p).strip()
                wd = r["Working Days"] if not pd.isna(r["Working Days"]) else None
                dh = r["Daily Std Hours"] if not pd.isna(r["Daily Std Hours"]) else None
                notes = r["Notes"] if not pd.isna(r["Notes"]) else ""
                db.upsert_period_override(p, wd, dh, notes)
                new_periods.add(p)
            for p in old_periods - new_periods:
                db.delete_period_override(p)
            st.success("✅ Period overrides saved.")
            st.rerun()

    # Resolved values per loaded period (helpful in either mode)
    if periods:
        st.markdown("---")
        st.markdown("**Resolved values per loaded period:**")
        from lib import calculations as _calc
        rows = []
        u = USERNAME if PERSONAL_MODE else None
        for p in periods:
            wd, total_hrs = _calc.standard_working_days_in_period(p, u)
            user_ov = (db.get_user_override(USERNAME, "period_overrides") or {}).get(p) if PERSONAL_MODE else None
            admin_ov = db.get_period_override(p)
            source = ("Your personal override" if user_ov else
                       "Master override" if admin_ov else
                       "Auto (Holidays + Hour Rules)")
            rows.append({
                "Period": p,
                "Working Days": wd,
                "Daily Std Hours": round(total_hrs / wd, 4) if wd else 0,
                "Total Std Hrs / Employee": round(total_hrs, 2),
                "Source": source,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ============================================================================
# 🎨 Org Chart Style tab — admin-customizable colors per dept/role/level
# ============================================================================
with t6:
    if PERSONAL_MODE:
        st.info(
            "🎨 Org chart colors are a **shared / master** setting — they're the same "
            "for everyone in the company. Switch to **Master mode** at the top of "
            "the page to edit them (admin only)."
        )
    elif not is_admin():
        st.warning("🔒 Only admins can change the org chart colors.")
    else:
        st.markdown("#### 🎨 Customize the Visual Org Chart")
        st.caption(
            "Pick colors used to render employee boxes in the **🌳 Org Chart → 🎨 Visual Chart** view. "
            "The chart can be colored either **By department** (everyone in the same dept shares a color "
            "= visual unity) or **By position role** (Managers all one color, Supervisors another, etc.). "
            "End users pick which scheme they prefer in the chart's color-scheme dropdown."
        )

        emps_for_style = db.list_employees_with_extended()
        unique_depts = sorted({(e.get("dept_by_location") or "").strip() for e in emps_for_style if e.get("dept_by_location")})
        unique_roles = ["Mgr.", "Sup.", "Leader", "(staff)"]

        sub1, sub2 = st.tabs(["🏢 By Department", "👔 By Position Role"])

        # ------------- Color by Department --------------
        with sub1:
            st.markdown(f"##### Pick a color for each of the {len(unique_depts)} departments")
            st.caption(
                "Each department's box will use this color when the chart's color scheme "
                "is set to **By department**. Tip: pick visually distinct hues so departments "
                "are easy to tell apart at a glance."
            )

            saved_depts = db.get_org_chart_colors("dept")

            # Default palette: a 12-color set. Cycle through for unset departments.
            DEFAULT_PALETTE = [
                "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899",
                "#14B8A6", "#F97316", "#6366F1", "#84CC16", "#06B6D4", "#A855F7",
            ]

            with st.form("dept_colors_form"):
                dept_inputs: dict[str, str] = {}
                cols_per_row = 3
                for i, d in enumerate(unique_depts):
                    if i % cols_per_row == 0:
                        cols = st.columns(cols_per_row)
                    saved = saved_depts.get(d, {})
                    default_color = saved.get("fill") or DEFAULT_PALETTE[i % len(DEFAULT_PALETTE)]
                    with cols[i % cols_per_row]:
                        c = st.color_picker(d or "(no department)", value=default_color, key=f"deptcol_{i}")
                        dept_inputs[d] = c

                col_save, col_reset = st.columns([1, 1])
                save_btn = col_save.form_submit_button("💾 Save department colors", type="primary")
                reset_btn = col_reset.form_submit_button("🔄 Reset all to defaults")

            if save_btn:
                for dept, color in dept_inputs.items():
                    # Auto-pick text color: white if dark fill, black if light fill
                    h = color.lstrip("#")
                    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                    font = "#FFFFFF" if luminance < 0.6 else "#1F2937"
                    db.set_org_chart_color("dept", dept, fill_color=color, font_color=font, border_color=color)
                st.success(f"✓ Saved colors for {len(dept_inputs)} departments.")
                st.rerun()
            if reset_btn:
                for d in unique_depts:
                    db.delete_org_chart_color("dept", d)
                st.success("✓ All department colors reset to defaults.")
                st.rerun()

        # ------------- Color by Position Role --------------
        with sub2:
            st.markdown(f"##### Pick a color for each position role")
            st.caption(
                "These colors are used when the chart's color scheme is set to **By role**. "
                "The default values match Anca's CI palette."
            )

            saved_roles = db.get_org_chart_colors("role")
            ROLE_DEFAULTS = {
                "Mgr.":     {"fill": "#715091", "font": "#FFFFFF", "border": "#4A2F62"},
                "Sup.":     {"fill": "#009ADE", "font": "#FFFFFF", "border": "#0073A8"},
                "Leader":   {"fill": "#E31D93", "font": "#FFFFFF", "border": "#A8126B"},
                "(staff)":  {"fill": "#F3F4F6", "font": "#1F2937", "border": "#D1D5DB"},
            }

            with st.form("role_colors_form"):
                role_inputs = {}
                cols = st.columns(4)
                for i, r in enumerate(unique_roles):
                    saved = saved_roles.get(r, {})
                    default_fill = saved.get("fill") or ROLE_DEFAULTS[r]["fill"]
                    with cols[i]:
                        st.markdown(f"**{r}**")
                        fill = st.color_picker("Box color", value=default_fill, key=f"rolefill_{r}")
                        role_inputs[r] = fill

                col_save2, col_reset2 = st.columns([1, 1])
                save2 = col_save2.form_submit_button("💾 Save role colors", type="primary")
                reset2 = col_reset2.form_submit_button("🔄 Reset roles to CI defaults")

            if save2:
                for role, color in role_inputs.items():
                    h = color.lstrip("#")
                    r2, g2, b2 = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                    lum = (0.299 * r2 + 0.587 * g2 + 0.114 * b2) / 255
                    font = "#FFFFFF" if lum < 0.6 else "#1F2937"
                    db.set_org_chart_color("role", role, fill_color=color, font_color=font, border_color=color)
                st.success("✓ Saved role colors.")
                st.rerun()
            if reset2:
                for r in unique_roles:
                    db.delete_org_chart_color("role", r)
                st.success("✓ Role colors reset to CI defaults.")
                st.rerun()
