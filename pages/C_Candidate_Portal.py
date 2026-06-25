# pages/C_Candidate_Portal.py
# Candidate self-service application = the full FM-HR-003 data set
# (+ เอกสารแนบท้าย / สปส.1-03 / ล.ย.01 fields). Single fields render from the
# schema; the four FM-HR-003 tables (employment, education, other
# qualifications, talent language) are captured as STRUCTURED rows and stored
# as JSON so the printed form can fill the real table cells.
import json
import uuid
import pandas as pd
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme

from lib.auth import require_capability
from lib.employee_schema import (FIELDS, GROUPS, BY_KEY, CANDIDATE_KEYS)
from lib import employee_db as edb

_theme.inject()
require_capability("candidate.apply")
edb.migrate()

st.title("📝 ใบสมัครงาน / Job Application — ANCA (AMS) Thailand")
st.caption("กรอกข้อมูลได้ทั้งภาษาไทยและอังกฤษ • Fields are shown in Thai and "
           "English. ข้อมูลของท่านได้รับความคุ้มครองตาม PDPA พ.ศ. 2562")

tok = st.text_input("มีรหัสผู้สมัครแล้ว? ใส่เพื่อแก้ไขใบสมัครเดิม / "
                    "Returning applicant token", value="")
rec = edb.get_record(token=tok.strip()) if tok.strip() else None
if tok.strip() and not rec:
    st.warning("ไม่พบใบสมัครจากรหัสนี้ / Token not found")
if rec and rec["record_status"] != "candidate":
    st.info("ใบสมัครนี้ถูกโอนเข้าระบบพนักงานแล้ว แก้ไขผ่านหน้า My Profile / "
            "This application was already transferred to the employee master.")
    st.stop()

# ---- the four FM-HR-003 tables (kept out of the generic field loop) ----
TABLE_KEYS = {"prev_employment", "education_history", "other_qualifications",
              "languages"}
EMP_COLS = ["ปีจาก/From", "ปีถึง/To", "บริษัท/Company", "ธุรกิจ/Business",
            "ตำแหน่ง/Position", "เงินเดือน/Salary", "เหตุที่ออก/Reason"]
EDU_COLS = ["ระดับ/Level", "ปีจบ/Year", "สถานศึกษา/Institute",
            "คณะ-สาขา/Faculty", "เกรด/GPA"]
QUAL_COLS = ["ประเภท/Type", "สถาบัน/Institute", "ปี/Year"]
LANG_SKILLS = ["พูด/Speaking", "เขียน/Writing", "อ่าน/Reading", "ฟัง/Listening"]


def _rows(val, cols, n=0):
    """Parse stored JSON rows -> DataFrame with the given columns."""
    data = []
    if val:
        try:
            data = json.loads(val)
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []
    df = pd.DataFrame(data)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df = df[cols] if len(df) else pd.DataFrame(columns=cols)
    while len(df) < n:
        df.loc[len(df)] = {c: "" for c in cols}
    return df


def _lang_seed(val):
    base = {r["ภาษา/Language"]: r for r in (json.loads(val) if val else [])} \
        if val else {}
    rows = []
    for name in ["ไทย/Thai", "อังกฤษ/English", "อื่นๆ/Other"]:
        r = {"ภาษา/Language": name}
        src = base.get(name, {})
        for s in LANG_SKILLS:
            r[s] = src.get(s, "")
        rows.append(r)
    return pd.DataFrame(rows)


GROUP_ORDER = ["personal", "address", "emergency", "apply", "health",
               "sso", "tax"]

