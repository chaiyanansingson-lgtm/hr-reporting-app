# pages/E_My_Profile.py
# Requirement 2: current staff review their own record and request updates;
# nothing changes in the master until an admin approves.
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme

from lib.auth import require_capability, current_user  # your existing helpers
from lib.employee_schema import BY_KEY, GROUPS, STAFF_EDIT_KEYS, SALARY_KEYS
from lib import employee_db as edb

_theme.inject()
require_capability("self.view_profile")

edb.migrate()
user = current_user()  # expected: {"username":..., "emp_no":..., "caps":set()}

st.title("👤 ข้อมูลของฉัน / My Profile")

emp_no = (user or {}).get("emp_no")
if not emp_no:
    st.warning("บัญชีของคุณยังไม่ผูกรหัสพนักงาน — แจ้ง HR เพื่อผูก emp_no / "
               "Your login is not linked to an Emp. No. yet. Ask HR/Admin "
               "to link it in user management.")
    st.stop()

rec = edb.get_record(emp_no=str(emp_no))
if not rec:
    st.error(f"ไม่พบข้อมูลพนักงานรหัส {emp_no} / Employee record not found.")
    st.stop()

# ---------------------------------------------------------------- view
hide = set(SALARY_KEYS)  # staff never see the salary tier here
st.subheader("ข้อมูลปัจจุบัน / Current information")
for g, (en, th) in GROUPS.items():
    if g == "salary":
        continue
    keys = [k for k, f in BY_KEY.items()
            if f.grp == g and rec.get(k) not in (None, "") and k not in hide]
    if not keys:
        continue
    with st.expander(f"{th} / {en}", expanded=(g in ("org", "personal"))):
        for k in keys:
            f = BY_KEY[k]
            st.markdown(f"**{f.th} / {f.en}:** {rec.get(k)}")

# ---------------------------------------------------------------- request change
st.divider()
st.subheader("ขอแก้ไขข้อมูล / Request an update")
st.caption("การแก้ไขจะมีผลเมื่อผู้ดูแลระบบอนุมัติเท่านั้น / Changes take "
           "effect only after admin approval.")

editable = [k for k in STAFF_EDIT_KEYS]
sel = st.selectbox(
    "เลือกรายการ / Field",
    editable,
    format_func=lambda k: f"{BY_KEY[k].th} / {BY_KEY[k].en}")
st.text(f"ค่าปัจจุบัน / Current value: {rec.get(sel) or '—'}")
newv = st.text_area("ค่าที่ต้องการ / New value", height=80) \
    if BY_KEY[sel].typ == "longtext" else \
    st.text_input("ค่าที่ต้องการ / New value")

if st.button("ส่งคำขอ / Submit request", type="primary"):
    if not str(newv).strip():
        st.error("กรุณาใส่ค่าใหม่ / Please enter the new value.")
    else:
        edb.submit_change_request(rec["id"], sel, str(newv).strip(),
                                  actor=user["username"])
        st.success("ส่งคำขอแล้ว รออนุมัติ / Request submitted for approval.")

# ---------------------------------------------------------------- my pending
mine = [r for r in edb.pending_change_requests()
        if r["employee_id"] == rec["id"]]
if mine:
    st.divider()
    st.subheader("คำขอที่รออนุมัติ / Pending requests")
    for r in mine:
        f = BY_KEY.get(r["field_key"])
        st.markdown(f"- **{f.th if f else r['field_key']}**: "
                    f"`{r['old_value'] or '—'}` → `{r['new_value']}` "
                    f"(ส่งเมื่อ {r['requested_at'][:16]})")
