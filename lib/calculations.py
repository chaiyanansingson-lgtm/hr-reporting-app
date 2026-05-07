"""
Calculation engine for the main HR report.

The HRM stores everything in HOURS at daily granularity.  The user wants the
report to optionally display in DAYS (via a configurable hours-per-day factor)
or HOURS.  All conversions happen at display time -- raw data on disk stays in
hours, so changing the factor never rewrites the database.

Report shape (matches the screenshot the user shared):

    SG&A/Manu   Function    Total HC | Permanent HC | Contract HC | TP HC
                            Total Working Hrs | Perm WH | Contract WH
                            Total Absent (excl AL) | Perm AB | Contract AB
                            % Total Absent | % Perm AB | % Contract AB
                            OT*1 | OT*1.5 | OT*2 | OT*3 | Total OT | % OT
                            Total AL | Perm AL | Contract AL    <-- optional
"""
from __future__ import annotations
import pandas as pd
import sqlite3
from . import db


def standard_working_days_in_period(period_yyyy_mm: str,
                                     username: str | None = None) -> tuple[int, float]:
    """Return (num_working_days, total_standard_hours_per_employee) for a period.

    When `username` is given, the user's personal overrides for
    holidays / hour_config / period_overrides take precedence over master.

    Resolution order:
      1. Auto-compute from effective holidays + effective weekday hours
         (effective = user override if set, else master).
      2. Apply effective period_override for this period (if any).
    """
    from calendar import monthrange
    from datetime import date as _date

    cfg = db.effective_hour_config(username)
    weekday_hours = [
        cfg.get("monday_hours", 8.0),    cfg.get("tuesday_hours", 8.0),
        cfg.get("wednesday_hours", 8.0), cfg.get("thursday_hours", 8.0),
        cfg.get("friday_hours", 8.0),    cfg.get("saturday_hours", 0.0),
        cfg.get("sunday_hours", 0.0),
    ]
    holidays_list = db.effective_holidays(username)
    holidays_set = {h.get("holiday_date") for h in holidays_list if h.get("holiday_date")}

    year, month = map(int, period_yyyy_mm.split("-"))
    days_in_month = monthrange(year, month)[1]
    auto_work_days = 0
    auto_total_hrs = 0.0
    nonzero_hrs = []
    for d in range(1, days_in_month + 1):
        dt = _date(year, month, d)
        if dt.isoformat() in holidays_set:
            continue
        hrs = weekday_hours[dt.weekday()] or 0.0
        if hrs > 0:
            auto_work_days += 1
            auto_total_hrs += float(hrs)
            nonzero_hrs.append(float(hrs))
    auto_daily = (sum(nonzero_hrs) / len(nonzero_hrs)) if nonzero_hrs else 8.0

    override = db.effective_period_override(period_yyyy_mm, username) or {}
    wd_o = override.get("working_days")
    dh_o = override.get("daily_std_hours")
    wd = int(wd_o) if wd_o not in (None, "") else auto_work_days
    dh = float(dh_o) if dh_o not in (None, "") else auto_daily
    return wd, wd * dh


# ----------------------------- main report builder -----------------------------

