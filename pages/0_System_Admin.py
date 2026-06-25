# pages/0_System_Admin.py
# Users & roles + the emp_no/email link that powers My Profile, the 3-level
# approval chain, and email notifications.
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme
from lib.auth import (require_capability, list_users, create_user,
                      set_user_emp_no, set_user_email,
                      set_user_line_id, ROLES, has_capability,
                      list_signup_requests, approve_signup, reject_signup,
                      get_login_audit)
from lib import employee_db as edb
from lib.auth import current_user

_theme.inject()
require_capability("system.users")

st.title("⚙️ System Admin / ตั้งค่าระบบ")

t1, t2, t3, t4, t5, t6 = st.tabs(["👥 Users", "📖 Capabilities reference",
                                  "📢 ประกาศ · Announcements",
                                  "📤 ข้อมูล & อัปโหลด · Data & Uploads",
                                  "📝 คำขอสมัคร · Signup",
                                  "🛡️ บันทึกเข้าระบบ · Login audit"])
with t1:
    st.subheader("สร้างผู้ใช้ / Create user")
    with st.form("new_user"):
        c1, c2 = st.columns(2)
        un = c1.text_input("Username")
        pw = c2.text_input("Password", type="password")
        c3, c4, c5 = st.columns(3)
        role = c3.selectbox("Role", ROLES, index=1)
        emp = c4.text_input("Emp. No. (link to employee master)")
        em = c5.text_input("Email (for notifications)")
        if st.form_submit_button("Create", type="primary"):
            try:
                create_user(un.strip(), pw, role, emp.strip() or None,
                            em.strip() or None)
                st.success(f"Created {un} ({role})")
            except Exception as e:
                st.error(f"Failed: {e}")
    st.subheader("ผู้ใช้ทั้งหมด / All users")
    users = list_users()
    st.dataframe(users, use_container_width=True)
    st.subheader("ผูกบัญชีกับพนักงาน / Link account ↔ employee")
    c1, c2, c3, c4 = st.columns(4)
    sel = c1.selectbox("User", [u["username"] for u in users])
    emp2 = c2.text_input("Emp. No.", key="link_emp")
    em2 = c3.text_input("Email", key="link_email")
    li2 = c4.text_input("LINE userId (U…)", key="link_line",
                        help="สำหรับแจ้งเตือนอนุมัติทาง LINE @529aaynp — "
                             "ดู userId จาก LINE Official Account Manager "
                             "หรือ webhook log")
    if st.button("💾 Save link"):
        if emp2.strip():
            if not edb.get_record(emp_no=emp2.strip()):
                st.warning(f"emp_no {emp2} not found in employee master — "
                           f"saved anyway, but check it.")
            set_user_emp_no(sel, emp2.strip())
        if em2.strip():
            set_user_email(sel, em2.strip())
        if li2.strip():
            set_user_line_id(sel, li2.strip())
        st.success("Saved.")
with t2:
    from lib.rbac_seed import CAPS, MATRIX
    st.caption("เมทริกซ์สิทธิ์เริ่มต้น (แก้ในฐานข้อมูล role_capabilities) / "
               "Default matrix; edit role_capabilities to customise.")
    for role, caps in MATRIX.items():
        with st.expander(role):
            st.write(sorted(caps) if caps else "ALL capabilities")


