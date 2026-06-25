# pages/D_Employee_Data.py
# Requirement 3: Admin manages everything; ONLY Super Admin sees/edits the
# salary tier; template download; bulk upload; Internal + External (PDPA-safe)
# exports. Plus: candidate review/promotion, change-request approvals,
# original-format document printing, photos, and the full audit log.
import datetime as dt
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme

from lib.auth import require_capability, current_user, has_capability
from lib.employee_schema import (BY_KEY, GROUPS, FIELDS, SALARY_KEYS,
                                 RECORD_STATUSES)
from lib import employee_db as edb
from lib import employee_excel as exio
from lib import print_docs

_theme.inject()
require_capability("employee.access")

edb.migrate()
user = current_user()
me = user["username"]
CAN_SALARY_VIEW = has_capability("employee.view_salary")
CAN_SALARY_EDIT = has_capability("employee.edit_salary")

st.title("🗂️ Employee Data / ข้อมูลพนักงาน")

tabs = st.tabs(["📋 Employees", "🧑‍💼 Candidates", "✅ Approvals",
                "📤 Bulk & Exports", "🖨️ Print documents", "📸 Photos",
                "🧾 Audit log", "📋 Doc checklist"])


def _field_editor(rec, keys, prefix):
    out = {}
    cols = st.columns(2)
    for i, k in enumerate(keys):
        f = BY_KEY[k]
        label = f"{f.th} / {f.en}"
        cur = rec.get(k)
        with cols[i % 2]:
            if f.typ == "choice":
                opts = [""] + list(f.choices)
                out[k] = st.selectbox(label, opts,
                                      index=opts.index(cur) if cur in opts
                                      else 0, key=f"{prefix}_{k}")
            elif f.typ == "longtext":
                out[k] = st.text_area(label, value=cur or "",
                                      key=f"{prefix}_{k}", height=80)
            else:
                out[k] = st.text_input(label, value="" if cur is None
                                       else str(cur), key=f"{prefix}_{k}")
    return out


# ============================================================ 1. Employees
with tabs[0]:
    status = st.selectbox("Status / สถานะ", RECORD_STATUSES,
                          index=RECORD_STATUSES.index("active"))
    recs = edb.list_records(status)
    st.caption(f"{len(recs)} records")
    q = st.text_input("ค้นหา / Search (name, emp no, dept)")
    if q:
        ql = q.lower()
        recs = [r for r in recs if ql in " ".join(
            str(r.get(k) or "") for k in
            ("emp_no", "emp_name_en", "emp_name_th", "nickname",
             "dept_location", "title")).lower()]
    if recs:
        view_keys = ["emp_no", "emp_name_en", "nickname", "dept_location",
                     "title", "joined_date"]
        st.dataframe([{BY_KEY[k].en: r.get(k) for k in view_keys}
                      for r in recs], use_container_width=True)
        pick = st.selectbox(
            "เปิดดู/แก้ไข / Open record", [r["id"] for r in recs],
            format_func=lambda i: next(
                f"{r.get('emp_no') or '—'} • {r.get('emp_name_en')}"
                for r in recs if r["id"] == i))
        rec = edb.get_record(employee_id=pick)
        if has_capability("employee.edit"):
            groups = [g for g in GROUPS if g != "salary"]
            gsel = st.selectbox("หมวด / Section", groups,
                                format_func=lambda g: f"{GROUPS[g][1]} / "
                                                      f"{GROUPS[g][0]}")
            keys = [f.key for f in FIELDS if f.grp == gsel]
            with st.form(f"edit_{pick}_{gsel}"):
                vals = _field_editor(rec, keys, f"e{pick}")
                if st.form_submit_button("💾 Save", type="primary"):
                    diff = edb.update_record(
                        pick, {k: (v or None) for k, v in vals.items()}, me)
                    st.success(f"Saved — {len(diff)} field(s) changed "
                               f"(audited).")
                    st.rerun()
            # ---- salary tier: SUPER ADMIN ONLY -------------------------
            if CAN_SALARY_VIEW:
                st.divider()
                st.subheader("💰 Salary & remuneration (Super Admin)")
                if CAN_SALARY_EDIT:
                    with st.form(f"sal_{pick}"):
                        vals = _field_editor(rec, SALARY_KEYS, f"s{pick}")
                        if st.form_submit_button("💾 Save salary",
                                                 type="primary"):
                            edb.update_record(
                                pick, {k: (v or None)
                                       for k, v in vals.items()}, me)
                            st.success("Salary data saved (audited).")
                            st.rerun()
                else:
                    for k in SALARY_KEYS:
                        st.markdown(f"**{BY_KEY[k].en}:** "
                                    f"{rec.get(k) or '—'}")
            # status transitions
            st.divider()
            ns = st.selectbox("เปลี่ยนสถานะ / Change record status",
                              RECORD_STATUSES,
                              index=RECORD_STATUSES.index(
                                  rec["record_status"]))
            if ns != rec["record_status"] and st.button("Apply status"):
                edb.set_status(pick, ns, me)
                st.rerun()