def build_report(period: str,
                 unit: str = "Hours",
                 include_annual_leave_cols: bool = True,
                 cost_codes_filter: list[str] | None = None,
                 wh_mode: str = "actual",
                 deduct_al_from_wh: bool = False,
                 deduct_sick_from_wh: bool = False,
                 deduct_business_from_wh: bool = False,
                 deduct_without_pay_from_wh: bool = False,
                 deduct_other_leaves_from_wh: bool = False,  # legacy: applies to all 3 if True
                 include_al_in_absent_pct: bool = False,
                 username: str | None = None) -> dict:
    """
    Build the main report for one period.

    Returns a dict containing:
        - rows        : list of dict (one per Function row)
        - groups      : list of dict (one per SG&A/Manu group totals)
        - grand_total : dict
        - meta        : echo of period / unit / etc.
    """
    cfg = db.effective_hour_config(username)
    hpd = cfg.get("hours_per_day", 8.0) or 8.0
    factor = 1.0 if unit == "Hours" else 1.0 / hpd

    conn = db.get_connection()
    try:
        # Pull joined rows: timesheet * employee * cost_group, filter by period
        sql = """
            SELECT t.emp_no, t.work_date, t.period, t.work_hours, t.late_hours, t.early_hours,
                   t.ot1_hours, t.ot15_hours, t.ot2_hours, t.ot3_hours,
                   t.absent_hours, t.sick_hours, t.personal_hours, t.annual_hours,
                   e.emp_type, e.cost_code, e.d_in,
                   c.department, c.sg_a_manu, c.sort_order
              FROM timesheet t
              JOIN employees e   ON e.emp_no = t.emp_no
              LEFT JOIN cost_groups c ON c.code = e.cost_code
             WHERE t.period = ?
        """
        params = [period]
        if cost_codes_filter:
            sql += f" AND e.cost_code IN ({','.join(['?']*len(cost_codes_filter))})"
            params.extend(cost_codes_filter)

        df = pd.read_sql_query(sql, conn, params=params)

        # If detailed OT data exists for this period, REPLACE timesheet OT columns
        ot_check = pd.read_sql_query(
            """SELECT emp_no, work_date, multiplier, SUM(hours) AS h
                 FROM ot_entries WHERE period = ?
                 GROUP BY emp_no, work_date, multiplier""",
            conn, params=[period],
        )
    finally:
        conn.close()

    # Apply user's cost-group top reassignments (if any)
    if username:
        cg_ov = db.get_user_override(username, "cost_group_tops") or {}
        if cg_ov and not df.empty:
            for code, vals in cg_ov.items():
                mask = df["cost_code"] == code
                if mask.any():
                    if "sg_a_manu" in vals:
                        df.loc[mask, "sg_a_manu"] = vals["sg_a_manu"]
                    if "sort_order" in vals:
                        df.loc[mask, "sort_order"] = vals["sort_order"]

    if not df.empty and not ot_check.empty:
        # Pivot OT detail into per-(emp,date) per-multiplier columns
        pivot = ot_check.pivot_table(
            index=["emp_no", "work_date"], columns="multiplier",
            values="h", aggfunc="sum", fill_value=0,
        ).reset_index()
        pivot.columns.name = None
        for mult, col in [(1.0, "ot1_h"), (1.5, "ot15_h"), (2.0, "ot2_h"), (3.0, "ot3_h")]:
            if mult in pivot.columns:
                pivot = pivot.rename(columns={mult: col})
            else:
                pivot[col] = 0
        df = df.merge(
            pivot[["emp_no", "work_date", "ot1_h", "ot15_h", "ot2_h", "ot3_h"]],
            on=["emp_no", "work_date"], how="left",
        )
        # Override the timesheet OT columns
        df["ot1_hours"] = df["ot1_h"].fillna(0)
        df["ot15_hours"] = df["ot15_h"].fillna(0)
        df["ot2_hours"] = df["ot2_h"].fillna(0)
        df["ot3_hours"] = df["ot3_h"].fillna(0)
        df = df.drop(columns=["ot1_h", "ot15_h", "ot2_h", "ot3_h"])

    if df.empty:
        return {"rows": [], "groups": [], "grand_total": {}, "meta":
                {"period": period, "unit": unit, "hours_per_day": hpd,
                 "warning": "No timesheet data for this period."}}

    # Fill missing department / sg_a_manu so unmapped employees show in a bucket
    df["department"] = df["department"].fillna("(Unmapped)")
    df["sg_a_manu"] = df["sg_a_manu"].fillna("(Unmapped)")
    df["sort_order"] = df["sort_order"].fillna(999).astype(int)

    # Resolve per-leave-type deduction flags
    # Legacy `deduct_other_leaves_from_wh=True` means deduct all 3
    d_sick = deduct_sick_from_wh or deduct_other_leaves_from_wh
    d_business = deduct_business_from_wh or deduct_other_leaves_from_wh
    d_without_pay = deduct_without_pay_from_wh or deduct_other_leaves_from_wh

    # Function-level rollup
    rows = _aggregate(df, group_cols=["sg_a_manu", "department", "sort_order"],
                      factor=factor, period=period, wh_mode=wh_mode,
                      deduct_al=deduct_al_from_wh,
                      deduct_sick=d_sick, deduct_business=d_business,
                      deduct_without_pay=d_without_pay,
                      include_al_in_absent=include_al_in_absent_pct,
                      username=username)
    rows = rows.sort_values(["sort_order", "sg_a_manu", "department"]).reset_index(drop=True)

    # Group-level rollup (Total SG&A, Total MANU, etc.)
    groups = _aggregate(df, group_cols=["sg_a_manu"],
                        factor=factor, period=period, wh_mode=wh_mode,
                        deduct_al=deduct_al_from_wh,
                        deduct_sick=d_sick, deduct_business=d_business,
                        deduct_without_pay=d_without_pay,
                        include_al_in_absent=include_al_in_absent_pct,
                        username=username)
    groups = groups.sort_values(["sg_a_manu"]).reset_index(drop=True)

    # Grand total row
    grand = _aggregate(df, group_cols=None,
                       factor=factor, period=period, wh_mode=wh_mode,
                       deduct_al=deduct_al_from_wh,
                       deduct_sick=d_sick, deduct_business=d_business,
                       deduct_without_pay=d_without_pay,
                       include_al_in_absent=include_al_in_absent_pct,
                       username=username)
    grand_dict = grand.iloc[0].to_dict() if not grand.empty else {}

    work_days_meta, std_hrs_meta = (None, None)
    if wh_mode == "standard":
        work_days_meta, std_hrs_meta = standard_working_days_in_period(period, username)

    return {
        "rows": rows.to_dict("records"),
        "groups": groups.to_dict("records"),
        "grand_total": grand_dict,
        "meta": {
            "period": period, "unit": unit, "hours_per_day": hpd,
            "include_al": include_annual_leave_cols,
            "wh_mode": wh_mode,
            "deduct_al": deduct_al_from_wh,
            "deduct_sick": d_sick,
            "deduct_business": d_business,
            "deduct_without_pay": d_without_pay,
            "include_al_in_absent": include_al_in_absent_pct,
            "standard_work_days": work_days_meta,
            "standard_hrs_per_emp": std_hrs_meta,
            "has_user_overrides": bool(username and db.list_user_overrides(username)),
        },
    }


