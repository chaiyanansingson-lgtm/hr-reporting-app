# pages/M_Training.py — Training / LMS (§7)
# My training (progress cards, lessons, anti-skip video, tests, certificate)
# + course builder/assignment/analytics (train.manage) + grading queue
# (train.grade). Visitors see ONLY courses assigned to them.
import datetime as dt
import json
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme
import streamlit.components.v1 as components

from lib.auth import require_capability, current_user, has_capability
from lib import employee_db as edb
from lib import lms_db as lms
from lib import notify

_theme.inject()
require_capability("train.take")

user = current_user(); me = user["username"]
rec = edb.get_record(emp_no=str(user.get("emp_no") or "")) or {}
emp_key = str(user.get("emp_no") or f"user:{me}")

st.title("🎓 ระบบอบรม / Training")

tab_names = ["📚 หลักสูตรของฉัน / My training"]
if has_capability("train.manage"):
    tab_names += ["🛠️ จัดการหลักสูตร / Manage", "📈 Analytics"]
if has_capability("train.grade"):
    tab_names += ["✍️ ตรวจข้อสอบ / Grading"]
tab_names.append("📹 วิดีโอ Quiz · Video quiz")
VQ_IX = len(tab_names) - 1
tabs = st.tabs(tab_names)


def _player(youtube_id, code):
    """Anti-skip player: seek blocked, speed locked 1x, pauses on tab
    blur, Netflix-style presence check every 4 min; the completion code
    appears only at >=100% watch — and the SERVER additionally enforces a
    wall-clock time floor equal to the video length."""
    components.html(f"""
<div id="wrap" style="position:relative">
 <div id="yt"></div>
 <div id="presence" style="display:none;position:absolute;inset:0;
  background:rgba(15,23,42,.86);z-index:5;border-radius:8px;
  text-align:center;color:#fff;font-family:sans-serif;padding-top:140px">
  <div style="font-size:17px;font-weight:700">ยังดูอยู่ไหม? / Still
  watching?</div>
  <div style="font-size:12px;opacity:.85;margin:6px 0 14px">วิดีโอหยุด
  ชั่วคราวและตัวจับเวลาหยุดนับ จนกว่าจะกดยืนยัน</div>
  <button onclick="resumeWatch()" style="padding:10px 26px;border:0;
  border-radius:10px;font-weight:700;font-size:15px;cursor:pointer;
  color:#fff;background:linear-gradient(135deg,#009ADE,#715091)">
  ▶ ยังดูอยู่ / Yes, continue</button></div>
</div>
<div id="bar" style="font-family:sans-serif;font-size:13px;margin-top:8px;
 padding:10px;border-radius:10px;background:#f4f6fb;color:#26303E">
 ⏳ ดูแล้ว <b id="pct">0%</b> — ดูให้ครบ 100% โค้ดยืนยันจะปรากฏที่นี่ (เกณฑ์กรมพัฒนาฝีมือแรงงาน)
 (เลื่อนข้าม/เร่งความเร็ว/สลับหน้าต่าง/ปล่อยทิ้งไว้ = หยุดนับ
 และเซิร์ฟเวอร์จับเวลาจริงเทียบความยาววิดีโออีกชั้น)</div>
<script src="https://www.youtube.com/iframe_api"></script>
<script>
var player, maxW=0, watched=0, dur=0, doneShown=false, sinceCheck=0;
var CHECK_EVERY = 240;   // presence check every 4 minutes of play
function onYouTubeIframeAPIReady(){{
  player = new YT.Player('yt', {{height:'380', width:'100%',
    videoId:'{youtube_id}',
    playerVars:{{rel:0, controls:1, disablekb:1, modestbranding:1}},
    events:{{'onReady':e=>{{dur=player.getDuration();}},
             'onPlaybackRateChange':e=>{{player.setPlaybackRate(1);}} }}
  }});
}}
function resumeWatch(){{
  document.getElementById('presence').style.display='none';
  sinceCheck=0; try{{player.playVideo();}}catch(e){{}}
}}
window.addEventListener('blur', ()=>{{try{{player.pauseVideo();}}catch(e){{}}}});
setInterval(function(){{
  try{{
    if(!player||!player.getCurrentTime) return;
    var t=player.getCurrentTime(); dur=player.getDuration()||dur;
    if(t > maxW + 2){{ player.seekTo(maxW, true); }}   // block skipping
    else if(player.getPlayerState()===1){{
      watched++; sinceCheck++; maxW=Math.max(maxW,t);
      if(sinceCheck>=CHECK_EVERY && !doneShown){{      // presence check
        player.pauseVideo();
        document.getElementById('presence').style.display='block';
      }}
    }}
    var pct = dur? Math.min(100, Math.round(100*maxW/dur)) : 0;
    document.getElementById('pct').textContent = pct + '%';
    if(pct>=99.5 && !doneShown){{
      doneShown=true;
      document.getElementById('bar').innerHTML =
       '✅ ดูครบแล้ว! โค้ดยืนยัน / Completion code: <b style="font-size:18px;'+
       'color:#715091;letter-spacing:2px">{code}</b> — คัดลอกไปวางในช่อง'+
       'ด้านล่างวิดีโอ';
    }}
  }}catch(e){{}}
}}, 1000);
</script>""", height=490)