# ============================================================ 2. Candidates
with tabs[1]:
    require = has_capability("employee.manage_candidates")
    if not require:
        st.info("Requires employee.manage_candidates")
    else:
        cands = edb.list_records("candidate")
        st.caption(f"{len(cands)} open applications")
        for c in cands:
            name = c.get("emp_name_en") or c.get("emp_name_th") or "?"
            with st.expander(f"{name} — {c.get('position_applied') or '—'} "
                             f"(applied {str(c.get('created_at'))[:10]})"):
                for g in ("personal", "apply", "health", "sso", "tax"):
                    keys = [k for k, f in BY_KEY.items() if f.grp == g and
                            c.get(k) not in (None, "")]
                    if keys:
                        st.markdown(f"**{GROUPS[g][0]}**")
                        for k in keys:
                            st.markdown(f"- {BY_KEY[k].en}: {c.get(k)}")
                st.divider()
                st.markdown("**โอนเข้าทะเบียนพนักงาน / Promote to employee "
                            "master** (Requirement 1)")
                with st.form(f"promo_{c['id']}"):
                    emp_no = st.text_input("Emp. No. *")
                    org = _field_editor(c, ["dept_location", "cost_centre",
                                            "title", "level", "mgr_name",
                                            "direct_indirect", "emp_type",
                                            "joined_date"], f"p{c['id']}")
                    ok = st.form_submit_button("✅ Promote", type="primary")
                    rej = st.form_submit_button("❌ Reject application")
                if ok:
                    if not emp_no.strip():
                        st.error("Emp. No. required")
                    else:
                        s = edb.promote_candidate(
                            c["id"], emp_no.strip(),
                            {k: (v or None) for k, v in org.items()}, me)
                        st.success(f"Promoted → record status '{s}'. All "
                                   f"application data transferred (audited).")
                        st.rerun()
                if rej:
                    edb.set_status(c["id"], "rejected", me)
                    st.rerun()

