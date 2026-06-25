# lib/nav.py
# ============================================================================
# Module → Function navigation model (the "mother-menu" reorganisation).
#
# A MODULE is a group shown in the sidebar (st.navigation section) and as a
# card on the home page. A FUNCTION is a page inside a module. Visibility is
# role-based: a function shows if the user holds its capability; a module
# shows in the sidebar only if it has >=1 visible function. The home page
# shows EVERY module as a card — accessible ones open, the rest render as
# "🔒 เปิดใช้งานเร็วๆนี้ / Coming soon" (no functions yet, e.g. Performance)
# or "🔒 ไม่มีสิทธิ์ / No access" (role lacks every function).
#
# Existing page files are reused unchanged — this layer only regroups them.
# ============================================================================
from lib import auth


def _has(cap):
    return bool(cap) and auth.has_capability(cap)


# Each function: (path, icon, th, en, cap, url_path, guard)
#   cap   = capability gate (None => always visible to a logged-in user)
#   guard = optional callable() -> bool, overrides cap when present
# Each module: dict(key, icon, th, en, desc_th, desc_en, funcs=[...])
def _is_staff():
    return auth.has_capability("self.view_profile")


def _training_visitor():
    # Visitors see Training under "Visitor"; staff see it under "Employees".
    return auth.has_capability("train.take") and not _is_staff()


def _training_employee():
    # Staff (anyone with a profile) see Training under "Employees".
    return auth.has_capability("train.take") and _is_staff()


def _can_view_requests():
    from lib import feature_grants
    return feature_grants.has_feature("requests.view")


