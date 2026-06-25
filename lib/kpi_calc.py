# lib/kpi_calc.py — derives all KPI-dashboard metrics from the ingested
# face-scan timesheet (timesheet_db.ts_days) joined to the employee master.
# Mirrors the old HRM dashboard's calculations exactly:
#   absenteeism (excl AL) = absent + sick + personal ; %=absent/(absent+work)
#   sick/business/without-pay % use denom = absent+sick+personal+work
#   annual % uses denom = work ; OT % = total OT / work
import pandas as pd
from lib.db import get_conn, IS_POSTGRES, PH
from lib import employee_db as edb
from lib import timesheet_db as tdb

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"

TARGET_DEFAULTS = {
    "absenteeism_total": 0.025, "sick_leave": 0.0440, "business_leave": 0.0189,
    "without_pay": 0.0000, "annual_leave": 0.0692, "ot_total": 0.2800,
    "turnover": 0.0200,
}


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS kpi_targets (
        target_key TEXT PRIMARY KEY, target_value REAL)""")
    cur.execute("SELECT COUNT(*) FROM kpi_targets")
    if (cur.fetchone()[0] or 0) == 0:
        for k, v in TARGET_DEFAULTS.items():
            cur.execute(f"INSERT INTO kpi_targets (target_key, target_value) "
                        f"VALUES ({PH},{PH})", (k, v))
    conn.commit()


def get_targets():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT target_key, target_value FROM kpi_targets")
    d = dict(TARGET_DEFAULTS)
    d.update({r[0]: r[1] for r in cur.fetchall()})
    return d


def set_targets(vals):
    conn = get_conn(); cur = conn.cursor()
    for k, v in vals.items():
        cur.execute(f"""INSERT INTO kpi_targets (target_key, target_value)
            VALUES ({PH},{PH})
            ON CONFLICT(target_key) DO UPDATE SET target_value=excluded.target_value"""
                    if not IS_POSTGRES else
                    f"""INSERT INTO kpi_targets (target_key, target_value)
            VALUES ({PH},{PH})
            ON CONFLICT(target_key) DO UPDATE SET target_value=EXCLUDED.target_value""",
                    (k, float(v)))
    conn.commit()


def _master_df():
    rows = []
    for r in edb.list_records("active"):
        g, fn = tdb.classify(r)
        rows.append({"emp_no": str(r.get("emp_no")), "group": g,
                     "function": fn,
                     "emp_type": (r.get("emp_type") or "PER").upper()})
    return pd.DataFrame(rows)


def load(upload_id):
    """Per-day rows joined to master. Columns: emp_no, period, work, ot1,
    ot15, ot2, ot3, absent, sick, personal, annual, group, function, emp_type."""
    conn = get_conn()
    df = pd.read_sql_query(
        f"""SELECT emp_no, work_date, working_hrs AS work, ot1, ot15, ot2, ot3,
            absent, sick, personal, annual FROM ts_days WHERE upload_id={PH}""",
        conn, params=(upload_id,))
    if df.empty:
        return df
    df["emp_no"] = df["emp_no"].astype(str)
    df["period"] = df["work_date"].astype(str).str.slice(0, 7)
    m = _master_df()
    df = df.merge(m, on="emp_no", how="left")
    df["group"] = df["group"].fillna("(Unmapped)")
    df["function"] = df["function"].fillna("(Unmapped)")
    df["emp_type"] = df["emp_type"].fillna("PER")
    return df


def periods(df):
    return sorted(df["period"].dropna().unique().tolist()) if not df.empty else []


def _safe(n, d):
    return (n / d) if d else 0.0


def absenteeism_breakdown_by_month(df, last_n=12):
    cols = ["period", "working_hrs", "total_absent_pct", "sick_pct",
            "business_pct", "without_pay_pct", "annual_pct"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    g = df.groupby("period").agg(
        working=("work", "sum"), absent=("absent", "sum"),
        sick=("sick", "sum"), personal=("personal", "sum"),
        annual=("annual", "sum")).reset_index()
    g["denom"] = g["absent"] + g["sick"] + g["personal"] + g["working"]
    g["sick_pct"] = g.apply(lambda r: _safe(r["sick"], r["denom"]) * 100, axis=1)
    g["business_pct"] = g.apply(lambda r: _safe(r["personal"], r["denom"]) * 100, axis=1)
    g["without_pay_pct"] = g.apply(lambda r: _safe(r["absent"], r["denom"]) * 100, axis=1)
    g["total_absent_pct"] = g["sick_pct"] + g["business_pct"] + g["without_pay_pct"]
    g["annual_pct"] = g.apply(lambda r: _safe(r["annual"], r["working"]) * 100, axis=1)
    g = g.rename(columns={"working": "working_hrs"})
    return g[cols].sort_values("period").tail(last_n).reset_index(drop=True)


def absenteeism_by_group_by_month(df, last_n=12, use_top=True):
    if df.empty:
        return pd.DataFrame(columns=["period", "group", "absenteeism_pct"])
    key = "group" if use_top else "function"
    d = df.copy()
    d["ab"] = d["absent"] + d["sick"] + d["personal"]
    g = d.groupby(["period", key]).agg(ab=("ab", "sum"),
                                       work=("work", "sum")).reset_index()
    g["absenteeism_pct"] = g.apply(
        lambda r: _safe(r["ab"], r["ab"] + r["work"]) * 100, axis=1)
    g = g.rename(columns={key: "group"})
    keep = sorted(g["period"].unique())[-last_n:]
    return g[g["period"].isin(keep)][["period", "group", "absenteeism_pct"]]\
        .sort_values(["period", "group"]).reset_index(drop=True)


def ot_by_group_by_month(df, last_n=12, use_top=True):
    if df.empty:
        return pd.DataFrame(columns=["period", "group", "ot_pct"])
    key = "group" if use_top else "function"
    d = df.copy()
    d["ot"] = d["ot1"] + d["ot15"] + d["ot2"] + d["ot3"]
    g = d.groupby(["period", key]).agg(ot=("ot", "sum"),
                                       work=("work", "sum")).reset_index()
    g["ot_pct"] = g.apply(lambda r: _safe(r["ot"], r["work"]) * 100, axis=1)
    g = g.rename(columns={key: "group"})
    keep = sorted(g["period"].unique())[-last_n:]
    return g[g["period"].isin(keep)][["period", "group", "ot_pct"]]\
        .sort_values(["period", "group"]).reset_index(drop=True)


def working_vs_ot_by_function(df, period):
    if df.empty:
        return pd.DataFrame(columns=["function", "working_hrs", "ot_hrs"])
    d = df[df["period"] == period].copy()
    d["ot"] = d["ot1"] + d["ot15"] + d["ot2"] + d["ot3"]
    g = d.groupby("function").agg(working_hrs=("work", "sum"),
                                  ot_hrs=("ot", "sum")).reset_index()
    return g.sort_values("function").reset_index(drop=True)


def single_month_table(df, period):
    """Per (group, function): HC by class + OT by multiplier — for the
    single-month headcount and OT-multiplier charts."""
    if df.empty:
        return pd.DataFrame()
    d = df[df["period"] == period]
    if d.empty:
        return pd.DataFrame()
    # headcount by class (distinct emp per function)
    hc = (d.groupby(["group", "function", "emp_type"])["emp_no"].nunique()
          .reset_index().pivot_table(index=["group", "function"],
          columns="emp_type", values="emp_no", fill_value=0).reset_index())
    for c in ("PER", "SUB", "TEM"):
        if c not in hc.columns:
            hc[c] = 0
    hc = hc.rename(columns={"PER": "Permanent HC", "SUB": "Contract HC",
                            "TEM": "TP HC"})
    ot = d.groupby(["group", "function"]).agg(
        **{"OT*1": ("ot1", "sum"), "OT*1.5": ("ot15", "sum"),
           "OT*2": ("ot2", "sum"), "OT*3": ("ot3", "sum")}).reset_index()
    return hc.merge(ot, on=["group", "function"], how="outer").fillna(0)
