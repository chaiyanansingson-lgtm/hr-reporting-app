"""
Upload Data page (admin only).

Tabs:
  📋 Timesheet — primary HRM monthly export
  ⏱️ OT — accepts BOTH the new dated detail format AND the legacy monthly summary
  🏖️ Leave — legacy summary cross-check
  👥 Reference — NameList / Manager / Cost Group / Holidays

Every tab includes a "📥 Download templates" expander so admin always knows
the expected file format and can use a blank template when needed.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import db, parsers
from lib.page_utils import require_login, page_header
from lib.templates import TEMPLATES

st.set_page_config(page_title="Upload Data", page_icon="📤", layout="wide")
require_login(admin_only=True)
page_header(title_key="upload_title", subtitle_key="upload_subtitle")

st.info(
    "**Workflow:** every month, export the 3 raw files from the HRM "
    "(Timesheet, OT, Leave) and upload them here. Re-uploading the same period "
    "replaces that period cleanly. Upload reference files (NameList / Manager / "
    "Cost Group / Holidays) when they change. **Each tab has a 📥 Download templates "
    "section — use these to see the exact format expected.**"
)


def _template_dl(label_key: str, *template_keys: str):
    """Render an expander with one or more template download buttons."""
    with st.expander(f"📥 Download templates / format references — {label_key}"):
        st.caption(
            "Each download is a ready-to-fill Excel file with the expected columns, "
            "example rows, and notes about what each field means."
        )
        cols = st.columns(min(len(template_keys), 3))
        for i, k in enumerate(template_keys):
            filename, generator = TEMPLATES[k]
            with cols[i % len(cols)]:
                st.download_button(
                    label=f"⬇️  {filename}",
                    data=generator(),
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"tpl_{k}",
                    use_container_width=True,
                )


tab_ts, tab_ot, tab_lv, tab_ref = st.tabs(
    ["📋 Timesheet (primary)", "⏱️ OT", "🏖️ Leave (cross-check)", "👥 Reference data"]
)

# ============================================================================
# 📋 Timesheet
# ============================================================================
with tab_ts:
    st.markdown("### Monthly Timesheet (`*.xls` from HRM)")
    st.caption(
        "This is the **primary source** for the report. The file should be the standard "
        "*รายงานผลการคำนวณตอกเวลาแสดงตามพนักงาน* export covering one month."
    )

    _template_dl("Timesheet", "timesheet_ref")

    f = st.file_uploader("Upload Timesheet .xls / .xlsx", type=["xls", "xlsx"], key="ts_upload")
    if f:
        with st.spinner("Parsing…"):
            df = parsers.parse_timesheet(f)
        if df.empty:
            st.error("No data rows found. Is the file format correct?")
        else:
            st.success(f"Parsed {len(df):,} rows for **{df['emp_no'].nunique()}** employees.")
            st.write(f"Periods detected: `{', '.join(sorted(df['period'].unique()))}`")
            with st.expander("Preview first 20 rows"):
                st.dataframe(df.head(20), use_container_width=True, hide_index=True)
            replace = st.checkbox(
                "Replace existing data for these periods (recommended)", value=True,
                help="If unchecked, rows for the same employee+date will still be overwritten "
                     "but other rows in the same period are kept."
            )
            if st.button("✅ Confirm import", type="primary", key="ts_confirm"):
                f.seek(0)
                n, periods = parsers.import_timesheet(f, replace_period=replace)
                db.log_upload("timesheet", f.name, ",".join(periods), n,
                              st.session_state.username, f"replace_period={replace}")
                st.success(f"Imported {n:,} rows for periods: {', '.join(periods)}")
                st.rerun()


# ============================================================================
# ⏱️ OT — accepts BOTH dated detail and legacy summary formats
# ============================================================================
with tab_ot:
    st.markdown("### OT — both formats supported")
    st.caption(
        "Upload the OT file — the app will **auto-detect** which format it is:\n\n"
        "• **Dated OT Detail** (preferred, like `OT_Summary_Trial.xlsx`) — one row per "
        "OT occurrence with `Booked Date`, `OT From`, `OT To`. This is used as the "
        "**authoritative** OT source and overrides the Timesheet's OT columns.\n\n"
        "• **Legacy monthly summary** (HRM export, like `20260504_OT.xls`) — totals per "
        "employee per multiplier, no per-day dates. Used as a **cross-check** only "
        "(it cannot override the Timesheet because it has no dates)."
    )

    _template_dl("OT", "ot_detail", "ot_legacy")

    f = st.file_uploader("Upload OT file .xls / .xlsx", type=["xls", "xlsx"], key="ot_upload")
    if f:
        try:
            with st.spinner("Detecting format and parsing…"):
                fmt, df = parsers.parse_ot_any_format(f)
        except ValueError as e:
            st.error(str(e))
            df = None
            fmt = None

        if df is not None and not df.empty:
            if fmt == "dated":
                st.success(
                    f"✅ Detected **dated OT Detail format** — {len(df):,} entries for "
                    f"{df['emp_no'].nunique()} employees."
                )
                st.write(f"Periods detected: `{', '.join(sorted(df['period'].unique()))}`")
                st.write(f"Date range: `{df['work_date'].min()}` → `{df['work_date'].max()}`")

                summary = df.groupby("multiplier")["hours"].agg(["sum", "count"]).reset_index()
                summary.columns = ["Multiplier", "Total Hours", "# Entries"]
                st.dataframe(summary, use_container_width=True, hide_index=True)
                with st.expander("Preview first 20 rows"):
                    st.dataframe(df.head(20), use_container_width=True, hide_index=True)

                replace = st.checkbox(
                    "Replace existing OT data for these periods (recommended)", value=True,
                    key="ot_replace"
                )
                if st.button("✅ Confirm OT import (overrides Timesheet OT)",
                              type="primary", key="ot_confirm_dated"):
                    f.seek(0)
                    n, periods = parsers.import_ot_detail(f, replace_period=replace)
                    db.log_upload("ot_detail", f.name, ",".join(periods), n,
                                  st.session_state.username, f"replace_period={replace}")
                    st.success(
                        f"Imported {n:,} OT entries for periods: {', '.join(periods)}. "
                        "Report and Charts will now use these values for OT."
                    )
                    st.rerun()

            elif fmt == "legacy":
                st.warning(
                    f"📋 Detected **legacy monthly OT summary** — {len(df):,} rows. "
                    "This format has no per-day dates, so it can be displayed as a "
                    "cross-check but **cannot override** the Timesheet's OT calculation. "
                    "For dated tracking, prefer the OT Detail template above."
                )
                # Show summary by multiplier (legacy parser returns hours + multiplier)
                if "multiplier" in df.columns and "hours" in df.columns:
                    summary = df.groupby("multiplier")["hours"].agg(["sum", "count"]).reset_index()
                    summary.columns = ["Multiplier", "Total Hours", "# Rows"]
                    st.dataframe(summary, use_container_width=True, hide_index=True)
                with st.expander("Preview first 20 rows"):
                    st.dataframe(df.head(20), use_container_width=True, hide_index=True)
                # Log it but do NOT import to ot_entries
                if st.button("📝 Log this file (cross-check only, not used in calculations)",
                              key="ot_log_legacy"):
                    db.log_upload("ot_legacy", f.name, "", len(df),
                                  st.session_state.username, "format=legacy_summary; cross-check only")
                    st.success("Logged.")
                    st.rerun()
        elif df is not None:
            st.error("File parsed but contained no OT entries.")

    # Show which periods currently have OT detail
    detail_periods = db.get_periods_with_ot_detail()
    if detail_periods:
        st.info(
            f"📅 OT Detail is currently loaded for: {', '.join(f'`{p}`' for p in detail_periods)}. "
            "These periods use the dated OT values; other periods use the Timesheet's OT columns."
        )
    else:
        st.caption(
            "No dated OT Detail loaded yet — Report uses the Timesheet's OT columns by default."
        )


# ============================================================================
# 🏖️ Leave (cross-check)
# ============================================================================
with tab_lv:
    st.markdown("### Leave summary (`*.xls`)")
    st.caption(
        "Optional cross-check, same idea as the legacy OT format above. "
        "The Timesheet is the primary source for leave hours."
    )

    _template_dl("Leave", "leave_legacy")

    f = st.file_uploader("Upload Leave .xls / .xlsx", type=["xls", "xlsx"], key="lv_upload")
    if f:
        df = parsers.parse_leave_summary(f)
        if df.empty:
            st.error("Couldn't parse any rows.")
        else:
            st.success(f"Parsed {len(df):,} leave-summary rows.")
            st.write("**Totals from this Leave file (days):**")
            st.dataframe(df.groupby("leave_type")["days"].sum().reset_index(),
                         use_container_width=True, hide_index=True)
            if st.button("📝 Log this Leave file", key="lv_log"):
                db.log_upload("leave", f.name, "", len(df),
                              st.session_state.username, "cross-check only")
                st.success("Logged.")
                st.rerun()


# ============================================================================
# 👥 Reference data (NameList / Manager / Cost Group / Holidays)
# ============================================================================
with tab_ref:
    st.markdown("### Reference data (upload when it changes)")

    _template_dl("Reference data", "employee_master", "name_list", "manager",
                  "cost_group", "holidays")

    # Employee MASTER list — preferred format with org-chart fields
    st.markdown("#### 🌟 Employee MASTER list (recommended)")
    st.caption(
        "**Use this for the Org Chart feature.** Single rich file containing all "
        "employee fields including the manager hierarchy. Replaces the simpler "
        "NameList format below — you only need ONE of the two."
    )
    f = st.file_uploader("Employee MASTER list (.xlsx)", type=["xlsx"], key="em_upload")
    if f and st.button("Import Employee MASTER list", key="btn_em", type="primary"):
        with st.spinner("Parsing & importing…"):
            try:
                n_emps, n_resolved = parsers.import_employee_master(f)
                db.log_upload("employee_master", f.name, "", n_emps,
                              st.session_state.username,
                              f"resolved {n_resolved} manager links")
                st.success(
                    f"✅ Imported {n_emps} employees, resolved {n_resolved} "
                    f"manager-employee relationships for the Org Chart."
                )
            except ValueError as e:
                st.error(f"Could not parse: {e}")

    st.markdown("---")
    st.markdown("#### Alternative: simpler files (use only if MASTER list is not available)")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### 👤 NameList")
        f = st.file_uploader("Employee name list (.xlsx)", type=["xlsx"], key="nl_upload")
        if f and st.button("Import NameList", key="btn_nl"):
            df = parsers.parse_name_list(f)
            with st.spinner("Importing…"):
                f.seek(0)
                n = parsers.import_name_list(f)
            db.log_upload("name_list", f.name, "", n, st.session_state.username, "")
            st.success(f"Imported {n} employees.")
            st.dataframe(df.head(8), use_container_width=True, hide_index=True)

        st.markdown("#### 🧑‍💼 Manager")
        f = st.file_uploader("Manager list (.xlsx)", type=["xlsx"], key="mgr_upload")
        if f and st.button("Import Manager list", key="btn_mgr"):
            df = parsers.parse_manager_list(f)
            with st.spinner("Importing…"):
                f.seek(0)
                n = parsers.import_manager_list(f)
            db.log_upload("manager", f.name, "", n, st.session_state.username, "")
            st.success(f"Imported {n} managers.")
            st.dataframe(df.head(8), use_container_width=True, hide_index=True)

    with c2:
        st.markdown("#### 🗂️ Cost Group")
        f = st.file_uploader("Cost group mapping (.xlsx)", type=["xlsx"], key="cg_upload")
        if f and st.button("Import Cost Group", key="btn_cg"):
            df = parsers.parse_cost_group(f)
            with st.spinner("Importing…"):
                f.seek(0)
                n = parsers.import_cost_group(f)
            db.log_upload("cost_group", f.name, "", n, st.session_state.username, "")
            st.success(f"Imported {n} cost-group rows. Edit the SG&A/MANU level on the Configuration page.")
            st.dataframe(df.head(8), use_container_width=True, hide_index=True)

        st.markdown("#### 📅 Holidays")
        f = st.file_uploader("Holiday list (.xlsx)", type=["xlsx"], key="hd_upload")
        if f and st.button("Import Holidays", key="btn_hd"):
            df = parsers.parse_holidays(f)
            with st.spinner("Importing…"):
                f.seek(0)
                n = parsers.import_holidays(f)
            db.log_upload("holidays", f.name, "", n, st.session_state.username, "")
            st.success(f"Imported {n} holidays.")
            st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================================
# Upload history
# ============================================================================
st.markdown("---")
st.markdown("### Upload history (last 50)")
hist = db.get_upload_log(limit=50)
if hist:
    df = pd.DataFrame(hist)[
        ["uploaded_at", "file_type", "file_name", "period", "rows_inserted", "uploaded_by", "notes"]
    ].rename(columns={"uploaded_at": "When", "file_type": "Type", "file_name": "File",
                      "period": "Period", "rows_inserted": "Rows",
                      "uploaded_by": "By", "notes": "Notes"})
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.caption("No uploads yet.")
