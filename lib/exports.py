"""
Excel + PNG export for the report.

Excel export uses xlsxwriter to produce a formatted workbook that mirrors the
screenshot:
    - merged group-header band (Absenteeism / OT / Annual)
    - colored bands per top-level group (SG&A / MANU Support / MANU)
    - subtotal rows in a darker band
    - grand total row at the bottom

PNG export builds a Plotly Table figure (which can be downloaded as PNG via
kaleido) -- one click for the user.
"""
from __future__ import annotations
import io
from typing import Any
import pandas as pd
import xlsxwriter

# Column groupings in display order
ID_COLS = ["sg_a_manu", "department"]
HC_COLS = ["Total HC", "Permanent HC", "Contract HC", "TP HC"]
WORK_COLS = ["Total Working Hrs", "Permanent Working Hrs", "Contract Working Hrs"]
ABSENT_COLS = ["Total Absent Hrs", "Permanent Absent Hrs", "Contract Absent Hrs"]
PCT_ABSENT_COLS = ["% Total Absent", "% Permanent Absent", "% Contract Absent"]
OT_COLS = ["OT*1", "OT*1.5", "OT*2", "OT*3", "Total OT", "% OT"]
AL_COLS = ["Total AL", "Permanent AL", "Contract AL"]
SICK_COLS = ["Total Sick", "Permanent Sick", "Contract Sick"]
BUSINESS_COLS = ["Total Business", "Permanent Business", "Contract Business"]
WITHOUT_PAY_COLS = ["Total Without Pay", "Permanent Without Pay", "Contract Without Pay"]


def _all_display_cols(include_al: bool, include_sick: bool = False,
                      include_business: bool = False, include_without_pay: bool = False) -> list[str]:
    cols = ID_COLS + HC_COLS + WORK_COLS + ABSENT_COLS + PCT_ABSENT_COLS + OT_COLS
    if include_sick:
        cols += SICK_COLS
    if include_business:
        cols += BUSINESS_COLS
    if include_without_pay:
        cols += WITHOUT_PAY_COLS
    if include_al:
        cols += AL_COLS
    return cols


# ----------------------------- Excel export -----------------------------