# ====================================================== ANNOUNCEMENTS (admin)
with t3:
    from lib import announce_db
    from lib import auth as _auth
    st.subheader("📢 ประกาศ / ป็อปอัพ · Announcements & pop-ups")
    st.caption("ตั้งค่าป็อปอัพแจ้งพนักงาน เช่น กฎระเบียบ หรือ Consent — เลือกสื่อ ช่วงเวลา "
               "และบังคับให้กดยอมรับได้ / Configure pop-ups (rules, consent): media, "
               "date window, and force-accept.")
    st.markdown("##### ➕ สร้างประกาศใหม่ · New announcement")
    c1, c2 = st.columns([3, 2])
    title = c1.text_input("หัวข้อ · Title", key="ann_title")
    mode = c2.selectbox("ความถี่ในการแสดง · Frequency",
        ["once", "until_accept", "always"],
        format_func=lambda m: {
            "once": "ครั้งเดียว/ครั้งแรกเท่านั้น · once (first time only)",
            "until_accept": "จนกว่าจะกดยอมรับ · until accepted",
            "always": "ทุกครั้งที่เข้าระบบ · every visit"}[m], key="ann_mode")
    body = st.text_area("เนื้อหา / ข้อความขอความยินยอม · Body / consent text",
                        height=120, key="ann_body")

    st.markdown("**สื่อประกอบ · Media**")
    msrc = st.radio("แหล่งสื่อ · Media source",
        ["ไม่มี · none", "อัปโหลด · upload", "ลิงก์ · link (YouTube/URL)"],
        horizontal=True, key="ann_msrc")
    media_type, media_url, media_data, media_mime = "none", None, None, None
    if msrc.startswith("อัปโหลด"):
        st.caption("📐 คำแนะนำ: รูปแนวนอน ~1600×900 px (16:9), ไฟล์ ≤ 5 MB · "
                   "วิดีโอ .mp4 ≤ 25 MB (วิดีโอยาวแนะนำใช้ลิงก์ YouTube) · "
                   "Recommended image ~1600×900 (16:9) ≤5 MB; video .mp4 ≤25 MB "
                   "(use a YouTube link for long videos). รูปจะถูกย่อให้พอดีอัตโนมัติ.")
        up = st.file_uploader("เลือกไฟล์ รูป/วิดีโอ/PDF · image / video / pdf",
            type=["png", "jpg", "jpeg", "webp", "gif", "mp4", "webm", "pdf"],
            key="ann_up")
        if up is not None:
            import base64 as _b64
            raw = up.read(); ext = up.name.lower().rsplit(".", 1)[-1]
            if ext in ("png", "jpg", "jpeg", "webp", "gif"):
                media_type = "image"
                try:
                    from PIL import Image
                    import io as _io
                    im = Image.open(_io.BytesIO(raw)); im.thumbnail((1600, 1600))
                    is_png = ext in ("png", "webp", "gif")
                    if im.mode in ("RGBA", "P") and not is_png:
                        im = im.convert("RGB")
                    ob = _io.BytesIO(); fmt = "PNG" if is_png else "JPEG"
                    im.save(ob, fmt, optimize=True); raw = ob.getvalue()
                    media_mime = "image/png" if is_png else "image/jpeg"
                except Exception:
                    media_mime = "image/jpeg" if ext in ("jpg", "jpeg") \
                        else f"image/{ext}"
                st.image(raw, caption="ตัวอย่าง · preview",
                         use_container_width=True)
            elif ext in ("mp4", "webm"):
                media_type, media_mime = "video", f"video/{ext}"
                if len(raw) > 25 * 1024 * 1024:
                    st.warning("ไฟล์ใหญ่เกิน 25 MB — แนะนำใช้ลิงก์ YouTube แทน · "
                               "over 25 MB; use a YouTube link instead.")
                else:
                    st.video(raw)
            elif ext == "pdf":
                media_type, media_mime = "pdf", "application/pdf"
                st.caption(f"📄 แนบ PDF · {up.name} ({len(raw)//1024} KB)")
            media_data = _b64.b64encode(raw).decode()
    elif msrc.startswith("ลิงก์"):
        media_url = st.text_input("ลิงก์สื่อ · Media URL",
            placeholder="https://… (image / mp4 / YouTube / pdf)", key="ann_url")
        media_type = st.selectbox("ชนิดสื่อ · media type",
                                  ["image", "video", "pdf"], key="ann_urltype")
        if not media_url:
            media_type = "none"

    media_fit = st.selectbox("ปรับสื่อให้พอดีหน้าจอ (เดสก์ท็อป/มือถือ) · Fit media",
        ["width", "contain", "original"],
        format_func=lambda f: {
            "width": "เต็มความกว้าง responsive · fit screen width",
            "contain": "พอดีกรอบ ไม่ล้นจอ · contain (no overflow)",
            "original": "ขนาดจริง · original size"}[f], key="ann_fit")

    st.markdown("**ความยินยอม · Consent**")
    req = st.checkbox("บังคับให้กดยอมรับก่อนใช้งาน · Require the user to accept",
                      key="ann_req")
    consent_text = st.text_area(
        "ช่องติ๊กยินยอม — 1 บรรทัด = 1 ช่อง · Consent tick-boxes (one per line)",
        value="ข้าพเจ้าได้อ่านและยอมรับเงื่อนไข · I have read and accept",
        height=90, key="ann_consent", disabled=not req,
        help="ผู้ใช้ต้องติ๊กครบทุกช่องจึงจะกดยอมรับได้ · the user must tick "
             "every box before they can accept.")
    cd = st.columns(2)
    sd = cd[0].date_input("เริ่ม · Start", value=None, key="ann_sd")
    ed = cd[1].date_input("สิ้นสุด · End", value=None, key="ann_ed")
    if st.button("➕ สร้างประกาศ · Create announcement", type="primary",
                 key="ann_create"):
        if not title.strip():
            st.error("กรอกหัวข้อก่อน · title required")
        else:
            u = _auth.current_user() or {}
            items = ([ln.strip() for ln in consent_text.splitlines() if ln.strip()]
                     if req else [])
            announce_db.create(title.strip(), body, media_type,
                               (media_url or None), media_data, media_mime,
                               media_fit, mode, req, items, sd, ed,
                               u.get("username", "admin"))
            st.success("สร้างประกาศแล้ว · created"); st.rerun()
    st.divider()
    st.markdown("**ประกาศทั้งหมด · All announcements**")
    anns = announce_db.list_all()
    if not anns:
        st.caption("— ยังไม่มีประกาศ · none yet —")
    for a in anns:
        with st.container(border=True):
            st.markdown(
                f"**{a['title']}** · `{a['mode']}`"
                f"{' · 🔒 require-accept' if a['require_accept'] else ''} · "
                f"{'✅ active' if a['active'] else '⏸️ off'}  \n"
                f"{a['start_date'] or '—'} → {a['end_date'] or '—'} · "
                f"media: {a['media_type']}")
            cc1, cc2 = st.columns(2)
            if cc1.button(("⏸️ ปิด" if a["active"] else "▶️ เปิด") + " · toggle",
                          key=f"annt{a['id']}"):
                announce_db.set_active(a["id"], not a["active"]); st.rerun()
            if cc2.button("🗑️ ลบ · delete", key=f"annd{a['id']}"):
                announce_db.delete(a["id"]); st.rerun()

    st.divider()
    with st.expander("🧾 ประวัติการยอมรับเงื่อนไข · Consent / acknowledgement log "
                     "(ใครยอมรับ เมื่อไร)"):
        acks = announce_db.list_acks()
        if not acks:
            st.caption("— ยังไม่มีบันทึกการยอมรับ · no acknowledgements yet —")
        else:
            import pandas as _pd
            _df = _pd.DataFrame([{
                "ผู้ใช้ · User": a["username"],
                "ประกาศ · Announcement": a["title"],
                "สถานะ · Status": ("✅ ยอมรับ accepted" if a["accepted"]
                                   else "👁️ รับทราบ seen"),
                "เวลา · Timestamp": a["acked_at"]} for a in acks])
            st.dataframe(_df, use_container_width=True, hide_index=True)
            import io as _io
            from openpyxl import Workbook as _WB
            _wb = _WB(); _ws = _wb.active; _ws.append(list(_df.columns))
            for _, _r in _df.iterrows():
                _ws.append(list(_r.values))
            _b = _io.BytesIO(); _wb.save(_b)
            st.download_button("⬇️ ส่งออก Excel · export consent log",
                               _b.getvalue(), file_name="consent_log.xlsx")


