# pages/A_Org_Chart.py
# Org chart: interactive chart (photos, vertical stacking, profile bubble)
# + in-app PROFILE OPENER (search -> role-gated full profile)
# + PRINT BY BUSINESS UNIT (A4 document: legend top-left, version/
#   proposed-by/approved-by block bottom-right).
import datetime as dt
import html as _html
import json
import pathlib

import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme

from lib.auth import require_capability, has_capability, current_user
from lib import employee_db as edb
from lib import employee_schema as schema

_theme.inject()
require_capability("orgchart.view")

st.title("🌳 ผังองค์กร / Organisation Chart")

act = edb.list_records("active")

# ====================================================== profile opener
with st.expander("🔎 เปิดโปรไฟล์พนักงาน / Open staff profile", expanded=False):
    q = st.text_input("ค้นหา (รหัส / ชื่อ / นามสกุล / ชื่อเล่น) — วางรหัสที่"
                      "คัดลอกจากการ์ดในผังได้เลย / Search by ID, name, "
                      "surname or nickname — paste the Emp. No. copied from "
                      "a chart card", key="prof_q")
    sel_rec = None
    if q.strip():
        ql = q.strip().lower()
        hits = [r for r in act if ql in str(r.get("emp_no", "")).lower()
                or ql in str(r.get("emp_name_en", "")).lower()
                or ql in str(r.get("emp_name_th", "")).lower()
                or ql in str(r.get("nickname", "")).lower()]
        if not hits:
            st.caption("ไม่พบ / no match")
        elif len(hits) == 1:
            sel_rec = hits[0]
        else:
            pid = st.selectbox("เลือก / Pick", [r["id"] for r in hits],
                               format_func=lambda i: next(
                                   f"{r['emp_no']} • {r.get('emp_name_en')} "
                                   f"({r.get('nickname') or '-'})"
                                   for r in hits if r["id"] == i),
                               key="prof_pick")
            sel_rec = edb.get_record(employee_id=pid)

    if sel_rec:
        rec = sel_rec
        is_super = has_capability("employee.view_salary")
        PREVIEW_KEYS = ["emp_no", "emp_name_en", "emp_name_th", "nickname",
                        "title", "dept_location", "mobile", "personal_email",
                        "mgr_name"]
        PREVIEW_LABELS = {
            "emp_no": "รหัสพนักงาน / Emp No.",
            "emp_name_en": "ชื่อ-สกุล / Name (EN)",
            "emp_name_th": "ชื่อ-สกุล (ไทย) / Name (TH)",
            "nickname": "ชื่อเล่น / Nickname",
            "title": "ตำแหน่ง / Position",
            "dept_location": "แผนก / Department",
            "mobile": "โทรศัพท์ / Phone",
            "personal_email": "อีเมล / Email",
            "mgr_name": "ผู้บังคับบัญชา / Manager"}
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            if rec.get("photo"):
                c1.image(bytes(rec["photo"]), width=110)
            c2.subheader(f"{rec.get('emp_name_en')} "
                         f"({rec.get('nickname') or '-'})")
            c2.caption(f"{rec.get('title') or ''} • "
                       f"{rec.get('dept_location') or ''}")
            for k in PREVIEW_KEYS:
                if rec.get(k):
                    a, b = st.columns([1, 2])
                    a.markdown(f"**{PREVIEW_LABELS[k]}**")
                    b.write(rec.get(k))
            if is_super:
                st.divider()
                st.markdown("#### 🔒 PDPA & เงินเดือน (เฉพาะ Super Admin) / "
                            "PDPA & salary (Super Admin only)")
                _shown = set(PREVIEW_KEYS)
                sens = [k for k in (list(schema.PDPA_KEYS)
                                    + list(schema.SALARY_KEYS))
                        if rec.get(k) and k not in _shown]
                if sens:
                    for k in sens:
                        fld = schema.BY_KEY.get(k)
                        lbl = (f"{fld.en} / {fld.th}" if fld else k)
                        a, b = st.columns([1, 2])
                        a.markdown(f"**{lbl}**")
                        b.write(rec.get(k))
                else:
                    st.caption("ไม่มีข้อมูลในกลุ่มนี้ / none recorded")
            else:
                st.info("ข้อมูล PDPA และเงินเดือนแสดงเฉพาะ Super Admin / "
                        "PDPA and salary details are visible to Super Admin "
                        "only.")

