# pages/S_Super_Admin.py — confidential data + role-rights editor (super admin)
import streamlit as st
from lib import theme as _theme
from lib.auth import require_capability, current_user
from lib.db import get_conn, PH, IS_POSTGRES
from lib.rbac_seed import ROLES, CAPS, MODULES as RBAC_MODULES

require_capability("employee.view_salary")
_theme.inject()
me = (current_user() or {}).get("username", "system")
st.title("🔐 ผู้ดูแลระบบสูงสุด / Super Admin")
st.caption("ข้อมูลลับ (เงินเดือน/สวัสดิการ) และการกำหนดสิทธิ์บทบาท — เฉพาะผู้ดูแลระบบสูงสุด · "
           "Confidential data (salary/benefits) and role-rights — super admin only.")

t_roles, t_conf = st.tabs(["🛡️ สิทธิ์บทบาท / Role rights",
                           "💼 ข้อมูลลับ & เงินเดือน / Confidential & Salary"])

# ----------------------------------------------------------------- role rights
with t_roles:
    st.subheader("กำหนดสิทธิ์ของแต่ละบทบาท / Configure capabilities per role")
    st.caption("แก้ไขแล้วมีผลทันที (เขียนลงตาราง role_capabilities) · Saved straight to "
               "role_capabilities. Super Admin always has every capability.")
    editable = [r for r in ROLES if r[0] != "super_admin"]
    rkey = st.selectbox("บทบาท / Role", [r[0] for r in editable],
                        format_func=lambda k: next(f"{e} / {t}" for kk, e, t, _ in
                                                   ROLES if kk == k))
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT cap_key FROM role_capabilities WHERE role_key={PH}", (rkey,))
    current = {row[0] for row in cur.fetchall()}

    mod_name = {m[0]: f"{m[2]} / {m[1]}" for m in RBAC_MODULES}
    by_mod = {}
    for key, en, th, mod in CAPS:
        by_mod.setdefault(mod, []).append((key, en, th))

    with st.form(f"rights_{rkey}"):
        chosen = set()
        for mod, items in by_mod.items():
            st.markdown(f"**{mod_name.get(mod, mod)}**")
            cols = st.columns(2)
            for i, (key, en, th) in enumerate(sorted(items)):
                on = cols[i % 2].checkbox(f"{th} · {en}", value=(key in current),
                                          key=f"{rkey}:{key}")
                if on:
                    chosen.add(key)
        save = st.form_submit_button("💾 บันทึกสิทธิ์ / Save rights", type="primary")

    if save:
        to_add = chosen - current
        to_del = current - chosen
        for k in to_add:
            if IS_POSTGRES:
                cur.execute("INSERT INTO role_capabilities (role_key, cap_key) "
                            "VALUES (%s,%s) ON CONFLICT DO NOTHING", (rkey, k))
            else:
                cur.execute("INSERT OR IGNORE INTO role_capabilities "
                            "(role_key, cap_key) VALUES (?,?)", (rkey, k))
        for k in to_del:
            cur.execute(f"DELETE FROM role_capabilities WHERE role_key={PH} "
                        f"AND cap_key={PH}", (rkey, k))
        try:
            from lib import employee_db as edb
            edb._audit(conn, me, "role_rights_update",
                       detail={"role": rkey, "added": sorted(to_add),
                               "removed": sorted(to_del)})
        except Exception:
            pass
        conn.commit()
        st.success(f"บันทึกแล้ว · Saved. +{len(to_add)} / −{len(to_del)} สิทธิ์ "
                   f"สำหรับบทบาท {rkey}. ผู้ใช้บทบาทนี้ต้องรีเฟรช/ล็อกอินใหม่เพื่อให้มีผล "
                   "· users of this role re-login to refresh their menu.")

# --------------------------------------------------------------- confidential
with t_conf:
    st.subheader("💼 ข้อมูลลับและเงินเดือน / Confidential & salary")
    st.markdown(
        "- ช่องเงินเดือน/เบี้ยเลี้ยง (base salary, allowances) แก้ไข/ดูได้เฉพาะ Super "
        "Admin ในโมดูล **Admin → ข้อมูลพนักงาน** (gated by `employee.view_salary` / "
        "`employee.edit_salary`).\n"
        "- โครงสร้างเงินเดือน/สวัสดิการของพนักงาน ใช้สำหรับสร้างสลิปและหนังสือรับรองใน "
        "**ขอเอกสาร (Document requisition)**.")
    st.markdown("**อัปโหลดโครงสร้างเงินเดือน (ลับ) · Upload salary structure "
                "(confidential)**")
    up = st.file_uploader("ANCA Current Staff Salary Structure (.xlsx)",
                          type=["xlsx"], key="sa_salary_struct")
    if up is not None:
        st.caption("⏳ การนำเข้าและจับคู่โครงสร้างเงินเดือนเข้ากับพนักงาน (เพื่อใช้ในสลิป/"
                   "หนังสือรับรอง) กำลังถูกพัฒนาเป็นลำดับถัดไป · Parsing + mapping the "
                   "salary structure to employees (for payslip/certificate generation) "
                   "is the next build. ไฟล์: " + up.name)