# ============================================ Data & Uploads (central console)
with t4:
    import pandas as _pd
    from lib import employee_excel as _exio, timesheet_db as _ts, \
        upload_log as _ulog, attendance_db as _att
    _u = current_user()
    _actor = _u["username"] if _u else "admin"
    st.subheader("📤 ศูนย์รวมการอัปโหลดข้อมูล · Central data uploads")
    st.caption("รวมทุกการอัปโหลดไว้ที่เดียว เพื่อให้ดูแลข้อมูลง่าย · all data "
               "uploads in one place. Every import is recorded in the history "
               "log below so you can audit and correct mistakes.")

    cm, ct = st.columns(2)
    with cm:
        st.markdown("##### 👥 ทะเบียนพนักงาน · Employee master (.xlsx)")
        mf = st.file_uploader("master .xlsx", type=["xlsx"], key="adm_master",
                              label_visibility="collapsed")
        if mf is not None and st.button("📥 นำเข้า master · Import",
                                        key="adm_master_btn"):
            try:
                rows, _, _ = _exio.parse_upload(mf.read())
                _exio.apply_upload(rows, _actor)
                _ulog.log("Employee master", mf.name, "", len(rows), _actor,
                          "master import")
                st.success(f"นำเข้าแล้ว · imported {len(rows)} records")
                st.rerun()
            except Exception as e:
                st.error(f"ไม่สำเร็จ · failed: {e}")
    with ct:
        st.markdown("##### ⏱️ บันทึกเวลา face-scan · Timesheet (.xls)")
        st.caption("รายงานผลการคำนวณบันทึกเวลาแสดงตามพนักงาน — ขับเคลื่อนทั้งรายงาน "
                   "แดชบอร์ด KPI และหน้าเวลาทำงาน · drives the Report, KPI "
                   "Dashboard and Attendance pages.")
        tf = st.file_uploader("timesheet .xls", type=["xls", "xlsx"],
                              key="adm_ts", label_visibility="collapsed")
        if tf is not None and st.button("📥 นำเข้า timesheet · Import",
                                        key="adm_ts_btn"):
            try:
                _b = tf.read()
                rws, meta = _ts.parse_timesheet(_b)
                _ts.apply_upload(rws, tf.name, _actor, meta)     # report engine
                try:
                    _att.import_timesheet(_b, tf.name, _actor)   # attendance eng.
                except Exception:
                    pass
                st.success(f"นำเข้าแล้ว · imported {meta['n_emp']} emp, "
                           f"{meta['n_days']:,} day-rows "
                           f"({meta['date_from']}→{meta['date_to']})")
                st.rerun()
            except Exception as e:
                st.error(f"ไม่สำเร็จ · failed: {e}")

    cl, co = st.columns(2)
    for col, kind, tag, label, fn in [
            (cl, "leave", "Leave requests", "ใบลา · Leave requests (.xls)",
             _att.import_leave),
            (co, "ot", "OT requests", "ใบโอที · OT requests (.xls)",
             _att.import_ot)]:
        with col:
            st.markdown(f"##### 🗂️ {label}")
            uf = col.file_uploader(label, type=["xls", "xlsx"],
                                   key=f"adm_{kind}",
                                   label_visibility="collapsed")
            if uf is not None and col.button(f"📥 นำเข้า · Import {tag}",
                                             key=f"adm_{kind}_btn"):
                try:
                    _uid, _n = fn(uf.read(), uf.name, _actor)
                    st.success(f"นำเข้าแล้ว · imported {_n:,} rows")
                    st.rerun()
                except Exception as e:
                    st.error(f"ไม่สำเร็จ · failed: {e}")

    # --- file-source chooser for the 3 HR reports (admin-only home, req.1.1) ---
    st.divider()
    st.subheader("🗂️ เลือกไฟล์ที่ใช้งานของ 3 รายงานหลัก · Active source — 3 HR "
                 "reports")
    st.caption("ถ้าอัปโหลดไฟล์ผิด สามารถเลือกย้อนกลับไปใช้ไฟล์ก่อนหน้าได้ · revert "
               "to an earlier file if a wrong one was uploaded.")
    for _k, _lbl in [("timesheet", "⏱️ บันทึกเวลา · Timesheet"),
                     ("leave", "🌴 ใบลา · Leave"), ("ot", "⏰ ใบโอที · OT")]:
        _hist = _att.list_uploads(_k)
        st.markdown(f"**{_lbl}** — {len(_hist)} file(s)")
        if not _hist:
            st.caption("— ยังไม่มีไฟล์ · none yet")
            continue
        _ids = [h["id"] for h in _hist]
        _cur = next((h["id"] for h in _hist if h["active"]), _ids[0])

        def _osrc(i, _h=_hist):
            u = next(x for x in _h if x["id"] == i)
            return (("✅ " if u["active"] else "▫️ ")
                    + f"{u['filename']} · {u['n_rows']:,} แถว · "
                    + f"{u['period_from']}→{u['period_to']} · "
                    + f"{str(u['uploaded_at'])[:16]} · {u['uploaded_by']}")
        _pick = st.radio("src", _ids, index=_ids.index(_cur),
                         format_func=_osrc, key=f"admsrc_{_k}",
                         label_visibility="collapsed")
        if _pick != _cur and st.button("✅ ใช้ไฟล์นี้ · use this",
                                       key=f"admset_{_k}"):
            _att.set_active(_k, _pick)
            st.success("เปลี่ยนแหล่งข้อมูลแล้ว · active source changed.")
            st.rerun()

    st.divider()
    st.subheader("🧾 ประวัติการอัปโหลด · Upload history log")
    st.caption("ผู้ดูแลใช้ตรวจสอบการอัปเดตข้อมูล และแก้ไขเมื่อมีข้อผิดพลาด · "
               "audit trail of all imports.")
    _log = _ulog.recent(150)
    if not _log:
        st.info("ยังไม่มีประวัติการอัปโหลด · no uploads recorded yet.")
    else:
        _df = _pd.DataFrame(_log).rename(columns={
            "file_type": "ประเภท · Type", "file_name": "ไฟล์ · File",
            "period": "ช่วง · Period", "rows_inserted": "แถว · Rows",
            "uploaded_by": "โดย · By", "uploaded_at": "เวลา · When",
            "notes": "หมายเหตุ · Notes"})
        st.dataframe(_df, use_container_width=True, hide_index=True)

    # ----------- one-click content seeders (DSD courses + SC&L VQ) ----------
    st.divider()
    st.subheader("🌱 โหลดเนื้อหาตั้งต้น · Seed starter content")
    st.caption("ปุ่มเดียวจบ ไม่ต้องใช้เทอร์มินัล — เขียนลงฐานข้อมูลที่ระบบใช้งานอยู่ "
               "(รวมถึง Supabase เมื่อกดในแอปที่ดีพลอยแล้ว) · one click, no "
               "terminal; writes to whatever database the app is using.")
    st.caption("📍 หลังโหลด: หลักสูตรจะอยู่ที่ **อบรม → 🛠️ จัดการหลักสูตร** "
               "(มอบหมายให้พนักงานเพื่อให้ขึ้นใน 'หลักสูตรของฉัน') และ Video Quiz "
               "ที่ **อบรม → 📹 วิดีโอ Quiz** · after loading, courses live in "
               "**Training → Manage** (assign them to staff so they appear in "
               "'My training'); quizzes in **Training → Video quiz**.")
    import os as _os
    import sys as _sys
    _scripts_dir = _os.path.join(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__))), "scripts")
    if _scripts_dir not in _sys.path:
        _sys.path.insert(0, _scripts_dir)

    _sc1, _sc2 = st.columns(2)
    with _sc1:
        st.markdown("**📚 หลักสูตร DSD (5 หลักสูตร) · DSD courses**")
        _rep_c = st.checkbox("แทนที่ของเดิม · Replace existing",
                             key="seed_courses_replace")
        if st.button("โหลดหลักสูตร DSD · Load DSD courses",
                     key="seed_courses_btn"):
            try:
                import seed_dsd_courses as _seed_courses
                _r = _seed_courses.seed_all(replace=_rep_c)
                st.success(f"สำเร็จ · created {len(_r['created'])} / skipped "
                           f"{len(_r['skipped'])} of {_r['total']} courses.")
                if _r["created"]:
                    st.write("สร้าง/แทนที่ · created: " + ", ".join(_r["created"]))
                if _r["skipped"]:
                    st.caption("ข้าม (มีอยู่แล้ว) · skipped: "
                               + ", ".join(_r["skipped"]))
            except Exception as _e:
                st.error(f"ผิดพลาด · error: {_e}")
    with _sc2:
        st.markdown("**🎬 Video Quiz — Supply Chain (8 บท) · SC&L video quiz**")
        _rep_v = st.checkbox("แทนที่ของเดิม · Replace existing",
                             key="seed_vq_replace")
        if st.button("โหลด Video Quiz SC&L · Load SC&L video quiz",
                     key="seed_vq_btn"):
            try:
                import seed_scl_video_quiz as _seed_vq
                _r = _seed_vq.seed_quiz(replace=_rep_v)
                st.success(f"สำเร็จ · created {_r['created']} / skipped "
                           f"{_r['skipped']} of {_r['total']} videos.")
                st.caption("เพิ่ม YouTube ID ได้ที่ อบรม → 📹 วิดีโอ Quiz · "
                           "add the YouTube IDs there.")
            except FileNotFoundError:
                st.error("ไม่พบไฟล์ scripts/scl_invideo_quiz.json · "
                         "JSON missing in scripts/.")
            except Exception as _e:
                st.error(f"ผิดพลาด · error: {_e}")


