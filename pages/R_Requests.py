# Request Register — Admin / Superadmin (and anyone granted)
# One place to see every request in the system with its live status (approved /
# waiting-on-whom / rejected / cancelled), download the raw data for analysis,
# and grant both rights to any role or staff number.
import io

import streamlit as st
import pandas as pd

from lib import theme as _theme
from lib.auth import current_user
from lib import request_registry as rr
from lib import feature_grants as fg

_theme.inject()

_u = current_user()
if not _u:
    st.warning("กรุณาเข้าสู่ระบบก่อน · Please sign in to continue.")
    st.stop()
if not fg.has_feature("requests.view"):
    st.warning("คุณไม่มีสิทธิ์เข้าถึงทะเบียนคำขอ · You don't have access to the "
               "request register. Ask an administrator to grant it.")
    st.stop()

_is_admin = "system.users" in _u.get("caps", [])
_can_export = fg.has_feature("requests.export")

_theme.header(
    "ทะเบียนคำขอ", "Request register",
    "คำขอทุกประเภทในระบบ พร้อมสถานะการอนุมัติ และดาวน์โหลดข้อมูลดิบเพื่อวิเคราะห์ · "
    "every request with approval status, plus raw-data export.")

# ----------------------------- status metrics -----------------------------
_c = rr.counts()
m = st.columns(5)
m[0].metric("ทั้งหมด · Total", _c["total"])
m[1].metric("⏳ รออนุมัติ · Pending", _c["pending"])
m[2].metric("✅ อนุมัติ · Approved", _c["approved"])
m[3].metric("⛔ ไม่อนุมัติ · Rejected", _c["rejected"])
m[4].metric("🚫 ยกเลิก · Cancelled", _c["cancelled"])

# ------------------------------- filters ----------------------------------
f = st.columns([2, 1.4, 2])
_types = f[0].multiselect(
    "ประเภท · Type", rr.KINDS,
    format_func=lambda k: rr.TYPE_LABEL[k], default=rr.KINDS)
_status = f[1].selectbox(
    "สถานะ · Status",
    ["all", "pending", "approved", "rejected", "cancelled"],
    format_func=lambda s: ("ทั้งหมด · All" if s == "all"
                           else rr.STATUS_LABEL.get(s, s)))
_q = f[2].text_input("ค้นหา (ชื่อ/รหัส/เลขเอกสาร) · Search (name / emp / doc no)")

_data = rr.all_requests(kinds=_types or None, status=_status, q=_q or None)

st.caption(f"พบ {len(_data)} รายการ · {len(_data)} request(s)")

if _data:
    _df = pd.DataFrame([{
        "เลขเอกสาร · Doc no": d["doc_no"],
        "ประเภท · Type": d["type_label"],
        "ผู้ขอ · Requester": d["requester"] or "—",
        "รหัส · Emp": d["emp_no"] or "—",
        "ยื่นเมื่อ · Submitted": (d["submitted"] or "")[:16].replace("T", " "),
        "สถานะ · Status": d["status_label"],
        "รออนุมัติที่ · Waiting on": d["waiting_on"],
        "รายละเอียด · Detail": d["summary"],
    } for d in _data])
    st.dataframe(_df, use_container_width=True, hide_index=True)
else:
    st.info("ไม่มีคำขอตามเงื่อนไข · no requests match the filters.")

# ------------------------------- raw export -------------------------------
st.divider()
st.subheader("⬇️ ส่งออกข้อมูลดิบ · Export raw data")
if not _can_export:
    st.caption("คุณไม่มีสิทธิ์ส่งออกข้อมูลดิบ · you don't have export rights "
               "(an administrator can grant 'requests.export').")