def to_excel_bytes(report: dict, include_al: bool = True,
                   include_sick: bool = False, include_business: bool = False,
                   include_without_pay: bool = False,
                   username: str | None = None) -> bytes:
    """Return a styled .xlsx as bytes, suitable for st.download_button.

    If `username` is given AND that user has personal overrides active, a
    memo block is appended to the worksheet listing every difference between
    the user's settings and the master settings.
    """
    buf = io.BytesIO()
    rows = report["rows"]
    groups = report["groups"]
    grand = report["grand_total"]
    period = report["meta"].get("period", "")
    unit = report["meta"].get("unit", "Hours")

    cols = _all_display_cols(include_al, include_sick, include_business, include_without_pay)
    df_rows = pd.DataFrame(rows)
    df_groups = pd.DataFrame(groups).set_index("sg_a_manu") if groups else pd.DataFrame()

    workbook = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = workbook.add_worksheet("Report")

    # Formats
    title_f = workbook.add_format({"bold": True, "font_size": 14})
    sub_f = workbook.add_format({"italic": True, "font_color": "#555555"})
    hdr_band = workbook.add_format({
        "bold": True, "align": "center", "valign": "vcenter",
        "bg_color": "#9C8B6E", "font_color": "white", "border": 1,
    })
    hdr_band_orange = workbook.add_format({
        "bold": True, "align": "center", "valign": "vcenter",
        "bg_color": "#B7973F", "font_color": "white", "border": 1,
    })
    hdr_band_red = workbook.add_format({
        "bold": True, "align": "center", "valign": "vcenter",
        "bg_color": "#C00000", "font_color": "white", "border": 1,
    })
    hdr_cell = workbook.add_format({
        "bold": True, "align": "center", "valign": "vcenter",
        "bg_color": "#E7DDC6", "border": 1, "text_wrap": True,
    })
    cell_text = workbook.add_format({"border": 1, "valign": "vcenter"})
    cell_num = workbook.add_format({"border": 1, "num_format": "#,##0.0"})
    cell_int = workbook.add_format({"border": 1, "num_format": "#,##0", "align": "right"})
    cell_pct = workbook.add_format({"border": 1, "num_format": "0.00%"})
    band_sgna = workbook.add_format({"bg_color": "#FCE4D6", "border": 1, "num_format": "#,##0.0"})
    band_manus = workbook.add_format({"bg_color": "#DEEBF7", "border": 1, "num_format": "#,##0.0"})
    band_manu = workbook.add_format({"bg_color": "#E2EFDA", "border": 1, "num_format": "#,##0.0"})
    subtotal_f = workbook.add_format({
        "bold": True, "bg_color": "#305496", "font_color": "white",
        "border": 1, "num_format": "#,##0.0",
    })
    grand_f = workbook.add_format({
        "bold": True, "bg_color": "#1F3864", "font_color": "white",
        "border": 1, "num_format": "#,##0.0",
    })

    band_for_top = {"SG&A": band_sgna, "MANU Support": band_manus, "MANU": band_manu}
    subtotal_pct_f = workbook.add_format({
        "bold": True, "bg_color": "#305496", "font_color": "white",
        "border": 1, "num_format": "0.00%",
    })
    grand_pct_f = workbook.add_format({
        "bold": True, "bg_color": "#1F3864", "font_color": "white",
        "border": 1, "num_format": "0.00%",
    })
    hdr_band_sick = workbook.add_format({
        "bold": True, "align": "center", "valign": "vcenter",
        "bg_color": "#7C9444", "font_color": "white", "border": 1,
    })
    hdr_band_bus = workbook.add_format({
        "bold": True, "align": "center", "valign": "vcenter",
        "bg_color": "#5E479F", "font_color": "white", "border": 1,
    })
    hdr_band_wp = workbook.add_format({
        "bold": True, "align": "center", "valign": "vcenter",
        "bg_color": "#A23B3B", "font_color": "white", "border": 1,
    })

    # --- Title block ---
    ws.write(0, 0, f"Actual Working Hours - {period}", title_f)
    ws.write(1, 0, f"Unit: {unit}    |    Generated by HR Reporting App", sub_f)

    # --- Header rows (merged bands + per-column headers) ---
    HEADER_ROW1 = 3
    HEADER_ROW2 = 4
    DATA_START = 5

    # Build column ordering
    col_order = cols.copy()
    # Index of slices for header bands
    def col_idx(name): return col_order.index(name)

    # Plain header cells (row 2)
    for c, name in enumerate(col_order):
        ws.write(HEADER_ROW2, c, name, hdr_cell)

    # Merged band headers (row 1)
    def merge_band(start_col, end_col, label, fmt):
        if start_col == end_col:
            ws.write(HEADER_ROW1, start_col, label, fmt)
        else:
            ws.merge_range(HEADER_ROW1, start_col, HEADER_ROW1, end_col, label, fmt)

    merge_band(col_idx(ID_COLS[0]), col_idx(ID_COLS[-1]), "Group / Function", hdr_cell)
    merge_band(col_idx(HC_COLS[0]), col_idx(HC_COLS[-1]), "Headcount", hdr_band)
    merge_band(col_idx(WORK_COLS[0]), col_idx(WORK_COLS[-1]), f"Working ({unit})", hdr_band)
    merge_band(col_idx(ABSENT_COLS[0]), col_idx(ABSENT_COLS[-1]),
               f"Absenteeism (Excl AL, {unit})", hdr_band)
    merge_band(col_idx(PCT_ABSENT_COLS[0]), col_idx(PCT_ABSENT_COLS[-1]),
               "% Absenteeism", hdr_band)
    merge_band(col_idx(OT_COLS[0]), col_idx(OT_COLS[-1]), f"OT ({unit})", hdr_band_orange)
    if include_sick:
        merge_band(col_idx(SICK_COLS[0]), col_idx(SICK_COLS[-1]),
                   f"Sick Leave ({unit})", hdr_band_sick)
    if include_business:
        merge_band(col_idx(BUSINESS_COLS[0]), col_idx(BUSINESS_COLS[-1]),
                   f"Business Leave ({unit})", hdr_band_bus)
    if include_without_pay:
        merge_band(col_idx(WITHOUT_PAY_COLS[0]), col_idx(WITHOUT_PAY_COLS[-1]),
                   f"Without Pay ({unit})", hdr_band_wp)
    if include_al:
        merge_band(col_idx(AL_COLS[0]), col_idx(AL_COLS[-1]),
                   f"Annual Leave ({unit})", hdr_band_red)

    # --- Data rows ---
    r = DATA_START
    # We write one row per Function plus a subtotal after each top-level change
    last_top = None
    for row_dict in rows:
        top = row_dict.get("sg_a_manu", "")
        # When we move to a new top-level group, emit subtotal for previous group
        if last_top is not None and top != last_top:
            _write_subtotal(ws, r, col_order, df_groups, last_top, subtotal_f, subtotal_pct_f, include_al)
            r += 1
        last_top = top

        band = band_for_top.get(top, cell_num)
        for c, name in enumerate(col_order):
            val = row_dict.get(name, "")
            if name in ID_COLS:
                ws.write(r, c, val, cell_text)
            elif name in HC_COLS:
                ws.write(r, c, val, cell_int)
            elif name in PCT_ABSENT_COLS or name == "% OT":
                ws.write_number(r, c, (val or 0) / 100.0, cell_pct)
            else:
                ws.write_number(r, c, val or 0, band)
        r += 1

    # Final subtotal for last group
    if last_top is not None:
        _write_subtotal(ws, r, col_order, df_groups, last_top, subtotal_f, subtotal_pct_f, include_al)
        r += 1

    # Grand total row
    _write_grand_total(ws, r, col_order, grand, grand_f, grand_pct_f, include_al)
    r += 1

    # Column widths
    ws.set_column(0, 0, 16)
    ws.set_column(1, 1, 22)
    ws.set_column(2, len(col_order) - 1, 13)
    ws.freeze_panes(DATA_START, 2)

    # ───── Personal-overrides memo (only if user has overrides) ─────
    if username:
        try:
            from . import db as _db
            diffs = _db.get_user_override_summary(username)
            if diffs:
                memo_r = r + 3
                memo_title_f = workbook.add_format({
                    "bold": True, "font_size": 12, "font_color": "#FFFFFF",
                    "bg_color": "#715091", "align": "left", "valign": "vcenter",
                    "border": 1,
                })
                memo_hdr_f = workbook.add_format({
                    "bold": True, "bg_color": "#F0EBDF", "border": 1, "font_color": "#715091",
                })
                memo_cell_f = workbook.add_format({"border": 1, "valign": "top"})
                memo_note_f = workbook.add_format({
                    "italic": True, "font_color": "#6B7280", "text_wrap": True,
                })

                ws.merge_range(memo_r, 0, memo_r, 5,
                                f"📝  Personal calculation overrides applied — user: {username}",
                                memo_title_f)
                ws.set_row(memo_r, 24)
                ws.merge_range(memo_r + 1, 0, memo_r + 1, 5,
                                "These values differ from the master defaults. "
                                "The numbers in this report are calculated using YOUR personal "
                                "settings, not the company-wide master settings.",
                                memo_note_f)
                ws.set_row(memo_r + 1, 30)

                ws.write(memo_r + 3, 0, "Setting", memo_hdr_f)
                ws.merge_range(memo_r + 3, 1, memo_r + 3, 5, "Detail", memo_hdr_f)
                for i, d in enumerate(diffs, start=memo_r + 4):
                    ws.write(i, 0, d.get("setting", ""), memo_cell_f)
                    ws.merge_range(i, 1, i, 5, d.get("detail", ""), memo_cell_f)
        except Exception:
            pass  # never break the export over a memo

    workbook.close()
    buf.seek(0)
    return buf.getvalue()