def _aggregate(df: pd.DataFrame, group_cols: list[str] | None, factor: float,
               period: str = None, wh_mode: str = "actual",
               deduct_al: bool = False,
               deduct_sick: bool = False,
               deduct_business: bool = False,
               deduct_without_pay: bool = False,
               include_al_in_absent: bool = False,
               username: str | None = None) -> pd.DataFrame:
    """Single aggregation routine reused for function rows, group totals, and
    grand total.  Pass group_cols=None for the grand total."""

    # Per-employee monthly aggregation first (so HC = distinct employees)
    emp_agg = (
        df.groupby(["emp_no", "emp_type", "d_in"] + (group_cols or []), dropna=False)
          .agg(
              work_hours=("work_hours", "sum"),
              late_hours=("late_hours", "sum"),
              early_hours=("early_hours", "sum"),
              ot1_hours=("ot1_hours", "sum"),
              ot15_hours=("ot15_hours", "sum"),
              ot2_hours=("ot2_hours", "sum"),
              ot3_hours=("ot3_hours", "sum"),
              absent_hours=("absent_hours", "sum"),
              sick_hours=("sick_hours", "sum"),
              personal_hours=("personal_hours", "sum"),
              annual_hours=("annual_hours", "sum"),
          )
          .reset_index()
    )

    if group_cols:
        grouped = emp_agg.groupby(group_cols, dropna=False)
    else:
        # treat whole frame as a single group
        emp_agg["__all__"] = "ALL"
        grouped = emp_agg.groupby("__all__")

    # Pre-compute standard working hours per employee for the period if needed
    std_hrs_per_emp = 0.0
    if wh_mode == "standard" and period:
        _, std_hrs_per_emp = standard_working_days_in_period(period, username)

    result_rows = []
    for keys, g in grouped:
        if not isinstance(keys, tuple):
            keys = (keys,)

        # Headcount
        total_hc = g["emp_no"].nunique()
        perm_hc = g.loc[g["emp_type"] == "PER", "emp_no"].nunique()
        cont_hc = g.loc[g["emp_type"] == "SUB", "emp_no"].nunique()
        tp_hc = g.loc[g["emp_type"] == "TEM", "emp_no"].nunique()

        # Working hours: actual (from timesheet) or standard (HC × std hrs)
        f = factor
        if wh_mode == "standard":
            total_wh = total_hc * std_hrs_per_emp * f
            perm_wh = perm_hc * std_hrs_per_emp * f
            cont_wh = cont_hc * std_hrs_per_emp * f
        else:
            total_wh = g["work_hours"].sum() * f
            perm_wh = g.loc[g["emp_type"] == "PER", "work_hours"].sum() * f
            cont_wh = g.loc[g["emp_type"] == "SUB", "work_hours"].sum() * f

        # Absenteeism (excl AL) = absent + sick + personal
        def _ab(row): return row["absent_hours"] + row["sick_hours"] + row["personal_hours"]
        total_ab = (g["absent_hours"] + g["sick_hours"] + g["personal_hours"]).sum() * f
        perm_ab = (g.loc[g["emp_type"] == "PER",
                         ["absent_hours", "sick_hours", "personal_hours"]].sum().sum()) * f
        cont_ab = (g.loc[g["emp_type"] == "SUB",
                         ["absent_hours", "sick_hours", "personal_hours"]].sum().sum()) * f

        def _pct(absent, working): return (absent / (absent + working) * 100) if (absent + working) > 0 else 0.0

        # OT (in chosen unit)
        ot1 = g["ot1_hours"].sum() * f
        ot15 = g["ot15_hours"].sum() * f
        ot2 = g["ot2_hours"].sum() * f
        ot3 = g["ot3_hours"].sum() * f
        ot_total = ot1 + ot15 + ot2 + ot3
        pct_ot = (ot_total / total_wh * 100) if total_wh > 0 else 0.0

        # Per-leave-type breakdowns (in chosen unit)
        # Sick = sick_hours, Business/Personal = personal_hours, Without Pay = absent_hours
        total_sick = g["sick_hours"].sum() * f
        perm_sick = g.loc[g["emp_type"] == "PER", "sick_hours"].sum() * f
        cont_sick = g.loc[g["emp_type"] == "SUB", "sick_hours"].sum() * f

        total_bus = g["personal_hours"].sum() * f
        perm_bus = g.loc[g["emp_type"] == "PER", "personal_hours"].sum() * f
        cont_bus = g.loc[g["emp_type"] == "SUB", "personal_hours"].sum() * f

        total_wp = g["absent_hours"].sum() * f
        perm_wp = g.loc[g["emp_type"] == "PER", "absent_hours"].sum() * f
        cont_wp = g.loc[g["emp_type"] == "SUB", "absent_hours"].sum() * f

        # Annual leave (in chosen unit)
        total_al = g["annual_hours"].sum() * f
        perm_al = g.loc[g["emp_type"] == "PER", "annual_hours"].sum() * f
        cont_al = g.loc[g["emp_type"] == "SUB", "annual_hours"].sum() * f

        # Apply optional WH deductions per leave type
        if deduct_al:
            total_wh -= total_al
            perm_wh -= perm_al
            cont_wh -= cont_al
        if deduct_sick:
            total_wh -= total_sick
            perm_wh -= perm_sick
            cont_wh -= cont_sick
        if deduct_business:
            total_wh -= total_bus
            perm_wh -= perm_bus
            cont_wh -= cont_bus
        if deduct_without_pay:
            total_wh -= total_wp
            perm_wh -= perm_wp
            cont_wh -= cont_wp

        # % Absenteeism: optionally include AL in numerator and denominator
        if include_al_in_absent:
            t_abs = total_ab + total_al
            p_abs = perm_ab + perm_al
            c_abs = cont_ab + cont_al
        else:
            t_abs, p_abs, c_abs = total_ab, perm_ab, cont_ab

        row = {
            "Total HC": total_hc, "Permanent HC": perm_hc,
            "Contract HC": cont_hc, "TP HC": tp_hc,
            "Total Working Hrs": total_wh,
            "Permanent Working Hrs": perm_wh,
            "Contract Working Hrs": cont_wh,
            "Total Absent Hrs": total_ab,
            "Permanent Absent Hrs": perm_ab,
            "Contract Absent Hrs": cont_ab,
            "% Total Absent": _pct(t_abs, total_wh),
            "% Permanent Absent": _pct(p_abs, perm_wh),
            "% Contract Absent": _pct(c_abs, cont_wh),
            "OT*1": ot1, "OT*1.5": ot15, "OT*2": ot2, "OT*3": ot3,
            "Total OT": ot_total, "% OT": pct_ot,
            # Per-leave breakdown columns
            "Total Sick": total_sick, "Permanent Sick": perm_sick, "Contract Sick": cont_sick,
            "Total Business": total_bus, "Permanent Business": perm_bus, "Contract Business": cont_bus,
            "Total Without Pay": total_wp, "Permanent Without Pay": perm_wp, "Contract Without Pay": cont_wp,
            "Total AL": total_al, "Permanent AL": perm_al, "Contract AL": cont_al,
        }
        # attach grouping keys
        for col_name, val in zip(group_cols or [], keys):
            row[col_name] = val
        result_rows.append(row)

    return pd.DataFrame(result_rows)