else:
    st.caption("ดาวน์โหลดทุกคอลัมน์ของคำขอทุกประเภท เพื่อนำไปวิเคราะห์ต่อ · "
               "all columns of every request, for your own analysis.")
    _raw = rr.raw_frame(kinds=_types or None)
    if _raw.empty:
        st.info("ยังไม่มีข้อมูลให้ส่งออก · no data to export yet.")
    else:
        # Excel: a friendly Summary sheet + one raw sheet per request type
        _buf = io.BytesIO()
        with pd.ExcelWriter(_buf, engine="openpyxl") as xw:
            if _data:
                _df.to_excel(xw, sheet_name="Summary", index=False)
            for _k in (_types or rr.KINDS):
                _sub = _raw[_raw["request_type"] == _k]
                if not _sub.empty:
                    _sub.to_excel(xw, sheet_name=_k[:31], index=False)
        _buf.seek(0)
        cdl = st.columns(2)
        cdl[0].download_button(
            "📊 ดาวน์โหลด Excel · Download Excel (.xlsx)",
            _buf.getvalue(), file_name="request_register_raw.xlsx",
            mime=("application/vnd.openxmlformats-officedocument."
                  "spreadsheetml.sheet"), use_container_width=True)
        cdl[1].download_button(
            "📄 ดาวน์โหลด CSV (รวม) · Download CSV (combined)",
            _raw.to_csv(index=False).encode("utf-8-sig"),
            file_name="request_register_raw.csv", mime="text/csv",
            use_container_width=True)

# --------------------- access grants (admin/superadmin) -------------------
if _is_admin:
    st.divider()
    st.subheader("🔑 ให้สิทธิ์เข้าถึง · Grant access")
    st.caption("ให้สิทธิ์ดูทะเบียน/ส่งออกข้อมูล แก่บทบาทใด ๆ หรือรหัสพนักงานใด ๆ "
               "(ผู้ดูแลระบบ/ซูเปอร์แอดมินมีสิทธิ์อยู่แล้วเสมอ) · grant view/export "
               "to any role or staff number (admins always have access).")

    def _roles():
        from lib.db import get_conn
        conn = get_conn(); cur = conn.cursor()
        try:
            cur.execute("SELECT role_key, name_th FROM roles ORDER BY role_key")
            return [(r[0], r[1]) for r in cur.fetchall()]
        except Exception:
            return []

    _rolelist = _roles()
    gc = st.columns([1.4, 1.2, 1.6, 1])
    _feat = gc[0].selectbox("สิทธิ์ · Feature", list(fg.FEATURES.keys()),
                            format_func=lambda x: fg.FEATURES[x])
    _gtype = gc[1].radio("ให้แก่ · Grant to", ["role", "emp_no"],
                         format_func=lambda x: ("บทบาท · Role" if x == "role"
                                                else "รหัสพนักงาน · Staff no"),
                         horizontal=False)
    if _gtype == "role":
        _gval = gc[2].selectbox(
            "บทบาท · Role", [r[0] for r in _rolelist] or [""],
            format_func=lambda k: next((f"{k} — {n}" for kk, n in _rolelist
                                        if kk == k), k))
    else:
        _gval = gc[2].text_input("รหัสพนักงาน · Staff number")
    if gc[3].button("➕ ให้สิทธิ์ · Grant", use_container_width=True):
        if str(_gval).strip():
            ok = fg.grant(_feat, _gtype, _gval, _u.get("username", "admin"))
            st.success("ให้สิทธิ์แล้ว · granted." if ok else
                       "มีอยู่แล้ว · already granted.")
            st.rerun()
        else:
            st.warning("กรอกค่าก่อน · enter a value first.")

    _grants = fg.list_grants()
    if _grants:
        st.markdown("**สิทธิ์ที่ให้ไว้ · Current grants**")
        for g in _grants:
            gcol = st.columns([3, 2, 2, 1])
            gcol[0].write(fg.FEATURES.get(g["feature"], g["feature"]))
            gcol[1].write("บทบาท · Role" if g["grantee_type"] == "role"
                          else "รหัส · Emp")
            gcol[2].write(g["grantee"])
            if gcol[3].button("🗑️", key=f"rv_{g['id']}"):
                fg.revoke(g["id"]); st.rerun()
    else:
        st.caption("ยังไม่ได้ให้สิทธิ์เพิ่มเติม · no extra grants yet "
                   "(admins still have full access).")
