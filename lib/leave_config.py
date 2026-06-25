# lib/leave_config.py
# ---------------------------------------------------------------------------
# One admin-managed source of truth for leave types and leave-form rules:
#   • leave_types     — the list shown everywhere (key, TH/EN name, whether it
#                       REQUIRES evidence, active flag, display order)
#   • leave_settings  — form rules: which fields are mandatory, and whether
#                       leave may be submitted in HOUR units (admin toggle)
# Seeded with the standard AMS set, including the types from the 3 HR reports.
# ---------------------------------------------------------------------------
import datetime as dt

from lib.db import get_conn, IS_POSTGRES, PH

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
    "INTEGER PRIMARY KEY AUTOINCREMENT"

# (key, name_th, name_en, requires_evidence)
DEFAULT_TYPES = [
    ("annual", "ลาพักร้อน", "Annual leave", 0),
    ("sick_cert", "ลาป่วยมีใบรับรองแพทย์", "Sick — with medical certificate", 1),
    ("sick_nocert", "ลาป่วยไม่มีใบรับรองแพทย์", "Sick — no certificate", 0),
    ("sick", "ลาป่วย", "Sick (legacy)", 0),
    ("business", "ลากิจ", "Personal business", 0),
    ("business_urgent", "ลากิจฉุกเฉิน", "Emergency personal", 0),
    ("maternity", "ลาคลอด", "Maternity", 1),
    ("ordination", "ลาบวช", "Ordination", 0),
    ("military", "ลารับราชการทหาร", "Military service", 1),
    ("sterilization", "ลาทำหมัน", "Sterilization", 1),
    ("training", "ลาเพื่อฝึกอบรม/พัฒนาความรู้", "Training / development", 0),
    ("without_pay", "ลาไม่รับค่าจ้าง", "Leave without pay", 0),
    ("other", "อื่นๆ", "Other", 0),
]

DEFAULT_SETTINGS = {
    "mandatory_reason": "1",       # reason text required
    "mandatory_evidence": "0",     # require evidence for EVERY leave type
    "hour_unit_enabled": "0",      # allow submitting leave in hours
}


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS leave_types (
        id {SERIAL},
        lkey TEXT UNIQUE NOT NULL,
        name_th TEXT, name_en TEXT,
        requires_evidence INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        seq INTEGER NOT NULL DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS leave_settings (
        skey TEXT PRIMARY KEY, sval TEXT)""")
    conn.commit()
    # seed defaults once
    cur.execute("SELECT COUNT(*) FROM leave_types")
    if (cur.fetchone()[0] or 0) == 0:
        for i, (k, th, en, ev) in enumerate(DEFAULT_TYPES):
            cur.execute(f"""INSERT INTO leave_types (lkey, name_th, name_en,
                requires_evidence, active, seq)
                VALUES ({PH},{PH},{PH},{PH},1,{PH})""", (k, th, en, ev, i))
        conn.commit()
    for k, v in DEFAULT_SETTINGS.items():
        cur.execute(f"SELECT 1 FROM leave_settings WHERE skey={PH}", (k,))
        if not cur.fetchone():
            cur.execute(f"INSERT INTO leave_settings (skey, sval) "
                        f"VALUES ({PH},{PH})", (k, v))
    conn.commit()


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


def list_types(active_only=True):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM leave_types" +
                (" WHERE active=1" if active_only else "") +
                " ORDER BY seq, id")
    return _rows(cur)


def get_type(lkey):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM leave_types WHERE lkey={PH}", (lkey,))
    r = _rows(cur)
    return r[0] if r else None


def labels(active_only=False):
    """{lkey: 'ไทย / English'} for display everywhere."""
    return {t["lkey"]: f"{t['name_th']} / {t['name_en']}"
            for t in list_types(active_only=active_only)}


def requires_evidence(lkey):
    t = get_type(lkey)
    return bool(t and t.get("requires_evidence"))


def upsert_type(lkey, name_th, name_en, requires_evidence, active, seq):
    conn = get_conn(); cur = conn.cursor()
    if get_type(lkey):
        cur.execute(f"""UPDATE leave_types SET name_th={PH}, name_en={PH},
            requires_evidence={PH}, active={PH}, seq={PH} WHERE lkey={PH}""",
                    (name_th, name_en, int(requires_evidence), int(active),
                     int(seq), lkey))
    else:
        cur.execute(f"""INSERT INTO leave_types (lkey, name_th, name_en,
            requires_evidence, active, seq) VALUES ({PH},{PH},{PH},{PH},{PH},{PH})""",
                    (lkey, name_th, name_en, int(requires_evidence),
                     int(active), int(seq)))
    conn.commit()


def get_setting(key, default=""):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT sval FROM leave_settings WHERE skey={PH}", (key,))
    r = cur.fetchone()
    return r[0] if r else default


def set_setting(key, val):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT 1 FROM leave_settings WHERE skey={PH}", (key,))
    if cur.fetchone():
        cur.execute(f"UPDATE leave_settings SET sval={PH} WHERE skey={PH}",
                    (str(val), key))
    else:
        cur.execute(f"INSERT INTO leave_settings (skey, sval) VALUES ({PH},{PH})",
                    (key, str(val)))
    conn.commit()


def hour_unit_enabled():
    return get_setting("hour_unit_enabled", "0") == "1"


def mandatory_reason():
    return get_setting("mandatory_reason", "1") == "1"


def mandatory_evidence_global():
    return get_setting("mandatory_evidence", "0") == "1"
