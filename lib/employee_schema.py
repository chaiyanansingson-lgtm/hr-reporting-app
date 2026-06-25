# lib/employee_schema.py
# ============================================================================
# SINGLE SOURCE OF TRUTH for the Employee Data module.
# Every field the system knows about is declared here once, with flags that
# drive everything else: forms, approvals, exports, templates, bulk upload.
#
#   key            : database column name (snake_case)
#   en / th        : labels
#   grp            : section grouping for forms and exports
#   typ            : text | date | int | float | bool | choice | longtext
#   choices        : for typ == choice
#   master_col     : header text in "Copy of Employee List MASTER V.6"
#                    (sheet "Headcount Updated", rows 4-5) used by the
#                    bulk-upload parser to map columns automatically
#   pdpa           : True  -> EXCLUDED from the External export
#   salary         : True  -> visible/editable by SUPER ADMIN ONLY
#   candidate      : True  -> appears on the candidate application form
#   staff_edit     : True  -> staff may request a change to it (via approval)
#
# PDPA rule of thumb applied (พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562):
# identifiers (ID card, birth date, address, phone, email), health,
# religion, family and emergency-contact data are personal data -> pdpa=True.
# Org facts (emp no, name, title, dept, joined date) stay in External export.
# ============================================================================

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class F:
    key: str
    en: str
    th: str
    grp: str
    typ: str = "text"
    choices: tuple = ()
    master_col: Optional[str] = None
    pdpa: bool = False
    salary: bool = False
    candidate: bool = False
    staff_edit: bool = False


