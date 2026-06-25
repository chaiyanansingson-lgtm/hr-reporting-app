# Consecutive no-show, org-wide — Admin module (req. 2.6)
# Whole-company view of LPA s.119(5) abandonment runs from the active
# timesheet snapshot. (Managers see only their team's version in K Attendance →
# My team; this page is the organisation-wide picture for admins/HR.)
import streamlit as st

from lib import theme as _theme
from lib.auth import require_capability
from lib import attendance_db as att

_theme.inject()
require_capability("attend.upload")          # HR / admin only
_theme.header("ขาดงานต่อเนื่อง (ทั้งองค์กร)", "Consecutive no-show (org-wide)",
              "เฝ้าระวังการละทิ้งหน้าที่ทั่วทั้งบริษัท ตาม พ.ร.บ.คุ้มครองแรงงาน "
              "พ.ศ.2541 ม.119(5)")

if not att.active_upload("timesheet"):
    st.info("ยังไม่มีไฟล์เวลาทำงาน — อัปโหลดที่ **ผู้ดูแลระบบ → ข้อมูล & อัปโหลด** "
            "/ No timesheet snapshot yet.")
    st.stop()

runs = att.noshow_runs(None, min_days=2)      # None = whole organisation
open_runs = [r for r in runs if r["open"]]
hist = [r for r in runs if not r["open"] and r["days"] >= 3]
st.caption("นับเฉพาะวันทำงาน (วันหยุด/วันลาไม่ตัดความต่อเนื่อง) • เริ่มเตือนที่ "
           "2 วัน • ครบ 3 วัน = เงื่อนไขเลิกจ้างตาม ม.119(5).")

c1, c2, c3 = st.columns(3)
c1.metric("⚠️ กำลังขาดงานอยู่ (≥2 วัน)", len(open_runs))
c2.metric("🔴 ครบ ม.119(5) (≥3 วัน, ยังขาด)",
          len([r for r in open_runs if r["days"] >= 3]))
c3.metric("ประวัติขาด ≥3 วัน (ในช่วงไฟล์)", len(hist))

if open_runs:
    st.markdown("**🔴 ต้องดำเนินการ / Action needed**")
    st.dataframe([{
        "Emp": r["emp_no"], "ชื่อ / Name": r["emp_name"],
        "ตั้งแต่ / From": r["start"], "ถึง / To": r["end"],
        "วันที่ขาด / Days": r["days"],
        "สถานะ / Status": ("🔴 ครบ ม.119(5) — ยื่นเลิกจ้างได้"
                           if r["days"] >= 3 else "⚠️ เตือนวันที่ 2")}
        for r in sorted(open_runs, key=lambda r: -r["days"])],
        use_container_width=True)
    st.caption("ดำเนินการเลิกจ้าง/ยื่นแทนได้ที่หน้า อนุมัติแทน · process the "
               "termination via Submit-on-behalf.")
else:
    st.success("ไม่พบการขาดงานต่อเนื่องที่ยังเปิดอยู่ · no open consecutive "
               "no-show across the organisation.")

if hist:
    with st.expander(f"📋 ประวัติ (ปิดแล้ว) — {len(hist)} ราย / closed runs"):
        st.dataframe([{
            "Emp": r["emp_no"], "ชื่อ / Name": r["emp_name"],
            "ตั้งแต่ / From": r["start"], "ถึง / To": r["end"],
            "วัน / Days": r["days"]}
            for r in sorted(hist, key=lambda r: r["start"])],
            use_container_width=True)
