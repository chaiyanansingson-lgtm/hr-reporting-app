"""
Generate downloadable Excel templates for each input file type.

Used by the Upload page to give admin a one-click "Download blank template"
button so they always know the expected format.
"""
from __future__ import annotations
import io
import xlsxwriter


def _make_xlsx(sheet_name: str, headers: list[str], example_rows: list[list],
               notes: list[str] | None = None,
               column_widths: dict | None = None,
               freeze_first_row: bool = True) -> bytes:
    """Generic helper: build a single-sheet xlsx with a styled header + a few example rows."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet(sheet_name[:31])  # Excel sheet names max 31 chars

    # Formats
    hdr = wb.add_format({
        "bold": True, "bg_color": "#715091", "font_color": "white",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    cell = wb.add_format({"border": 1, "valign": "vcenter"})
    note_fmt = wb.add_format({"italic": True, "font_color": "#6B7280",
                              "text_wrap": True, "valign": "top"})
    title = wb.add_format({"bold": True, "font_size": 13, "font_color": "#715091"})

    # Title row
    ws.merge_range(0, 0, 0, max(0, len(headers) - 1),
                   f"Template: {sheet_name}", title)
    ws.set_row(0, 22)

    # Header row
    for c, h in enumerate(headers):
        ws.write(2, c, h, hdr)
    ws.set_row(2, 28)

    # Example data rows
    for r, row in enumerate(example_rows, start=3):
        for c, v in enumerate(row):
            ws.write(r, c, v, cell)

    # Notes block below the data
    notes_start_row = 3 + len(example_rows) + 2
    if notes:
        ws.write(notes_start_row, 0, "📝 Notes:", title)
        for i, n in enumerate(notes, start=1):
            ws.merge_range(notes_start_row + i, 0, notes_start_row + i,
                           max(0, len(headers) - 1), f"  • {n}", note_fmt)
            ws.set_row(notes_start_row + i, 18)

    # Column widths
    if column_widths:
        for col_idx, w in column_widths.items():
            ws.set_column(col_idx, col_idx, w)
    else:
        ws.set_column(0, len(headers) - 1, 18)

    if freeze_first_row:
        ws.freeze_panes(3, 0)

    wb.close()
    buf.seek(0)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────
# Each function returns the bytes of a ready-to-download template file.
# ─────────────────────────────────────────────────────────────────────────

def name_list_template() -> bytes:
    return _make_xlsx(
        sheet_name="NameList",
        headers=["Emp. No.", "Emp. Name", "TYPE", "COST", "LEVEL", "D/IN"],
        example_rows=[
            ["1021568", "Mr.Nantachai Somboot",   "PER", "210",  1, "Direct"],
            ["1021629", "Mr.Choochai Nilada",     "PER", "210",  1, "Direct"],
            ["1021501", "Ms.Pranee Boonwang",     "SUB", "353",  2, "Indirect"],
        ],
        notes=[
            "Emp. No. = unique employee number. Cannot be blank.",
            "TYPE: PER = Permanent, SUB = Contract / Subcontract, TEM = Temporary part-time.",
            "COST = the cost-centre code (must match a Code in the Cost Group file).",
            "LEVEL = 1, 2 or 3 (organisational level).",
            "D/IN: 'Direct' (production) or 'Indirect' (support / overhead).",
            "Re-uploading this file marks any employees not in the new list as Inactive.",
        ],
        column_widths={0: 12, 1: 28, 2: 8, 3: 8, 4: 8, 5: 12},
    )


def manager_template() -> bytes:
    return _make_xlsx(
        sheet_name="Manager",
        headers=["Emp. No.", "Emp. Name", "ชื่อ", "Title", "Mgr."],
        example_rows=[
            ["1021499", "Mr.Nicholas Doyle",        "นายนิโคลัส ดอยล์",        "General Manager", "Mgr."],
            ["1021656", "Mr. Chaiyanan Singson",    "นายชัยนันท์ สิงห์สน",     "HR Manager",       "Mgr."],
            ["1021445", "Ms.Pranee Boonwang",       "น.ส.ปราณี บุญวัง",       "Finance Manager",  "Mgr."],
        ],
        notes=[
            "Emp. No. must match an entry in the NameList file.",
            "Title = the manager's job title (e.g. 'HR Manager', 'Production Manager').",
            "ชื่อ (Thai name) is optional but recommended.",
            "The Mgr. column should always be 'Mgr.' for managers.",
        ],
        column_widths={0: 12, 1: 28, 2: 28, 3: 26, 4: 8},
    )


def cost_group_template() -> bytes:
    return _make_xlsx(
        sheet_name="Cost Group",
        headers=["Code", "Department"],
        example_rows=[
            ["353",  "Admin"],
            ["310",  "Eng. Mechanical"],
            ["352",  "Sales"],
            ["280",  "QP"],
            ["210",  "CNC"],
            ["220",  "Cutting"],
        ],
        notes=[
            "Code = cost-centre code as it appears in the COST column of NameList.",
            "Department = the Function name shown in the report (e.g. 'CNC', 'Welding').",
            "After importing here, edit the SG&A / MANU / MANU Support 'Top Group' assignment "
            "in Configuration → Cost Groups (top groups can be any name you like).",
        ],
        column_widths={0: 10, 1: 22},
    )


def holidays_template() -> bytes:
    return _make_xlsx(
        sheet_name="Holidays",
        headers=["วันที่", "ชื่อวันหยุด"],
        example_rows=[
            ["2026-01-01", "วันหยุดปีใหม่"],
            ["2026-01-02", "วันหยุดปีใหม่"],
            ["2026-04-13", "วันสงกรานต์"],
            ["2026-04-14", "วันสงกรานต์"],
            ["2026-04-15", "วันสงกรานต์"],
            ["2026-12-31", "วันสิ้นปี"],
        ],
        notes=[
            "Date column accepts ISO format (YYYY-MM-DD) or Excel date format.",
            "Holidays affect the auto-computed Standard Working Days for each month.",
            "Re-uploading this file replaces the holiday calendar entirely.",
        ],
        column_widths={0: 14, 1: 32},
    )


def ot_detail_template() -> bytes:
    """Template for the new dated OT format (preferred — supports correct period aggregation)."""
    return _make_xlsx(
        sheet_name="OT Detail",
        headers=[
            "Emp. No.", "Emp. Name", "Emp. Type", "Cost Centre", "Cost Group",
            "Department", "Booked Date", "OT From", "OT To", "OT Multiplier",
            "OT Period (TH)", "Multiplier Label", "OT Type (TH)", "Hour", "Minute",
        ],
        example_rows=[
            ["1021594", "พนักงานตัวอย่าง 1", "PER", "354", "353/354/356",
             "ASM356", "2026-04-04", "2026-04-04", "2026-04-04", 1.5,
             "วันหยุด", "x1.5", "ค่าล่วงเวลา x1.5 (วันหยุด)", 7, 55],
            ["1021463", "พนักงานตัวอย่าง 2", "PER", "310", "310/330",
             "ASM310", "2026-04-07", "2026-04-07", "2026-04-07", 1.5,
             "หลังงาน", "x1.5", "ค่าล่วงเวลา x1.5 (หลังงาน)", 3, 0],
            ["1021463", "พนักงานตัวอย่าง 2", "PER", "310", "310/330",
             "ASM310", "2026-04-29", "2026-04-29", "2026-04-29", 2.0,
             "วันหยุดนักขัตฤกษ์", "x2", "ค่าล่วงเวลา x2", 8, 0],
        ],
        notes=[
            "PREFERRED FORMAT — every OT occurrence has its own date, "
            "so totals are always correct even if the timesheet covers a partial month.",
            "Required columns: Emp. No., OT From, OT Multiplier, Hour.  Other columns optional.",
            "Date columns accept Thai Buddhist year (e.g. 04/04/2569) or ISO (2026-04-04).",
            "OT Multiplier = 1.0, 1.5, 2.0, or 3.0.  Total = Hour + Minute/60.",
            "Re-uploading replaces all OT entries for the periods present in the file.",
        ],
        column_widths={0: 11, 1: 22, 2: 8, 3: 10, 4: 14, 5: 10,
                        6: 12, 7: 12, 8: 12, 9: 9, 10: 18, 11: 8, 12: 28, 13: 6, 14: 6},
    )


def ot_legacy_template() -> bytes:
    """Sample of the OLD monthly-summary OT format (still supported as cross-check)."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet("OT Summary (legacy)")

    title = wb.add_format({"bold": True, "font_size": 13, "font_color": "#715091"})
    note = wb.add_format({"italic": True, "font_color": "#6B7280", "text_wrap": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#715091", "font_color": "white",
                          "align": "center", "border": 1})
    cell = wb.add_format({"border": 1})

    ws.write(0, 0, "Sample of legacy OT summary format", title)
    ws.merge_range(1, 0, 1, 5,
                   "This is the OLD HRM monthly-summary export format. "
                   "It does not include OT dates, so it can only be aggregated correctly "
                   "when the timesheet covers exactly one month. "
                   "PREFER the dated 'OT Detail' template instead.", note)
    ws.set_row(1, 36)

    # Mimic the actual structure (Thai company header + summary rows)
    ws.write(4, 1, "บริษัท แอนคา แมนูแฟคเจอริ่ง โซลูชั่นส์ (ประเทศไทย) จำกัด", title)
    ws.write(6, 1, "รายงานสรุปค่าล่วงเวลา", title)
    ws.write(8, 1, "ตั้งแต่วันที่   01/04/2569   ถึง   30/04/2569")

    # Column headers row
    headers = ["รหัส", "ชื่อพนักงาน", "ประเภทเงินเพิ่ม", "ครั้ง", "จำนวน", "หน่วยนาที"]
    for c, h in enumerate(headers):
        ws.write(10, c + 1, h, hdr)

    # Example rows
    examples = [
        ["1021568", "พนักงานตัวอย่าง 1", "ค่าล่วงเวลาX1.5 (วันทำงานและสุดสัปดาห์)", 9, 41, "41:00"],
        ["",        "",                   "ค่าล่วงเวลาX2 (วันหยุดนักขัตฤกษ์)",        4, 32, "32:00"],
        ["",        "",                   "ค่าล่วงเวลาX3 (ก่อน-หลังงาน)",            3,  9, "9:00"],
        ["1021629", "พนักงานตัวอย่าง 2", "ค่าล่วงเวลาX1.5 (วันทำงานและสุดสัปดาห์)", 15, 63, "63:00"],
    ]
    for r, row in enumerate(examples, start=11):
        for c, v in enumerate(row):
            ws.write(r, c + 1, v, cell)

    ws.set_column(0, 0, 4)
    ws.set_column(1, 1, 12)
    ws.set_column(2, 2, 22)
    ws.set_column(3, 3, 36)
    ws.set_column(4, 6, 12)

    wb.close()
    buf.seek(0)
    return buf.getvalue()