# ---------------------------------------------------------------- field list
FIELDS = [
    # --- Identity / org (mirrors MASTER V.6 columns B-M) -------------------
    F("emp_no", "Emp. No.", "รหัสพนักงาน", "org", master_col="Emp. No."),
    F("emp_name_en", "Emp. Name (EN)", "ชื่อ-สกุล (อังกฤษ)", "org",
      master_col="Emp. Name", candidate=True),
    F("emp_name_th", "ชื่อ-สกุล (ไทย)", "ชื่อ-สกุล (ไทย)", "org",
      master_col="ชื่อ", candidate=True),
    F("nickname", "Nick name", "ชื่อเล่น", "org", master_col="Nick name",
      candidate=True, staff_edit=True),
    F("dept_location", "Dept by Location", "แผนก", "org",
      master_col="Dept by Location"),
    F("cost_centre", "Cost Centre Name", "ศูนย์ต้นทุน", "org",
      master_col="Cost Centre Name"),
    F("thai_expat", "Thai or Expat", "ไทย/ต่างชาติ", "org", typ="choice",
      choices=("Thai", "Expat"), master_col="Thai or Expat"),
    F("mgr_name", "Manager", "ผู้บังคับบัญชา", "org", master_col="Mgr"),
    F("level", "Level", "ระดับ", "org", master_col="Level"),
    F("title", "Title", "ตำแหน่ง", "org", master_col="Title"),
    F("mgr_flag", "Mgr. flag", "เป็นผู้จัดการ", "org", master_col="Mgr."),
    F("direct_indirect", "Direct / Indirect", "Direct / Indirect", "org",
      typ="choice", choices=("Direct", "Indirect"),
      master_col="Direct / Indirect"),
    F("emp_type", "Employment type", "ประเภทการจ้าง", "org", typ="choice",
      choices=("PER", "SUB", "TEM")),

    # --- Dates --------------------------------------------------------------
    F("joined_date_sub", "Joined date (Subcontract)", "วันที่เริ่มงาน (ซับ)",
      "dates", typ="date", master_col="Joined date Subcontract"),
    F("joined_date", "Joined date", "วันที่เริ่มงาน", "dates", typ="date",
      master_col="Joined date"),
    F("subcontract_end", "Subcontract end date", "วันสิ้นสุดสัญญาซับ",
      "dates", typ="date", master_col="Subcontract End date"),
    # probation_end / year_of_work / age are COMPUTED, never stored

    # --- Personal (PDPA) ----------------------------------------------------
    F("id_card", "ID card / Passport no.", "เลขบัตรประชาชน/พาสปอร์ต",
      "personal", master_col="ID card number", pdpa=True, candidate=True),
    F("birth_day", "Birth day", "วันเกิด", "personal", typ="date",
      master_col="Birth day", pdpa=True, candidate=True),
    F("sex", "Sex", "เพศ", "personal", typ="choice", choices=("M", "F"),
      master_col="SEX", pdpa=True, candidate=True),
    F("religion", "Religion", "ศาสนา", "personal", pdpa=True,
      candidate=True, staff_edit=True),
    F("nationality", "Nationality", "สัญชาติ", "personal", pdpa=True,
      candidate=True),
    F("marital_status", "Marital status", "สถานภาพ", "personal",
      typ="choice",
      choices=("โสด/Single", "สมรส/Married", "หย่าร้าง/Divorced",
               "หม้าย/Widowed", "แยกกันอยู่/Separated"),
      pdpa=True, candidate=True, staff_edit=True),
    F("mobile", "Mobile", "เบอร์โทรศัพท์", "personal", master_col="Mobile",
      pdpa=True, candidate=True, staff_edit=True),
    F("personal_email", "Personal email", "อีเมลส่วนตัว", "personal",
      master_col="Personal ", pdpa=True, candidate=True, staff_edit=True),
    F("education", "Education", "วุฒิการศึกษา", "personal",
      master_col="Educational ", pdpa=True, candidate=True, staff_edit=True),

    # --- Addresses (PDPA) ---------------------------------------------------
    F("address_house_reg", "Address (House registration)",
      "ที่อยู่ตามทะเบียนบ้าน", "address", typ="longtext",
      master_col="Address (House registration)", pdpa=True,
      candidate=True, staff_edit=True),
    F("cur_addr_no", "Current address - No.", "ที่อยู่ปัจจุบัน - เลขที่",
      "address", master_col="Current Address|No.", pdpa=True,
      candidate=True, staff_edit=True),
    F("cur_addr_subdistrict", "Current address - Sub-district",
      "ตำบล/แขวง", "address", master_col="Current Address|Sub-district",
      pdpa=True, candidate=True, staff_edit=True),
    F("cur_addr_district", "Current address - District", "อำเภอ/เขต",
      "address", master_col="Current Address|District", pdpa=True,
      candidate=True, staff_edit=True),
    F("cur_addr_province", "Current address - Province", "จังหวัด",
      "address", master_col="Current Address|Province", pdpa=True,
      candidate=True, staff_edit=True),
    F("postcode", "Postcode", "รหัสไปรษณีย์", "address", pdpa=True,
      candidate=True, staff_edit=True),

    # --- Emergency contact (PDPA) -------------------------------------------
    F("emergency_name", "Emergency contact - Name",
      "ผู้ติดต่อฉุกเฉิน - ชื่อ", "emergency",
      master_col="Contact Emergency|Name", pdpa=True, candidate=True,
      staff_edit=True),
    F("emergency_phone", "Emergency contact - Phone",
      "ผู้ติดต่อฉุกเฉิน - เบอร์โทร", "emergency",
      master_col="Contact Emergency|Phone No.", pdpa=True, candidate=True,
      staff_edit=True),
    F("emergency_relation", "Emergency contact - Relationship",
      "ความสัมพันธ์", "emergency",
      master_col="Contact Emergency|Relationship", pdpa=True,
      candidate=True, staff_edit=True),
    F("emergency_address", "Emergency contact - Address",
      "ผู้ติดต่อฉุกเฉิน - ที่อยู่", "emergency", typ="longtext", pdpa=True,
      candidate=True, staff_edit=True),

    # --- Benefits / company admin -------------------------------------------
    F("status", "Status", "สถานะบริษัท", "company", master_col="Status"),
    F("pvd", "PVD", "กองทุนสำรองเลี้ยงชีพ", "company", master_col="PVD"),
    F("sso_inform", "SSO Inform", "แจ้งเข้า สปส.", "company",
      master_col="SSO |Inform"),
    F("service_years", "Service awards - Years", "รางวัลอายุงาน - ปี",
      "company", master_col="Service awards|Service Years"),
    F("service_year_reward", "Service awards - Year reward",
      "รางวัลอายุงาน - ปีที่ได้รับ", "company",
      master_col="Service awards|Year Reward"),
    F("lunch_with_gm", "Lunch with GM", "Lunch with GM", "company",
      master_col="Lunch with|GM"),
    F("transfer_sub", "Transfer from sub to sub company",
      "โอนย้ายจากซับ", "company",
      master_col="Transfer from sub to sub compa"),
    F("extend_1", "Extend 1", "ต่อสัญญา 1", "company", typ="date",
      master_col="Extend 1"),
    F("extend_2", "Extend 2", "ต่อสัญญา 2", "company", typ="date",
      master_col="Extend 2"),
    F("extend_3", "Extend 3", "ต่อสัญญา 3", "company", typ="date",
      master_col="Extend 3"),
    F("extend_4", "Extend 4", "ต่อสัญญา 4", "company", typ="date",
      master_col="Extend 4"),
    F("extend_25", "Extend 25", "Extend 25", "company", typ="date",
      master_col="Extend 25"),
    F("skill_mig_steel", "MIG - Steel", "ทักษะ MIG - เหล็ก", "skills",
      master_col="MIG -Steel"),
    F("skill_mig_alu", "MIG - Alu", "ทักษะ MIG - อลูมิเนียม", "skills",
      master_col="MIG Alu"),

    # --- SALARY TIER (SUPER ADMIN ONLY; also PDPA) ---------------------------
    F("base_salary", "Base salary", "เงินเดือนพื้นฐาน", "salary",
      typ="float", pdpa=True, salary=True),
    F("position_allowance", "Position allowance", "ค่าตำแหน่ง", "salary",
      typ="float", pdpa=True, salary=True),
    F("other_allowance", "Other allowance", "เบี้ยเลี้ยง/ค่าอื่นๆ", "salary",
      typ="float", pdpa=True, salary=True),
    F("salary_note", "Remuneration note", "หมายเหตุค่าตอบแทน", "salary",
      typ="longtext", pdpa=True, salary=True),

    # --- Application form FM-HR-003 (candidate-only narrative) ---------------
    F("position_applied", "Position applied for", "ตำแหน่งที่สมัคร", "apply",
      pdpa=True, candidate=True),
    F("prev_employment", "Previous employment", "ประวัติการทำงาน", "apply",
      typ="longtext", pdpa=True, candidate=True),
    F("education_history", "Education history", "ประวัติการศึกษา", "apply",
      typ="longtext", pdpa=True, candidate=True),
    F("other_qualifications", "Other qualifications / courses",
      "การอบรม/คุณสมบัติอื่น", "apply", typ="longtext", pdpa=True,
      candidate=True),
    F("languages", "Languages", "ความสามารถด้านภาษา", "apply", pdpa=True,
      candidate=True, staff_edit=True),
    F("hobbies", "Hobbies / interests", "กิจกรรมยามว่าง", "apply",
      pdpa=True, candidate=True, staff_edit=True),
    F("driver_licence", "Driver licence", "ใบขับขี่", "apply", pdpa=True,
      candidate=True, staff_edit=True),
    F("can_shift_work", "Able to work shift rotation",
      "ทำงานเป็นกะได้", "apply", typ="choice",
      choices=("ได้/Yes", "ไม่ประสงค์/No"), pdpa=True, candidate=True),
    F("start_availability", "When able to start",
      "ระยะเวลาที่เริ่มงานได้", "apply", typ="choice",
      choices=("ได้ทันที/Now", "15 วัน/15 days", "30 วัน/30 days",
               "อื่นๆ/Other"), pdpa=True, candidate=True),
    F("ever_discharged", "Ever discharged from employment",
      "เคยถูกเลิกจ้าง", "apply", typ="longtext", pdpa=True, candidate=True),
    F("criminal_record", "Criminal record", "ประวัติคดีอาญา", "apply",
      typ="longtext", pdpa=True, candidate=True),

    # --- Health disclosures (FM-HR-003 + เอกสารแนบท้าย) — SENSITIVE PDPA -----
    F("health_injury", "Injury affecting work/safety",
      "เคยบาดเจ็บที่กระทบงาน", "health", typ="longtext", pdpa=True,
      candidate=True),
    F("health_illness", "Serious illness / operations",
      "เคยป่วยหนัก/ผ่าตัด", "health", typ="longtext", pdpa=True,
      candidate=True),
    F("health_drugs", "Drug addiction history", "ประวัติสารเสพติด",
      "health", typ="longtext", pdpa=True, candidate=True),
    F("health_chronic", "Medical problems / chronic disease",
      "โรคประจำตัว", "health", typ="longtext", pdpa=True, candidate=True),
    F("health_medical_exam_consent", "Willing to undergo medical exam",
      "ยินยอมตรวจสุขภาพ", "health", typ="choice",
      choices=("ยินยอม/Yes", "ไม่ยินยอม/No"), pdpa=True, candidate=True),
    F("disclosure_image_disease", "Disease affecting work image (แนบท้าย 1)",
      "โรคที่กระทบภาพลักษณ์งาน", "health", typ="longtext", pdpa=True,
      candidate=True),
    F("disclosure_care_duty", "Care duty for patient/bedridden (แนบท้าย 5)",
      "ภาระดูแลผู้ป่วย", "health", typ="longtext", pdpa=True,
      candidate=True),
    F("disclosure_relatives_at_work", "Relatives working at site (แนบท้าย 6)",
      "ญาติทำงานในสถานประกอบการ", "health", typ="longtext", pdpa=True,
      candidate=True),

    # --- สปส.1-03 SSO registration data --------------------------------------
    F("sso_prev_registered", "Previously SSO-registered (สปส.1-03)",
      "เคยขึ้นทะเบียนผู้ประกันตน", "sso", typ="choice",
      choices=("ไม่เคย/Never", "เคย/Yes"), pdpa=True, candidate=True),
    F("sso_multi_employer", "Works for multiple employers",
      "ทำงานกับนายจ้างหลายแห่ง", "sso", pdpa=True, candidate=True),
    F("sso_children_u6", "Children under 6 (count + birth years)",
      "บุตรอายุไม่เกิน 6 ปี", "sso", pdpa=True, candidate=True,
      staff_edit=True),
    F("sso_disability", "Disability (type per สปส.1-03 §2.5)",
      "ความพิการ", "sso", typ="longtext", pdpa=True, candidate=True),
    F("work_permit_no", "Work permit no. (foreigner)",
      "เลขใบอนุญาตทำงาน", "sso", pdpa=True, candidate=True),
    F("passport_no", "Passport no. (foreigner)", "เลขหนังสือเดินทาง",
      "sso", pdpa=True, candidate=True),
    F("hospital_choice_1", "Hospital choice 1", "สถานพยาบาล ลำดับ 1",
      "sso", pdpa=True, candidate=True, staff_edit=True),
    F("hospital_choice_2", "Hospital choice 2", "สถานพยาบาล ลำดับ 2",
      "sso", pdpa=True, candidate=True, staff_edit=True),
    F("hospital_choice_3", "Hospital choice 3", "สถานพยาบาล ลำดับ 3",
      "sso", pdpa=True, candidate=True, staff_edit=True),

    # --- ล.ย.01 tax deduction declaration ------------------------------------
    F("tax_spouse_income", "Spouse income status (ล.ย.01)",
      "สถานะเงินได้คู่สมรส", "tax", typ="choice",
      choices=("มีเงินได้/Has income", "ไม่มีเงินได้/No income",
               "ไม่เกี่ยวข้อง/N.A."), pdpa=True, candidate=True,
      staff_edit=True),
    F("tax_children_total", "Total children", "จำนวนบุตรรวม", "tax",
      typ="int", pdpa=True, candidate=True, staff_edit=True),
    F("tax_children_30k", "Children @30,000 deduction",
      "บุตรลดหย่อน 30,000", "tax", typ="int", pdpa=True, candidate=True,
      staff_edit=True),
    F("tax_children_60k", "Children @60,000 (2nd+, born ≥2561)",
      "บุตรลดหย่อน 60,000", "tax", typ="int", pdpa=True, candidate=True,
      staff_edit=True),
    F("tax_parent_care", "Parent care deduction (บิดา/มารดา)",
      "ลดหย่อนบิดามารดา", "tax", pdpa=True, candidate=True,
      staff_edit=True),
    F("tax_disabled_care", "Disabled/incapacitated care",
      "อุปการะคนพิการ/ทุพพลภาพ", "tax", pdpa=True, candidate=True,
      staff_edit=True),
    F("tax_life_insurance", "Life insurance premium (THB)",
      "เบี้ยประกันชีวิต", "tax", typ="float", pdpa=True, candidate=True,
      staff_edit=True),
    F("tax_health_insurance", "Health insurance premium (THB)",
      "เบี้ยประกันสุขภาพ", "tax", typ="float", pdpa=True, candidate=True,
      staff_edit=True),
    F("tax_rmf", "RMF purchase (THB)", "ค่าซื้อ RMF", "tax", typ="float",
      pdpa=True, candidate=True, staff_edit=True),
    F("tax_home_loan_interest", "Home loan interest (THB)",
      "ดอกเบี้ยกู้ที่อยู่อาศัย", "tax", typ="float", pdpa=True,
      candidate=True, staff_edit=True),
    F("tax_donations", "Donations (THB / detail)", "เงินบริจาค", "tax",
      pdpa=True, candidate=True, staff_edit=True),
]