# ----------------------------- chart-friendly time series -----------------------------

def monthly_trend(metric: str, last_n_periods: int = 12, sg_a_manu: str | None = None) -> pd.DataFrame:
    """Return monthly time series of a metric for charts (FY2026 style).
    metric in: 'absenteeism_pct', 'ot_pct', 'headcount', 'annual_leave_hours'.
    """
    conn = db.get_connection()
    try:
        sql = """
            SELECT t.emp_no, t.work_date, t.period,
                   t.work_hours, t.absent_hours, t.sick_hours, t.personal_hours,
                   t.ot1_hours, t.ot15_hours, t.ot2_hours, t.ot3_hours, t.annual_hours,
                   e.emp_type, c.sg_a_manu
              FROM timesheet t
              JOIN employees e ON e.emp_no = t.emp_no
              LEFT JOIN cost_groups c ON c.code = e.cost_code
        """
        df = pd.read_sql_query(sql, conn)
    finally:
        conn.close()
    if df.empty:
        return pd.DataFrame(columns=["period", "value"])
    if sg_a_manu:
        df = df[df["sg_a_manu"] == sg_a_manu]
    df["absent_total"] = df["absent_hours"] + df["sick_hours"] + df["personal_hours"]

    by_period = df.groupby("period").agg(
        work=("work_hours", "sum"),
        absent=("absent_total", "sum"),
        ot=("ot1_hours", "sum"),
        ot15=("ot15_hours", "sum"),
        ot2=("ot2_hours", "sum"),
        ot3=("ot3_hours", "sum"),
        al=("annual_hours", "sum"),
        hc=("emp_no", "nunique"),
    ).reset_index()
    by_period["ot_total"] = by_period[["ot", "ot15", "ot2", "ot3"]].sum(axis=1)
    by_period["absenteeism_pct"] = by_period.apply(
        lambda r: r["absent"] / (r["absent"] + r["work"]) * 100 if (r["absent"] + r["work"]) > 0 else 0,
        axis=1,
    )
    by_period["ot_pct"] = by_period.apply(
        lambda r: r["ot_total"] / r["work"] * 100 if r["work"] > 0 else 0, axis=1
    )

    metric_map = {
        "absenteeism_pct": "absenteeism_pct",
        "ot_pct": "ot_pct",
        "headcount": "hc",
        "annual_leave_hours": "al",
        "working_hours": "work",
    }
    col = metric_map.get(metric, "absenteeism_pct")
    out = by_period[["period", col]].rename(columns={col: "value"})
    return out.sort_values("period").tail(last_n_periods).reset_index(drop=True)


