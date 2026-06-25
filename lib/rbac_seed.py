# lib/rbac_seed.py
# ============================================================================
# Seeds the 7 roles, all modules, all capabilities, and the default
# role->capability matrix for the COMPLETE system:
#   Report, Org Chart, Visitor Portal, Employee Data, Leave & OT (3-level),
#   Car Booking, Stationery ERP, System admin.
# Idempotent: INSERTs ignore duplicates, so re-seeding on every boot is safe
# and new capabilities appear automatically after an upgrade.
# Super Admin can re-shape the matrix later in 0_System_Admin.
# ============================================================================
from lib.db import get_conn, IS_POSTGRES, PH

IGNORE = "ON CONFLICT DO NOTHING" if IS_POSTGRES else "OR IGNORE"


ROLES = [
    # key, en, th, rank
    ("visitor", "Visitor", "ผู้เยี่ยมชม/ผู้สมัคร", 1),
    ("viewer", "Viewer (Staff)", "พนักงาน", 2),
    ("supervisor", "Supervisor", "หัวหน้างาน", 3),
    ("manager", "Manager", "ผู้จัดการ", 4),
    ("finance", "Finance", "การเงิน", 5),
    ("admin", "Admin (HR)", "ผู้ดูแลระบบ (HR)", 6),
    ("super_admin", "Super Admin", "ผู้ดูแลระบบสูงสุด", 7),
]

MODULES = [
    ("report", "HR Report", "รายงาน HR"),
    ("orgchart", "Org Chart", "ผังองค์กร"),
    ("visitor", "Visitor Portal", "พอร์ทัลผู้เยี่ยมชม"),
    ("employee", "Employee Data", "ข้อมูลพนักงาน"),
    ("leave_ot", "Leave & OT", "การลาและโอที"),
    ("car", "Car Booking", "จองรถบริษัท"),
    ("erp", "Stationery ERP", "ระบบสั่งซื้อ/เบิกเครื่องเขียน"),
    ("system", "System Admin", "ตั้งค่าระบบ"),
]

