# pages/Q_Doc_Requisition.py — self-service request: salary certificate / payslip
import streamlit as st
from lib import theme as _theme
from lib.auth import require_capability, current_user

require_capability("self.view_profile")
_theme.inject()
st.title("🧾 ขอเอกสาร / Document Requisition")
st.caption("ขอเอกสารของคุณเอง — หนังสือรับรองเงินเดือน และสลิปเงินเดือน "
           "(เห็นและขอได้เฉพาะข้อมูลของตัวเองเท่านั้น) · Request YOUR OWN salary "
           "certificate and pay slip. You can only ever see your own data.")

# --- own record only ---
u = current_user() or {}
emp_no = u.get("emp_no")
rec = None
try:
    from lib import employee_db as edb
    if emp_no:
        rec = edb.get_record(emp_no=emp_no)
except Exception:
    rec = None

if not emp_no or not rec:
    st.warning("บัญชีของคุณยังไม่ได้ผูกกับรหัสพนักงาน — โปรดให้ผู้ดูแลระบบผูกบัญชีก่อน · "
               "Your account isn't linked to an employee number yet; ask an admin.")
    st.stop()

st.success(f"ผู้ขอ / Requester: **{rec.get('emp_name_th') or rec.get('emp_name_en')}** "
           f"· {emp_no}")

doc = st.radio("เลือกเอกสาร / Choose document", [
    "หนังสือรับรองเงินเดือน / Salary Certificate",
    "สลิปเงินเดือน / Salary Pay Slip"])

cycle = None
if doc.startswith("สลิป"):
    from lib import payroll_cycle as pc
    cycles = pc.recent_cycles(12)
    i = st.selectbox("รอบเงินเดือน / Pay period", list(range(len(cycles))),
                     format_func=lambda i: pc.cycle_label(*cycles[i]))
    cycle = cycles[i]

st.info(
    "🔐 **ความปลอดภัย / Security**\n\n"
    "- ระบบจะสร้างไฟล์ **PDF ที่ใส่รหัสผ่าน** แล้วส่งไปยัง **อีเมลของคุณ** ที่ผู้ดูแล"
    "ระบบกำหนดไว้ในระบบ (ไม่ใช่อีเมลที่กรอกเอง)\n"
    "- **รหัสเปิดไฟล์** = เลขบัตรประชาชน 3 หลักสุดท้าย + วันเกิดแบบ ปปปปดดวว (ค.ศ.)\n\n"
    "- The file is generated as a **password-protected PDF** and emailed to the "
    "address an admin set for you. **Password** = last 3 digits of your national ID "
    "+ your date of birth as YYYYMMDD (C.E.).")

if st.button("📨 ส่งคำขอ / Submit request", type="primary"):
    # password rule preview (does not reveal the salary data)
    idc = "".join(c for c in str(rec.get("id_card") or "") if c.isdigit())
    last3 = idc[-3:] if len(idc) >= 3 else "—"
    bd = str(rec.get("birth_day") or "")[:10].replace("-", "") or "—"
    pw_hint = f"{last3} + {bd}"
    dest = rec.get("work_email") or rec.get("company_email") or "(อีเมลที่ผู้ดูแลกำหนด)"
    st.warning(f"🔑 **รหัสเปิดไฟล์ของคุณ / Your file password:** `{pw_hint}`  \n"
               f"(เลขบัตร 3 หลักสุดท้าย + วันเกิด YYYYMMDD ค.ศ.)")
    st.info(f"คำขอถูกบันทึก — เอกสารจะถูกส่งไปที่ **{dest}** · Request recorded; the "
            "document will be emailed to the address on file.")
    st.caption("⏳ เครื่องมือสร้างเอกสาร (สลิป/หนังสือรับรองรูปแบบ AMS) และการส่งอีเมล"
               "แบบใส่รหัสผ่าน กำลังถูกพัฒนาเป็นลำดับถัดไป · The AMS-format generator "
               "(payslip / certificate) and password-protected email delivery are the "
               "next build — wired to your salary structure.")

with st.expander("ℹ️ รูปแบบเอกสาร / Document formats (reference)"):
    st.markdown(
        "- **สลิปเงินเดือน** อ้างอิงรูปแบบจากสลิป CCM แต่ใช้โลโก้ ข้อมูลบริษัท โครงสร้าง"
        "เงินเดือน/สวัสดิการ ผู้ติดต่อ และผู้ลงนามของ **AMS**\n"
        "- **หนังสือรับรองเงินเดือน** อ้างอิงรูปแบบ AMS (เช่น AMS 12-2026) ปรับโครงสร้าง"
        "เงินเดือน/สวัสดิการตามพนักงานแต่ละคน · Pay slip follows the CCM layout but with "
        "AMS branding/structure/signatory; certificate follows the AMS letter format, "
        "adjusted per employee.")