# ====================================================== MY TRAINING
with tabs[0]:
    ens = lms.my_enrollments(emp_key)
    if not ens:
        st.info("ยังไม่มีหลักสูตรที่ได้รับมอบหมาย / no assigned courses yet")
    today = dt.date.today().isoformat()
    for e in ens:
        pct = lms.enrollment_pct(e["id"], e["course_id"])
        overdue = e["status"] != "completed" and \
            (e["due_date"] or "9999") < today
        days_left = ""
        try:
            dl = (dt.date.fromisoformat(e["due_date"]) -
                  dt.date.today()).days
            days_left = (f"เหลือ {dl} วัน" if dl >= 0
                         else f"เกินกำหนด {-dl} วัน")
        except Exception:
            pass
        ring_col = ("#16a34a" if e["status"] == "completed" else
                    "#dc2626" if overdue else "#715091")
        st.markdown(f"""<div style="display:flex;gap:14px;align-items:center;
border:1px solid #E4E8F0;border-radius:14px;padding:12px 16px;margin:6px 0;
background:#fff">
<div style="width:62px;height:62px;border-radius:50%;flex:none;
background:conic-gradient({ring_col} {pct*3.6}deg,#edf0f7 0);
display:grid;place-items:center">
<div style="width:46px;height:46px;border-radius:50%;background:#fff;
display:grid;place-items:center;font-weight:800;color:{ring_col}">{pct}%
</div></div>
<div style="flex:1"><b>{e['code']} — {e['title_th'] or e['title_en']}</b>
<div style="font-size:12px;color:#5a6478">{e['purpose'] or ''}</div>
<div style="font-size:12px;color:{'#dc2626' if overdue else '#5a6478'}">
กำหนดเสร็จ {e['due_date']} • {days_left} • สถานะ: {e['status']}</div></div>
</div>""", unsafe_allow_html=True)

        with st.expander(f"เปิดหลักสูตร / Open — {e['code']}"):
            course0 = lms.get_course(e["course_id"])
            hrs = lms.course_video_hours(e["course_id"])
            st.markdown(
                f"<div style='font-size:12.5px;color:#5a6478;border:1px "
                f"solid #E4E8F0;border-radius:10px;padding:8px 12px'>"
                f"<b>ข้อมูลหลักสูตร (เกณฑ์กรมพัฒนาฝีมือแรงงาน)</b><br>"
                f"รหัสหลักสูตร: {course0.get('dsd_code') or '—'} • ระดับ: "
                f"{course0.get('level') or '—'} • กลุ่ม: "
                f"{course0.get('course_group') or '—'} • ระยะเวลา (วิดีโอ): "
                f"{hrs:g} ชม.<br>วิทยากร: {course0.get('instructor') or '—'}"
                f"<br>วัตถุประสงค์: {course0.get('objectives') or course0.get('purpose') or '—'}"
                f"<br>เกณฑ์สำเร็จ: เรียนครบ 100% ทุกบท + Post-test ≥ "
                f"{course0.get('pass_pct') or 60:g}%</div>",
                unsafe_allow_html=True)
            for lesson, done, unlocked in lms.lesson_state(e["id"],
                                                           e["course_id"]):
                if unlocked and not done:
                    lms.log_view(e["id"], lesson["id"])   # DSD 2-yr log
                icon = "✅" if done else ("🔓" if unlocked else "🔒")
                st.markdown(f"**{icon} บทที่ {lesson['seq']}: "
                            f"{lesson['title']}** "
                            f"({ {'video':'วิดีโอ','slides':'สไลด์','test':'แบบทดสอบ'}[lesson['kind']] })")
                if done or not unlocked:
                    if not unlocked:
                        st.caption("ปลดล็อกเมื่อจบบทก่อนหน้า / finish the "
                                   "previous lesson first")
                    continue
                # ---------- video ----------
                if lesson["kind"] == "video":
                    lms.mark_opened(e["id"], lesson["id"])  # server clock
                    code = lms.watch_code(e["id"], lesson["id"])
                    _player(lesson["youtube_id"], code)
                    if lesson.get("duration_min"):
                        st.caption(f"⏱️ ความยาววิดีโอ {lesson['duration_min']:g} "
                                   f"นาที — เซิร์ฟเวอร์จะไม่รับโค้ดก่อนเวลา"
                                   f"จริงครบ แม้โค้ดถูกต้อง")
                    c1, c2 = st.columns([2, 1])
                    inp = c1.text_input("โค้ดยืนยันจากวิดีโอ / Completion "
                                        "code", key=f"wc{e['id']}_{lesson['id']}")
                    if c2.button("ยืนยัน / Verify",
                                 key=f"wv{e['id']}_{lesson['id']}"):
                        ok, msg = lms.verify_watch_code(e["id"],
                                                        lesson["id"], inp)
                        if ok:
                            st.success(msg + " — บทถัดไปปลดล็อก")
                            st.rerun()
                        else:
                            st.error("⛔ " + msg)
                # ---------- slides ----------
                elif lesson["kind"] == "slides":
                    pages = json.loads(lesson["pages"] or "[]")
                    kp = f"pg{e['id']}_{lesson['id']}"
                    pg = st.session_state.get(kp, 0)
                    if pages:
                        st.markdown(
                            f"<div style='border:1px solid #E4E8F0;"
                            f"border-radius:12px;padding:18px;background:#fff;"
                            f"min-height:140px'>{pages[pg]}</div>",
                            unsafe_allow_html=True)
                        st.caption(f"หน้า {pg+1}/{len(pages)} — ต้องอ่านถึง"
                                   f"หน้าสุดท้ายจึงจะจบบท")
                        c1, c2, c3 = st.columns(3)
                        if pg > 0 and c1.button("◀ ก่อนหน้า", key=kp+"b"):
                            st.session_state[kp] = pg - 1; st.rerun()
                        if pg < len(pages) - 1 and c2.button("ถัดไป ▶",
                                                             key=kp+"n"):
                            st.session_state[kp] = pg + 1
                            lms.set_progress(e["id"], lesson["id"],
                                             page_reached=pg + 1)
                            st.rerun()
                        if pg == len(pages) - 1 and c3.button(
                                "✅ อ่านจบแล้ว", key=kp+"d", type="primary"):
                            lms.set_progress(e["id"], lesson["id"],
                                             page_reached=pg + 1, done=True)
                            st.rerun()
                # ---------- test ----------
                elif lesson["kind"] == "test":
                    t = lms.get_test(lesson["test_id"])
                    qs = lms.questions(lesson["test_id"])
                    role = t.get("role") or "quiz"
                    if role == "pre":
                        st.caption("📊 Pre-test (วัดพื้นฐานก่อนเรียน — "
                                   "ไม่มีผลตก ใช้เทียบพัฒนาการ)")
                    else:
                        st.caption(f"เกณฑ์ผ่าน {t['pass_pct']:g}% • "
                                   f"สิทธิ์สอบ {t['attempts_allowed']} "
                                   f"ครั้ง • แสดงคะแนนทันทีหลังส่ง")
                    with st.form(f"tf{e['id']}_{lesson['id']}"):
                        answers = {}
                        for q in qs:
                            opts = json.loads(q["options"] or "[]")
                            st.markdown(f"**ข้อ {q['seq']}** ({q['points']:g} "
                                        f"คะแนน): {q['text']}")
                            if q["kind"] == "mcq1":
                                a = st.radio("เลือก 1 ข้อ",
                                             range(len(opts)),
                                             format_func=lambda i: opts[i],
                                             key=f"q{q['id']}", index=None,
                                             label_visibility="collapsed")
                                answers[q["id"]] = a
                            elif q["kind"] == "mcqN":
                                sel = [i for i in range(len(opts))
                                       if st.checkbox(opts[i],
                                                      key=f"q{q['id']}_{i}")]
                                answers[q["id"]] = sel
                            elif q["kind"] == "short":
                                answers[q["id"]] = st.text_input(
                                    "คำตอบ", key=f"q{q['id']}",
                                    label_visibility="collapsed")
                            else:
                                answers[q["id"]] = st.text_area(
                                    "คำตอบ (แสดงวิธีทำ/สูตรได้)",
                                    key=f"q{q['id']}",
                                    label_visibility="collapsed")
                        sub = st.form_submit_button("📨 ส่งคำตอบ / Submit",
                                                    type="primary")
                    if sub:
                        aid, err = lms.start_attempt(e["id"],
                                                     lesson["test_id"])
                        if err:
                            st.error(err)
                        else:
                            at = lms.submit_attempt(aid, answers)
                            if at["grading"] == "pending":
                                st.info("ส่งแล้ว — มีข้อเขียนรอผู้ดูแลตรวจ "
                                        "จะแจ้งผลเมื่อตรวจเสร็จ")
                            elif (t.get("role") or "quiz") == "pre":
                                pct0 = (100*at['score']/at['max_score']) \
                                    if at['max_score'] else 0
                                lms.record_test_pass(e["id"], lesson["id"])
                                st.info(f"บันทึก Pre-test: {at['score']:g}/"
                                        f"{at['max_score']:g} "
                                        f"({pct0:.0f}%) — เริ่มเรียนได้เลย")
                                st.rerun()
                            elif at["passed"]:
                                pct0 = (100*at['score']/at['max_score']) \
                                    if at['max_score'] else 0
                                lms.record_test_pass(e["id"], lesson["id"])
                                st.success(f"ผ่าน! {at['score']:g}/"
                                           f"{at['max_score']:g} "
                                           f"({pct0:.0f}%) ✅")
                                st.rerun()
                            else:
                                pct0 = (100*at['score']/at['max_score']) \
                                    if at['max_score'] else 0
                                st.error(f"ไม่ผ่าน {at['score']:g}/"
                                         f"{at['max_score']:g} "
                                         f"({pct0:.0f}%) — ลองใหม่ได้")
            if e["status"] == "completed":
                st.success(f"🎉 จบหลักสูตรแล้ว • ใบประกาศเลขที่ "
                           f"**{e['cert_no']}**")
                if not lms.has_survey(e["id"]):
                    st.markdown("**📝 แบบสำรวจความพึงพอใจ (ตามเกณฑ์กรมฯ — "
                                "ตอบก่อนพิมพ์ใบประกาศ)**")
                    with st.form(f"sv{e['id']}"):
                        qs_sv = ["เนื้อหาหลักสูตรเป็นประโยชน์",
                                 "สื่อวิดีโอ/เอกสารชัดเจน เข้าใจง่าย",
                                 "ระบบใช้งานสะดวก",
                                 "แบบทดสอบสอดคล้องกับเนื้อหา",
                                 "ความพึงพอใจโดยรวม"]
                        ans = [st.slider(q, 1, 5, 4, key=f"sv{e['id']}{i}")
                               for i, q in enumerate(qs_sv)]
                        cm = st.text_area("ข้อเสนอแนะ / Comments")
                        if st.form_submit_button("ส่งแบบสำรวจ / Submit"):
                            lms.save_survey(e["id"], ans, cm)
                            st.rerun()
                else:
                    course = lms.get_course(e["course_id"])
                    course["hours_display"] = \
                        f"{lms.course_video_hours(e['course_id']):g}"
                    cert = lms.certificate_html(e, course)
                    if st.button("🖨️ พิมพ์ใบประกาศ / Print certificate",
                                 key=f"cert{e['id']}"):
                        components.html(
                            f"<script>var w=window.open('','_blank');"
                            f"w.document.write({cert!r});w.document.close();"
                            f"</script>", height=0)