CAPS = [
    # cap_key, en, th, module
    ("report.view", "View HR reports (own department scope)",
     "ดูรายงาน HR (เฉพาะแผนกตน)", "report"),
    ("report.view_all", "View HR reports across ALL departments",
     "ดูรายงาน HR ทุกแผนก", "report"),
    # resignation & no-show (§6)
    ("resign.submit", "Submit own resignation", "ยื่นใบลาออก", "report"),
    ("resign.delegate", "File resignation for a no-show subordinate",
     "ยื่นแทนลูกน้องขาดงาน", "report"),
    ("resign.admin", "HR resignation admin & no-show watchdog",
     "ผู้ดูแลการลาออก/ขาดงาน", "report"),
    # training / LMS (§7)
    ("train.take", "Take assigned training courses", "เข้าอบรมหลักสูตร",
     "visitor"),
    ("train.manage", "Build courses, assign, analytics",
     "จัดการหลักสูตรอบรม", "visitor"),
    ("train.grade", "Grade manual test answers", "ตรวจข้อสอบ", "visitor"),
    ("docs.completion_checklist", "Employee document completeness checklist",
     "เช็คลิสต์เอกสารพนักงาน", "report"),
    ("orgchart.view", "View org chart", "ดูผังองค์กร", "orgchart"),
    ("visitor.access", "Open Visitor Portal", "เข้าพอร์ทัลผู้เยี่ยมชม",
     "visitor"),
    ("candidate.apply", "Submit/edit a job application", "ส่งใบสมัครงาน",
     "visitor"),
    # employee module
    ("self.view_profile", "View own record", "ดูข้อมูลตนเอง", "employee"),
    ("self.edit_profile", "Request changes to own record",
     "ขอแก้ไขข้อมูลตนเอง", "employee"),
    ("employee.access", "Open Employee Data", "เข้าโมดูลข้อมูลพนักงาน",
     "employee"),
    ("employee.view_all", "View all records", "ดูข้อมูลทั้งหมด", "employee"),
    ("employee.edit", "Edit records", "แก้ไขข้อมูล", "employee"),
    ("employee.manage_candidates", "Review & promote candidates",
     "จัดการผู้สมัคร", "employee"),
    ("employee.approve_changes", "Approve change requests",
     "อนุมัติคำขอแก้ไข", "employee"),
    ("employee.bulk_upload", "Bulk upload", "อัปโหลดจำนวนมาก", "employee"),
    ("employee.export_internal", "Internal export", "ส่งออกภายใน",
     "employee"),
    ("employee.export_external", "External (PDPA-safe) export",
     "ส่งออกภายนอก", "employee"),
    ("employee.view_salary", "View salary (SUPER ADMIN)", "ดูเงินเดือน",
     "employee"),
    ("employee.edit_salary", "Edit salary (SUPER ADMIN)", "แก้ไขเงินเดือน",
     "employee"),
    # leave & OT
    ("leave.submit", "Submit leave/OT", "ส่งคำขอลา/โอที", "leave_ot"),
    ("leave.approve", "Approve leave/OT in my chain",
     "อนุมัติลา/โอทีในสายบังคับบัญชา", "leave_ot"),
    ("leave.admin", "HR override & reminders", "จัดการ/แจ้งเตือนการลา",
     "leave_ot"),
    # car booking (native)
    ("car.book", "Book a company car", "จองรถบริษัท", "car"),
    ("car.approve", "Approve car bookings in my chain",
     "อนุมัติการจองรถ", "car"),
    ("car.admin", "Car booking admin (fleet, drivers, assign)",
     "ผู้ดูแลการจองรถ", "car"),
    # entrance & take-out permits
    ("permit.request", "Request entry card / take-out permit",
     "ขอใบผ่านเข้า-ออก/นำของออก", "visitor"),
    ("permit.approve", "Approve permits (host/department head)",
     "อนุมัติใบอนุญาต", "visitor"),
    ("permit.admin", "Permit admin & security list",
     "ผู้ดูแลใบอนุญาต/รปภ.", "visitor"),
    # ERP
    ("erp.browse", "Browse stationery catalog", "ดูแคตตาล็อกเครื่องเขียน",
     "erp"),
    ("erp.request", "Request items (PO cart)", "ขอสั่งซื้อ", "erp"),
    ("erp.reimburse", "Submit reimbursement claim", "ขอเบิกคืนเงิน", "erp"),
    ("erp.approve", "Approve PO/reimbursement", "อนุมัติ PO/เบิกคืน", "erp"),
    ("erp.purchase", "Place & receive OFFICEMATE orders",
     "สั่งซื้อ/รับของ OFFICEMATE", "erp"),
    ("erp.pay", "Mark reimbursements paid (Finance)", "จ่ายเงินคืน", "erp"),
    ("erp.manage_catalog", "Import/edit catalog & suppliers",
     "จัดการแคตตาล็อก/ผู้ขาย", "erp"),
    ("erp.config_lines", "Configure purchase approval lines",
     "ตั้งค่าสายอนุมัติสั่งซื้อ", "erp"),
    ("erp.reports", "ERP reports & budget", "รายงาน/งบประมาณ ERP", "erp"),
    # stationery stock & issue (§4)
    ("stock.request", "Request items from stock", "เบิกของจากสต๊อก", "erp"),
    ("stock.approve", "Approve stock issues", "อนุมัติการเบิกของ", "erp"),
    ("stock.manage", "Manage stock (receive/count/handover)",
     "จัดการสต๊อก", "erp"),
    # attendance reports (§5)
    ("attend.view_team", "View team attendance & abnormalities",
     "ดูเวลาทำงานทีมตนเอง", "report"),
    ("attend.upload", "Upload the 3 standard attendance files",
     "อัปโหลดไฟล์เวลาทำงาน", "report"),
    # OT-by-department comparison report (§8) — aggregated dept view for
    # managers; raw salary upload/detail stays gated on employee.view_salary
    ("salary.ot_report", "View OT-by-department comparison report",
     "ดูรายงานเปรียบเทียบ OT ตามแผนก", "report"),
    # system
    ("system.users", "Manage users & roles", "จัดการผู้ใช้", "system"),
    ("system.view_audit", "View audit log", "ดูบันทึกการแก้ไข", "system"),
]

