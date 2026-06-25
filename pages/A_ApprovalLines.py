# Approval lines — Admin / Superadmin
# Three ways to configure who approves each request:
#   1) Routing table  — the Routing-Request layout (Applicant + Petitioner1/2 +
#                        Approver1/2/3 + Reviewer), per request kind & scope.
#   2) Bulk upload     — download an Excel template, fill it, upload many lines.
#   3) Advanced steps  — a free-form ordered list (person or "next manager").
# All three save to the same engine; where nothing is set, the manager-walk
# applies automatically.
import json

import streamlit as st

from lib import theme as _theme
from lib.auth import require_capability, current_user
from lib import approval_rules as ar
from lib import employee_db as edb

_theme.inject()
require_capability("system.users")
_theme.header(
    "สายการอนุมัติ", "Approval lines",
    "กำหนดผู้อนุมัติของแต่ละประเภทคำขอ แยกตามแผนกได้ — ในรูปแบบใบ Routing Request "
    "หรืออัปโหลดทีละมาก · set the approver routing per request type & department, "
    "in the Routing-Request layout or via bulk upload.")

_emps = edb.list_records("active")
_emp_name = {str(e.get("emp_no")): (e.get("emp_name_en") or e.get("emp_name_th")
             or "") for e in _emps if e.get("emp_no")}
_valid = set(_emp_name)
_depts = sorted({(e.get("dept_location") or "").strip() for e in _emps
                 if (e.get("dept_location") or "").strip()})
_NONE = "— ไม่มี · none —"
_opts = [_NONE] + list(_emp_name.keys())


def _fmt(v):
    return _NONE if v == _NONE else f"{v} — {_emp_name.get(v, '')}"


t_route, t_bulk, t_adv = st.tabs([
    "🧭 ตารางสายอนุมัติ · Routing table",
    "📤 อัปโหลดทีละมาก · Bulk upload",
    "🛠️ ขั้นสูง · Advanced steps"])

# =============================================================== ROUTING TABLE
with t_route:
    st.caption("รูปแบบเดียวกับใบ Routing Request — เลือกผู้ลงนามแต่ละช่องตามลำดับ "
               "(เว้นว่างได้). “Applicant” คือผู้ยื่นเอง (อัตโนมัติ). ลำดับการเซ็น "
               "= ซ้าย→ขวา.")
    rc = st.columns([1.5, 1.2, 2])
    kind = rc[0].selectbox("ประเภทคำขอ · Request kind", ar.KINDS,
                           format_func=lambda k: ar.KIND_LABEL[k], key="rt_kind")
    scope_type = rc[1].radio(
        "ขอบเขต · Scope", ["all", "department"],
        format_func=lambda s: ("ทุกแผนก · All" if s == "all"
                               else "เฉพาะแผนก · Dept"), key="rt_scope")
    scope_value = (rc[2].selectbox("แผนก · Department", _depts or [""],
                   key="rt_dept") if scope_type == "department" else "*")

    cur = ar.get_routing(kind, scope_type, scope_value)
    st.markdown("##### ผู้ลงนามตามลำดับ · Signers in order")
    st.text_input("Applicant · ผู้ยื่น", value="พนักงานผู้ยื่นคำขอ (อัตโนมัติ)",
                  disabled=True, key="rt_applicant")
    cols = st.columns(3)
    vals = {}
    for i, (key, en, th) in enumerate(ar.ROUTING_SLOTS):
        saved = cur.get(key) or _NONE
        idx = _opts.index(saved) if saved in _opts else 0
        vals[key] = cols[i % 3].selectbox(
            f"{en} · {th}", _opts, index=idx, format_func=_fmt, key=f"rt_{key}")
    slots = {k: ("" if v == _NONE else v) for k, v in vals.items()}

    sc = st.columns(2)
    if sc[0].button("💾 บันทึก Routing · Save routing", type="primary",
                    use_container_width=True):
        ar.set_routing(kind, scope_type, scope_value, slots,
                       current_user().get("username", "admin"))
        st.success("บันทึกแล้ว · saved."); st.rerun()
    if sc[1].button("🗑️ ลบสายนี้ · Delete this line", use_container_width=True):
        ln = ar.get_line(kind, scope_type, scope_value)
        if ln:
            ar.delete_line(ln["id"]); st.success("ลบแล้ว · deleted."); st.rerun()
        else:
            st.caption("ยังไม่ได้บันทึกสายนี้ · nothing saved yet.")
    _chain = [slots.get(k) for k, _e, _t in ar.ROUTING_SLOTS if slots.get(k)]
    if _chain:
        st.info("ลำดับที่จะใช้จริง · resolves to:  " +
                "  →  ".join(f"{v} ({_emp_name.get(v, v)})" for v in _chain))

