# Cost-centre groups — Admin module
# Map each 3-digit cost-centre code (the first 3 chars of an employee's cost
# centre) to a reporting group/department. This drives the live weekly KPI
# compute, and new cost centres are discovered automatically from the uploaded
# employee list.
import streamlit as st
import pandas as pd

from lib import theme as _theme
from lib.auth import require_capability
from lib import weekly_metrics as wm

_theme.inject()
require_capability("system.users")          # admin / superadmin only
_theme.header(
    "กลุ่มรหัสต้นทุน", "Cost-centre groups",
    "กำหนดว่ารหัสต้นทุน (3 หลักแรกของ cost centre พนักงาน) อยู่กลุ่ม/แผนกใด — "
    "ใช้ตอนคำนวณ KPI รายสัปดาห์แบบสด")

groups = wm.get_cc_groups()
cc_map = wm.get_cc_map()
usage = wm.cost_centre_usage()

# ─────────────────────────── 1) Group names ───────────────────────────
st.subheader("1) กลุ่ม (แผนก) / Groups")
st.caption("ชื่อกลุ่มที่ใช้จัดหมวดรหัสต้นทุน · the group/department names")
st.write("  •  ".join(groups) if groups else "—")

c1, c2 = st.columns(2)
with c1:
    with st.form("cc_add_group", clear_on_submit=True):
        ng = st.text_input("เพิ่มกลุ่มใหม่ / Add a group")
        if st.form_submit_button("➕ เพิ่ม / Add") and ng.strip():
            wm.set_cc_groups(groups + [ng.strip()])
            st.success(f"เพิ่มกลุ่ม '{ng.strip()}' แล้ว")
            st.rerun()
with c2:
    with st.form("cc_rename_group", clear_on_submit=True):
        og = st.selectbox("เปลี่ยนชื่อกลุ่ม / Rename group", groups)
        nn = st.text_input("ชื่อใหม่ / New name")
        if st.form_submit_button("✏️ เปลี่ยนชื่อ / Rename") and nn.strip():
            wm.rename_cc_group(og, nn.strip())
            st.success(f"เปลี่ยน '{og}' → '{nn.strip()}' (อัปเดตแผนผังให้แล้ว)")
            st.rerun()

# ──────────────────── 2) Cost-centre → group (+ discovery) ─────────────
st.subheader("2) แผนผังรหัสต้นทุน → กลุ่ม / Cost-centre → group")
codes = sorted(set(cc_map) | set(usage))
unmapped = sorted(c for c in usage if c not in cc_map)
if unmapped:
    st.info(f"พบรหัสต้นทุนในรายชื่อพนักงานที่ยังไม่ได้จับกลุ่ม {len(unmapped)} "
            f"รหัส: **{', '.join(unmapped)}** — เลือกกลุ่มในตารางแล้วกดบันทึก / "
            f"new unmapped codes from the employee list; assign them below.")

rows = [{"รหัส / Code": c, "กลุ่ม / Group": cc_map.get(c, ""),
         "พบในรายชื่อ / In list": int(usage.get(c, 0))} for c in codes]
if not rows:
    rows = [{"รหัส / Code": "", "กลุ่ม / Group": "", "พบในรายชื่อ / In list": 0}]

edited = st.data_editor(
    pd.DataFrame(rows), num_rows="dynamic", use_container_width=True,
    hide_index=True, key="cc_editor",
    column_config={
        "รหัส / Code": st.column_config.TextColumn(
            "รหัส / Code", width="small", help="3 หลักแรกของ cost centre"),
        "กลุ่ม / Group": st.column_config.SelectboxColumn(
            "กลุ่ม / Group", options=[""] + groups, required=False),
        "พบในรายชื่อ / In list": st.column_config.NumberColumn(
            "พบในรายชื่อ / In list", disabled=True,
            help="จำนวนพนักงานที่ใช้รหัสนี้ (จากรายชื่อที่อัปโหลด)"),
    })

if st.button("💾 บันทึกแผนผัง / Save mapping", type="primary"):
    new_map = {}
    for _, r in edited.iterrows():
        code = str(r["รหัส / Code"] or "").strip()[:3]
        grp = str(r["กลุ่ม / Group"] or "").strip()
        if code and grp:
            new_map[code] = grp
    wm.set_cc_map(new_map)
    extra = [g for g in dict.fromkeys(new_map.values()) if g not in groups]
    if extra:
        wm.set_cc_groups(groups + extra)
    st.success(f"บันทึก {len(new_map)} รหัสแล้ว / saved {len(new_map)} codes.")
    st.rerun()

st.divider()
st.caption("รหัสที่ไม่ได้จับกลุ่มจะไม่ถูกนับใน KPI รายสัปดาห์ • "
           "ระบบค้นพบรหัสใหม่อัตโนมัติทุกครั้งที่อัปโหลดรายชื่อพนักงานใหม่ / "
           "unmapped codes are excluded from the weekly KPIs; new codes are "
           "auto-discovered each time a new employee list is uploaded.")