MATRIX = {
    "visitor": ["visitor.access", "candidate.apply", "permit.request",
                "train.take"],
    "viewer": ["report.view", "orgchart.view", "self.view_profile",
               "self.edit_profile", "leave.submit", "car.book",
               "permit.request", "permit.approve",
               "erp.browse", "erp.request", "erp.reimburse",
               "stock.request", "resign.submit", "train.take"],
    "supervisor": ["report.view", "orgchart.view", "self.view_profile",
                   "self.edit_profile", "leave.submit", "leave.approve",
                   "car.book", "car.approve", "permit.request",
                   "permit.approve", "erp.browse", "erp.request",
                   "erp.reimburse", "stock.request", "stock.approve",
                   "attend.view_team", "resign.submit", "resign.delegate",
                   "train.take"],
    "manager": ["report.view", "orgchart.view", "self.view_profile",
                "self.edit_profile", "leave.submit", "leave.approve",
                "car.book", "car.approve", "permit.request",
                "permit.approve", "erp.browse", "erp.request",
                "erp.reimburse", "erp.approve", "erp.reports",
                "stock.request", "stock.approve", "attend.view_team",
                "salary.ot_report",
                "resign.submit", "resign.delegate", "train.take"],
    "finance": ["report.view", "orgchart.view", "self.view_profile",
                "self.edit_profile", "leave.submit", "car.book",
                "permit.request", "permit.approve", "erp.browse",
                "erp.request", "erp.reimburse", "erp.pay", "erp.reports",
                "stock.request", "attend.view_team", "report.view_all",
                "salary.ot_report",
                "resign.submit", "train.take"],
    "admin": ["report.view", "orgchart.view", "visitor.access",
              "self.view_profile", "self.edit_profile",
              "leave.submit", "leave.approve", "leave.admin",
              "employee.access", "employee.view_all", "employee.edit",
              "employee.manage_candidates", "employee.approve_changes",
              "employee.bulk_upload", "employee.export_internal",
              "employee.export_external",
              "car.book", "car.approve", "car.admin",
              "permit.request", "permit.approve", "permit.admin",
              "erp.browse", "erp.request", "erp.reimburse", "erp.approve",
              "erp.purchase", "erp.manage_catalog", "erp.config_lines",
              "erp.reports", "stock.request", "stock.approve",
              "stock.manage", "attend.view_team", "attend.upload",
              "salary.ot_report",
              "report.view_all", "resign.submit", "resign.delegate",
              "resign.admin", "train.take", "train.manage", "train.grade",
              "docs.completion_checklist",
              "system.users", "system.view_audit"],
    # super_admin = admin + salary + pay (everything)
    "super_admin": None,  # filled below = ALL capabilities
}


def seed():
    conn = get_conn(); cur = conn.cursor()
    for k, en, th, rank in ROLES:
        cur.execute(f"INSERT {IGNORE} INTO roles (role_key, name_en, "
                    f"name_th, rank) VALUES ({PH},{PH},{PH},{PH})"
                    if not IS_POSTGRES else
                    f"INSERT INTO roles (role_key, name_en, name_th, rank) "
                    f"VALUES ({PH},{PH},{PH},{PH}) ON CONFLICT DO NOTHING",
                    (k, en, th, rank))
    for k, en, th in MODULES:
        cur.execute(f"INSERT {IGNORE} INTO modules (module_key, name_en, "
                    f"name_th) VALUES ({PH},{PH},{PH})"
                    if not IS_POSTGRES else
                    f"INSERT INTO modules (module_key, name_en, name_th) "
                    f"VALUES ({PH},{PH},{PH}) ON CONFLICT DO NOTHING",
                    (k, en, th))
    for k, en, th, m in CAPS:
        cur.execute(f"INSERT {IGNORE} INTO capabilities (cap_key, name_en, "
                    f"name_th, module_key) VALUES ({PH},{PH},{PH},{PH})"
                    if not IS_POSTGRES else
                    f"INSERT INTO capabilities (cap_key, name_en, name_th, "
                    f"module_key) VALUES ({PH},{PH},{PH},{PH}) "
                    f"ON CONFLICT DO NOTHING",
                    (k, en, th, m))
    all_caps = [c[0] for c in CAPS]
    for role, caps in MATRIX.items():
        for cap in (all_caps if caps is None else caps):
            cur.execute(f"INSERT {IGNORE} INTO role_capabilities (role_key, "
                        f"cap_key) VALUES ({PH},{PH})"
                        if not IS_POSTGRES else
                        f"INSERT INTO role_capabilities (role_key, cap_key) "
                        f"VALUES ({PH},{PH}) ON CONFLICT DO NOTHING",
                        (role, cap))
    conn.commit()

    # first-boot bootstrap account (change the password immediately!)
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        from lib import auth
        auth.create_user("superadmin", "ChangeMe!2026", "super_admin",
                         must_change=True)
    conn.commit()