# ----------------------------- FY2026 dashboard-style breakdowns -----------------------------

def _load_joined_timesheet() -> pd.DataFrame:
    """Helper: pull the full joined timesheet across all periods.
    Applies OT-detail override per-period when ot_entries has data."""
    conn = db.get_connection()
    try:
        sql = """
            SELECT t.emp_no, t.work_date, t.period,
                   t.work_hours, t.absent_hours, t.sick_hours,
                   t.personal_hours, t.annual_hours,
                   t.ot1_hours, t.ot15_hours, t.ot2_hours, t.ot3_hours,
                   e.emp_type, c.department, c.sg_a_manu
              FROM timesheet t
              JOIN employees e ON e.emp_no = t.emp_no
              LEFT JOIN cost_groups c ON c.code = e.cost_code
        """
        df = pd.read_sql_query(sql, conn)

        # Per-period OT override from ot_entries
        ot_all = pd.read_sql_query(
            """SELECT period, emp_no, work_date, multiplier, SUM(hours) AS h
                 FROM ot_entries GROUP BY period, emp_no, work_date, multiplier""",
            conn,
        )
    finally:
        conn.close()

    if not df.empty and not ot_all.empty:
        periods_with_detail = set(ot_all["period"].unique())
        # Pivot OT detail
        pivot = ot_all.pivot_table(
            index=["emp_no", "work_date"], columns="multiplier",
            values="h", aggfunc="sum", fill_value=0,
        ).reset_index()
        pivot.columns.name = None
        for mult, col in [(1.0, "ot1_h"), (1.5, "ot15_h"), (2.0, "ot2_h"), (3.0, "ot3_h")]:
            if mult in pivot.columns:
                pivot = pivot.rename(columns={mult: col})
            else:
                pivot[col] = 0
        df = df.merge(
            pivot[["emp_no", "work_date", "ot1_h", "ot15_h", "ot2_h", "ot3_h"]],
            on=["emp_no", "work_date"], how="left",
        )
        # Only override OT for periods that have detail data; preserve timesheet OT otherwise
        mask = df["period"].isin(periods_with_detail)
        for src, dst in [("ot1_h", "ot1_hours"), ("ot15_h", "ot15_hours"),
                          ("ot2_h", "ot2_hours"), ("ot3_h", "ot3_hours")]:
            df.loc[mask, dst] = df.loc[mask, src].fillna(0)
        df = df.drop(columns=["ot1_h", "ot15_h", "ot2_h", "ot3_h"])

    return df


