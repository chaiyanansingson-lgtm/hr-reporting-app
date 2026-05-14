"""
RBAC seed data for Anca HR App.
v11.5 — Module 3 Salary & Compensation activated (2026-05-14).
v11.4 — RBAC Phase 1 foundation (2026-05-08).

Seeds the canonical roles, modules, capabilities, default role-capability
matrix, and the bootstrap user_roles entries for the v11.3 default accounts.

Idempotency rules:
  - roles, modules, capabilities         INSERT OR IGNORE (definitions are stable)
  - role_capabilities (the matrix)       Only seeds for a role if that role has
                                          ZERO entries — so Super Admin edits
                                          made later in the UI are preserved
                                          across redeploys.
  - user_roles bootstrap                 INSERT OR IGNORE — never overwrites
                                          assignments made via the Session 2 UI.

Tweak applied per user request 2026-05-08:
  Supervisor does NOT receive 'report.submit_changes' — only system.login
  and orgchart.view.

v11.5 changes (2026-05-14):
  - 'salary' module flipped from is_active=0 to is_active=1 (now usable)
  - Module access_cap renamed 'salary.access' → 'salary.view' (matches code)
  - 6 new salary.* capabilities registered
  - Role defaults: finance/admin/super_admin get salary access (others none)
  - 'salary.edit_bands' restricted to super_admin only (sensitive operation)

Public function:
    seed_rbac_defaults() -> dict   summary of seeded rows

Note on user account model:
    Anca HR app stores user accounts in YAML (config/auth_config.py),
    NOT in a SQLite 'users' table. This seed populates the 'user_roles'
    table with bootstrap entries for the default v11.3 accounts only.
    For users not in user_roles, lib/auth.get_user_role() falls back to
    mapping the YAML legacy role through LEGACY_ROLE_MAP (defined in
    lib/auth.py). To make YOUR own account a Super Admin permanently
    (surviving Streamlit Cloud's ephemeral DB), add your username to
    USER_MIGRATION_MAP below.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional


def _resolve_db_path(db_path: Optional[str] = None) -> str:
    if db_path:
        return db_path
    env = os.environ.get("HR_DB_PATH")
    if env:
        return env
    return str(Path(__file__).resolve().parent.parent / "data" / "hr.db")


# ============================================================================
#  ROLES (low → high privilege, rank 1–7)
# ============================================================================
ROLES = [
    {
        "role_key": "visitor", "rank": 1, "is_external": 1,
        "name_en": "Visitor", "name_th": "ผู้เยี่ยมชม",
        "desc_en": "External guest — safety standards portal only",
        "desc_th": "บุคคลภายนอก — เข้าถึงเฉพาะข้อมูลมาตรฐานความปลอดภัย",
    },
    {
        "role_key": "viewer", "rank": 2, "is_external": 0,
        "name_en": "Viewer", "name_th": "ผู้ดู",
        "desc_en": "Read-only — org chart only by default",
        "desc_th": "ผู้ใช้แบบดูได้อย่างเดียว — เข้าถึงผังองค์กรเท่านั้น (ค่าเริ่มต้น)",
    },
    {
        "role_key": "supervisor", "rank": 3, "is_external": 0,
        "name_en": "Supervisor", "name_th": "หัวหน้างาน",
        "desc_en": "Team-level supervisor",
        "desc_th": "หัวหน้างานระดับทีม",
    },
    {
        "role_key": "manager", "rank": 4, "is_external": 0,
        "name_en": "Manager", "name_th": "ผู้จัดการ",
        "desc_en": "Cost-centre manager — own dept reports",
        "desc_th": "ผู้จัดการศูนย์ต้นทุน — ดูรายงานของแผนกตนเอง",
    },
    {
        "role_key": "finance", "rank": 5, "is_external": 0,
        "name_en": "Finance Manager", "name_th": "ผู้จัดการฝ่ายการเงิน",
        "desc_en": "Finance / budget owner — all-dept reports + salary module access",
        "desc_th": "ผู้จัดการฝ่ายการเงิน — ดูรายงานทุกแผนก และเข้าถึงโมดูลเงินเดือน",
    },
    {
        "role_key": "admin", "rank": 6, "is_external": 0,
        "name_en": "Admin", "name_th": "ผู้ดูแลระบบ",
        "desc_en": "Data entry & user management — cannot edit roles or salary bands",
        "desc_th": "ผู้ดูแลระบบ — จัดการข้อมูลและผู้ใช้ (แก้ไขบทบาทหรือช่วงเงินเดือนไม่ได้)",
    },
    {
        "role_key": "super_admin", "rank": 7, "is_external": 0,
        "name_en": "Super Admin", "name_th": "ผู้ดูแลระบบสูงสุด",
        "desc_en": "Full access — only role that can edit role defaults, salary bands & per-user overrides",
        "desc_th": "ผู้ดูแลระบบสูงสุด — บทบาทเดียวที่แก้ไขสิทธิ์เริ่มต้น ช่วงเงินเดือน และสิทธิ์เฉพาะบุคคลได้",
    },
]


# ============================================================================
#  MODULES
# ============================================================================
MODULES = [
    {"module_key": "report", "sort_order": 10, "is_active": 1, "is_external_allowed": 0,
     "name_en": "Report Module", "name_th": "โมดูลรายงาน",
     "icon": "📊", "access_cap": "report.access",
     "desc_en": "Monthly absenteeism, OT, working hours, and headcount reports",
     "desc_th": "รายงานการขาดงาน OT ชั่วโมงทำงาน และจำนวนพนักงานรายเดือน"},
    {"module_key": "orgchart", "sort_order": 20, "is_active": 1, "is_external_allowed": 0,
     "name_en": "Org Chart", "name_th": "ผังองค์กร",
     "icon": "🌳", "access_cap": "orgchart.view",
     "desc_en": "Visual org chart with photos, dept clusters, dotted-line reports",
     "desc_th": "ผังองค์กรพร้อมรูปภาพ กลุ่มแผนก และสายบังคับบัญชา"},
    {"module_key": "budget", "sort_order": 30, "is_active": 0, "is_external_allowed": 0,
     "name_en": "Manpower Budget", "name_th": "งบประมาณกำลังคน",
     "icon": "💼", "access_cap": "budget.access",
     "desc_en": "(Coming soon) Headcount budget vs actual",
     "desc_th": "(เปิดให้ใช้งานเร็ว ๆ นี้) งบประมาณกำลังคนเทียบกับจริง"},
    # ── v11.5: Salary module ACTIVATED — was is_active=0, now is_active=1 ──
    {"module_key": "salary", "sort_order": 40, "is_active": 1, "is_external_allowed": 0,
     "name_en": "Salary & Compensation", "name_th": "เงินเดือนและค่าตอบแทน",
     "icon": "💰", "access_cap": "salary.view",
     "desc_en": "15-grade structure, offer calculator, market benchmark, statutory compliance (SSO/PVF/WCF/EWF)",
     "desc_th": "โครงสร้าง 15 ระดับ, เครื่องคำนวณข้อเสนอ, การเทียบตลาด, การปฏิบัติตามกฎหมาย (SSO/PVF/WCF/EWF)"},
    {"module_key": "training", "sort_order": 50, "is_active": 0, "is_external_allowed": 0,
     "name_en": "Training Records", "name_th": "บันทึกการฝึกอบรม",
     "icon": "🎓", "access_cap": "training.access",
     "desc_en": "(Coming soon) Training records and certifications",
     "desc_th": "(เปิดให้ใช้งานเร็ว ๆ นี้) บันทึกการฝึกอบรมและใบรับรอง"},
    {"module_key": "recruitment", "sort_order": 60, "is_active": 0, "is_external_allowed": 0,
     "name_en": "Recruitment", "name_th": "การสรรหาบุคลากร",
     "icon": "🤝", "access_cap": "recruitment.access",
     "desc_en": "(Coming soon) Recruitment and onboarding pipeline",
     "desc_th": "(เปิดให้ใช้งานเร็ว ๆ นี้) ระบบสรรหาและรับพนักงานเข้าทำงาน"},
    {"module_key": "performance", "sort_order": 70, "is_active": 0, "is_external_allowed": 0,
     "name_en": "Performance Reviews", "name_th": "การประเมินผลการปฏิบัติงาน",
     "icon": "⭐", "access_cap": "performance.access",
     "desc_en": "(Coming soon) Annual and mid-year performance reviews",
     "desc_th": "(เปิดให้ใช้งานเร็ว ๆ นี้) การประเมินผลประจำปีและกลางปี"},
    {"module_key": "visitor", "sort_order": 80, "is_active": 1, "is_external_allowed": 1,
     "name_en": "Visitor Portal", "name_th": "พอร์ทัลผู้เยี่ยมชม",
     "icon": "🛡️", "access_cap": "visitor.access",
     "desc_en": "Safety standards portal for external visitors",
     "desc_th": "พอร์ทัลข้อมูลมาตรฐานความปลอดภัยสำหรับผู้เยี่ยมชมภายนอก"},
]


# ============================================================================
#  CAPABILITIES
# ============================================================================
CAPABILITIES = [
    # System-wide
    ("system.login",                None, "action", "Can log in to the application",                  "เข้าสู่ระบบ"),
    ("system.manage_users",         None, "action", "Can create / edit / delete users",               "จัดการผู้ใช้"),
    ("system.manage_roles",         None, "action", "Can edit role default capabilities (Super Admin only)", "แก้ไขสิทธิ์เริ่มต้นของบทบาท (เฉพาะ Super Admin)"),
    ("system.override_user_caps",   None, "action", "Can grant / revoke per-user capabilities (Super Admin only)", "กำหนดสิทธิ์เฉพาะบุคคล (เฉพาะ Super Admin)"),
    ("system.bulk_upload_users",    None, "action", "Can use Excel bulk upload for users",            "อัปโหลดผู้ใช้แบบกลุ่มจาก Excel"),
    ("system.view_audit",           None, "action", "Can view login audit log",                       "ดูบันทึกการเข้าสู่ระบบ"),

    # Report module
    ("report.access",               "report", "module", "Can see Report module on hub",               "เข้าถึงโมดูลรายงาน"),
    ("report.view_own_dept",        "report", "action", "Can view own dept reports only",             "ดูรายงานของแผนกตนเองเท่านั้น"),
    ("report.view_all",             "report", "action", "Can view all departments",                   "ดูรายงานทุกแผนก"),
    ("report.upload",               "report", "action", "Can upload timesheet / OT / leave files",    "อัปโหลดไฟล์ข้อมูล"),
    ("report.edit_config",          "report", "action", "Can edit holidays / cost groups / hour rules", "แก้ไขการตั้งค่า (วันหยุด ฯลฯ)"),
    ("report.approve_changes",      "report", "action", "Can approve change requests",                "อนุมัติคำขอเปลี่ยนแปลง"),
    ("report.submit_changes",       "report", "action", "Can submit change requests",                 "ส่งคำขอเปลี่ยนแปลง"),
    ("report.view_charts",          "report", "action", "Can view charts dashboard",                  "ดูแดชบอร์ด"),
    ("report.export",               "report", "action", "Can export reports to Excel / PDF",          "ส่งออกรายงาน"),

    # Org Chart module
    ("orgchart.view",               "orgchart", "module", "Can view org chart (and see card on hub)", "ดูผังองค์กร"),
    ("orgchart.edit",               "orgchart", "action", "Can edit photos / dotted-lines / styling", "แก้ไขผังองค์กร"),

    # Visitor Portal module
    ("visitor.access",              "visitor", "module", "Can access Visitor Portal",                 "เข้าถึงพอร์ทัลผู้เยี่ยมชม"),

    # ── v11.5: Salary & Compensation module ──────────────────────────────
    ("salary.view",                 "salary", "module", "Can see Salary module on hub & view structure", "เข้าถึงโมดูลเงินเดือนและดูโครงสร้าง"),
    ("salary.calculate_offer",      "salary", "action", "Can use the new-hire offer calculator",      "ใช้เครื่องคำนวณข้อเสนอผู้สมัครใหม่"),
    ("salary.upload",               "salary", "action", "Can upload salary master data",              "อัปโหลดข้อมูลเงินเดือนหลัก"),
    ("salary.export",               "salary", "action", "Can export salary data to Excel",            "ส่งออกข้อมูลเงินเดือนเป็น Excel"),
    ("salary.edit_bands",           "salary", "action", "Can edit grade bands (Super Admin only)",    "แก้ไขช่วงเงินเดือนระดับ (เฉพาะ Super Admin)"),
    ("salary.view_audit",           "salary", "action", "Can view saved offer audit trail",           "ดูประวัติการคำนวณข้อเสนอที่บันทึกไว้"),
]


# ============================================================================
#  DEFAULT ROLE-CAPABILITY MATRIX (with Supervisor tweak)
# ============================================================================
ROLE_CAPS = {
    "visitor": [
        "system.login",
        "visitor.access",
    ],
    "viewer": [
        "system.login",
        "orgchart.view",
    ],
    "supervisor": [
        "system.login",
        "orgchart.view",
        # Per tweak 2026-05-08: Supervisor only views org chart. No report.submit_changes.
        # Per v11.5 (2026-05-14): Supervisor has NO salary access by default.
        # Super Admin can grant per-user via override UI if a specific supervisor
        # needs offer-calculator access for hiring discussions.
    ],
    "manager": [
        "system.login",
        "report.access", "report.view_own_dept", "report.approve_changes",
        "report.submit_changes", "report.view_charts", "report.export",
        "orgchart.view",
        # Per v11.5: 'manager' role has NO salary access by default.
        # HR Manager and Finance Manager should be assigned the 'finance' role
        # (which carries salary.view / calculate_offer / upload / export / view_audit).
    ],
    "finance": [
        "system.login",
        "report.access", "report.view_all", "report.approve_changes",
        "report.submit_changes", "report.view_charts", "report.export",
        "orgchart.view",
        # v11.5 — Salary module access for Finance / HR Manager
        "salary.view", "salary.calculate_offer", "salary.upload",
        "salary.export", "salary.view_audit",
    ],
    "admin": [
        "system.login",
        "system.manage_users", "system.bulk_upload_users", "system.view_audit",
        "report.access", "report.view_all", "report.upload", "report.edit_config",
        "report.approve_changes", "report.submit_changes", "report.view_charts", "report.export",
        "orgchart.view", "orgchart.edit",
        # v11.5 — Salary read + calculator + audit (no edit_bands, no upload, no export)
        "salary.view", "salary.calculate_offer", "salary.view_audit",
    ],
    "super_admin": [
        "system.login",
        "system.manage_users", "system.manage_roles", "system.override_user_caps",
        "system.bulk_upload_users", "system.view_audit",
        "report.access", "report.view_all", "report.upload", "report.edit_config",
        "report.approve_changes", "report.submit_changes", "report.view_charts", "report.export",
        "orgchart.view", "orgchart.edit",
        # v11.5 — Full salary access including edit_bands
        "salary.view", "salary.calculate_offer", "salary.upload",
        "salary.export", "salary.edit_bands", "salary.view_audit",
    ],
}


# ============================================================================
#  USER MIGRATION MAP — bootstrap user_roles for v11.3 default accounts
# ============================================================================
# These are inserted into 'user_roles' on first run with INSERT OR IGNORE.
# Subsequent edits via the Session 2 user-editor UI take precedence.
#
# IMPORTANT FOR CHAIYANAN: If you log into your live app as a username OTHER
# than 'admin', add an entry here so YOU get the super_admin role permanently.
# Example:    "chaiyanan": "super_admin",
# Streamlit Cloud's SQLite is ephemeral, so this map is the only thing that
# survives DB resets.
USER_MIGRATION_MAP = {
    "admin":  "super_admin",   # default v11.3 admin → Super Admin
    "viewer": "viewer",
    "trial":  "visitor",
    # "chaiyanan": "super_admin",  # ← uncomment & edit to your own username
}


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def seed_rbac_defaults(db_path: Optional[str] = None) -> dict:
    """Seed roles/modules/capabilities, the default matrix, and bootstrap user_roles.
    Idempotent — safe to call on every app start.

    v11.5 note: this function does NOT re-seed role_capabilities for a role that
    already has any rows. So if you deployed v11.4 and the 'finance' role already
    has 7 caps in the DB, this redeploy will NOT add the new salary.* caps to
    that role's existing matrix. You have two options:

      Option A — UI (preferred): log in as Super Admin → System ▸ Role Editor →
                tick the new salary.* boxes for Finance / Admin / Super Admin →
                Save. This preserves any other customisations.

      Option B — Forced re-seed (destroys role customisations): manually clear
                role_capabilities table, then redeploy. Only do this if you
                haven't customised the matrix.

      Option C — Targeted backfill: run the small script in v11.5 release notes
                that inserts ONLY the missing salary.* role_capabilities rows.

    Returns a summary dict.
    """
    path = _resolve_db_path(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    summary = {
        "roles_inserted": 0,
        "modules_inserted": 0,
        "capabilities_inserted": 0,
        "role_caps_seeded_for": [],
        "user_roles_inserted": 0,
    }

    try:
        # 1. Roles
        for r in ROLES:
            cur = conn.execute(
                """INSERT OR IGNORE INTO roles
                   (role_key, role_name_en, role_name_th, rank, is_external,
                    description_en, description_th)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (r["role_key"], r["name_en"], r["name_th"], r["rank"],
                 r["is_external"], r["desc_en"], r["desc_th"]),
            )
            summary["roles_inserted"] += cur.rowcount

        # 2. Modules
        # NOTE v11.5: 'salary' module is_active is now 1 in the MODULES list above,
        # but INSERT OR IGNORE means an EXISTING DB row with is_active=0 will NOT
        # be updated by this seeder. After deploying v11.5, run this one-liner
        # manually OR use the Super Admin module editor to activate it:
        #   UPDATE modules SET is_active=1, access_capability_key='salary.view'
        #   WHERE module_key='salary';
        for m in MODULES:
            cur = conn.execute(
                """INSERT OR IGNORE INTO modules
                   (module_key, module_name_en, module_name_th, icon_emoji,
                    sort_order, is_active, is_external_allowed,
                    access_capability_key, description_en, description_th)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (m["module_key"], m["name_en"], m["name_th"], m["icon"],
                 m["sort_order"], m["is_active"], m["is_external_allowed"],
                 m["access_cap"], m["desc_en"], m["desc_th"]),
            )
            summary["modules_inserted"] += cur.rowcount

        # 2b. v11.5 — Force-activate 'salary' module on existing deployments.
        # This is safe because there's only one row for the salary module and
        # we want it active everywhere after the v11.5 deployment.
        conn.execute(
            """UPDATE modules
               SET is_active = 1,
                   access_capability_key = 'salary.view',
                   description_en = ?,
                   description_th = ?
               WHERE module_key = 'salary'""",
            (
                "15-grade structure, offer calculator, market benchmark, statutory compliance (SSO/PVF/WCF/EWF)",
                "โครงสร้าง 15 ระดับ, เครื่องคำนวณข้อเสนอ, การเทียบตลาด, การปฏิบัติตามกฎหมาย (SSO/PVF/WCF/EWF)",
            ),
        )

        # 3. Capabilities
        for cap_key, mod_key, cap_type, desc_en, desc_th in CAPABILITIES:
            cur = conn.execute(
                """INSERT OR IGNORE INTO capabilities
                   (capability_key, module_key, capability_type,
                    description_en, description_th)
                   VALUES (?, ?, ?, ?, ?)""",
                (cap_key, mod_key, cap_type, desc_en, desc_th),
            )
            summary["capabilities_inserted"] += cur.rowcount

        # 4. Role-capability matrix
        # IMPORTANT: only seed defaults for roles with ZERO entries, so Super
        # Admin edits in the role editor (Session 2 UI) survive redeploys.
        for role_key, caps in ROLE_CAPS.items():
            cur = conn.execute(
                "SELECT COUNT(*) AS n FROM role_capabilities WHERE role_key = ?",
                (role_key,),
            )
            existing_count = cur.fetchone()["n"]
            if existing_count == 0:
                for cap_key in caps:
                    conn.execute(
                        """INSERT OR IGNORE INTO role_capabilities
                           (role_key, capability_key) VALUES (?, ?)""",
                        (role_key, cap_key),
                    )
                summary["role_caps_seeded_for"].append(role_key)

        # 4b. v11.5 — Targeted backfill: add NEW salary.* capabilities to
        # existing role matrices (finance/admin/super_admin) without touching
        # any custom changes already made via the role editor. INSERT OR IGNORE
        # ensures we never duplicate or overwrite.
        salary_backfill = {
            "finance":     ["salary.view", "salary.calculate_offer", "salary.upload",
                            "salary.export", "salary.view_audit"],
            "admin":       ["salary.view", "salary.calculate_offer", "salary.view_audit"],
            "super_admin": ["salary.view", "salary.calculate_offer", "salary.upload",
                            "salary.export", "salary.edit_bands", "salary.view_audit"],
        }
        backfilled = 0
        for role_key, new_caps in salary_backfill.items():
            for cap_key in new_caps:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO role_capabilities
                       (role_key, capability_key) VALUES (?, ?)""",
                    (role_key, cap_key),
                )
                backfilled += cur.rowcount
        summary["salary_caps_backfilled"] = backfilled

        # 5. Bootstrap user_roles for default v11.3 accounts
        for username, role_key in USER_MIGRATION_MAP.items():
            cur = conn.execute(
                """INSERT OR IGNORE INTO user_roles
                   (username, role_key, set_by_username, note)
                   VALUES (?, ?, 'rbac_seed_v11.5', 'Initial seed from USER_MIGRATION_MAP')""",
                (username, role_key),
            )
            summary["user_roles_inserted"] += cur.rowcount

        conn.commit()
    finally:
        conn.close()

    return summary


# CLI entry-point
if __name__ == "__main__":
    result = seed_rbac_defaults()
    print("RBAC seed summary:")
    for key, items in result.items():
        print(f"  {key}: {items}")
