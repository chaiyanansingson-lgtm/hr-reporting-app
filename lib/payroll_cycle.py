# lib/payroll_cycle.py
# ============================================================================
# AMS payroll-cycle windows for a given cycle month.
#
# Rule (from HR):
#   * Face-scan / attendance       : 1st  → last day of the CYCLE month
#   * OT, shift allowance, daily    : 21st of the PREVIOUS month → 20th of the
#     meal allowance (working-day      cycle month
#     based items)
#
# Example — "May 2026" cycle:
#   scan  : 2026-05-01 .. 2026-05-31
#   ot/allw: 2026-04-21 .. 2026-05-20
# ============================================================================
import calendar
import datetime as dt


def payroll_windows(year: int, month: int):
    """Return dict with the two date windows for a cycle month."""
    scan_start = dt.date(year, month, 1)
    scan_end = dt.date(year, month, calendar.monthrange(year, month)[1])
    # previous month for the OT/allowance window start
    py, pm = (year - 1, 12) if month == 1 else (year, month - 1)
    ot_start = dt.date(py, pm, 21)
    ot_end = dt.date(year, month, 20)
    return {
        "scan_start": scan_start, "scan_end": scan_end,
        "ot_start": ot_start, "ot_end": ot_end,
    }


def recent_cycles(n=12, today=None):
    """List the last n cycle (year, month) tuples, newest first."""
    today = today or dt.date.today()
    out = []
    y, m = today.year, today.month
    for _ in range(n):
        out.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out


def cycle_label(year, month, lang="th"):
    th = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
          "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    en = ["", "January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
    return f"{(th if lang=='th' else en)[month]} {year}"