def absenteeism_breakdown_by_month(last_n_periods: int = 12) -> pd.DataFrame:
    """Return per-month % breakdown by leave type, matching the FY2026 chart layout.

    Columns: period, working_hrs,
             total_absent_pct, sick_pct, business_pct, without_pay_pct, annual_pct
    """
    df = _load_joined_timesheet()
    if df.empty:
        return pd.DataFrame(columns=["period", "working_hrs",
                                     "total_absent_pct", "sick_pct", "business_pct",
                                     "without_pay_pct", "annual_pct"])
    g = df.groupby("period").agg(
        working=("work_hours", "sum"),
        absent=("absent_hours", "sum"),
        sick=("sick_hours", "sum"),
        personal=("personal_hours", "sum"),
        annual=("annual_hours", "sum"),
    ).reset_index()
    # absenteeism denominator excludes annual (per HR convention used in original file)
    g["denom_excl_al"] = g["absent"] + g["sick"] + g["personal"] + g["working"]
    g["denom_total"] = g["working"]   # for AL%, denominator is working hours
    def safe_div(n, d): return (n / d) if d > 0 else 0.0
    g["sick_pct"]       = g.apply(lambda r: safe_div(r["sick"], r["denom_excl_al"]) * 100, axis=1)
    g["business_pct"]   = g.apply(lambda r: safe_div(r["personal"], r["denom_excl_al"]) * 100, axis=1)
    g["without_pay_pct"] = g.apply(lambda r: safe_div(r["absent"], r["denom_excl_al"]) * 100, axis=1)
    g["total_absent_pct"] = g["sick_pct"] + g["business_pct"] + g["without_pay_pct"]
    g["annual_pct"]     = g.apply(lambda r: safe_div(r["annual"], r["denom_total"]) * 100, axis=1)
    out = g[["period", "working", "total_absent_pct", "sick_pct", "business_pct",
             "without_pay_pct", "annual_pct"]].rename(columns={"working": "working_hrs"})
    return out.sort_values("period").tail(last_n_periods).reset_index(drop=True)