# ============================================================ 3. Approvals
with tabs[2]:
    if not has_capability("employee.approve_changes"):
        st.info("Requires employee.approve_changes")
    else:
        pend = edb.pending_change_requests()
        st.caption(f"{len(pend)} pending change request(s)")
        for r in pend:
            f = BY_KEY.get(r["field_key"])
            label = f.en if f else r["field_key"]
            st.markdown(
                f"**{r['e_emp_no']} • {r['e_name']}** — {label}: "
                f"`{r['old_value'] or '—'}` → `{r['new_value']}` "
                f"<span style='color:#888'>(by {r['requested_by']}, "
                f"{r['requested_at'][:16]})</span>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns([1, 1, 3])
            note = c3.text_input("Note", key=f"n{r['id']}",
                                 label_visibility="collapsed")
            if c1.button("✅ Approve", key=f"a{r['id']}"):
                edb.review_change_request(r["id"], True, me, note)
                st.rerun()
            if c2.button("❌ Reject", key=f"r{r['id']}"):
                edb.review_change_request(r["id"], False, me, note)
                st.rerun()

# ============================================================ 4. Bulk & exports
with tabs[3]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("⬇️ Template")
        inc_sal = CAN_SALARY_EDIT and st.checkbox(
            "Include salary columns (Super Admin template)")
        st.download_button(
            "Download upload template (.xlsx)",
            exio.build_template(include_salary=inc_sal),
            file_name="AMS_Employee_Upload_Template.xlsx")
        st.subheader("⬆️ Bulk upload")
        if has_capability("employee.bulk_upload"):
            up = st.file_uploader(
                "Filled template OR the original Employee List MASTER file",
                type=["xlsx"])
            if up:
                try:
                    rows, fmt, cmap = exio.parse_upload(
                        up.read(), allow_salary=CAN_SALARY_EDIT)
                    st.info(f"Detected **{fmt}** layout • {len(rows)} rows • "
                            f"{len(cmap)} mapped columns")
                    if st.button("Apply upload", type="primary"):
                        summary = exio.apply_upload(rows, me)
                        st.success(f"Created {summary['created']}, updated "
                                   f"{summary['updated']}, unchanged "
                                   f"{summary['unchanged']} (audited).")
                except Exception as e:
                    st.error(f"Upload failed: {e}")
        else:
            st.info("Requires employee.bulk_upload")
    with c2:
        st.subheader("📦 Exports")
        stat = st.selectbox("Records", RECORD_STATUSES,
                            index=RECORD_STATUSES.index("active"),
                            key="exp_stat")
        if has_capability("employee.export_internal"):
            sal = CAN_SALARY_VIEW and st.checkbox(
                "Include salary tier (Super Admin)")
            st.download_button(
                "Internal export (all HR fields)",
                exio.export_internal(stat, me, include_salary=sal),
                file_name=f"AMS_Employees_Internal_{dt.date.today()}.xlsx")
        if has_capability("employee.export_external"):
            st.download_button(
                "External export (PDPA-protected fields removed)",
                exio.export_external(stat, me),
                file_name=f"AMS_Employees_External_{dt.date.today()}.xlsx")
        st.caption("External export excludes every field flagged PDPA in "
                   "lib/employee_schema.py — ID card, birth date, addresses, "
                   "phones, emails, health, family, SSO, tax — and the whole "
                   "salary tier. Both exports are audit-logged.")

# ============================================================ 5. Print docs
with tabs[4]:
    import streamlit.components.v1 as _components
    from lib import doc_templates as dtpl

    st.caption("พิมพ์เอกสารที่กรอกแล้วในรูปแบบต้นฉบับ — ถ้าอัปโหลดแบบฟอร์ม"
               "จริง (template) ระบบจะพิมพ์ทับลงบนต้นฉบับตามตำแหน่ง / Print "
               "the filled result; with an uploaded template the data is "
               "laid ON the original form (ISO 14001).")
    everyone = edb.list_records()
    sel = st.selectbox(
        "Person", [r["id"] for r in everyone],
        format_func=lambda i: next(
            f"[{r['record_status']}] {r.get('emp_no') or '—'} • "
            f"{r.get('emp_name_en') or r.get('emp_name_th')}"
            for r in everyone if r["id"] == i))
    rec = edb.get_record(employee_id=sel) if sel is not None else None
    if not rec:
        st.info("ยังไม่มีพนักงานให้เลือกพิมพ์เอกสาร · no employee record "
                "selected to print yet.")
        st.stop()
    doc = st.radio("Document", [
        "ชุดใบสมัครรวม (FM-HR-003 + เอกสารแนบท้าย) — กรอกครั้งเดียว",
        "FM-HR-003 Application for Employment",
        "เอกสารแนบท้าย (Additional disclosures)",
        "สปส.1-03 แบบขึ้นทะเบียนผู้ประกันตน",
        "ล.ย.01 แบบแจ้งรายการเพื่อการหักลดหย่อน"], horizontal=False)

    _doc_key = ("fm_hr_003" if doc.startswith("FM") else
                "addendum" if doc.startswith("เอกสาร") else
                "sso103" if doc.startswith("สปส") else
                "ly01" if doc.startswith("ล.ย") else None)
    _is_set = doc.startswith("ชุดใบสมัคร")
    tpl = dtpl.active_template(_doc_key) if _doc_key else None

    # All four forms render the employee's data back onto the REAL originals
    # (faithful overlay/fill) — FM-HR-003 (AMS logo) and เอกสารแนบท้าย the same
    # way as สปส.1-03 / ล.ย.01. A custom uploaded template (doc_templates)
    # overrides a single form with the overlay-HTML path.
    faithful_pdf = None
    faithful_label = None
    if _is_set:
        # one application packet: FM-HR-003 (2 pp) + เอกสารแนบท้าย (2 pp)
        _p1 = print_docs.render_fmhr003_pdf(rec, show_salary=CAN_SALARY_VIEW)
        _p2 = print_docs.render_addendum_pdf(rec)
        if _p1 or _p2:
            try:
                from pypdf import PdfReader as _PR, PdfWriter as _PW
                import io as _io
                _wr = _PW()
                for _bb in (_p1, _p2):
                    if _bb:
                        for _pg in _PR(_io.BytesIO(_bb)).pages:
                            _wr.add_page(_pg)
                _ob = _io.BytesIO(); _wr.write(_ob)
                faithful_pdf = _ob.getvalue()
            except Exception:
                faithful_pdf = _p1 or _p2
        faithful_label = "ชุดใบสมัคร FM-HR-003 + เอกสารแนบท้าย"
    elif not tpl:
        if _doc_key == "ly01":
            faithful_pdf = print_docs.render_ly01_pdf(rec)
            faithful_label = "ล.ย.01"
        elif _doc_key == "sso103":
            faithful_pdf = print_docs.render_sso103_pdf(rec)
            faithful_label = "สปส.1-03"
        elif _doc_key == "fm_hr_003":
            faithful_pdf = print_docs.render_fmhr003_pdf(
                rec, show_salary=CAN_SALARY_VIEW)
            faithful_label = "FM-HR-003"
        elif _doc_key == "addendum":
            faithful_pdf = print_docs.render_addendum_pdf(rec)
            faithful_label = "เอกสารแนบท้าย"

    if faithful_pdf is not None:
        name = (rec.get("emp_no") or "candidate")
        _key = "application_set" if _is_set else _doc_key
        st.success(f"{faithful_label} — กรอกข้อมูลจากทะเบียนพนักงานลงบน "
                   "**ฟอร์มต้นฉบับ** ให้แล้ว (ช่องติ๊ก / ตาราง / ลายเซ็น "
                   "กรอกเพิ่มด้วยมือได้) · filled from the employee record onto "
                   "the original form.")
        c1, c2 = st.columns(2)
        c1.download_button(f"⬇️ ดาวน์โหลด {faithful_label} (PDF ต้นฉบับ)",
                           faithful_pdf, file_name=f"{name}_{_key}.pdf",
                           type="primary")
        try:
            import fitz as _fitz
            _d = _fitz.open(stream=faithful_pdf, filetype="pdf")
            with st.expander("Preview", expanded=True):
                for _i in range(_d.page_count):
                    _png = _d[_i].get_pixmap(
                        matrix=_fitz.Matrix(1.5, 1.5)).tobytes("png")
                    st.image(_png, use_container_width=True)
        except Exception:
            pass
    else:
        if doc.startswith("ชุดใบสมัคร"):
            # MERGED one-time-fill set: application + addendum in ONE print job
            h1 = print_docs.render_application(rec, show_salary=CAN_SALARY_VIEW)
            h2 = print_docs.render_addendum(rec)
            b2 = h2[h2.index("<body") + h2[h2.index("<body"):].index(">") + 1:
                    h2.index("</body>")]
            html = h1.replace("</body>",
                              '<div style="page-break-before:always"></div>'
                              + b2 + "</body>")
            fname = "Application_set"
        elif tpl:
            html = dtpl.render_overlay(rec, tpl)
            st.info(f"ใช้ template ต้นฉบับ v{tpl['version']} "
                    f"(มีผล {tpl['effective_date']}) — overlay-on-original ✅")
            fname = _doc_key
        else:
            if doc.startswith("FM"):
                html = print_docs.render_application(
                    rec, show_salary=CAN_SALARY_VIEW)
            elif doc.startswith("เอกสาร"):
                html = print_docs.render_addendum(rec)
            elif doc.startswith("สปส"):
                html = print_docs.render_sso103(rec)
            else:
                html = print_docs.render_ly01(rec)
            fname = _doc_key or "doc"

        c1, c2, c3 = st.columns(3)
        if c1.button("🖨️ พิมพ์ทันที / Print now", type="primary"):
            _components.html(
                f"<script>var w=window.open('','_blank');"
                f"w.document.write({html!r});w.document.close();</script>",
                height=0)
        pdf = print_docs.html_to_pdf(html)
        name = (rec.get("emp_no") or "candidate")
        if pdf:
            c2.download_button("⬇️ PDF", pdf, file_name=f"{name}_{fname}.pdf")
        c3.download_button("⬇️ HTML", html, file_name=f"{name}_{fname}.html")
        with st.expander("Preview"):
            st.components.v1.html(html, height=760, scrolling=True)

    conn = edb.get_conn()
    edb._audit(conn, me, "print_document", rec["id"], rec.get("emp_no"),
               {"doc": doc, "overlay": bool(tpl),
                "faithful": faithful_pdf is not None})
    conn.commit()

    # -------- template versioning admin (overlay-on-original) --------
    with st.expander("⚙️ Template ต้นฉบับ & เวอร์ชัน / Original-form "
                     "templates (admin)"):
        st.caption("อัปโหลดสแกนฟอร์มจริง (PNG/JPG ต่อหน้า) + แผนที่ตำแหน่ง"
                   "ฟิลด์ → ระบบพิมพ์ข้อมูลทับบนต้นฉบับ • เมื่อมาตรฐานแก้ไข "
                   "อัปโหลดเวอร์ชันใหม่ได้เลย ไม่ต้องแก้โค้ด เวอร์ชันเก่าเก็บ"
                   "ไว้ครบ / Upload the real form scans + field-position map; "
                   "new standard = new version, no code edit.")
        for t in dtpl.list_templates():
            st.write(f"- **{t['doc_key']}** v{t['version']} "
                     f"(มีผล {t['effective_date']}) "
                     f"{'🟢 active' if t['active'] else '⚪'} • "
                     f"โดย {t['created_by']}")
        with st.form("tpl_form"):
            c1, c2, c3 = st.columns(3)
            dk = c1.selectbox("เอกสาร / Document",
                              list(dtpl.DOC_KEYS),
                              format_func=lambda k: dtpl.DOC_KEYS[k])
            ver = c2.text_input("Version", value="Rev.01")
            eff = c3.date_input("Effective date")
            imgs = st.file_uploader("หน้าเอกสารต้นฉบับ (เรียงหน้า) / Page "
                                    "scans in order", type=["png", "jpg",
                                    "jpeg"], accept_multiple_files=True)
            fmap = st.text_area(
                "Field map (JSON — x/y/w เป็น % ของหน้า; key = ฟิลด์พนักงาน"
                " หรือ th_day/th_month/th_year, today_th, id_d1..id_d13)",
                value=dtpl.DEFAULT_FIELD_MAP_EXAMPLE, height=180)
            act = st.checkbox("ตั้งเป็นเวอร์ชันใช้งาน / Activate", True)
            if st.form_submit_button("💾 Save template") and imgs:
                pages = [(f.read(), f.type) for f in imgs]
                tid, err = dtpl.save_template(dk, ver, eff, fmap, pages, me,
                                              act)
                (st.error if err else st.success)(err or
                                                  f"บันทึก v{ver} แล้ว")
                if not err:
                    st.rerun()
        if tpl and st.button("📐 เปิดตัวช่วยวัดตำแหน่ง (grid 5%) / "
                             "Calibration preview"):
            cal = dtpl.render_overlay(rec, tpl, calibrate=True)
            _components.html(
                f"<script>var w=window.open('','_blank');"
                f"w.document.write({cal!r});w.document.close();</script>",
                height=0)

# ============================================================ 6. Photos
with tabs[5]:
    st.caption("รูปจะถูกย่อเป็น 200×200 JPEG (≤100 KB) อัตโนมัติ และแสดงใน "
               "Org Chart / Photos auto-resize to 200×200 JPEG and feed the "
               "org chart avatars.")
    act = edb.list_records("active")

    t_one, t_bulk = st.tabs(["👤 ทีละคน / One person",
                             "📦 อัปโหลดจำนวนมาก / Bulk upload"])

    # ---- single upload with SEARCH ----
    with t_one:
        pq = st.text_input("ค้นหา (รหัส / ชื่อ / นามสกุล / ชื่อเล่น) / Search "
                           "by ID, name, surname, nickname", key="photo_q")
        if pq.strip():
            ql = pq.strip().lower()
            matches = [r for r in act if ql in str(r.get("emp_no", "")).lower()
                       or ql in str(r.get("emp_name_en", "")).lower()
                       or ql in str(r.get("emp_name_th", "")).lower()
                       or ql in str(r.get("nickname", "")).lower()]
        else:
            matches = act
        st.caption(f"{len(matches)} คนที่ตรงกับการค้นหา / matches")
        if matches:
            psel = st.selectbox(
                "เลือกพนักงาน / Pick employee", [r["id"] for r in matches],
                format_func=lambda i: next(
                    f"{r['emp_no']} • {r.get('emp_name_en')} "
                    f"({r.get('nickname') or '-'})"
                    for r in matches if r["id"] == i), key="photo_sel")
            prec = edb.get_record(employee_id=psel)
            c1, c2 = st.columns([1, 3])
            if prec.get("photo"):
                c1.image(bytes(prec["photo"]), width=120,
                         caption="รูปปัจจุบัน / Current")
            img = c2.file_uploader("JPG/PNG/WebP ≤5 MB",
                                   type=["jpg", "jpeg", "png", "webp"],
                                   key="photo_one")
            if img and c2.button("💾 Save photo", type="primary"):
                edb.save_photo(psel, img.read(), me)
                st.success("Saved (audited).")
                st.rerun()

    # ---- BULK upload: filenames = emp_no ----
    with t_bulk:
        st.markdown(
            "ตั้งชื่อไฟล์รูปเป็น **รหัสพนักงาน** เช่น `1021656.jpg` แล้วลากมา"
            "พร้อมกันหลายไฟล์ หรือรวมเป็น **ZIP** เดียว — ตรงกับวิธีที่เก็บรูป"
            "ในไดรฟ์อยู่แล้ว / Name each file by **Emp. No.** (e.g. "
            "`1021656.jpg`), then drop many files at once or one **ZIP**. "
            "Matching is by filename → Emp. No.")
        ups = st.file_uploader(
            "หลายไฟล์ JPG/PNG/WebP หรือ ZIP / Many image files or a ZIP",
            type=["jpg", "jpeg", "png", "webp", "zip"],
            accept_multiple_files=True, key="photo_bulk")
        if ups and st.button("🚀 Bulk import photos", type="primary"):
            import io as _io, zipfile, os as _os
            by_no = {str(r.get("emp_no") or "").strip(): r for r in act}
            items = []   # (filename, bytes)
            for up in ups:
                if up.name.lower().endswith(".zip"):
                    try:
                        zf = zipfile.ZipFile(_io.BytesIO(up.read()))
                        for n in zf.namelist():
                            if n.lower().endswith((".jpg", ".jpeg", ".png",
                                                   ".webp")) \
                                    and not n.startswith("__MACOSX"):
                                items.append((_os.path.basename(n),
                                              zf.read(n)))
                    except Exception as e:
                        st.error(f"ZIP {up.name}: {e}")
                else:
                    items.append((up.name, up.read()))
            ok, fail = [], []
            prog = st.progress(0.0)
            for i, (fn, data) in enumerate(items):
                stem = _os.path.splitext(fn)[0].strip()
                rec = by_no.get(stem)
                if not rec:
                    fail.append((fn, "ไม่พบรหัสนี้ / Emp. No. not found"))
                else:
                    try:
                        edb.save_photo(rec["id"], data, me)
                        ok.append((fn, rec.get("emp_name_en")))
                    except Exception as e:
                        fail.append((fn, str(e)[:60]))
                prog.progress((i + 1) / max(len(items), 1))
            st.success(f"สำเร็จ {len(ok)} รูป / imported")
            if ok:
                with st.expander(f"✅ Imported ({len(ok)})"):
                    for fn, nm in ok:
                        st.write(f"- {fn} → {nm}")
            if fail:
                st.error(f"ไม่สำเร็จ {len(fail)} ไฟล์ / failed")
                for fn, why in fail:
                    st.write(f"- {fn}: {why}")

# ============================================================ 7. Audit log
with tabs[6]:
    if not has_capability("system.view_audit"):
        st.info("Requires system.view_audit")
    else:
        rows = edb.audit_log(limit=300)
        st.caption("ใคร-ทำอะไร-เมื่อไร ทุกการเปลี่ยนแปลง / who-what-when "
                   "for every change (Requirement 4)")
        st.dataframe(
            [{"When": r["at"], "Who": r["actor"], "Action": r["action"],
              "Emp No": r["emp_no"], "Detail": (r["detail"] or "")[:160]}
             for r in (dict(x) for x in rows)], use_container_width=True)


# ============================================================ 8. Doc checklist
with tabs[7]:
    from lib.auth import has_capability as _hc
    from lib import doc_templates as dtpl2
    if not _hc("docs.completion_checklist"):
        st.info("Requires docs.completion_checklist (admin)")
    else:
        st.caption("ความครบถ้วนของข้อมูล/เอกสารพนักงานรายคน — สำหรับแฟ้ม"
                   "เอกสารกระดาษตาม ISO 14001 / Per-employee document-data "
                   "completeness for the ISO 14001 paper records.")
        rows = dtpl2.checklist()
        if rows:
            full = sum(1 for r in rows if r["pct"] == 100)
            c1, c2, c3 = st.columns(3)
            c1.metric("พนักงานทั้งหมด", len(rows))
            c2.metric("ครบ 100%", full)
            c3.metric("เฉลี่ยความครบถ้วน",
                      f"{sum(r['pct'] for r in rows)/len(rows):.0f}%")
            st.bar_chart({"100%": full,
                          "80-99%": sum(1 for r in rows
                                        if 80 <= r["pct"] < 100),
                          "50-79%": sum(1 for r in rows
                                        if 50 <= r["pct"] < 80),
                          "<50%": sum(1 for r in rows if r["pct"] < 50)},
                         horizontal=True)
            st.dataframe([{"Emp": r["Emp"], "Name": r["Name"],
                           "Dept": r["Dept"], "% complete": r["pct"]}
                          for r in rows], use_container_width=True,
                         height=380)
            st.download_button("⬇️ ดาวน์โหลดเช็คลิสต์ Excel",
                               dtpl2.checklist_xlsx(rows),
                               file_name="Doc_completeness_checklist.xlsx")
            st.markdown("**🔍 รายการที่ขาด / Missing-item drill-down**")
            opts = {f"{r['Emp']} • {r['Name']} ({r['pct']}%)": r
                    for r in rows if r["missing"]}
            if opts:
                pick = st.selectbox("เลือกพนักงาน", list(opts))
                for grp, miss in opts[pick]["missing"].items():
                    st.write(f"**{grp}**: " + ", ".join(miss))
            else:
                st.success("ทุกคนครบ 100% 🎉")