def _write_subtotal(ws, r, col_order, df_groups, top_label, fmt, pct_fmt, include_al):
    if top_label not in df_groups.index:
        return
    g = df_groups.loc[top_label]
    for c, name in enumerate(col_order):
        if name == "sg_a_manu":
            ws.write(r, c, f"Total {top_label}", fmt)
        elif name == "department":
            ws.write(r, c, "", fmt)
        elif name in ("% Total Absent", "% Permanent Absent", "% Contract Absent", "% OT"):
            ws.write_number(r, c, (g[name] or 0) / 100.0, pct_fmt)
        else:
            ws.write_number(r, c, g[name] or 0, fmt)


def _write_grand_total(ws, r, col_order, grand, fmt, pct_fmt, include_al):
    for c, name in enumerate(col_order):
        if name == "sg_a_manu":
            ws.write(r, c, "Grand Total", fmt)
        elif name == "department":
            ws.write(r, c, "", fmt)
        elif name in ("% Total Absent", "% Permanent Absent", "% Contract Absent", "% OT"):
            ws.write_number(r, c, (grand.get(name, 0) or 0) / 100.0, pct_fmt)
        else:
            ws.write_number(r, c, grand.get(name, 0) or 0, fmt)


# ----------------------------- PNG export (Plotly Table) -----------------------------