# ====================================================== MANAGE
if has_capability("train.manage"):
    with tabs[1]:
        st.subheader("สร้างหลักสูตร / New course")
        with st.form("course_form"):
            c1, c2 = st.columns([1, 2])
            code = c1.text_input("รหัส / Code", placeholder="SAFETY-01")
            tth = c2.text_input("ชื่อ (ไทย)")
            ten = st.text_input("Title (EN)")
            purp = st.text_input("วัตถุประสงค์ / Purpose")
            pp = st.number_input("เกณฑ์ผ่านรวม %", 0.0, 100.0, 70.0)
            submitted = st.form_submit_button("💾 Create")
        if submitted:
            if not code.strip():
                st.error("⛔ กรุณากรอกรหัสหลักสูตร (ช่อง Code) ก่อน — "
                         "'SAFETY-01' เป็นเพียงตัวอย่าง / Course Code is "
                         "required ('SAFETY-01' is only a placeholder)")
            elif not (tth.strip() or ten.strip()):
                st.error("⛔ กรุณากรอกชื่อหลักสูตร (ไทยหรืออังกฤษ) / "
                         "Course title is required")
            else:
                try:
                    new_id = lms.create_course(code.strip(), tth.strip(),
                                               ten.strip(), purp.strip(),
                                               pp, me)
                    st.success(f"✅ สร้างหลักสูตรแล้ว / Created: "
                               f"{code.strip()} — {tth.strip() or ten.strip()}"
                               f" — เลื่อนลงไปเพิ่มบทเรียน/ข้อสอบด้านล่าง / "
                               f"scroll down to add lessons & tests")
                except Exception:
                    st.error(f"⛔ สร้างไม่สำเร็จ — รหัส '{code.strip()}' "
                             f"อาจถูกใช้แล้ว กรุณาใช้รหัสอื่น / Could not "
                             f"create — code '{code.strip()}' may already "
                             f"exist, try another")
        courses = lms.list_courses(active_only=False)
        if courses:
            cid = st.selectbox("เลือกหลักสูตรเพื่อแก้ไข / Edit course",
                               [c["id"] for c in courses],
                               format_func=lambda i: next(
                                   f"{c['code']} {c['title_th']}"
                                   for c in courses if c["id"] == i))
            with st.expander("🏛️ ข้อมูลหลักสูตรตามเกณฑ์กรมพัฒนาฝีมือ"
                             "แรงงาน / DSD metadata"):
                c_now = lms.get_course(cid)
                with st.form("dsd_meta"):
                    c1, c2, c3 = st.columns(3)
                    dsd_code = c1.text_input("รหัสหลักสูตร 9 หลัก (กรมฯ "
                                             "ออกให้เมื่อรับรอง)",
                                             c_now.get("dsd_code") or "")
                    level = c2.selectbox("ระดับ", ["", "พื้นฐาน (Fundamental)",
                                         "ต้น (Basic)", "กลาง (Intermediate)",
                                         "สูง (Advanced)"],
                                         index=0 if not c_now.get("level")
                                         else ["", "พื้นฐาน (Fundamental)",
                                               "ต้น (Basic)",
                                               "กลาง (Intermediate)",
                                               "สูง (Advanced)"].index(
                                                   c_now.get("level")))
                    ctype = c3.selectbox("ประเภท", ["Upskill (≥6 ชม.)",
                                         "Reskill (≥18 ชม.)"])
                    grp = st.selectbox("กลุ่มหลักสูตร", [
                        "1. การพัฒนาความรู้", "2. การพัฒนาเทคนิคการทำงาน",
                        "3. ทัศนคติในการทำงาน", "4. ระบบการจัดการ",
                        "5. เทคโนโลยีสารสนเทศและโปรแกรมคอมพิวเตอร์"])
                    instr = st.text_input("วิทยากร (ชื่อ/ตำแหน่ง/สังกัด — "
                                          "ห้ามเสียงสังเคราะห์ AI)",
                                          c_now.get("instructor") or "")
                    objs = st.text_area("วัตถุประสงค์ (เป็นข้อๆ)",
                                        c_now.get("objectives") or "")
                    if st.form_submit_button("💾 Save DSD metadata"):
                        lms.update_course_meta(cid, dsd_code=dsd_code,
                                               level=level,
                                               course_type=ctype,
                                               course_group=grp,
                                               instructor=instr,
                                               objectives=objs)
                        st.rerun()
                hrs_now = lms.course_video_hours(cid)
                need = 18 if "Reskill" in (c_now.get("course_type") or "") \
                    else 6
                if hrs_now < need:
                    st.warning(f"⏱️ ชั่วโมงวิดีโอรวมขณะนี้ {hrs_now:g} ชม. — "
                               f"เกณฑ์กรมฯ ต้อง ≥ {need} ชม. "
                               f"(นับเฉพาะวิดีโอ)")
                else:
                    st.success(f"⏱️ ชั่วโมงวิดีโอรวม {hrs_now:g} ชม. ≥ "
                               f"{need} ชม. ✅")
            st.markdown("**บทเรียน / Lessons**")
            for l in lms.lessons(cid):
                st.write(f"- บทที่ {l['seq']} [{l['kind']}] {l['title']}")
            lk = st.selectbox("เพิ่มบทเรียนชนิด", ["video", "slides", "test"])
            with st.form("lesson_form"):
                lt = st.text_input("ชื่อบท / Lesson title")
                yt = pgtext = None
                dur_min = 0.0
                if lk == "video":
                    yt = st.text_input("YouTube video ID (เช่น dQw4w9WgXcQ)")
                    dur_min = st.number_input(
                        "ความยาววิดีโอ (นาที) — ใช้บังคับเวลาดูจริงฝั่ง"
                        "เซิร์ฟเวอร์", 0.0, 600.0, 0.0, 0.5)
                elif lk == "slides":
                    pgtext = st.text_area(
                        "เนื้อหาสไลด์ — คั่นหน้าด้วยบรรทัด `---` "
                        "(ใส่ HTML/รูปได้)", height=160)
                else:
                    c1, c2, c3, c4 = st.columns(4)
                    trole = c1.selectbox("ชนิดข้อสอบ", ["pre", "post",
                                         "quiz"], index=1,
                                         format_func=lambda x: {
                                             "pre": "Pre-test (ก่อนเรียน)",
                                             "post": "Post-test (วัดผลจบ)",
                                             "quiz": "Quiz ระหว่างบท"}[x])
                    tpp = c2.number_input("เกณฑ์ผ่าน % (กรมฯ ≥60)",
                                          0.0, 100.0, 60.0)
                    tat = c3.number_input("สิทธิ์สอบ (ครั้ง)", 1, 99, 3)
                    tsa = c4.checkbox("เฉลยหลังสอบ")
                if st.form_submit_button("➕ Add lesson") and lt.strip():
                    if lk == "video":
                        lms.add_lesson(cid, "video", lt, youtube_id=yt,
                                       duration_min=dur_min)
                    elif lk == "slides":
                        pages = [p.strip() for p in
                                 (pgtext or "").split("---") if p.strip()]
                        lms.add_lesson(cid, "slides", lt, pages=pages)
                    else:
                        tid = lms.create_test(cid, lt, tpp, int(tat), tsa,
                                              role=trole)
                        lms.add_lesson(cid, "test", lt, test_id=tid)
                    st.rerun()
            # question editor for test lessons
            test_lessons = [l for l in lms.lessons(cid)
                            if l["kind"] == "test"]
            if test_lessons:
                tsel = st.selectbox("แบบทดสอบ", [l["test_id"] for l in
                                    test_lessons],
                                    format_func=lambda i: next(
                                        l["title"] for l in test_lessons
                                        if l["test_id"] == i))
                if st.button("🖨️ พิมพ์ชุดข้อสอบ (PDF สำหรับยื่น ยป.2)",
                             key=f"tp{tsel}"):
                    _tp = lms.test_paper_html(tsel)
                    components.html(
                        f"<script>var w=window.open('','_blank');"
                        f"w.document.write({_tp!r});w.document.close();"
                        f"</script>", height=0)
                for q in lms.questions(tsel):
                    st.caption(f"ข้อ {q['seq']} [{q['kind']}] "
                               f"{q['text'][:70]}")
                with st.form("q_form"):
                    qk = st.selectbox("ชนิดคำถาม", ["mcq1", "mcqN", "short",
                                                    "long"],
                                      format_func=lambda x: {
                                          "mcq1": "ปรนัย 1 คำตอบ (ตรวจอัตโนมัติ)",
                                          "mcqN": "ปรนัยหลายคำตอบ (อัตโนมัติ)",
                                          "short": "เติมคำสั้น (อัตโนมัติถ้าใส่เฉลย)",
                                          "long": "อัตนัย/สูตร (ผู้ดูแลตรวจ)"}[x])
                    qt = st.text_area("โจทย์")
                    qo = st.text_input("ตัวเลือก (คั่นด้วย | สำหรับปรนัย)")
                    qa = st.text_input("เฉลย: mcq1=เลขข้อ(เริ่ม 0) • "
                                       "mcqN=0,2 • short=คำตอบ|คำตอบ • "
                                       "long=เว้นว่าง")
                    qp = st.number_input("คะแนน", 0.5, 20.0, 1.0)
                    if st.form_submit_button("➕ Add question") and qt.strip():
                        opts = [o.strip() for o in qo.split("|")
                                if o.strip()]
                        if qk == "mcq1":
                            key = int(qa) if qa.strip() else None
                        elif qk == "mcqN":
                            key = [int(x) for x in qa.split(",")
                                   if x.strip().isdigit()]
                        elif qk == "short":
                            key = [a.strip() for a in qa.split("|")
                                   if a.strip()]
                        else:
                            key = None
                        lms.add_question(tsel, qk, qt, opts, key, qp)
                        st.rerun()
            st.divider()
            st.markdown("**มอบหมาย / Assign**")
            with st.form("assign_form"):
                c1, c2, c3 = st.columns(3)
                tk = c1.selectbox("กลุ่มเป้าหมาย", ["person", "department",
                                                    "position", "role"],
                                  format_func=lambda x: {
                                      "person": "รายบุคคล (Emp No.)",
                                      "department": "ทั้งแผนก",
                                      "position": "ตามตำแหน่ง",
                                      "role": "ตาม role (เช่น visitor)"}[x])
                tv = c2.text_input("ค่า (Emp No./ชื่อแผนก/ตำแหน่ง/role)")
                due = c3.date_input("กำหนดเสร็จ / Due",
                                    dt.date.today() + dt.timedelta(days=30))
                if st.form_submit_button("📤 Assign", type="primary") and \
                        tv.strip():
                    n = lms.assign(cid, tk, tv.strip(), due, [14, 7, 1], me)
                    st.success(f"มอบหมายแล้ว {n} คน / enrolled")
    with tabs[2]:
        an = lms.analytics()
        if an["courses"]:
            st.dataframe(an["courses"], use_container_width=True)
            st.bar_chart({r["Course"][:24]: r["Completion %"]
                          for r in an["courses"]}, horizontal=True)
        od = lms.overdue_list()
        st.markdown(f"**⏰ เกินกำหนด / Overdue ({len(od)})**")
        if od:
            st.dataframe(od, use_container_width=True)
        st.divider()
        st.subheader("🏛️ รายงานกรมพัฒนาฝีมือแรงงาน / DSD report")
        all_c = lms.list_courses(active_only=False)
        if all_c:
            cdsd = st.selectbox("หลักสูตร", [c["id"] for c in all_c],
                                format_func=lambda i: next(
                                    f"{c['code']} {c['title_th']}"
                                    for c in all_c if c["id"] == i),
                                key="dsd_course")
            rows_d = lms.dsd_course_rows(cdsd)
            done_d = [r for r in rows_d if r["status"] == "completed"]
            if rows_d:
                pres = [r["pre"] for r in done_d if r["pre"] is not None]
                posts = [r["post"] for r in done_d if r["post"] is not None]
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("จบหลักสูตร", f"{len(done_d)}/{len(rows_d)}")
                c2.metric("Pre-test เฉลี่ย",
                          f"{sum(pres)/len(pres):.0f}%" if pres else "—")
                c3.metric("Post-test เฉลี่ย",
                          f"{sum(posts)/len(posts):.0f}%" if posts else "—")
                c4.metric("ศักยภาพเพิ่มขึ้น",
                          sum(1 for r in done_d
                              if r["potential"] == "เพิ่มขึ้น"))
                st.markdown("**ผลก่อน-หลัง รายคน / Pre-Post comparison**")
                st.dataframe([{
                    "Emp": r["emp_key"],
                    "ชื่อ": f"{r['title']}{r['first']} {r['last']}",
                    "Pre %": r["pre"], "Post %": r["post"],
                    "Δ": r["imp"], "ชม.เรียน": r["watch_hours"],
                    "คะแนนประเมิน(5เกณฑ์)": r["total"],
                    "ศักยภาพ": r["potential"],
                    "สถานะ": r["status"]} for r in rows_d],
                    use_container_width=True)
                st.markdown("**✍️ บันทึกผลประเมิน 5 เกณฑ์ (Generic9) — "
                            "เกณฑ์ที่ 1 ระบบเสนอให้จาก Pre/Post อัตโนมัติ "
                            "(0=ไม่เพิ่ม 1=เพิ่ม 2=เพิ่มมาก)**")
                opts_d = {f"{r['emp_key']} {r['first']}": r
                          for r in done_d}
                if opts_d:
                    pk = st.selectbox("พนักงาน", list(opts_d),
                                      key="dsd_emp")
                    r0 = opts_d[pk]
                    with st.form("ev_form"):
                        cc = st.columns(5)
                        vals = [cc[i].number_input(
                            lms.CRITERIA_TH[i][:14], 0.0, 2.0,
                            float(r0["c"][i] if r0["c"][i] is not None
                                  else 0), 1.0, key=f"ev{i}")
                            for i in range(5)]
                        c1, c2 = st.columns(2)
                        inc = c1.selectbox("ช่วงรายได้",
                                           lms.INCOME_RANGES,
                                           index=lms.INCOME_RANGES.index(
                                               r0["income"]))
                        prod = c2.checkbox("ผลิตภาพแรงงานเพิ่มขึ้น",
                                           r0["productivity"])
                        if st.form_submit_button("💾 บันทึกผลประเมิน"):
                            lms.save_skill_eval(r0["enrollment_id"], vals,
                                                inc, prod, me)
                            st.rerun()
                st.download_button(
                    "⬇️ Log File รายบุคคล (หลักฐาน 2 ปี)",
                    lms.view_log_xlsx(cdsd),
                    file_name="DSD_view_log.xlsx")
        st.divider()
        st.subheader("📄 สร้างรายงาน Generic9 / Generic9 builder")
        st.caption("เลือกหลักสูตร + ตัวกรอง → ระบบดึงผลจาก LMS กรอกให้ครบ"
                   "ตามแบบฟอร์มต้นฉบับ (Summary / Data / เกณฑ์ผลิตภาพ "
                   "ตำแหน่งเซลล์ตรงต้นฉบับทุกช่อง) — ไม่ต้องกรอกมือ")
        if all_c:
            g_cids = st.multiselect(
                "หลักสูตรที่จะรวมในรายงาน (เลือกได้หลายหลักสูตร)",
                [c["id"] for c in all_c],
                format_func=lambda i: next(
                    f"{c['code']} {c['title_th']}" for c in all_c
                    if c["id"] == i), key="g9_courses")
            c1, c2, c3 = st.columns(3)
            g_done = c1.checkbox("เฉพาะผู้เรียนจบหลักสูตร / completed only",
                                 True, key="g9_done")
            g_from = c2.date_input("จบตั้งแต่วันที่ / completed from",
                                   value=None, key="g9_from")
            g_to = c3.date_input("ถึงวันที่ / to", value=None, key="g9_to")
            if g_cids:
                prev = []
                for ci in g_cids:
                    prev += lms.dsd_course_rows(
                        ci, completed_only=g_done,
                        date_from=str(g_from) if g_from else None,
                        date_to=str(g_to) if g_to else None)
                st.markdown(f"**พรีวิว: {len(prev)} คนเข้าเงื่อนไข** — "
                            f"ศักยภาพเพิ่มขึ้น "
                            f"{sum(1 for r in prev if r['potential']=='เพิ่มขึ้น')} • "
                            f"ผลิตภาพเพิ่มขึ้น "
                            f"{sum(1 for r in prev if r['productivity'])}")
                if prev:
                    st.dataframe([{
                        "ID": r["id_card"],
                        "ชื่อ": f"{r['title']}{r['first']} {r['last']}",
                        "ตำแหน่ง": r["position"],
                        "1-5": "".join(str(int(v or 0)) for v in r["c"]),
                        "ศักยภาพ": r["potential"],
                        "ผลิตภาพ": "เพิ่มขึ้น" if r["productivity"]
                        else "คงเดิม",
                        "จบเมื่อ": str(r.get("cert_no") or "")}
                        for r in prev], use_container_width=True,
                        height=240)
                    st.download_button(
                        "⬇️ ดาวน์โหลด Generic9 (.xlsx) — กรอกครบจากระบบ",
                        lms.generic9_xlsx(
                            g_cids, completed_only=g_done,
                            date_from=str(g_from) if g_from else None,
                            date_to=str(g_to) if g_to else None),
                        file_name="Generic9_AMS.xlsx", type="primary",
                        key="g9_dl")
                else:
                    st.info("ไม่มีใครเข้าเงื่อนไขที่เลือก / no one matches "
                            "the filters")
        cf = lms.cheat_flags()
        st.markdown(f"**🕵️ ความพยายามลัดบทเรียน / Suspicious attempts "
                    f"({len(cf)})**")
        st.caption("นับครั้งที่ใส่โค้ดผิดหรือยืนยันเร็วกว่าความยาววิดีโอจริง "
                   "(ตัวจับเวลาเซิร์ฟเวอร์) / wrong-code or faster-than-"
                   "video attempts, counted server-side")
        if cf:
            st.dataframe([{"Emp": c["emp_key"], "Name": c["display_name"],
                           "Course": c["course"], "Lesson": c["lesson"],
                           "ครั้ง": c["flags"],
                           "จบแล้ว": "✅" if c["done"] else "—"}
                          for c in cf], use_container_width=True)

