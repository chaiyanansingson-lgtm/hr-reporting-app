# lib/db.py
# ============================================================================
# One connection switch for the whole app.
#   - No secret set            -> SQLite file  data/hr.db   (local dev only;
#     on Streamlit Community Cloud this file is WIPED on every redeploy/sleep
#     — that was the old "re-upload every 7 days" pain)
#   - st.secrets["DATABASE_URL"] set -> Supabase Postgres (persistent,
#     daily backups on the Pro plan)
# Every other module calls get_conn() / IS_POSTGRES and never cares which.
# ============================================================================
import os

try:
    import streamlit as st
    _DB_URL = st.secrets.get("DATABASE_URL", "")
except Exception:
    _DB_URL = os.environ.get("DATABASE_URL", "")

IS_POSTGRES = bool(_DB_URL)

if IS_POSTGRES:
    import psycopg2
    import psycopg2.extras

    def get_conn():
        conn = psycopg2.connect(_DB_URL)
        return conn
else:
    import sqlite3

    def get_conn():
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect("data/hr.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

PH = "%s" if IS_POSTGRES else "?"


def secret(section, key=None, default=""):
    """Safely read st.secrets even when no secrets.toml exists at all
    (st.secrets raises rather than returning empty in that case)."""
    try:
        import streamlit as st
        if key is None:
            return st.secrets.get(section, default)
        sec = st.secrets.get(section, {})
        try:
            return sec.get(key, default)
        except AttributeError:
            return default
    except Exception:
        return default


def init_db():
    """Called once from app.py on boot. Idempotent AND resilient: each step
    runs in isolation so a failure in one module's migrate() can no longer
    abort the whole sequence and skip every migration after it (which left
    e.g. the LMS tables uncreated -> UndefinedTable). Failures are collected
    and surfaced rather than silently swallowed."""
    import importlib
    steps = [
        ("auth", "migrate"), ("rbac_seed", "seed"),
        ("employee_db", "migrate"), ("approval_db", "migrate"),
        ("erp_db", "migrate"), ("car_db", "migrate"),
        ("permit_db", "migrate"), ("stock_db", "migrate"),
        ("attendance_db", "migrate"), ("resign_db", "migrate"),
        ("lms_db", "migrate"), ("doc_numbers", "migrate"),
        ("feature_grants", "migrate"), ("approval_rules", "migrate"),
        ("leave_config", "migrate"), ("doc_templates", "migrate"),
        ("working_hours_db", "migrate"), ("weekly_metrics", "migrate"),
        ("announce_db", "migrate"), ("timesheet_db", "migrate"),
        ("kpi_calc", "migrate"), ("ot_salary_db", "migrate"),
        ("upload_log", "migrate"), ("video_quiz_db", "migrate"),
    ]
    errors = []
    for mod_name, fn_name in steps:
        try:
            mod = importlib.import_module(f"lib.{mod_name}")
            getattr(mod, fn_name)()
        except Exception as ex:
            errors.append(f"{mod_name}.{fn_name}() -> {type(ex).__name__}: {ex}")
    if errors:
        try:
            import streamlit as st
            st.warning("ภาวะเริ่มต้นฐานข้อมูลบางส่วนล้มเหลว (ระบบยังทำงานต่อ) "
                       "/ some DB init steps failed (app continued):\n- "
                       + "\n- ".join(errors))
        except Exception:
            for e in errors:
                print("[init_db] step failed (continued):", e)
