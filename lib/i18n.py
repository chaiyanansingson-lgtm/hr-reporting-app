"""
Bilingual UI translations (Thai / English).
Default language is Thai; user can toggle in the sidebar.

Usage:
    from lib.i18n import t, init_language, language_toggle
    init_language()  # call once per session
    st.markdown(f"# {t('app_title')}")
"""
import streamlit as st

DEFAULT_LANG = "th"

TR = {
    # ──────────────── App-level / common ────────────────
    "app_title":           {"en": "HR Reporting",                  "th": "ระบบรายงาน HR"},
    "company_name":        {"en": "Anca Manufacturing Solutions",  "th": "Anca Manufacturing Solutions"},
    "company_tagline":     {"en": "(Thailand)",                    "th": "(ประเทศไทย)"},
    "language":            {"en": "Language",                      "th": "ภาษา"},
    "thai":                {"en": "ไทย",                           "th": "ไทย"},
    "english":             {"en": "English",                       "th": "English"},

    "sign_in":             {"en": "Sign in",                       "th": "เข้าสู่ระบบ"},
    "sign_out":            {"en": "Sign out",                      "th": "ออกจากระบบ"},
    "username":            {"en": "Username",                      "th": "ชื่อผู้ใช้"},
    "password":            {"en": "Password",                      "th": "รหัสผ่าน"},
    "invalid_credentials": {"en": "Invalid username or password.", "th": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"},
    "default_login_hint":  {"en": "Default for the prototype: **admin / admin123** or **viewer / viewer123**. Change in the Users page before going live.",
                            "th": "ค่าเริ่มต้นสำหรับทดลอง: **admin / admin123** หรือ **viewer / viewer123** กรุณาเปลี่ยนรหัสผ่านในหน้า Users ก่อนใช้งานจริง"},
    "welcome":             {"en": "Welcome",                       "th": "ยินดีต้อนรับ"},
    "role":                {"en": "Role",                          "th": "บทบาท"},

    # ──────────────── Navigation ────────────────
    "nav_home":            {"en": "Home",                          "th": "หน้าหลัก"},
    "nav_report":          {"en": "Report",                        "th": "รายงาน"},
    "nav_charts":          {"en": "Dashboard",                     "th": "แดชบอร์ด"},
    "nav_upload":          {"en": "Upload Data",                   "th": "อัปโหลดข้อมูล"},
    "nav_config":          {"en": "Configuration",                 "th": "ตั้งค่าระบบ"},
    "nav_employees":       {"en": "Employees",                     "th": "พนักงาน"},
    "nav_users":           {"en": "Users",                         "th": "ผู้ใช้"},
    "nav_change_req":      {"en": "Change Requests",               "th": "คำขอเปลี่ยนแปลง"},

    # ──────────────── Common controls ────────────────
    "save":                {"en": "Save",                          "th": "บันทึก"},
    "cancel":              {"en": "Cancel",                        "th": "ยกเลิก"},
    "confirm":             {"en": "Confirm",                       "th": "ยืนยัน"},
    "delete":              {"en": "Delete",                        "th": "ลบ"},
    "submit":              {"en": "Submit",                        "th": "ส่ง"},
    "approve":             {"en": "Approve",                       "th": "อนุมัติ"},
    "reject":              {"en": "Reject",                        "th": "ปฏิเสธ"},
    "edit":                {"en": "Edit",                          "th": "แก้ไข"},
    "add":                 {"en": "Add",                           "th": "เพิ่ม"},
    "remove":              {"en": "Remove",                        "th": "ลบออก"},
    "import":              {"en": "Import",                        "th": "นำเข้า"},
    "export":              {"en": "Export",                        "th": "ส่งออก"},
    "download":            {"en": "Download",                      "th": "ดาวน์โหลด"},
    "upload":              {"en": "Upload",                        "th": "อัปโหลด"},
    "search":              {"en": "Search",                        "th": "ค้นหา"},
    "filter":              {"en": "Filter",                        "th": "กรอง"},
    "all":                 {"en": "(all)",                         "th": "(ทั้งหมด)"},
    "loading":             {"en": "Loading…",                      "th": "กำลังโหลด…"},
    "no_data":             {"en": "No data available.",            "th": "ไม่มีข้อมูล"},
    "yes":                 {"en": "Yes",                           "th": "ใช่"},
    "no":                  {"en": "No",                            "th": "ไม่"},

    # ──────────────── Home/landing ────────────────
    "home_intro":          {"en": "Use the sidebar to navigate. Page access depends on your role.",
                            "th": "ใช้แถบด้านข้างเพื่อเข้าถึงเมนูต่างๆ สิทธิ์การเข้าถึงหน้าขึ้นอยู่กับบทบาทของคุณ"},
    "active_employees":    {"en": "Active employees",              "th": "พนักงานที่ปฏิบัติงาน"},
    "periods_loaded":      {"en": "Periods loaded",                "th": "ช่วงเวลาที่อัปโหลดแล้ว"},
    "hours_per_day":       {"en": "Hours per day",                 "th": "ชั่วโมงทำงานต่อวัน"},
    "holidays_defined":    {"en": "Holidays defined",              "th": "วันหยุดที่ตั้งค่า"},
    "loaded_periods":      {"en": "Loaded periods",                "th": "ช่วงเวลาที่อัปโหลดแล้ว"},
    "no_periods_msg":      {"en": "No timesheet data yet.  An admin can upload data on the Upload Data page.",
                            "th": "ยังไม่มีข้อมูลใบบันทึกเวลา ผู้ดูแลสามารถอัปโหลดข้อมูลได้ที่หน้าอัปโหลดข้อมูล"},

    # ──────────────── Report page ────────────────
    "report_title":        {"en": "Report",                        "th": "รายงาน"},
    "report_subtitle":     {"en": "Monthly HR report — filter, view, export.",
                            "th": "รายงาน HR รายเดือน — กรอง ดู ส่งออก"},
    "reporting_period":    {"en": "Reporting period",              "th": "ช่วงเวลารายงาน"},
    "unit":                {"en": "Unit",                          "th": "หน่วย"},
    "hours":               {"en": "Hours",                         "th": "ชั่วโมง"},
    "days":                {"en": "Days",                          "th": "วัน"},
    "top_group":           {"en": "Top group",                     "th": "กลุ่มหลัก"},
    "function_dept":       {"en": "Function (department)",         "th": "ฟังก์ชั่น (แผนก)"},
    "wh_mode":             {"en": "Working Hours mode",            "th": "วิธีคำนวณชั่วโมงทำงาน"},
    "wh_actual":           {"en": "Actual (from Timesheet)",       "th": "ใช้ค่าจริง (จากใบบันทึกเวลา)"},
    "wh_standard":         {"en": "Standard (HC × Working Days × Daily Std Hrs)",
                            "th": "ใช้ค่ามาตรฐาน (จำนวนพนักงาน × วันทำงาน × ชั่วโมงต่อวัน)"},
    "deduct_al":           {"en": "Deduct AL from WH",             "th": "หัก AL จากชั่วโมงทำงาน"},
    "deduct_other":        {"en": "Deduct other leaves from WH",   "th": "หักการลาอื่นๆ จากชั่วโมงทำงาน"},
    "include_al_pct":      {"en": "Include AL in %Absent",         "th": "รวม AL ในการคำนวณ %ขาดงาน"},
    "show_al_cols":        {"en": "Show Annual Leave columns",     "th": "แสดงคอลัมน์ลาพักร้อน"},
    "leave_breakdown":     {"en": "Add leave-type breakdown columns",
                            "th": "เพิ่มคอลัมน์แยกประเภทการลา"},
    "sick_leave":          {"en": "Sick Leave",                    "th": "ลาป่วย"},
    "business_leave":      {"en": "Business Leave",                "th": "ลากิจ"},
    "without_pay":         {"en": "Without Pay",                   "th": "ขาดงาน"},
    "annual_leave":        {"en": "Annual Leave",                  "th": "ลาพักร้อน"},
    "summary":             {"en": "Summary",                       "th": "สรุป"},
    "headcount":           {"en": "Headcount",                     "th": "จำนวนพนักงาน"},
    "working":             {"en": "Working",                       "th": "ชั่วโมงทำงาน"},
    "absent_excl_al":      {"en": "Absent excl AL",                "th": "ขาดงาน (ไม่รวม AL)"},
    "ot_total":            {"en": "OT total",                      "th": "ล่วงเวลารวม"},
    "no_data_filter":      {"en": "No data matches these filters.","th": "ไม่พบข้อมูลตามตัวกรองที่เลือก"},

    # ──────────────── Charts ────────────────
    "charts_title":        {"en": "KPI Dashboard",                 "th": "แดชบอร์ด KPI"},
    "charts_subtitle":     {"en": "Trend charts — actual vs target.",
                            "th": "กราฟแนวโน้ม — ค่าจริงเทียบกับเป้าหมาย"},
    "single_month_period": {"en": "Period (single-month charts)",  "th": "ช่วงเวลา (กราฟรายเดือน)"},
    "months_in_trend":     {"en": "Months in trend charts",        "th": "จำนวนเดือนในกราฟแนวโน้ม"},
    "trend_grouping":      {"en": "Trend grouping",                "th": "การจัดกลุ่มในกราฟ"},
    "by_top":              {"en": "By Top Group",                  "th": "ตามกลุ่มหลัก"},
    "by_function":         {"en": "By Function (detail)",          "th": "ตามฟังก์ชั่น (ละเอียด)"},
    "leave_charts_pick":   {"en": "Leave-type charts to display",  "th": "กราฟประเภทการลาที่แสดง"},
    "ot_mult_pick":        {"en": "OT multipliers to display",     "th": "ตัวคูณ OT ที่แสดง"},
    "absenteeism_target":  {"en": "Absenteeism — Actual vs Target","th": "การขาดงาน — ค่าจริงเทียบกับเป้าหมาย"},

    # ──────────────── Upload ────────────────
    "upload_title":        {"en": "Upload Data",                   "th": "อัปโหลดข้อมูล"},
    "upload_subtitle":     {"en": "Admin only — upload monthly HRM exports and reference files.",
                            "th": "เฉพาะผู้ดูแล — อัปโหลดไฟล์ส่งออกจาก HRM รายเดือน และไฟล์อ้างอิง"},

    # ──────────────── Configuration ────────────────
    "config_title":        {"en": "Configuration",                 "th": "ตั้งค่าระบบ"},
    "config_subtitle":     {"en": "Admin only — rules used by the report calculations.",
                            "th": "เฉพาะผู้ดูแล — ตั้งค่ากฎที่ใช้ในการคำนวณรายงาน"},

    # ──────────────── Employees ────────────────
    "employees_title":     {"en": "Employees",                     "th": "พนักงาน"},
    "employees_subtitle":  {"en": "Active employee directory.",    "th": "รายชื่อพนักงานปัจจุบัน"},

    # ──────────────── Users ────────────────
    "users_title":         {"en": "Users",                         "th": "ผู้ใช้"},
    "users_subtitle":      {"en": "Admin only — manage app login credentials.",
                            "th": "เฉพาะผู้ดูแล — จัดการบัญชีผู้ใช้และรหัสผ่าน"},

    # ──────────────── Change requests ────────────────
    "creq_title":          {"en": "Change Requests",               "th": "คำขอเปลี่ยนแปลง"},
    "creq_subtitle":       {"en": "Manager-submitted requests to update employee data.",
                            "th": "คำขอจากหัวหน้างานเพื่อแก้ไขข้อมูลพนักงาน"},

    # ──────────────── Roles ────────────────
    "role_admin":          {"en": "Administrator",                 "th": "ผู้ดูแล"},
    "role_manager":        {"en": "Manager",                       "th": "หัวหน้างาน"},
    "role_viewer":         {"en": "Viewer",                        "th": "ผู้อ่านอย่างเดียว"},

    # ──────────────── Sign up ────────────────
    "sign_up":             {"en": "Sign up",                       "th": "สมัครใช้งาน"},
    "signup_hint":         {"en": "Request access by filling in this form. An admin will review and approve.",
                            "th": "ขอสิทธิ์การใช้งานโดยกรอกฟอร์มนี้ ผู้ดูแลจะพิจารณาและอนุมัติ"},
    "signup_username":     {"en": "Username (will be your login name)",
                            "th": "ชื่อผู้ใช้ (สำหรับเข้าสู่ระบบ)"},
    "signup_username_help": {"en": "At least 3 characters; lowercase letters, digits, dots only.",
                             "th": "อย่างน้อย 3 ตัวอักษร; ตัวพิมพ์เล็ก ตัวเลข และจุด เท่านั้น"},
    "signup_email":        {"en": "Email address (work email preferred)",
                            "th": "อีเมล (แนะนำใช้อีเมลที่ทำงาน)"},
    "signup_full_name":    {"en": "Your full name",                "th": "ชื่อ-นามสกุล"},
    "signup_emp_no":       {"en": "Employee number (optional)",    "th": "รหัสพนักงาน (ถ้ามี)"},
    "signup_emp_no_help":  {"en": "Helps admin verify it's really you.",
                            "th": "เพื่อให้ผู้ดูแลตรวจสอบตัวตนได้"},
    "signup_requested_role": {"en": "Requested role",              "th": "บทบาทที่ขอ"},
    "signup_reason":       {"en": "Why do you need access? (required)",
                            "th": "เหตุผลที่ต้องการเข้าใช้งาน (จำเป็น)"},
    "signup_reason_help":  {"en": "Help admin decide. Mention your team and what reports you need.",
                            "th": "เพื่อให้ผู้ดูแลพิจารณาได้ง่าย ระบุทีมและรายงานที่ต้องการดู"},
    "signup_password":     {"en": "Password (8+ chars)",           "th": "รหัสผ่าน (อย่างน้อย 8 ตัว)"},
    "signup_password_confirm": {"en": "Confirm password",          "th": "ยืนยันรหัสผ่าน"},
    "signup_submit":       {"en": "Submit access request",         "th": "ส่งคำขอเข้าใช้งาน"},
    "signup_success":      {"en": "Your access request has been submitted.",
                            "th": "ส่งคำขอเข้าใช้งานเรียบร้อยแล้ว"},
    "signup_pending_info": {"en": "An admin will review and contact you. Once approved, sign in with the username and password you just chose.",
                            "th": "ผู้ดูแลจะพิจารณาและติดต่อกลับ เมื่ออนุมัติแล้ว เข้าสู่ระบบด้วยชื่อผู้ใช้และรหัสผ่านที่ตั้งไว้"},

    # ──────────────── Validation errors ────────────────
    "err_username_too_short": {"en": "Username must be at least 3 characters.",
                                "th": "ชื่อผู้ใช้ต้องมีอย่างน้อย 3 ตัวอักษร"},
    "err_invalid_email":   {"en": "Please enter a valid email address.",
                            "th": "กรุณากรอกอีเมลที่ถูกต้อง"},
    "err_name_required":   {"en": "Full name is required.",        "th": "กรุณากรอกชื่อ-นามสกุล"},
    "err_reason_too_short": {"en": "Please give a reason (at least 10 characters).",
                              "th": "กรุณาระบุเหตุผล (อย่างน้อย 10 ตัวอักษร)"},
    "err_password_too_short": {"en": "Password must be at least 8 characters.",
                                "th": "รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร"},
    "err_passwords_dont_match": {"en": "Passwords don't match.",   "th": "รหัสผ่านไม่ตรงกัน"},
    "err_username_taken":  {"en": "This username already exists.", "th": "ชื่อผู้ใช้นี้มีอยู่แล้ว"},

    # ──────────────── Sign-up review (admin) ────────────────
    "nav_signup_review":   {"en": "Sign-up Requests",              "th": "คำขอสมัครใช้งาน"},
    "signup_review_title": {"en": "Sign-up Requests",              "th": "คำขอสมัครใช้งาน"},
    "signup_review_subtitle": {"en": "Review and approve / reject account requests.",
                                "th": "พิจารณาและอนุมัติ / ปฏิเสธ คำขอบัญชีผู้ใช้"},
    "pending_requests":    {"en": "Pending",                       "th": "รอพิจารณา"},
    "approved_requests":   {"en": "Approved",                      "th": "อนุมัติแล้ว"},
    "rejected_requests":   {"en": "Rejected",                      "th": "ปฏิเสธแล้ว"},
    "review_notes":        {"en": "Review notes (recorded for audit)",
                            "th": "หมายเหตุการพิจารณา (บันทึกในระบบ)"},
    "grant_role":          {"en": "Grant role",                    "th": "ให้บทบาท"},
    "ip_address":          {"en": "IP address",                    "th": "หมายเลข IP"},
    "user_agent":          {"en": "Browser / device",              "th": "เบราว์เซอร์ / อุปกรณ์"},

    # ──────────────── Login audit (admin) ────────────────
    "nav_login_audit":     {"en": "Login Audit",                   "th": "ประวัติการเข้าสู่ระบบ"},
    "audit_title":         {"en": "Login Audit Log",               "th": "ประวัติการเข้าสู่ระบบ"},
    "audit_subtitle":      {"en": "Every sign-in attempt is recorded with IP and user-agent.",
                            "th": "ระบบบันทึกทุกการเข้าสู่ระบบพร้อม IP และอุปกรณ์ที่ใช้"},
    "filter_only_admin":   {"en": "Admin sign-ins only",           "th": "เฉพาะผู้ดูแล"},
    "filter_only_failures": {"en": "Failed attempts only",         "th": "เฉพาะที่เข้าไม่สำเร็จ"},
    "successful":          {"en": "✅ Success",                    "th": "✅ สำเร็จ"},
    "failed":              {"en": "❌ Failed",                     "th": "❌ ล้มเหลว"},

    # ──────────────── Org chart ────────────────
    "nav_org_chart":       {"en": "Org Chart",                     "th": "ผังองค์กร"},
    "nav_my_settings":     {"en": "My Settings",                   "th": "การตั้งค่าของฉัน"},
    "org_chart_title":     {"en": "Organization Chart",            "th": "ผังองค์กร"},
    "org_chart_subtitle":  {"en": "Browse the company structure by reporting hierarchy.",
                            "th": "ดูโครงสร้างองค์กรตามสายการบังคับบัญชา"},
    "org_view_tree":       {"en": "Tree view",                     "th": "มุมมองต้นไม้"},
    "org_view_table":      {"en": "Table view",                    "th": "มุมมองตาราง"},
    "org_view_dept":       {"en": "By department",                 "th": "ตามแผนก"},
    "no_org_data":         {"en": "No org chart data uploaded yet. Admin can import the Employee Master List on the Upload page.",
                            "th": "ยังไม่มีข้อมูลผังองค์กร ผู้ดูแลสามารถนำเข้าข้อมูลพนักงานได้ที่หน้าอัปโหลดข้อมูล"},
    "direct_reports":      {"en": "Direct reports",                "th": "ผู้ใต้บังคับบัญชาโดยตรง"},
    "reports_to":          {"en": "Reports to",                    "th": "รายงานต่อ"},
}


def init_language():
    """Initialize language in session_state — call once per page."""
    st.session_state.setdefault("lang", DEFAULT_LANG)


def t(key: str) -> str:
    """Translate a key to the current language."""
    init_language()
    lang = st.session_state.get("lang", DEFAULT_LANG)
    entry = TR.get(key, {})
    if not entry:
        return key
    return entry.get(lang) or entry.get("en") or key


def language_toggle(container=None):
    """Render the language toggle as a small segmented control."""
    init_language()
    target = container if container is not None else st
    cols = target.columns(2)
    is_th = st.session_state.get("lang", DEFAULT_LANG) == "th"
    if cols[0].button("🇹🇭  ไทย", use_container_width=True,
                       type="primary" if is_th else "secondary",
                       key="lang_th_btn"):
        st.session_state.lang = "th"
        st.rerun()
    if cols[1].button("🇬🇧  EN", use_container_width=True,
                       type="primary" if not is_th else "secondary",
                       key="lang_en_btn"):
        st.session_state.lang = "en"
        st.rerun()


def role_label(role: str) -> str:
    """Localized role display name."""
    return t({"admin": "role_admin", "manager": "role_manager", "viewer": "role_viewer"}.get(role, "role_viewer"))