# ====================================================== GRADING
if has_capability("train.grade"):
    with tabs[-1]:
        gq = lms.grading_queue()
        if not gq:
            st.caption("ไม่มีข้อสอบรอตรวจ / nothing to grade 🎉")
        for at in gq:
            with st.container(border=True):
                st.markdown(f"**{at['course_code']} — {at['test_title']}** "
                            f"• {at['display_name']} ({at['emp_key']}) • "
                            f"ส่งเมื่อ {str(at['submitted_at'])[:16]}")
                for a in lms.attempt_answers(at["id"]):
                    if a["kind"] not in ("long", "short") or \
                            a["score"] is not None:
                        st.caption(f"ข้อ: {a['text'][:60]} → "
                                   f"{a['score']}/{a['points']:g} (อัตโนมัติ)")
                        continue
                    st.markdown(f"**โจทย์:** {a['text']}")
                    ans = json.loads(a["answer"] or '""')
                    st.code(str(ans))
                    c1, c2, c3 = st.columns([1, 2, 1])
                    sc = c1.number_input("คะแนน", 0.0,
                                         float(a["points"] or 1),
                                         key=f"gs{a['id']}")
                    cm = c2.text_input("คอมเมนต์", key=f"gc{a['id']}")
                    if c3.button("💾", key=f"gb{a['id']}"):
                        lms.grade_answer(a["id"], sc, cm, me)
                        st.rerun()
                if st.button("✅ สรุปผลสอบ / Finalize",
                             key=f"fin{at['id']}", type="primary"):
                    ok, msg = lms.finalize_grading(at["id"], me)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()


