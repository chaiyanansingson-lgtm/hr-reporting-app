# lib/upload_log.py — central audit log of every data upload, so admin/
# superadmin can see what was loaded, when, by whom, and roll back mistakes.
import datetime as dt
from lib.db import get_conn, IS_POSTGRES, PH

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS upload_log (
        id {SERIAL}, file_type TEXT, file_name TEXT, period TEXT,
        rows_inserted INTEGER, uploaded_by TEXT, uploaded_at TEXT,
        notes TEXT)""")
    conn.commit()


def log(file_type, file_name, period="", rows=0, user="", notes=""):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute(f"""INSERT INTO upload_log (file_type, file_name, period,
            rows_inserted, uploaded_by, uploaded_at, notes)
            VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
                    (file_type, file_name, period or "", int(rows or 0),
                     user or "", dt.datetime.now().isoformat(timespec="seconds"),
                     notes or ""))
        conn.commit()
    except Exception:
        pass  # logging must never break an upload


def recent(limit=100):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT file_type, file_name, period, rows_inserted,
        uploaded_by, uploaded_at, notes FROM upload_log
        ORDER BY id DESC LIMIT {int(limit)}""")
    cols = ["file_type", "file_name", "period", "rows_inserted",
            "uploaded_by", "uploaded_at", "notes"]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