# =============================================================== BULK UPLOAD
with t_bulk:
    st.caption("ตั้งค่าหลายรายการพร้อมกัน: ดาวน์โหลดเทมเพลต → กรอกรหัสพนักงานในแต่ละ "
               "ช่อง → อัปโหลดกลับ. ใช้ได้ดีเมื่อมีหลายแผนก/หลายประเภทคำขอ.")
    st.download_button(
        "⬇️ ดาวน์โหลดเทมเพลต (พร้อมรายชื่อพนักงานจริง) · Download template",
        ar.routing_template_xlsx(_emps),
        file_name="ANCA_Approval_Routing_Template.xlsx",
        mime=("application/vnd.openxmlformats-officedocument."
              "spreadsheetml.sheet"), use_container_width=True)
    st.markdown("เทมเพลตมี 3 แผ่น: **Instructions** (วิธีใช้) · **Routing** "
                "(กรอกที่นี่) · **Employees** (ค้นรหัสพนักงาน).")
    st.divider()
    up = st.file_uploader("อัปโหลดไฟล์ที่กรอกแล้ว · Upload the filled template",
                          type=["xlsx"], key="rt_up")
    if up is not None and st.button("▶️ นำเข้า · Import", type="primary"):
        try:
            rows = ar.parse_routing_upload(up.read())
            applied, errors = ar.bulk_apply(
                rows, current_user().get("username", "admin"),
                valid_emp=_valid)
            if applied:
                st.success(f"นำเข้าสำเร็จ {applied} สาย · imported {applied} "
                           "routing lines.")
            if errors:
                st.warning("บางแถวมีปัญหา (ข้ามไป) · some rows were skipped:")
                for e in errors:
                    st.write("• " + e)
            if not applied and not errors:
                st.info("ไม่พบข้อมูลในไฟล์ · no rows found in the file.")
        except Exception as ex:
            st.error(f"อ่านไฟล์ไม่ได้ · could not read the file: {ex}")