# ==================================================== INTERACTIVE VIDEO QUIZ
def _extract_yt(u):
    import re
    if not u:
        return ""
    u = u.strip()
    m = re.search(r'(?:v=|youtu\.be/|embed/|/v/|shorts/)([A-Za-z0-9_-]{11})', u)
    if m:
        return m.group(1)
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', u):
        return u
    return ""


def _mmss(s):
    s = str(s).strip()
    if ":" in s:
        p = s.split(":")
        try:
            return int(p[0]) * 60 + int(p[1])
        except Exception:
            return 0
    try:
        return int(float(s))
    except Exception:
        return 0


with tabs[VQ_IX]:
    from lib import video_quiz_db as vq
    from lib import vq_player
    st.markdown("### 📹 วิดีโอ Quiz · Interactive video quiz")
    st.caption("วิดีโอที่มีคำถามเด้งขึ้นตามเวลาที่กำหนด (เช่น นาที 07:38 = ข้อ 1, "
               "15:30 = ข้อ 2) — ผู้ดูแลตั้งคำถามและลำดับเวลาได้ · questions pop up "
               "at the timestamps you set while the video plays.")
    courses = vq.list_courses()

    if courses:
        pick = st.selectbox("เลือกบทเรียน · choose a video lesson", courses,
                            format_func=lambda c: c["title"], key="vq_pick")
        if pick:
            qs = vq.questions(pick["id"])
            st.caption(f"⏱ {len(qs)} คำถามในวิดีโอ · in-video questions • "
                       f"เกณฑ์ผ่าน / pass ≥ {pick['pass_pct']:g}%")
            if pick["video_type"] == "upload" and not pick.get("video_data"):
                st.warning("วิดีโอยังไม่ถูกอัปโหลด · video not uploaded")
            elif pick["video_type"] == "youtube" and not pick.get("youtube_id"):
                st.warning("ยังไม่ได้ตั้งค่า YouTube · no YouTube video set")
            else:
                components.html(vq_player.build_player(pick, qs), height=730,
                                scrolling=True)
    else:
        st.info("ยังไม่มีบทเรียนวิดีโอ · no video lessons yet" +
                (" — สร้างได้ด้านล่าง" if has_capability("train.manage") else ""))

    if has_capability("train.manage"):
        st.divider()
        st.markdown("#### 🛠️ ผู้ดูแล · Author video lessons & questions")
        with st.expander("➕ สร้างบทเรียนวิดีโอใหม่ · New video lesson"):
            vt = st.text_input("ชื่อบทเรียน · Title", key="vqc_t")
            src = st.radio("แหล่งวิดีโอ · Video source",
                           ["YouTube", "อัปโหลด .mp4 · upload"],
                           horizontal=True, key="vqc_src")
            yid, vdata, vmime, vtype = "", None, None, "youtube"
            if src.startswith("YouTube"):
                yurl = st.text_input("YouTube URL หรือ ID", key="vqc_yt",
                    placeholder="https://youtu.be/XXXXXXXXXXX  หรือ  XXXXXXXXXXX")
                yid = _extract_yt(yurl)
                if yurl and not yid:
                    st.caption("⚠️ อ่าน YouTube ID ไม่ได้ — วางลิงก์เต็มหรือ ID 11 ตัว")
            else:
                vtype = "upload"
                st.caption("📐 แนะนำคลิปสั้น ≤ ~25 MB; คลิปยาวให้ใช้ YouTube · "
                           "short clips only; use YouTube for long videos.")
                vf = st.file_uploader("ไฟล์ .mp4 / .webm", type=["mp4", "webm"],
                                      key="vqc_vf")
                if vf is not None:
                    import base64 as _b64
                    raw = vf.read()
                    if len(raw) > 30 * 1024 * 1024:
                        st.warning("ไฟล์ใหญ่เกิน 30 MB — แนะนำใช้ YouTube")
                    vdata = _b64.b64encode(raw).decode()
                    vmime = f"video/{vf.name.rsplit('.', 1)[-1]}"
            pp = st.number_input("เกณฑ์ผ่าน % · Pass %", 0.0, 100.0, 70.0,
                                 key="vqc_pp")
            if st.button("สร้างบทเรียน · Create lesson", key="vqc_btn",
                         type="primary"):
                if not vt.strip():
                    st.error("กรอกชื่อบทเรียน · title required")
                elif vtype == "youtube" and not yid:
                    st.error("ใส่ YouTube URL/ID ที่ถูกต้อง")
                elif vtype == "upload" and not vdata:
                    st.error("อัปโหลดไฟล์วิดีโอก่อน")
                else:
                    vq.create_course(vt.strip(), vtype, yid, vdata, vmime, pp, me)
                    st.success("สร้างบทเรียนแล้ว · created"); st.rerun()

        if courses:
            ce = st.selectbox("เลือกบทเรียนเพื่อจัดการคำถาม · manage questions for",
                              courses, format_func=lambda c: c["title"],
                              key="vq_edit")
            if ce:
                exq = vq.questions(ce["id"])
                if exq:
                    st.markdown("**คำถามปัจจุบัน (เรียงตามเวลา) · current questions**")
                    for q in exq:
                        cols = st.columns([7, 1])
                        cols[0].caption(
                            f"⏱ {q['t_seconds']//60}:{q['t_seconds']%60:02d} · "
                            f"[{q['qtype']}] {q['prompt'][:64]}")
                        if cols[1].button("🗑️", key=f"vqdel{q['id']}"):
                            vq.delete_question(q["id"]); st.rerun()
                st.markdown("**➕ เพิ่มคำถาม · add a question**")
                ts = st.text_input("เวลา (mm:ss) ที่คำถามจะเด้ง · timestamp",
                                   "00:30", key="vqq_ts")
                qt = st.selectbox("ชนิดคำถาม · question type",
                    ["single", "multiple", "truefalse", "short"],
                    format_func=lambda x: {
                        "single": "เลือก 1 ข้อ · single choice",
                        "multiple": "เลือกหลายข้อ · multiple choice",
                        "truefalse": "ถูก/ผิด · true-false",
                        "short": "เติมคำ · short answer"}[x], key="vqq_t")
                prompt = st.text_area("คำถาม · prompt", key="vqq_p", height=70)
                opts, correct = [], None
                if qt in ("single", "multiple"):
                    otext = st.text_area(
                        "ตัวเลือก — 1 บรรทัด = 1 ข้อ · options, one per line",
                        key="vqq_o", height=100)
                    opts = [ln.strip() for ln in otext.splitlines() if ln.strip()]
                    if qt == "single":
                        ci = st.number_input("ข้อที่ถูก (ลำดับที่) · correct option #",
                                             1, max(1, len(opts)), 1, key="vqq_ci")
                        correct = int(ci) - 1
                    else:
                        cm = st.text_input("ข้อที่ถูก เช่น 1,3 · correct #s (comma)",
                                           key="vqq_cm")
                        correct = [int(x) - 1 for x in cm.replace(" ", "").split(",")
                                   if x.isdigit()]
                elif qt == "truefalse":
                    correct = st.radio("คำตอบที่ถูก · correct answer",
                                       ["True", "False"], horizontal=True,
                                       key="vqq_tf") == "True"
                else:
                    correct = st.text_input(
                        "คำตอบที่รับ (เทียบแบบไม่สนตัวพิมพ์) · accepted answer",
                        key="vqq_sa")
                pts = st.number_input("คะแนน · points", 1, 20, 1, key="vqq_pts")
                if st.button("➕ เพิ่มคำถามนี้ · Add question", key="vqq_add"):
                    if not prompt.strip():
                        st.error("กรอกคำถาม · prompt required")
                    elif qt in ("single", "multiple") and len(opts) < 2:
                        st.error("ใส่ตัวเลือกอย่างน้อย 2 ข้อ · at least 2 options")
                    else:
                        vq.add_question(ce["id"], _mmss(ts), qt, prompt.strip(),
                                        opts, correct, int(pts))
                        st.success(f"เพิ่มคำถามแล้ว (ที่ {ts}) · added"); st.rerun()
                if st.button("🗑️ ลบบทเรียนนี้ทั้งหมด · delete this lesson",
                             key="vqcdel"):
                    vq.delete_course(ce["id"]); st.rerun()