# ====================================================== interactive chart
html = pathlib.Path("assets/AMS-org-chart-v2.html").read_text(encoding="utf-8")
photos = json.dumps(edb.photos_as_data_uris(), ensure_ascii=False)
empmap = json.dumps(edb.orgchart_emp_map(), ensure_ascii=False)
html = html.replace("/*__PHOTOS_JSON__*/{}/*__END_PHOTOS_JSON__*/", photos)
html = html.replace("/*__EMPMAP_JSON__*/{}/*__END_EMPMAP_JSON__*/", empmap)
st.components.v1.html(html, height=860, scrolling=True)
st.caption("คลิกการ์ดเพื่อดูข้อมูลย่อ • ปุ่มในการ์ดจะคัดลอกรหัสไปวางในช่อง "
           "'เปิดโปรไฟล์พนักงาน' ด้านบน • ทีมใหญ่เรียงแนวตั้ง / Click a card "
           "for a preview; the card button copies the ID for the opener "
           "above; large teams stack vertically.")

# ====================================================== EXPORT PANEL
# One consolidated export panel. Pick a scope (report line / business unit /
# whole company), set the title-block fields, then either generate an image
# (PNG / JPG / PDF) or print/save-as-PDF an exact copy of the interactive chart.
import base64 as _b64
from lib import orgchart_export as _oce

st.divider()
st.subheader("📤 ส่งออกผังองค์กร / Export organisation chart")
st.caption(
    "เลือกสายบังคับบัญชาที่ต้องการ แล้วส่งออกเป็นรูป (PNG/JPG/PDF) หรือพิมพ์/"
    "บันทึกเป็น PDF ที่หน้าตาเหมือนผังด้านบนทุกประการ • Pick a report line and "
    "export it as an image, or print / save-as-PDF an exact copy of the chart "
    "above. Selecting a person includes their whole team (all levels) plus "
    "their one top manager — exactly like “Expand all”.")


def _photo_bytes(r):
    b = r.get("photo")
    if not b:
        return None
    return bytes(b) if not isinstance(b, (bytes, bytearray)) else bytes(b)


# _key-keyed photo maps (orgchart_export keys everything by cleaned lower name)
_photos_bytes = {_oce._key(r): _photo_bytes(r) for r in act if r.get("photo")}
_photos_uri = {
    _oce._key(r): "data:image/jpeg;base64," + _b64.b64encode(_photo_bytes(r)).decode()
    for r in act if r.get("photo")}

# ---- scope picker -------------------------------------------------------
_scope_label = st.radio(
    "ขอบเขต / Scope",
    ["📋 สายบังคับบัญชา / Report line",
     "🏢 หน่วยงาน / Business unit",
     "🌐 ทั้งบริษัท / Whole company"],
    horizontal=True, key="org_exp_scope")

scope = ("report_line" if _scope_label.startswith("📋")
         else "unit" if _scope_label.startswith("🏢") else "company")

focus_emp_no = None
include_manager = True
unit = None

if scope == "report_line":
    _emp_sorted = sorted(act, key=lambda r: (r.get("emp_name_en") or "").lower())
    _label_by_no = {}
    for r in _emp_sorted:
        nm = _oce.clean(r.get("emp_name_en"))
        nick = (r.get("nickname") or "").strip()
        ttl = (r.get("title") or "").strip()
        _label_by_no[r["emp_no"]] = (
            f"{r['emp_no']} • {nm}" + (f" ({nick})" if nick else "")
            + (f" — {ttl}" if ttl else ""))
    c1, c2 = st.columns([3, 2])
    focus_emp_no = c1.selectbox(
        "เลือกบุคคล (จะรวมลูกน้องทุกระดับ) / Pick a person "
        "(includes every level below them)",
        options=[r["emp_no"] for r in _emp_sorted],
        format_func=lambda no: _label_by_no.get(no, str(no)),
        key="org_exp_focus")
    include_manager = c2.checkbox(
        "รวมหัวหน้า 1 ระดับด้านบน / Include their one top manager",
        value=True, key="org_exp_incmgr")
elif scope == "unit":
    _units = sorted({(r.get("dept_location") or "—") for r in act})
    unit = st.selectbox("หน่วยงาน / Business unit", _units, key="org_exp_unit")

# ---- title-block fields -------------------------------------------------
b1, b2 = st.columns(2)
ver = b1.text_input("Version", value=f"Rev.{dt.date.today():%Y%m%d}",
                    key="org_exp_ver")
eff_date = b2.date_input("Effective date / วันที่มีผล", dt.date.today(),
                         key="org_exp_eff")
p1, p2 = st.columns(2)
proposed = p1.text_input("Proposed by / จัดทำโดย",
                         value="Chaiyanan Singson (HR Manager)",
                         key="org_exp_prop")
approved = p2.text_input("Approved by / อนุมัติโดย",
                         value="Nicholas Doyle (General Manager)",
                         key="org_exp_appr")


def _scope_kwargs():
    return dict(unit=unit, focus_emp_no=focus_emp_no,
                include_manager=include_manager)


def _fname_stub():
    if scope == "report_line":
        nm = _oce.clean(next((r.get("emp_name_en") for r in act
                              if r["emp_no"] == focus_emp_no), "person"))
        return "ReportLine_" + nm.replace(" ", "_")[:24]
    if scope == "unit":
        return "Unit_" + str(unit).replace("/", "-").replace(" ", "_")[:24]
    return "WholeCompany"