def to_png_bytes(report: dict, include_al: bool = True, scale: int = 2,
                 include_sick: bool = False, include_business: bool = False,
                 include_without_pay: bool = False) -> bytes | None:
    """Return PNG bytes via Plotly + Kaleido.  Returns None on failure (kaleido not installed)."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    cols = _all_display_cols(include_al, include_sick, include_business, include_without_pay)
    rows = report["rows"]
    groups_df = pd.DataFrame(report["groups"]).set_index("sg_a_manu") if report["groups"] else pd.DataFrame()
    grand = report["grand_total"]
    unit = report["meta"].get("unit", "Hours")

    # Build display table rows: function rows interleaved with subtotal rows
    display_rows = []
    row_kinds = []
    last_top = None
    for r in rows:
        top = r.get("sg_a_manu", "")
        if last_top is not None and top != last_top:
            if last_top in groups_df.index:
                sub = groups_df.loc[last_top].to_dict()
                sub["sg_a_manu"] = f"Total {last_top}"
                sub["department"] = ""
                display_rows.append(sub)
                row_kinds.append("sub")
        last_top = top
        display_rows.append(r)
        row_kinds.append("data")
    if last_top is not None and last_top in groups_df.index:
        sub = groups_df.loc[last_top].to_dict()
        sub["sg_a_manu"] = f"Total {last_top}"
        sub["department"] = ""
        display_rows.append(sub)
        row_kinds.append("sub")
    grand_row = dict(grand)
    grand_row["sg_a_manu"] = "Grand Total"
    grand_row["department"] = ""
    display_rows.append(grand_row)
    row_kinds.append("grand")

    # Build the Plotly Table cell matrix
    formatted = {c: [] for c in cols}
    for r in display_rows:
        for c in cols:
            v = r.get(c, "")
            if c in ID_COLS:
                formatted[c].append(str(v) if v else "")
            elif c in HC_COLS:
                formatted[c].append(f"{int(v):,}" if v not in (None, "", 0) or r.get(c) == 0 else "0")
            elif c in ("% Total Absent", "% Permanent Absent", "% Contract Absent", "% OT"):
                formatted[c].append(f"{(v or 0):.2f}%")
            else:
                formatted[c].append(f"{(v or 0):,.1f}")

    # Row colors
    color_map = {"data": "#FFFFFF", "sub": "#305496", "grand": "#1F3864"}
    fill_per_row = [color_map[k] for k in row_kinds]
    font_per_row = ["#000000" if k == "data" else "#FFFFFF" for k in row_kinds]
    cell_fills = [[fill_per_row[i] for i in range(len(row_kinds))] for _ in cols]
    cell_fonts = [[font_per_row[i] for i in range(len(row_kinds))] for _ in cols]

    fig = go.Figure(
        data=[
            go.Table(
                columnwidth=[2 if c in ID_COLS else 1 for c in cols],
                header=dict(
                    values=[f"<b>{c}</b>" for c in cols],
                    fill_color="#E7DDC6", align="center", height=34,
                    font=dict(color="#000", size=11),
                ),
                cells=dict(
                    values=[formatted[c] for c in cols],
                    fill_color=cell_fills,
                    font=dict(color=cell_fonts, size=10),
                    align="center", height=24,
                ),
            )
        ]
    )
    fig.update_layout(
        title=f"<b>Actual Working Hours - {report['meta'].get('period','')}</b> ({unit})",
        margin=dict(l=10, r=10, t=50, b=10),
        width=max(1400, 90 * len(cols)),
        height=80 + 26 * (len(display_rows) + 2),
    )
    try:
        return fig.to_image(format="png", scale=scale)
    except Exception:
        return None