# ============================== Signup requests (req. 4) ====================
with t5:
    st.subheader("📝 คำขอสมัครใช้งาน · Account sign-up requests")
    st.caption("ผู้ใช้ที่ส่งคำขอจากหน้าเข้าสู่ระบบ — อนุมัติเพื่อสร้างบัญชีทันที "
               "(ผู้ใช้คงรหัสผ่านที่ตั้งไว้) · Requests from the sign-in screen; "
               "approving creates the account immediately.")
    _pending = list_signup_requests("pending")
    st.markdown(f"**รอตรวจสอบ · Pending: {len(_pending)}**")
    if not _pending:
        st.info("ไม่มีคำขอที่รอตรวจสอบ · No pending requests.")
    for r in _pending:
        with st.container(border=True):
            st.markdown(f"**{r['req_username']}** · {r.get('req_full_name') or '—'}"
                        f" · {r.get('req_email') or '—'}")
            st.caption(f"ขอบทบาท · role: {r.get('req_role')} · รหัสพนักงาน · emp: "
                       f"{r.get('req_emp_no') or '—'} · {r.get('submitted_at') or ''}"
                       + (f" · IP {r['request_ip']}" if r.get('request_ip') else ""))
            if r.get("reason"):
                st.caption(f"เหตุผล · reason: {r['reason']}")
            cc = st.columns([2, 2, 3, 1, 1])
            _idx = ROLES.index(r["req_role"]) if r.get("req_role") in ROLES else 1
            grole = cc[0].selectbox("บทบาท · grant role", ROLES, index=_idx,
                                    key=f"sg_role_{r['id']}")
            gemp = cc[1].text_input("emp_no", value=r.get("req_emp_no") or "",
                                    key=f"sg_emp_{r['id']}",
                                    label_visibility="collapsed",
                                    placeholder="emp_no")
            gnote = cc[2].text_input("note", key=f"sg_note_{r['id']}",
                                     label_visibility="collapsed",
                                     placeholder="หมายเหตุ · note (optional)")
            if cc[3].button("✅", key=f"sg_ok_{r['id']}", help="อนุมัติ · Approve"):
                ok, msg = approve_signup(r["id"], me, granted_role=grole,
                                         emp_no=gemp, notes=gnote)
                (st.success if ok else st.error)(msg)
                st.rerun()
            if cc[4].button("❌", key=f"sg_no_{r['id']}", help="ปฏิเสธ · Reject"):
                reject_signup(r["id"], me, notes=gnote)
                st.warning("ปฏิเสธคำขอแล้ว · Request rejected.")
                st.rerun()
    with st.expander("ประวัติคำขอที่ตรวจสอบแล้ว · Reviewed history"):
        _hist = [x for x in list_signup_requests() if x["status"] != "pending"]
        if not _hist:
            st.caption("—")
        else:
            st.dataframe([{"User": h["req_username"], "Status": h["status"],
                           "Role": h.get("granted_role") or h.get("req_role"),
                           "By": h.get("reviewed_by"),
                           "When": h.get("reviewed_at"),
                           "Note": h.get("review_notes")} for h in _hist],
                         use_container_width=True, hide_index=True)