MODULES = [
    dict(key="visitor", icon="🚪", th="ผู้เยี่ยมชม", en="Visitor",
         desc_th="ผู้มาติดต่อ / ผู้สมัครงาน", desc_en="Guests & applicants",
         funcs=[
             dict(path="pages/I_Permits.py", icon="🪪", th="ใบอนุญาต",
                  en="Permits", cap="permit.request", url="permits"),
             dict(path="pages/C_Candidate_Portal.py", icon="📝",
                  th="สมัครงาน", en="Apply", cap="candidate.apply",
                  url="apply"),
             dict(path="pages/M_Training.py", icon="🎓", th="อบรม",
                  en="Training", cap="train.take", url="training",
                  guard=_training_visitor),
         ]),
    dict(key="management", icon="📊", th="บริหารจัดการ", en="Management",
         desc_th="รายงานและการวิเคราะห์", desc_en="Reports & analytics",
         funcs=[
             dict(path="pages/1_Report.py", icon="📈", th="รายงาน",
                  en="Report", cap="report.view", url="report"),
             dict(path="pages/K_Attendance.py", icon="⏱️", th="เวลาทำงาน",
                  en="Attendance", cap="attend.view_team", url="attendance"),
             dict(path="pages/U_Drilldown.py", icon="🔍", th="เจาะรายคน",
                  en="Employee drill-down", cap="attend.view_team",
                  url="drilldown"),
             dict(path="pages/W_KPI_Dashboard.py", icon="📈",
                  th="แดชบอร์ด KPI", en="KPI Dashboard",
                  cap="attend.view_team", url="kpi-dashboard"),
             dict(path="pages/N_OT_Report.py", icon="💰", th="OT ตามแผนก",
                  en="OT by dept", cap="salary.ot_report", url="ot-report"),
             dict(path="pages/T_On_Behalf.py", icon="🤝", th="อนุมัติแทน",
                  en="Submit on behalf", cap="leave.approve", url="on-behalf"),
         ]),
    dict(key="employees", icon="🗂️", th="พนักงาน", en="Employees",
         desc_th="ผังองค์กร โปรไฟล์ เอกสาร", desc_en="Org, profile, documents",
         funcs=[
             dict(path="pages/A_Org_Chart.py", icon="🌳", th="ผังองค์กร",
                  en="Org chart", cap="orgchart.view", url="org-chart"),
             dict(path="pages/E_My_Profile.py", icon="👤", th="โปรไฟล์ของฉัน",
                  en="My profile", cap="self.view_profile", url="my-profile"),
             dict(path="pages/M_Training.py", icon="🎓", th="อบรม",
                  en="Training", cap="train.take", url="emp-training",
                  guard=_training_employee),
             dict(path="pages/Q_Doc_Requisition.py", icon="🧾",
                  th="ขอเอกสาร", en="Document requisition",
                  cap="self.view_profile", url="doc-requisition"),
             dict(path="pages/R_Manual.py", icon="📘", th="คู่มือพนักงาน",
                  en="Employees' Manual", cap="self.view_profile",
                  url="manual"),
             dict(path="pages/P_Timesheet.py", icon="🗓️", th="ไทม์ชีท",
                  en="Timesheet", cap="self.view_profile", url="timesheet"),
         ]),
    dict(key="approvals", icon="✅", th="คำขอ & อนุมัติ", en="Approvals",
         desc_th="ยื่นคำขอและการอนุมัติ", desc_en="Requests & approvals",
         funcs=[
             dict(path="pages/F_Leave_OT.py", icon="🗓️", th="ลา / โอที",
                  en="Leave & OT", cap="leave.submit", url="leave-ot"),
             dict(path="pages/G_Car_Booking.py", icon="🚗", th="จองรถ",
                  en="Car Booking", cap="car.book", url="car-booking"),
             dict(path="pages/H_Stationery_ERP.py", icon="✏️",
                  th="เครื่องเขียน", en="Stationery", cap="erp.browse",
                  url="stationery"),
             dict(path="pages/J_Stock.py", icon="📦", th="สต๊อก",
                  en="Stock", cap="stock.request", url="stock"),
             dict(path="pages/L_Resignation.py", icon="📤", th="ลาออก",
                  en="Resignation", cap="resign.submit", url="resignation"),
             dict(path="pages/R_Requests.py", icon="🗂️", th="ทะเบียนคำขอ",
                  en="Request register", url="request-register",
                  guard=_can_view_requests),
         ]),
    dict(key="performance", icon="🎯", th="ผลการปฏิบัติงาน", en="Performance",
         desc_th="ประเมินผลและ KPI", desc_en="Appraisal & KPI",
         funcs=[]),                       # no functions yet → Coming soon
    dict(key="admin", icon="🛠️", th="ผู้ดูแลระบบ", en="Admin",
         desc_th="ข้อมูลพนักงาน ตั้งค่า อัปโหลด", desc_en="Records, settings, uploads",
         funcs=[
             dict(path="pages/D_Employee_Data.py", icon="🗂️",
                  th="ข้อมูลพนักงาน", en="Employees", cap="employee.access",
                  url="employees"),
             dict(path="pages/0_System_Admin.py", icon="⚙️",
                  th="ตั้งค่า & อัปโหลดข้อมูล", en="Settings & Data uploads",
                  cap="system.users", url="system-admin"),
             dict(path="pages/A_CostCentres.py", icon="🏷️",
                  th="กลุ่มรหัสต้นทุน", en="Cost-centre groups",
                  cap="system.users", url="cost-centres"),
             dict(path="pages/A_ApprovalLines.py", icon="🪜",
                  th="สายการอนุมัติ", en="Approval lines",
                  cap="system.users", url="approval-lines"),
             dict(path="pages/A_LeaveTypes.py", icon="🏖️",
                  th="ประเภทการลา", en="Leave types & rules",
                  cap="system.users", url="leave-types"),
             dict(path="pages/V_NoShow_Admin.py", icon="🚨",
                  th="ขาดงานต่อเนื่อง", en="Consecutive no-show",
                  cap="attend.upload", url="noshow-admin"),
         ]),
    dict(key="superadmin", icon="🔐", th="ผู้ดูแลระบบสูงสุด", en="Super Admin",
         desc_th="ข้อมูลลับ เงินเดือน และสิทธิ์", desc_en="Confidential, salary & roles",
         funcs=[
             dict(path="pages/S_Super_Admin.py", icon="🔐",
                  th="ข้อมูลลับ & สิทธิ์บทบาท", en="Confidential & Role rights",
                  cap="employee.view_salary", url="super-admin"),
         ]),
]


def _func_visible(f):
    g = f.get("guard")
    if g is not None:
        return g()
    cap = f.get("cap")
    return True if cap is None else _has(cap)


def visible_funcs(module):
    return [f for f in module["funcs"] if _func_visible(f)]


def build_sidebar():
    """Return an ordered dict {section_label: [st.Page, ...]} for
    st.navigation, containing only modules with >=1 visible function."""
    import streamlit as st
    sections = {}
    for m in MODULES:
        vis = visible_funcs(m)
        if not vis:
            continue
        label = f"{m['icon']} {m['th']} / {m['en']}"
        pages = [
            st.Page(f["path"], title=f"{f['th']} / {f['en']}",
                    icon=f["icon"], url_path=f["url"])
            for f in vis
        ]
        sections[label] = pages
    return sections


def home_cards():
    """Status of every module for the home page."""
    cards = []
    for m in MODULES:
        vis = visible_funcs(m)
        if not m["funcs"]:
            state = "soon"          # module exists but no functions yet
        elif vis:
            state = "open"
        else:
            state = "locked"        # has functions, but role lacks all of them
        cards.append(dict(
            key=m["key"], icon=m["icon"], th=m["th"], en=m["en"],
            desc_th=m["desc_th"], desc_en=m["desc_en"], state=state,
            first_path=vis[0]["path"] if vis else None,
            funcs=[(f["icon"], f["th"], f["en"]) for f in vis],
        ))
    return cards
