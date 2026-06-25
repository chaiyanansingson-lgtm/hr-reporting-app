# lib/feature_grants.py
# ---------------------------------------------------------------------------
# Lets Admin/Superadmin grant specific features to any ROLE or any STAFF NUMBER
# beyond what that role's capabilities give by default. Used by the Request
# Register (view + raw export); reusable for future grantable features.
# ---------------------------------------------------------------------------
import datetime as dt

from lib.db import get_conn, IS_POSTGRES, PH

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
    "INTEGER PRIMARY KEY AUTOINCREMENT"

# grantable features  ->  bilingual label
FEATURES = {
    "requests.view": "ดูทะเบียนคำขอ · View the request register",
    "requests.export": "ส่งออกข้อมูลดิบคำขอ · Export raw request data",
}


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS feature_grants (
        id {SERIAL},
        feature TEXT NOT NULL,
        grantee_type TEXT NOT NULL,          -- 'role' | 'emp_no'
        grantee TEXT NOT NULL,
        granted_by TEXT, granted_at TEXT,
        UNIQUE(feature, grantee_type, grantee)
    )""")
    conn.commit()


def grant(feature, grantee_type, grantee, actor="system"):
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute(f"""INSERT INTO feature_grants
            (feature, grantee_type, grantee, granted_by, granted_at)
            VALUES ({PH},{PH},{PH},{PH},{PH})""",
                    (feature, grantee_type, str(grantee).strip(), actor,
                     dt.datetime.now().isoformat(timespec="seconds")))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def revoke(grant_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"DELETE FROM feature_grants WHERE id={PH}", (grant_id,))
    conn.commit()


def list_grants(feature=None):
    conn = get_conn(); cur = conn.cursor()
    if feature:
        cur.execute("SELECT id,feature,grantee_type,grantee,granted_by,"
                    f"granted_at FROM feature_grants WHERE feature={PH} "
                    "ORDER BY feature,grantee_type,grantee", (feature,))
    else:
        cur.execute("SELECT id,feature,grantee_type,grantee,granted_by,"
                    "granted_at FROM feature_grants "
                    "ORDER BY feature,grantee_type,grantee")
    cols = ["id", "feature", "grantee_type", "grantee", "granted_by",
            "granted_at"]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _granted(feature, role, emp_no):
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute(f"""SELECT 1 FROM feature_grants WHERE feature={PH} AND (
            (grantee_type='role' AND grantee={PH}) OR
            (grantee_type='emp_no' AND grantee={PH}))""",
                    (feature, str(role or ""), str(emp_no or "")))
        return cur.fetchone() is not None
    except Exception:
        return False


def has_feature(feature):
    """True for Admin/Superadmin (system.users) or anyone granted by role/emp."""
    from lib.auth import current_user
    u = current_user()
    if not u:
        return False
    if "system.users" in u.get("caps", []):
        return True
    return _granted(feature, u.get("role"), u.get("emp_no"))