with st.form("candidate_form"):
    values = {}
    for g in GROUP_ORDER:
        gkeys = [k for k in CANDIDATE_KEYS
                 if BY_KEY[k].grp == g and k not in TABLE_KEYS]
        if not gkeys and g != "apply":
            continue
        en, th = GROUPS[g]
        st.subheader(f"{th} / {en}")
        cols = st.columns(2)
        for i, k in enumerate(gkeys):
            f = BY_KEY[k]
            cur = (rec or {}).get(k)
            label = f"{f.th} / {f.en}"
            with cols[i % 2]:
                if f.typ == "choice":
                    opts = [""] + list(f.choices)
                    values[k] = st.selectbox(
                        label, opts,
                        index=opts.index(cur) if cur in opts else 0, key=k)
                elif f.typ == "date":
                    values[k] = st.text_input(label, value=cur or "",
                                              placeholder="YYYY-MM-DD", key=k)
                elif f.typ == "longtext":
                    values[k] = st.text_area(label, value=cur or "", key=k,
                                             height=90)
                elif f.typ in ("int", "float"):
                    values[k] = st.text_input(label, value=str(cur or ""),
                                              key=k)
                else:
                    values[k] = st.text_input(label, value=cur or "", key=k)

        # the FM-HR-003 tables live inside the "apply" section
        if g == "apply":
            st.markdown("**ประวัติการทำงาน (เรียงจากล่าสุด) / Previous Employment**")
            emp_df = st.data_editor(
                _rows((rec or {}).get("prev_employment"), EMP_COLS, 1),
                num_rows="dynamic", use_container_width=True,
                key="emp_tbl", hide_index=True)
            st.markdown("**ประวัติการศึกษา / Education**")
            edu_df = st.data_editor(
                _rows((rec or {}).get("education_history"), EDU_COLS, 1),
                num_rows="dynamic", use_container_width=True,
                key="edu_tbl", hide_index=True)
            st.markdown("**คุณสมบัติอื่นๆ / Other Qualifications**")
            qual_df = st.data_editor(
                _rows((rec or {}).get("other_qualifications"), QUAL_COLS, 1),
                num_rows="dynamic", use_container_width=True,
                key="qual_tbl", hide_index=True)
            st.markdown("**ความสามารถพิเศษด้านภาษา / Talent Language** "
                        "(Good / Fair / Poor)")
            lang_df = st.data_editor(
                _lang_seed((rec or {}).get("languages")),
                use_container_width=True, key="lang_tbl", hide_index=True,
                disabled=["ภาษา/Language"],
                column_config={s: st.column_config.SelectboxColumn(
                    s, options=["", "Good", "Fair", "Poor"]) for s in LANG_SKILLS})

    st.divider()
    consent = st.checkbox(
        "ข้าพเจ้ายินยอมให้บริษัทรวบรวม จัดเก็บ และประมวลผลข้อมูลส่วนบุคคล "
        "เพื่อการสมัครงานและบริหารการจ้างงาน ตาม พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล "
        "พ.ศ. 2562 / I consent to the collection and processing of my "
        "personal data for recruitment and employment purposes under the "
        "PDPA B.E. 2562.", value=bool(rec and rec.get("pdpa_consent_at")))
    certify = st.checkbox(
        "ข้าพเจ้าขอรับรองว่าข้อความทั้งหมดเป็นความจริงทุกประการ หากปรากฏ"
        "ภายหลังว่าปกปิดข้อเท็จจริงหรือแจ้งข้อความอันเป็นเท็จ ข้าพเจ้า"
        "ยินยอมให้บริษัทฯ เลิกจ้างได้ทันทีโดยไม่จ่ายค่าชดเชย ตาม พ.ร.บ."
        "คุ้มครองแรงงาน พ.ศ. 2541 มาตรา 119(1) / I certify all "
        "statements are true, complete and correct (FM-HR-003).")
    submitted = st.form_submit_button("ส่งใบสมัคร / Submit application",
                                      type="primary")

if submitted:
    def _pack(df):
        rows = [r for r in df.to_dict("records")
                if any(str(v).strip() for v in r.values())]
        return json.dumps(rows, ensure_ascii=False) if rows else None
    values["prev_employment"] = _pack(emp_df)
    values["education_history"] = _pack(edu_df)
    values["other_qualifications"] = _pack(qual_df)
    lang_rows = [r for r in lang_df.to_dict("records")
                 if any(str(r.get(s, "")).strip() for s in LANG_SKILLS)]
    values["languages"] = json.dumps(lang_rows, ensure_ascii=False) \
        if lang_rows else None

    if not consent or not certify:
        st.error("ต้องยินยอม PDPA และรับรองความถูกต้องก่อนส่ง / Both consent "
                 "and certification are required.")
    elif not (values.get("emp_name_th") or values.get("emp_name_en")):
        st.error("กรุณากรอกชื่อ-สกุล / Please fill in your name.")
    else:
        clean = {k: (v if v not in ("", None) else None)
                 for k, v in values.items()}
        if rec:
            edb.update_record(rec["id"], clean,
                              actor=f"candidate:{tok.strip()[:8]}")
            st.success("อัปเดตใบสมัครเรียบร้อย / Application updated.")
        else:
            new_tok = uuid.uuid4().hex[:12]
            edb.create_record(clean, actor="candidate:new",
                              record_status="candidate",
                              pdpa_consent=True, token=new_tok)
            st.success("ส่งใบสมัครเรียบร้อย / Application submitted.")
            st.info(f"รหัสผู้สมัครของท่าน (เก็บไว้เพื่อกลับมาแก้ไข) / "
                    f"Your return token: **{new_tok}**")