# =============================================================== ADVANCED STEPS
with t_adv:
    st.caption("รูปแบบอิสระ: เพิ่มชั้นได้ไม่จำกัด แต่ละชั้นเป็น “บุคคลเจาะจง” หรือ "
               "“ผู้บังคับบัญชาคนถัดไป” ของผู้ขอ.")
    ac = st.columns([1.5, 1.2, 2])
    a_kind = ac[0].selectbox("ประเภทคำขอ · Request kind", ar.KINDS,
                             format_func=lambda k: ar.KIND_LABEL[k],
                             key="al_kind")
    a_stype = ac[1].radio("ขอบเขต · Scope", ["all", "department"],
                          format_func=lambda s: ("ทุกแผนก · All" if s == "all"
                                                 else "เฉพาะแผนก · Dept"),
                          key="al_stype")
    a_sval = (ac[2].selectbox("แผนก · Department", _depts or [""], key="al_dept")
              if a_stype == "department" else "*")
    _sig = f"{a_kind}|{a_stype}|{a_sval}"
    if st.session_state.get("al_sig") != _sig:
        _ln = ar.get_line(a_kind, a_stype, a_sval)
        st.session_state["al_steps"] = (json.loads(_ln["steps_json"])
                                        if _ln else [])
        st.session_state["al_sig"] = _sig
    steps = st.session_state["al_steps"]
    st.markdown("##### 🪜 ลำดับการอนุมัติ · Approval steps")
    if steps:
        for i, s in enumerate(steps):
            cc = st.columns([6, 1])
            if s.get("type") == ar.STEP_MANAGER:
                cc[0].write(f"**{i+1}.** 👔 ผู้จัดการลำดับถัดไป · next manager")
            else:
                cc[0].write(f"**{i+1}.** 👤 {s.get('value')} — "
                            f"{_emp_name.get(str(s.get('value')), s.get('value'))}"
                            + (f"  ·  {s.get('role')}" if s.get('role') else ""))
            if cc[1].button("🗑️", key=f"al_del_{i}"):
                steps.pop(i); st.rerun()
    else:
        st.caption("ยังไม่มีลำดับ · no steps yet.")
    addc = st.columns([1.4, 2.4, 1])
    addt = addc[0].radio("เพิ่มขั้น · Add", [ar.STEP_MANAGER, ar.STEP_EMP],
                         format_func=lambda t: ("ผู้จัดการ · Manager"
                                                if t == ar.STEP_MANAGER
                                                else "บุคคล · Person"),
                         key="al_addtype")
    pk = None
    if addt == ar.STEP_EMP:
        pk = addc[1].selectbox("บุคคล (พิมพ์ค้นหา) · Person",
                               list(_emp_name) or [""],
                               format_func=lambda n: f"{n} — {_emp_name.get(n,'')}",
                               key="al_pick")
    else:
        addc[1].caption("ใช้ผู้จัดการคนถัดไปของผู้ขอ · the requester's next "
                        "manager.")
    if addc[2].button("➕ เพิ่ม · Add", use_container_width=True):
        if addt == ar.STEP_MANAGER:
            steps.append({"type": ar.STEP_MANAGER}); st.rerun()
        elif pk:
            steps.append({"type": ar.STEP_EMP, "value": pk}); st.rerun()
    bc = st.columns(2)
    if bc[0].button("💾 บันทึก · Save", type="primary", use_container_width=True,
                    key="al_save"):
        ar.set_line(a_kind, a_stype, a_sval, steps,
                    current_user().get("username", "admin"))
        st.success("บันทึกแล้ว · saved.")
    if bc[1].button("🗑️ ลบสายนี้ · Delete", use_container_width=True,
                    key="al_delline"):
        _ln = ar.get_line(a_kind, a_stype, a_sval)
        if _ln:
            ar.delete_line(_ln["id"]); st.session_state["al_steps"] = []
            st.success("ลบแล้ว · deleted."); st.rerun()

# =============================================================== ALL LINES
st.divider()
st.subheader("📋 สายการอนุมัติทั้งหมด · All configured lines")
_lines = ar.list_lines()
if _lines:
    for ln in _lines:
        s2 = json.loads(ln.get("steps_json") or "[]")
        desc = "  →  ".join(
            ("Mgr" if s.get("type") == ar.STEP_MANAGER
             else f"{s.get('value')}({_emp_name.get(str(s.get('value')), '')})"
             ) for s in s2) or "(ว่าง)"
        scope_lbl = ("ทุกแผนก · All" if ln["scope_type"] == "all"
                     else f"แผนก · Dept {ln['scope_value']}")
        st.write(f"**{ar.KIND_LABEL.get(ln['request_kind'], ln['request_kind'])}**"
                 f" — {scope_lbl} :  {desc}")
else:
    st.caption("ยังไม่มีสายที่ตั้งค่า · none configured yet.")
st.info("ถ้าไม่ได้ตั้งสายสำหรับประเภท/แผนกใด ระบบจะไล่ตามคอลัมน์ Mgr อัตโนมัติ · "
        "where no line is set, the manager-walk is used automatically.")
