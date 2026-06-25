# Leave types & form rules — Admin / Superadmin
# Single source of truth for the leave-type list shown everywhere, each type's
# "evidence required" flag, plus the leave-form rules (hourly unit on/off,
# reason required, evidence required for all types).
import streamlit as st
import pandas as pd

from lib import theme as _theme
from lib.auth import require_capability
from lib import leave_config as lc

_theme.inject()
require_capability("system.users")
_theme.header(
    "ประเภทการลา & กฎฟอร์ม", "Leave types & form rules",
    "จัดการรายการประเภทการลาที่ใช้ทั้งระบบ กำหนดว่าประเภทใดต้องแนบหลักฐาน และ "
    "ตั้งกฎการกรอกฟอร์มลา · one place for the leave-type list, the evidence "
    "requirement per type, and the leave-form rules.")

# ----------------------------- form rules ---------------------------------
st.subheader("⚙️ กฎการกรอกฟอร์มลา · Leave-form rules")
rc = st.columns(3)
_hr = rc[0].toggle("อนุญาตลาเป็นชั่วโมง · Allow hourly leave",
                   value=lc.hour_unit_enabled())
_mr = rc[1].toggle("บังคับกรอกเหตุผล · Reason required",
                   value=lc.mandatory_reason())
_me = rc[2].toggle("บังคับแนบหลักฐานทุกประเภท · Require evidence for ALL types",
                   value=lc.mandatory_evidence_global())
if st.button("💾 บันทึกกฎ · Save rules"):
    lc.set_setting("hour_unit_enabled", "1" if _hr else "0")
    lc.set_setting("mandatory_reason", "1" if _mr else "0")
    lc.set_setting("mandatory_evidence", "1" if _me else "0")
    st.success("บันทึกแล้ว · saved."); st.rerun()
st.caption("• ลาเป็นชั่วโมง: เปิดเพื่อให้ผู้ขอเลือกหน่วยชั่วโมงในฟอร์มลา · hourly "
           "leave adds an Hour unit to the form. • บังคับแนบหลักฐาน: ถ้าเปิด "
           "ผู้ขอทุกประเภทต้องแนบไฟล์ก่อนส่ง · forces an attachment on every "
           "leave.")

# ----------------------------- leave types --------------------------------
st.divider()
st.subheader("📋 ประเภทการลา · Leave types")
st.caption("ติ๊ก 'ต้องแนบหลักฐาน' เพื่อบังคับแนบไฟล์เฉพาะประเภทนั้น • ปิด 'ใช้งาน' "
           "เพื่อซ่อนจากเมนู (ข้อมูลเก่ายังแสดงชื่อได้) • ปรับ 'ลำดับ' เพื่อจัดเรียง • "
           "เพิ่มแถวใหม่เพื่อสร้างประเภทใหม่ (ตั้ง key เป็นอักษรอังกฤษไม่มีเว้นวรรค) · "
           "add a row to create a new type; key must be lowercase, no spaces.")

_types = lc.list_types(active_only=False)
_df = pd.DataFrame([{
    "key": t["lkey"],
    "ชื่อ (ไทย)": t["name_th"],
    "Name (EN)": t["name_en"],
    "ต้องแนบหลักฐาน": bool(t["requires_evidence"]),
    "ใช้งาน": bool(t["active"]),
    "ลำดับ": int(t["seq"]),
} for t in _types])

_edited = st.data_editor(
    _df, num_rows="dynamic", use_container_width=True, hide_index=True,
    column_config={
        "key": st.column_config.TextColumn(
            "key", help="รหัสอังกฤษไม่มีเว้นวรรค เช่น sick_cert"),
        "ต้องแนบหลักฐาน": st.column_config.CheckboxColumn("ต้องแนบหลักฐาน"),
        "ใช้งาน": st.column_config.CheckboxColumn("ใช้งาน"),
        "ลำดับ": st.column_config.NumberColumn("ลำดับ", min_value=0, step=1),
    }, key="lt_editor")

if st.button("💾 บันทึกประเภทการลา · Save leave types", type="primary"):
    n = 0
    for _, row in _edited.iterrows():
        k = str(row.get("key") or "").strip()
        if not k:
            continue
        _ev = row.get("ต้องแนบหลักฐาน")
        _ac = row.get("ใช้งาน")
        ev = False if (pd.isna(_ev) if _ev is not None else True) else bool(_ev)
        ac = True if (_ac is None or pd.isna(_ac)) else bool(_ac)
        seq = row.get("ลำดับ")
        seq = 0 if (seq is None or pd.isna(seq)) else int(seq)
        lc.upsert_type(k, str(row.get("ชื่อ (ไทย)") or ""),
                       str(row.get("Name (EN)") or ""), ev, ac, seq)
        n += 1
    st.success(f"บันทึก {n} ประเภท · saved {n} leave types."); st.rerun()

st.info("รายการนี้ถูกใช้ทุกที่ในระบบ (ฟอร์มลา, คิวอนุมัติ, อนุมัติแทน ฯลฯ) · "
        "this list is used across the whole system — the leave form, the "
        "approval queue, on-behalf, and so on.")