# ============================== Login audit (req. 4) =======================
with t6:
    if not has_capability("system.view_audit"):
        st.info("ต้องมีสิทธิ์ system.view_audit · Requires the "
                "system.view_audit capability.")
    else:
        st.subheader("🛡️ ประวัติการเข้าสู่ระบบ · Login audit")
        st.caption("ทุกการพยายามเข้าสู่ระบบ (สำเร็จ/ล้มเหลว) พร้อม IP และอุปกรณ์ "
                   "· Every sign-in attempt with IP and device, for security "
                   "review.")
        f1, f2, f3, f4 = st.columns(4)
        only_fail = f1.toggle("เฉพาะที่ล้มเหลว · Failures only", key="au_fail")
        only_adm = f2.toggle("เฉพาะผู้ดูแล · Admins only", key="au_adm")
        fuser = f3.text_input("กรองผู้ใช้ · Filter username", "", key="au_user")
        lim = f4.number_input("ล่าสุด N · last N", min_value=50, max_value=2000,
                              value=200, step=50, key="au_lim")
        rows = get_login_audit(limit=int(lim), username=fuser.strip() or None,
                               only_admin=only_adm, only_failures=only_fail)
        m1, m2, m3, m4 = st.columns(4)
        _tot = len(rows); _suc = sum(1 for r in rows if r["success"])
        _uu = len({r["username"] for r in rows if r["username"]})
        m1.metric("เหตุการณ์ · Events", _tot)
        m2.metric("สำเร็จ · Success", _suc)
        m3.metric("ล้มเหลว · Failed", _tot - _suc)
        m4.metric("ผู้ใช้ · Users", _uu)
        if not rows:
            st.info("ไม่มีข้อมูลตามเงื่อนไข · No events match the filters.")
        else:
            disp = [{"สถานะ·Status": ("✅" if r["success"]
                                      else "❌ " + (r.get("failure_reason") or "")),
                     "เวลา·When": r.get("occurred_at"),
                     "ผู้ใช้·User": r.get("username"),
                     "บทบาท·Role": r.get("role_at_login") or "",
                     "IP": r.get("ip_address") or "",
                     "อุปกรณ์·Device": (r.get("user_agent") or "")[:60]}
                    for r in rows]
            st.dataframe(disp, use_container_width=True, hide_index=True,
                         height=460)
            import csv as _csv2
            import io as _io2
            _buf = _io2.StringIO()
            _w = _csv2.DictWriter(_buf, fieldnames=list(disp[0].keys()))
            _w.writeheader(); _w.writerows(disp)
            st.download_button("⬇️ ดาวน์โหลด CSV · Download CSV",
                               ("\ufeff" + _buf.getvalue()).encode("utf-8"),
                               file_name="login_audit.csv", mime="text/csv",
                               key="au_csv")