# ---- preview of what will be exported -----------------------------------
try:
    _plan_preview = _oce.people_for_scope(act, scope, **_scope_kwargs())
    _n = len(_plan_preview["members"])
    if scope == "report_line" and focus_emp_no:
        _focus_nm = _oce.clean(next((r.get("emp_name_en") for r in act
                               if r["emp_no"] == focus_emp_no), ""))
        _mgr_txt = (f" + หัวหน้า / manager: {_oce.clean(_plan_preview['ctx_key'].title())}"
                    if _plan_preview.get("ctx_key") and include_manager else "")
        st.info(f"จะส่งออก / Will export: **{_focus_nm}** และทีมทั้งหมด "
                f"({_n} คนรวมหัวหน้า / {_n} people incl. manager){_mgr_txt}")
    else:
        st.info(f"จะส่งออก / Will export: **{_plan_preview['title']}** "
                f"({_n} คน / {_n} people)")
except Exception as _e:  # pragma: no cover
    st.warning(f"ไม่สามารถสร้างผังได้ / cannot build plan: {_e}")

# ---- two actions --------------------------------------------------------
a1, a2 = st.columns(2)
_gen_img = a1.button("🖼️ สร้างรูป (PNG / JPG / PDF) / Generate image",
                     use_container_width=True, type="primary",
                     key="org_exp_genimg")
_gen_print = a2.button("🖨️ พิมพ์ / บันทึก PDF (เหมือนผังด้านบน) / "
                       "Print · Save-as-PDF (exact copy)",
                       use_container_width=True, key="org_exp_genprint")

if _gen_img:
    with st.spinner("กำลังวาดผัง / rendering chart…"):
        try:
            imgs = _oce.render_images(
                act, scope, photos_bytes=_photos_bytes, version=ver,
                fmts=("png", "jpg", "pdf"), **_scope_kwargs())
            if not imgs:
                st.session_state["_org_img"] = None
            else:
                st.session_state["_org_img"] = imgs
                st.session_state["_org_img_stub"] = _fname_stub()
                st.session_state["_org_img_ver"] = ver
        except Exception as _e:
            st.session_state["_org_img"] = None
            st.error(f"เกิดข้อผิดพลาด / error: {_e}")

_oi = st.session_state.get("_org_img")
if _oi:
    _stub = st.session_state.get("_org_img_stub", "OrgChart")
    _v = st.session_state.get("_org_img_ver", ver)
    st.image(_oi["png"], use_container_width=True,
             caption=f"ตัวอย่าง / Preview — {_stub} {_v}")
    d1, d2, d3 = st.columns(3)
    d1.download_button("⬇️ PNG", _oi["png"], use_container_width=True,
        file_name=f"AMS_OrgChart_{_stub}_{_v}.png", mime="image/png")
    d2.download_button("⬇️ JPG", _oi["jpg"], use_container_width=True,
        file_name=f"AMS_OrgChart_{_stub}_{_v}.jpg", mime="image/jpeg")
    d3.download_button("⬇️ PDF", _oi["pdf"], use_container_width=True,
        file_name=f"AMS_OrgChart_{_stub}_{_v}.pdf", mime="application/pdf")
elif _oi is None and "_org_img" in st.session_state:
    st.info("ไม่มีพนักงานในขอบเขตที่เลือก / no staff in the selected scope.")

if _gen_print:
    with st.spinner("กำลังสร้างไฟล์พิมพ์ / building printable file…"):
        try:
            doc = _oce.build_print_html(
                act, scope, photos=_photos_uri, version=ver,
                proposed=proposed, approved=approved, eff_date=eff_date,
                **_scope_kwargs())
            st.session_state["_org_print"] = doc
            st.session_state["_org_print_stub"] = _fname_stub()
            st.session_state["_org_print_ver"] = ver
        except Exception as _e:
            st.session_state["_org_print"] = None
            st.error(f"เกิดข้อผิดพลาด / error: {_e}")

_op = st.session_state.get("_org_print")
if _op:
    _pstub = st.session_state.get("_org_print_stub", "OrgChart")
    _pv = st.session_state.get("_org_print_ver", ver)
    st.download_button(
        "⬇️ เปิดไฟล์เพื่อพิมพ์ / บันทึก PDF — Open to print / Save-as-PDF",
        _op.encode("utf-8"), use_container_width=True, type="primary",
        file_name=f"AMS_OrgChart_{_pstub}_{_pv}.html", mime="text/html")
    st.caption("เปิดไฟล์แล้วหน้าต่างพิมพ์จะเด้งขึ้นเอง — เลือกเครื่องพิมพ์หรือ "
               "Save as PDF (แนะนำกระดาษ A3 แนวนอน) / The file opens straight "
               "into the print dialog — pick a printer or Save as PDF "
               "(A3 landscape recommended).")