def leave_legacy_template() -> bytes:
    """Sample of the legacy Leave summary format."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet("Leave Summary")

    title = wb.add_format({"bold": True, "font_size": 13, "font_color": "#715091"})
    note = wb.add_format({"italic": True, "font_color": "#6B7280", "text_wrap": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#715091", "font_color": "white",
                          "align": "center", "border": 1})
    cell = wb.add_format({"border": 1})

    ws.write(0, 0, "Sample of Leave summary format", title)
    ws.merge_range(1, 0, 1, 5,
                   "Legacy HRM monthly-summary format (no per-day dates). "
                   "Used as cross-check only — the Timesheet is the primary source for leave hours.", note)
    ws.set_row(1, 30)

    ws.write(3, 0, "บริษัท แอนคา แมนูแฟคเจอริ่ง โซลูชั่นส์ (ประเทศไทย) จำกัด", title)
    ws.write(5, 0, "***รายงานสรุปลาป่วย-กิจ-บวช-คลอด-พักร้อน", title)
    ws.write(7, 0, "ตั้งแต่วันที่   01/04/2569   ถึง   30/04/2569")

    headers = ["รหัส", "ชื่อพนักงาน", "ประเภทการลา", "ครั้ง", "จำนวน"]
    for c, h in enumerate(headers):
        ws.write(9, c, h, hdr)

    examples = [
        ["1021568", "พนักงานตัวอย่าง 1", "ลาพักร้อน(สิทธิการลา)",   4, 4],
        ["1021629", "พนักงานตัวอย่าง 2", "ลาพักร้อน(สิทธิการลา)",   2, 2],
        ["1021435", "พนักงานตัวอย่าง 3", "ป่วยมีใบแพทย์(สิทธิการลา)", 1, 1],
        ["1021500", "พนักงานตัวอย่าง 4", "หักลากิจ(สิทธิการลา)",     1, 0.5],
    ]
    for r, row in enumerate(examples, start=10):
        for c, v in enumerate(row):
            ws.write(r, c, v, cell)

    ws.set_column(0, 0, 12)
    ws.set_column(1, 1, 24)
    ws.set_column(2, 2, 28)
    ws.set_column(3, 4, 10)

    wb.close()
    buf.seek(0)
    return buf.getvalue()


def timesheet_format_reference() -> bytes:
    """Brief format reference for the Timesheet (which is HRM-exported, can't be templated)."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet("Timesheet Format")

    title = wb.add_format({"bold": True, "font_size": 13, "font_color": "#715091"})
    note = wb.add_format({"italic": True, "font_color": "#6B7280", "text_wrap": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#715091", "font_color": "white",
                          "align": "center", "border": 1})

    ws.write(0, 0, "Timesheet — Format reference (HRM export)", title)
    ws.merge_range(1, 0, 1, 4,
                   "The Timesheet file is exported from your HRM system "
                   "(รายงานผลการคำนวณตอกเวลาแสดงตามพนักงาน). You don't create it manually. "
                   "The app's parser handles the standard HRM format automatically — "
                   "Buddhist dates, multi-row headers, sparse employee blocks. "
                   "Just upload the file as-is from HRM each month.", note)
    ws.set_row(1, 60)

    ws.write(4, 0, "Expected columns (from HRM):", title)
    cols = [
        ("Emp Code",        "รหัส"),
        ("Emp Name",        "ชื่อพนักงาน"),
        ("Date (BE)",       "วันที่"),
        ("Shift code",      "รหัสกะ"),
        ("Working hours",   "ชม.งาน"),
        ("OT*1.5",          "OTx1.5"),
        ("OT*2",            "OTx2"),
        ("OT*3",            "OTx3"),
        ("Absent",          "ขาดงาน"),
        ("Sick leave",      "ลาป่วย"),
        ("Personal leave",  "ลากิจ"),
        ("Annual leave",    "พักร้อน"),
    ]
    for c, h in enumerate(["English", "Thai (HRM label)"]):
        ws.write(6, c, h, hdr)
    for i, (en, th) in enumerate(cols):
        ws.write(7 + i, 0, en)
        ws.write(7 + i, 1, th)

    ws.set_column(0, 1, 24)
    wb.close()
    buf.seek(0)
    return buf.getvalue()


def employee_master_template() -> bytes:
    """Rich employee master list template with all org-chart fields."""
    return _make_xlsx(
        sheet_name="Headcount Updated",
        headers=[
            "Emp. No.", "Emp. Name", "ชื่อ", "Nick name",
            "Dept by Location", "Cost Centre Name", "Thai or Expat",
            "Mgr", "Level", "Title", "Mgr.", "Direct / Indirect",
            "Joined date", "Status",
        ],
        example_rows=[
            ["1021499", "Mr.Nicholas Doyle", "นายนิโคลัส ดอยล์", "Nick",
             "Admin", "354 -Finance&HR&Admin&Safety Department", "Expat",
             "Martin U. Ripple", 3, "General Manager", "Mgr.", "Indirect",
             "2021-04-01", "AMS"],
            ["1021656", "Mr.Chaiyanan Singson", "นายชัยนันท์ สิงห์สน", "Nan",
             "HR", "356 -Finance&HR&Admin&Safety Department", "Thai",
             "Nicholas Doyle", 3, "HR Manager", "Mgr.", "Indirect",
             "2026-02-16", "AMS"],
            ["1021442", "Ms.Prattana Yuchamnean", "น.ส.ปรัชญา ยุชมเนียน", "Jeab",
             "HR", "356 -Finance&HR&Admin&Safety Department", "Thai",
             "Chaiyanan Singson", 2, "Safety Officer", "", "Indirect",
             "2019-04-01", "AMS"],
        ],
        notes=[
            "RICH FORMAT — required for the Org Chart page. Replaces the simpler NameList format.",
            "Emp. No. = unique employee number, must NOT be blank.",
            "Mgr = full name of this person's direct manager (must match another Emp. Name in this file).",
            "    The system will auto-resolve manager name → manager Emp. No.  Don't put Emp. No. here.",
            "Mgr. column = the role of THIS person (not their manager): 'Mgr.', 'Sup.', 'Leader', or blank.",
            "Cost Centre Name format: '<code> - <name>'.  The leading number becomes the cost code.",
            "Status: AMS = permanent staff, SUB = subcontract, Guard = security, CNK = C&K outsource.",
            "Level = 1 (operator), 2 (specialist/supervisor), 3 (manager+).",
            "Direct / Indirect: 'Direct' (production) or 'Indirect' (support / overhead).",
            "Re-uploading this file marks any employees not in the new list as INACTIVE.",
        ],
        column_widths={0: 12, 1: 26, 2: 26, 3: 12, 4: 16, 5: 36, 6: 12, 7: 22,
                        8: 8, 9: 22, 10: 8, 11: 14, 12: 12, 13: 10},
    )


def change_request_bulk_template() -> bytes:
    """Bulk change-request upload template — submit many requests at once."""
    return _make_xlsx(
        sheet_name="Bulk Change Requests",
        headers=["Emp. No.", "Field", "New Value", "Reason"],
        example_rows=[
            ["1021568", "cost_code", "210", "Reassignment to CNC team effective Apr 1"],
            ["1021629", "level", "2", "Promoted to Senior Operator after performance review"],
            ["1021501", "d_in", "Direct", "Moved from indirect support to production line"],
            ["1021445", "emp_type", "PER", "Converted from contract to permanent"],
        ],
        notes=[
            "BULK SUBMISSION — each row becomes one change request. All start as 'pending'.",
            "Field column accepts: cost_code, emp_type, d_in, level, emp_name.",
            "  - cost_code   → must match a code in your Cost Group config",
            "  - emp_type    → PER (Permanent), SUB (Contract), TEM (Temporary)",
            "  - d_in        → Direct or Indirect",
            "  - level       → 1, 2, or 3",
            "  - emp_name    → free text (employee's display name)",
            "Reason is REQUIRED (10+ characters). Empty reason rows will be skipped.",
            "Emp. No. must match an existing active employee. Unknown numbers will be skipped.",
            "Each row creates a separate request — admin reviews each individually.",
            "If you're an admin, you can apply them all immediately by ticking the box on import.",
        ],
        column_widths={0: 12, 1: 18, 2: 18, 3: 50},
    )


# Easy lookup table used by the Upload UI
TEMPLATES: dict[str, tuple[str, callable]] = {
    "employee_master": ("Employee_List_MASTER_template.xlsx", employee_master_template),
    "name_list":     ("NameList_template.xlsx",          name_list_template),
    "manager":       ("Manager_template.xlsx",           manager_template),
    "cost_group":    ("CostGroup_template.xlsx",         cost_group_template),
    "holidays":      ("Holidays_template.xlsx",          holidays_template),
    "ot_detail":     ("OT_Detail_template.xlsx",         ot_detail_template),
    "ot_legacy":     ("OT_Summary_legacy_sample.xlsx",   ot_legacy_template),
    "leave_legacy":  ("Leave_Summary_sample.xlsx",       leave_legacy_template),
    "timesheet_ref": ("Timesheet_format_reference.xlsx", timesheet_format_reference),
    "change_request_bulk": ("Change_Requests_bulk_template.xlsx", change_request_bulk_template),
}