def absenteeism_by_department_by_month(last_n_periods: int = 12,
                                       use_top_level: bool = True) -> pd.DataFrame:
    """Return long DataFrame with columns: period, group, absenteeism_pct.
    `group` is the SG&A/MANU top level if use_top_level else the Function (department)."""
    df = _load_joined_timesheet()
    if df.empty:
        return pd.DataFrame(columns=["period", "group", "absenteeism_pct"])
    df["absent_total"] = df["absent_hours"] + df["sick_hours"] + df["personal_hours"]
    key = "sg_a_manu" if use_top_level else "department"
    df[key] = df[key].fillna("(Unmapped)")
    g = df.groupby(["period", key]).agg(
        absent=("absent_total", "sum"),
        work=("work_hours", "sum"),
    ).reset_index()
    g["absenteeism_pct"] = g.apply(
        lambda r: (r["absent"] / (r["absent"] + r["work"]) * 100) if (r["absent"] + r["work"]) > 0 else 0.0,
        axis=1,
    )
    g = g.rename(columns={key: "group"})[["period", "group", "absenteeism_pct"]]
    # last_n: keep only the latest N periods overall
    keep_periods = sorted(g["period"].unique())[-last_n_periods:]
    return g[g["period"].isin(keep_periods)].sort_values(["period", "group"]).reset_index(drop=True)


def ot_by_department_by_month(last_n_periods: int = 12,
                              use_top_level: bool = True) -> pd.DataFrame:
    """Return long DataFrame: period, group, ot_pct (= total OT / working hours)."""
    df = _load_joined_timesheet()
    if df.empty:
        return pd.DataFrame(columns=["period", "group", "ot_pct"])
    df["ot_total"] = df[["ot1_hours", "ot15_hours", "ot2_hours", "ot3_hours"]].sum(axis=1)
    key = "sg_a_manu" if use_top_level else "department"
    df[key] = df[key].fillna("(Unmapped)")
    g = df.groupby(["period", key]).agg(
        ot=("ot_total", "sum"),
        work=("work_hours", "sum"),
    ).reset_index()
    g["ot_pct"] = g.apply(lambda r: (r["ot"] / r["work"] * 100) if r["work"] > 0 else 0.0, axis=1)
    g = g.rename(columns={key: "group"})[["period", "group", "ot_pct"]]
    keep_periods = sorted(g["period"].unique())[-last_n_periods:]
    return g[g["period"].isin(keep_periods)].sort_values(["period", "group"]).reset_index(drop=True)


def working_vs_ot_by_department(period: str) -> pd.DataFrame:
    """Single-month bar-chart data: department, working_hrs, ot_hrs, ot_pct."""
    df = _load_joined_timesheet()
    if df.empty:
        return pd.DataFrame(columns=["department", "working_hrs", "ot_hrs", "ot_pct"])
    df = df[df["period"] == period].copy()
    df["department"] = df["department"].fillna("(Unmapped)")
    df["ot_total"] = df[["ot1_hours", "ot15_hours", "ot2_hours", "ot3_hours"]].sum(axis=1)
    g = df.groupby("department").agg(
        working_hrs=("work_hours", "sum"),
        ot_hrs=("ot_total", "sum"),
    ).reset_index()
    g["ot_pct"] = g.apply(lambda r: (r["ot_hrs"] / r["working_hrs"] * 100) if r["working_hrs"] > 0 else 0.0, axis=1)
    return g.sort_values("department").reset_index(drop=True)