GROUPS = {
    "org": ("Organisation", "ข้อมูลองค์กร"),
    "dates": ("Employment dates", "วันที่จ้างงาน"),
    "personal": ("Personal details", "ประวัติส่วนตัว"),
    "address": ("Addresses", "ที่อยู่"),
    "emergency": ("Emergency contact", "ผู้ติดต่อฉุกเฉิน"),
    "company": ("Company admin & benefits", "สวัสดิการ/ข้อมูลบริษัท"),
    "skills": ("Skills", "ทักษะ"),
    "salary": ("Salary & remuneration (Super Admin)", "เงินเดือนและค่าตอบแทน"),
    "apply": ("Application details", "ข้อมูลการสมัครงาน"),
    "health": ("Health & disclosures", "สุขภาพและการเปิดเผยข้อมูล"),
    "sso": ("Social Security (สปส.1-03)", "ประกันสังคม"),
    "tax": ("Tax deductions (ล.ย.01)", "ลดหย่อนภาษี"),
}

BY_KEY = {f.key: f for f in FIELDS}
SALARY_KEYS = [f.key for f in FIELDS if f.salary]
PDPA_KEYS = [f.key for f in FIELDS if f.pdpa]
CANDIDATE_KEYS = [f.key for f in FIELDS if f.candidate]
STAFF_EDIT_KEYS = [f.key for f in FIELDS if f.staff_edit]
# External export = everything that is NOT pdpa and NOT salary
EXTERNAL_KEYS = [f.key for f in FIELDS if not f.pdpa and not f.salary]
# Internal export = everything except the salary tier
INTERNAL_KEYS = [f.key for f in FIELDS if not f.salary]

RECORD_STATUSES = ("candidate", "upcoming", "active", "resigned", "rejected")
