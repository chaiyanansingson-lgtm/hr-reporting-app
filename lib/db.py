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
    from psycopg2 import extensions as _pg_ext

    # TCP keepalives so a reused connection survives idle gaps to Supabase
    # (the database is in Singapore; this keeps the socket alive between clicks).
    _PG_KW = dict(keepalives=1, keepalives_idle=30,
                  keepalives_interval=10, keepalives_count=5)

    def _new_pg_conn():
        return psycopg2.connect(_DB_URL, **_PG_KW)

    def get_conn():
        # Reuse ONE warm connection per Streamlit session instead of opening a
        # brand-new connection — a full TCP + TLS handshake to Singapore — on
        # every single query. That repeated handshake (several network
        # round-trips each) was what made every button press slow. The reuse
        # check below is purely local (conn.closed), so it costs no round-trip.
        try:
            import streamlit as st
            c = st.session_state.get("_pgc")
            if c is not None and c.closed == 0:
                # If a previous query failed and left the transaction aborted,
                # clear it so this call isn't blocked (only after an error).
                if c.get_transaction_status() == _pg_ext.TRANSACTION_STATUS_INERROR:
                    c.rollback()
                return c
            c = _new_pg_conn()
            st.session_state["_pgc"] = c
            return c
        except Exception:
            # No active Streamlit session (rare — e.g. a background call):
            # fall back to a fresh connection.
            return _new_pg_conn()
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
    """Called once from app.py on boot. Idempotent."""
    from lib import auth, rbac_seed
    auth.migrate()
    rbac_seed.seed()
    from lib import employee_db
    employee_db.migrate()
    from lib import approval_db
    approval_db.migrate()
    from lib import erp_db
    erp_db.migrate()
    from lib import car_db
    car_db.migrate()
    from lib import permit_db
    permit_db.migrate()
    from lib import stock_db
    stock_db.migrate()
    from lib import attendance_db
    attendance_db.migrate()
    from lib import resign_db
    resign_db.migrate()
    from lib import lms_db
    lms_db.migrate()
    from lib import doc_numbers
    doc_numbers.migrate()
    from lib import feature_grants
    feature_grants.migrate()
    from lib import approval_rules
    approval_rules.migrate()
    from lib import leave_config
    leave_config.migrate()
    from lib import doc_templates
    doc_templates.migrate()
    from lib import working_hours_db
    working_hours_db.migrate()
    from lib import weekly_metrics
    weekly_metrics.migrate()
    from lib import announce_db
    announce_db.migrate()
    from lib import timesheet_db
    timesheet_db.migrate()
    from lib import kpi_calc
    kpi_calc.migrate()
    from lib import ot_salary_db
    ot_salary_db.migrate()
    from lib import upload_log
    upload_log.migrate()
    from lib import video_quiz_db
    video_quiz_db.migrate()
