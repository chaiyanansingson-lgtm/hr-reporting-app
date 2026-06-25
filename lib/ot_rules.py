# lib/ot_rules.py
# ============================================================================
# Canonical shift hours + OT scenario→multiplier rules (req. 5 & 6).
# Shared by pages/F_Leave_OT.py (the request UI) and lib/print_docs.py
# (the FM-HR-031 / shift-change printouts), so the rules live in ONE place.
#
# Shift hours (confirmed by HR):
#   Day shift   07:45 – 16:25   (OT after work starts 16:55 = end + 30-min break)
#   Night shift 23:00 – 07:40   (OT after work starts 08:10 = end + 30-min break)
#
# OT multipliers (payroll codes 1120/1130/1140, divisor 176):
#   ×1.5  after a normal workday, before a normal workday, and the FIRST 8h
#         on company weekends/holidays
#   ×3.0  holiday hours BEYOND the first 8
#   ×2.0  special holiday rate (e.g. department-approved Songkran exception)
#
# OT duration is always ≥ 0.5h and a multiple of 0.5h.
# ============================================================================

SHIFTS = {
    "day":   dict(th="กะกลางวัน", en="Day shift",
                  start="07:45", end="16:25", brk=30),
    "night": dict(th="กะกลางคืน", en="Night shift",
                  start="23:00", end="07:40", brk=30),
}

# OT scenarios.  mode controls how start/end times are derived:
#   "after"  → start = shift end + 30-min break  (day → 16:55, night → 08:10)
#   "before" → end   = shift start; start = end − hours
#   "free"   → staff picks a start time (weekend/holiday work)
OT_TYPES = {
    "after_workday":   dict(th="หลังเลิกงาน (วันทำงาน)",
                            en="After shift (workday)", rate=1.5, mode="after"),
    "before_workday":  dict(th="ก่อนเข้างาน (วันทำงาน)",
                            en="Before shift (workday)", rate=1.5, mode="before"),
    "holiday_first8":  dict(th="วันหยุด/นักขัตฤกษ์ 8 ชม.แรก",
                            en="Weekend/Holiday first 8h", rate=1.5, mode="free"),
    "holiday_beyond8": dict(th="วันหยุด เกิน 8 ชม.",
                            en="Holiday beyond 8h", rate=3.0, mode="free"),
    "holiday_special": dict(th="วันหยุดอัตราพิเศษ",
                            en="Special holiday rate", rate=2.0, mode="free"),
}

MIN_HOURS = 0.5
STEP_HOURS = 0.5


def shift_label(key, lang="th"):
    s = SHIFTS.get(key)
    if not s:
        return key or ""
    name = s["th"] if str(lang).startswith("th") else s["en"]
    return f"{name} {s['start']}–{s['end']}"


def ot_type_label(key, lang="th"):
    o = OT_TYPES.get(key)
    if not o:
        return key or ""
    name = o["th"] if str(lang).startswith("th") else o["en"]
    return f"{name} ×{o['rate']}"


def multiplier(ot_type_key):
    return OT_TYPES.get(ot_type_key, {}).get("rate", 1.5)


def _to_min(hhmm):
    h, m = str(hhmm)[:5].split(":")
    return int(h) * 60 + int(m)


def _to_hhmm(mins):
    mins %= (24 * 60)
    return f"{mins // 60:02d}:{mins % 60:02d}"


def snap_half_hour(hhmm):
    """Round a HH:MM string to the nearest 30 minutes."""
    return _to_hhmm(int(round(_to_min(hhmm) / 30.0)) * 30)


def ot_window(shift_key, ot_type_key, hours, free_start="08:00"):
    """Return (time_from, time_to) as 'HH:MM' for the scenario.
    Workday scenarios derive times from the shift; holiday scenarios use the
    chosen start (snapped to the 30-min grid)."""
    s = SHIFTS.get(shift_key, SHIFTS["day"])
    o = OT_TYPES.get(ot_type_key, OT_TYPES["after_workday"])
    dur = int(round(float(hours) * 60))
    if o["mode"] == "after":
        start = _to_min(s["end"]) + int(s["brk"])
        return _to_hhmm(start), _to_hhmm(start + dur)
    if o["mode"] == "before":
        end = _to_min(s["start"])
        return _to_hhmm(end - dur), _to_hhmm(end)
    start = int(round(_to_min(free_start) / 30.0)) * 30
    return _to_hhmm(start), _to_hhmm(start + dur)


def round_half(x):
    """Snap a number of hours to the nearest 0.5 (>= 0.5)."""
    try:
        v = round(float(x) * 2) / 2.0
    except Exception:
        v = MIN_HOURS
    return max(MIN_HOURS, v)
