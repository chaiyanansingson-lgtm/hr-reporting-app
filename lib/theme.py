# lib/theme.py — ANCA (AMS) design system v2
# Frosted-glass + squircle, Apple-like. Adapted & enhanced from the deployed
# ANCA build: real logo, capability-filtered bilingual sidebar menu (hides
# Streamlit's default nav), larger rounded corners, crisper type.
import base64
import pathlib
import streamlit as st
from lib import auth
from lib import i18n

ROOT = pathlib.Path(__file__).resolve().parent.parent
BLUE = "#009ADE"
PURPLE = "#715091"
MAGENTA = "#E31D93"
INK = "#1F2937"
MUTED = "#6B7280"


@st.cache_data
def _manual_bytes():
    p = ROOT / "assets" / "manual_th_en.pdf"
    return p.read_bytes() if p.exists() else None


@st.cache_data
def _logo_b64(name="logo_transparent.png"):
    p = ROOT / "assets" / name
    if not p.exists():
        p = ROOT / "assets" / "logo.png"
    return base64.b64encode(p.read_bytes()).decode("ascii") if p.exists() \
        else ""


# (path, icon, thai, english, capability or None) — None = all logged-in
NAV = [
    ("app.py", "🏠", "หน้าหลัก", "Home", None),
    ("pages/1_Report.py", "📊", "รายงาน", "Reports", "report.view"),
    ("pages/A_Org_Chart.py", "🌳", "ผังองค์กร", "Org chart", "orgchart.view"),
    ("pages/D_Employee_Data.py", "🗂️", "ข้อมูลพนักงาน", "Employees",
     "employee.access"),
    ("pages/K_Attendance.py", "⏱️", "เวลาทำงาน", "Attendance",
     "attend.view_team"),
    ("pages/N_OT_Report.py", "💰", "OT ตามแผนก", "OT by dept",
     "salary.ot_report"),
    ("pages/F_Leave_OT.py", "🌴", "ลางาน / โอที", "Leave & OT",
     "leave.submit"),
    ("pages/G_Car_Booking.py", "🚗", "จองรถ", "Car booking", "car.book"),
    ("pages/H_Stationery_ERP.py", "✏️", "เบิกเครื่องเขียน", "Stationery",
     "erp.browse"),
    ("pages/J_Stock.py", "📦", "สต๊อก", "Stock", "stock.request"),
    ("pages/I_Permits.py", "🪪", "ใบขออนุญาต", "Permits", "permit.request"),
    ("pages/M_Training.py", "🎓", "อบรม", "Training", "train.take"),
    ("pages/L_Resignation.py", "📤", "การลาออก", "Resignation",
     "resign.submit"),
    ("pages/C_Candidate_Portal.py", "📝", "สมัครงาน", "Apply",
     "candidate.apply"),
    ("pages/B_Visitor_Portal.py", "🛂", "ผู้มาติดต่อ", "Visitor",
     "visitor.access"),
    ("pages/E_My_Profile.py", "👤", "โปรไฟล์ของฉัน", "My profile",
     "self.view_profile"),
    ("pages/0_System_Admin.py", "⚙️", "ตั้งค่าระบบ", "System admin",
     "system.users"),
]

_CSS = """
<style>
@import url("https://fonts.googleapis.com/css2?family=Sarabun:wght@400;500;600;700&family=Inter:wght@400;500;600;700;800&display=swap");

:root{
  --blue:#009ADE; --purple:#715091; --magenta:#E31D93;
  --blue-15:rgba(0,154,222,.15); --purple-15:rgba(113,80,145,.15);
  --ink:#1F2937; --muted:#6B7280; --surface:#fff;
  --glass:rgba(255,255,255,.66); --hairline:rgba(15,23,42,.08);
  --sans:-apple-system,BlinkMacSystemFont,"SF Pro Text","Inter","Sarabun","Segoe UI",sans-serif;
  --r-card:22px; --r-btn:13px; --r-input:13px;
}

.stApp{
  background:
    radial-gradient(circle at 8% 8%, rgba(0,154,222,.10) 0%, transparent 34%),
    radial-gradient(circle at 95% 4%, rgba(227,29,147,.08) 0%, transparent 40%),
    radial-gradient(circle at 50% 100%, rgba(113,80,145,.07) 0%, transparent 46%),
    #FFFFFF;
  background-attachment:fixed;
}
html,body,[class*="css"],button,input,textarea,select{
  font-family:var(--sans)!important;
  -webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;
}
h1,h2,h3,h4{font-weight:700;letter-spacing:-.02em;color:var(--ink);}
h1{font-size:1.9rem;} h2{font-size:1.4rem;}
.block-container{padding-top:2rem;padding-bottom:3rem;max-width:1340px;}

[data-testid="stSidebarNav"]{display:none!important;}
#MainMenu,footer,[data-testid="stDecoration"],[data-testid="stStatusWidget"],[data-testid="stAppDeployButton"]{display:none!important;}
header[data-testid="stHeader"]{background:transparent;}
/* keep the sidebar collapse / expand (hamburger) ALWAYS reachable so the
   sidebar can never get stuck closed */
[data-testid="stSidebarCollapseButton"]{visibility:visible!important;opacity:1!important;}
[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"],
button[kind="header"]{visibility:visible!important;opacity:1!important;
  display:flex!important;z-index:1000000!important;}

[data-testid="stSidebar"]{
  background:linear-gradient(180deg,rgba(255,255,255,.86),rgba(245,247,255,.78))!important;
  -webkit-backdrop-filter:blur(22px) saturate(180%);
  backdrop-filter:blur(22px) saturate(180%);
  border-right:1px solid var(--hairline);
}
.company-badge{text-align:center;padding:1.1rem .5rem 1.2rem;
  border-bottom:1px solid var(--hairline);margin-bottom:.7rem;}
.company-badge img{max-width:188px;width:100%;height:auto;
  filter:drop-shadow(0 4px 10px rgba(113,80,145,.18));}
.company-badge .name{font-weight:800;font-size:.92rem;color:var(--ink);
  margin-top:.55rem;letter-spacing:-.01em;}
.company-badge .tag{font-size:.74rem;color:var(--muted);margin-top:2px;
  letter-spacing:.04em;text-transform:uppercase;}
.sb-sec{font-size:.72rem;font-weight:700;letter-spacing:.12em;
  text-transform:uppercase;color:var(--muted);margin:.2rem 0 .4rem .4rem;}
.sb-user{font-size:.86rem;color:var(--muted);padding:6px 4px;}

[data-testid="stSidebar"] [data-testid="stPageLink"] a{
  border-radius:12px;padding:9px 13px;margin:1px 0;font-weight:600;
  color:var(--ink)!important;border:1px solid transparent;transition:.15s;}
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover{
  background:rgba(0,154,222,.08)!important;border-color:rgba(0,154,222,.2);}
[data-testid="stSidebar"] [data-testid="stPageLink"] a p{color:inherit!important;}

.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{
  border-radius:var(--r-btn)!important;font-weight:600;border:1px solid var(--hairline);
  background:rgba(255,255,255,.7);color:var(--ink)!important;
  -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);
  transition:all .18s cubic-bezier(.4,0,.2,1);box-shadow:0 1px 2px rgba(15,23,42,.05);
  min-height:40px;padding:9px 17px!important;}
.stButton>button:hover,.stDownloadButton>button:hover{
  border-color:var(--blue);color:var(--blue)!important;transform:translateY(-1px);
  box-shadow:0 6px 16px rgba(0,154,222,.16);}
.stFormSubmitButton>button,.stButton>button[kind="primary"],
.stDownloadButton>button[kind="primary"],button[kind="primaryFormSubmit"]{
  background:linear-gradient(135deg,#009ADE 0%,#715091 60%,#E31D93 100%)!important;
  color:#fff!important;border:none!important;font-weight:700!important;
  box-shadow:0 4px 16px rgba(113,80,145,.32);}
.stFormSubmitButton>button *,.stButton>button[kind="primary"] *,
button[kind="primaryFormSubmit"] *{color:#fff!important;-webkit-text-fill-color:#fff!important;}
.stFormSubmitButton>button:hover,.stButton>button[kind="primary"]:hover{
  transform:translateY(-1px);box-shadow:0 8px 24px rgba(113,80,145,.45);filter:brightness(1.05);}
[data-testid="stSidebar"] .stButton>button{background:rgba(255,255,255,.55)!important;
  color:var(--ink)!important;font-weight:600;}
[data-testid="stSidebar"] .stButton>button:hover{
  border-color:rgba(227,29,147,.4)!important;color:var(--magenta)!important;}

.stTextInput input,.stNumberInput input,.stTextArea textarea,.stDateInput input{
  border-radius:var(--r-input)!important;border:1px solid var(--hairline)!important;
  background:rgba(255,255,255,.72)!important;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);
  color:var(--ink)!important;}
.stTextInput input:focus,.stNumberInput input:focus,.stTextArea textarea:focus{
  border-color:var(--blue)!important;box-shadow:0 0 0 3px var(--blue-15)!important;}
[data-baseweb="select"]>div,[data-baseweb="input"]{border-radius:var(--r-input)!important;
  background:rgba(255,255,255,.72)!important;}

.stTabs [data-baseweb="tab-list"]{gap:6px;border-bottom:1px solid var(--hairline);}
.stTabs [data-baseweb="tab"]{border-radius:11px 11px 0 0;padding:9px 16px;
  color:var(--muted);font-weight:600;background:transparent;}
.stTabs [data-baseweb="tab"]:hover{color:var(--blue);}
.stTabs [aria-selected="true"]{color:var(--purple)!important;background:transparent!important;
  border-bottom:3px solid var(--magenta)!important;margin-bottom:-1px;}
.stTabs [data-baseweb="tab-highlight"]{display:none;}

[data-testid="stMetric"]{background:var(--glass);
  -webkit-backdrop-filter:blur(14px) saturate(180%);backdrop-filter:blur(14px) saturate(180%);
  padding:16px 20px;border-radius:18px;border:1px solid var(--hairline);
  box-shadow:0 1px 3px rgba(15,23,42,.05);}
[data-testid="stMetricValue"]{font-weight:800;
  background:linear-gradient(135deg,var(--blue),var(--magenta));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
[data-testid="stMetricLabel"]{font-size:.78rem;color:var(--muted);font-weight:700;
  text-transform:uppercase;letter-spacing:.05em;}

[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--hairline)!important;
  border-radius:var(--r-card)!important;background:rgba(255,255,255,.55)!important;
  -webkit-backdrop-filter:blur(16px) saturate(180%);backdrop-filter:blur(16px) saturate(180%);}
[data-testid="stForm"]{background:var(--glass);border:1px solid var(--hairline);
  border-radius:var(--r-card);padding:22px;
  -webkit-backdrop-filter:blur(16px) saturate(180%);backdrop-filter:blur(16px) saturate(180%);
  box-shadow:0 8px 30px rgba(15,23,42,.06);}
[data-testid="stExpander"]{border:1px solid var(--hairline)!important;border-radius:16px!important;
  background:rgba(255,255,255,.6);overflow:hidden;}
[data-testid="stDataFrame"]{border-radius:14px;overflow:hidden;border:1px solid var(--hairline);}
.stAlert{border-radius:14px;background:rgba(255,255,255,.78)!important;
  -webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);}
code{background:rgba(0,154,222,.1);color:var(--purple);padding:2px 8px;border-radius:6px;font-weight:600;}
hr{border:none;border-top:1px solid var(--hairline);margin:1.4rem 0;}

.brand-band{height:4px;border-radius:3px;margin-bottom:1.1rem;
  background:linear-gradient(90deg,var(--blue),var(--purple) 50%,var(--magenta));}
.anca-hero{display:flex;align-items:center;gap:18px;background:var(--glass);
  border:1px solid var(--hairline);border-radius:var(--r-card);padding:18px 24px;
  -webkit-backdrop-filter:blur(18px) saturate(180%);backdrop-filter:blur(18px) saturate(180%);
  box-shadow:0 8px 30px rgba(15,23,42,.06);margin-bottom:6px;}
.anca-hero img{height:52px;width:auto;filter:drop-shadow(0 4px 10px rgba(113,80,145,.2));}

.login-wrap{max-width:430px;margin:1.5rem auto 0;padding:.5rem;}
.login-logo{text-align:center;margin-bottom:.4rem;}
.login-logo img{max-width:230px;width:80%;height:auto;
  filter:drop-shadow(0 6px 16px rgba(113,80,145,.18));}
.login-title{text-align:center;font-size:1.35rem;font-weight:800;margin:.2rem 0 0;
  background:linear-gradient(135deg,var(--blue),var(--purple) 50%,var(--magenta));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.login-tag{text-align:center;color:var(--muted);font-size:.9rem;margin:4px 0 1rem;}

.mod-card{border-radius:var(--r-card);padding:1.5rem 1.3rem 1.1rem;min-height:184px;
  background:rgba(255,255,255,.72);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);
  border:1px solid rgba(0,154,222,.16);
  box-shadow:0 6px 20px rgba(113,80,145,.07),0 1px 2px rgba(0,0,0,.04);
  transition:transform .16s ease,box-shadow .16s ease;}
.mod-card:hover{transform:translateY(-3px);
  box-shadow:0 12px 28px rgba(0,154,222,.18),0 2px 6px rgba(0,0,0,.06);
  border-color:rgba(0,154,222,.4);}
.mod-ic{width:54px;height:54px;border-radius:16px;display:grid;place-items:center;
  font-size:1.7rem;margin-bottom:.7rem;
  background:linear-gradient(135deg,rgba(0,154,222,.14),rgba(227,29,147,.12));}
.mod-t{font-weight:800;font-size:1.06rem;color:var(--purple);margin:0;}
.mod-d{font-size:.86rem;color:#374151;line-height:1.45;margin:.4rem 0 0;min-height:48px;}

/* ── floating Help bubble (bottom-right, JS-free, mobile-safe) ── */
.help-fab{position:fixed;right:20px;bottom:20px;z-index:99999;}
.help-fab > summary{list-style:none;cursor:pointer;width:56px;height:56px;
  border-radius:50%;display:grid;place-items:center;font-size:1.5rem;color:#fff;
  background:linear-gradient(135deg,#009ADE,#715091 55%,#E31D93);
  box-shadow:0 8px 22px rgba(113,80,145,.45);transition:transform .15s;}
.help-fab > summary:hover{transform:scale(1.06);}
.help-fab > summary::-webkit-details-marker{display:none;}
.help-fab-panel{position:fixed;right:20px;bottom:88px;width:360px;max-width:92vw;
  max-height:72vh;overflow-y:auto;background:#fff;border:1px solid var(--hairline);
  border-radius:18px;box-shadow:0 16px 48px rgba(15,23,42,.22);padding:16px;}
.help-fab-head{font-weight:800;color:var(--purple);font-size:1.05rem;}
.help-fab-sub{font-size:.8rem;color:var(--muted);margin:4px 0 10px;line-height:1.45;}
.help-item{border-top:1px solid var(--hairline);padding:9px 0;font-size:.86rem;
  color:var(--ink);line-height:1.5;}
.help-item b{color:var(--blue);}
@media(max-width:520px){.help-fab-panel{width:92vw;right:4vw;bottom:82px;
  max-height:66vh;} .help-fab{right:14px;bottom:14px;}
  .help-fab>summary{width:50px;height:50px;font-size:1.3rem;}}

/* ===== Item 2: mobile top utility bar — keep search + controls on ONE row,
   with the controls pushed to the RIGHT (BaNANA-style), instead of stacking
   into full-width boxes. Desktop (>680px) is untouched. ===== */
@media (max-width: 680px){
  .st-key-ams_topbar [data-testid="stHorizontalBlock"]{
    flex-wrap:nowrap!important; align-items:center!important; gap:6px!important;
  }
  .st-key-ams_topbar [data-testid="stColumn"]{
    width:auto!important; flex:0 0 auto!important; min-width:0!important;
  }
  /* search column grows and pushes the 3 controls to the right edge */
  .st-key-ams_topbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:first-child{
    flex:1 1 auto!important; min-width:0!important;
  }
  /* compact, tappable control buttons (language / bell / account) */
  .st-key-ams_topbar [data-testid="stColumn"] button{
    width:auto!important; min-width:40px!important;
    padding-left:9px!important; padding-right:9px!important;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  }
  /* account button can show the username; cap width so it stays on the row */
  .st-key-ams_topbar [data-testid="stColumn"]:last-child{ max-width:40vw!important; }
}
</style>
"""


_RUN = {"done": False}


def begin_run():
    """Reset the once-per-run guard; call at the top of app.py every run."""
    _RUN["done"] = False


def inject():
    """CSS + sidebar account footer + top utility bar. Idempotent within one
    script run (app.py and the page that st.navigation runs may both call it)."""
    if _RUN["done"]:
        return
    _RUN["done"] = True
    st.markdown(_CSS, unsafe_allow_html=True)
    _sidebar()
    _topbar()
    _announcements()
    _help_fab()


# kind -> (icon, label, page) for the notification bell
_NOTIF = [
    ("leave", "🌴", "ลา · Leave", "pages/F_Leave_OT.py"),
    ("ot", "⏰", "โอที · OT", "pages/F_Leave_OT.py"),
    ("car", "🚗", "จองรถ · Car", "pages/G_Car_Booking.py"),
    ("permit", "🪪", "ใบขออนุญาต · Permit", "pages/I_Permits.py"),
    ("stock", "📦", "สต๊อก · Stock", "pages/J_Stock.py"),
    ("resign", "📤", "ลาออก · Resign", "pages/L_Resignation.py"),
]


def _topbar():
    user = auth.current_user()
    if not user:
        return
    lang = i18n.cur_lang()
    emp_no = str(user.get("emp_no") or "")
    items = []
    if emp_no:
        try:
            from lib import approval_db as _adb
            for kind, ic, lbl, page in _NOTIF:
                try:
                    q = _adb.my_queue(kind, emp_no)
                    if q:
                        items.append((ic, lbl, len(q), page))
                except Exception:
                    pass
        except Exception:
            pass
    total = sum(n for _, _, n, _ in items)

    _tb = st.container(key="ams_topbar")     # keyed → mobile CSS keeps it 1 row
    c_search, c_lang, c_notif, c_acct = _tb.columns([7, 1, 1.1, 2.3])
    with c_search:
        q = st.text_input("search", key="tb_search",
                          placeholder="🔍 " + i18n.t("search_modules"),
                          label_visibility="collapsed")
    with c_lang:
        _flag = "🇹🇭" if lang == "th" else "🇬🇧"
        with st.popover(_flag, use_container_width=True):
            st.caption(i18n.t("language"))
            if st.button("🇹🇭  ไทย", key="lang_th", use_container_width=True,
                         type="primary" if lang == "th" else "secondary"):
                i18n.set_lang("th"); st.rerun()
            if st.button("🇬🇧  English", key="lang_en",
                         use_container_width=True,
                         type="primary" if lang == "en" else "secondary"):
                i18n.set_lang("en"); st.rerun()
    with c_notif:
        with st.popover(f"🔔 {total}" if total else "🔔",
                        use_container_width=True):
            st.markdown(f"**{i18n.t('notifications')}**")
            if not items:
                st.caption(i18n.t("nothing_pending"))
            for ic, lbl, n, page in items:
                try:
                    st.page_link(page, label=f"{ic} {lbl} — {n} {i18n.t('pending')}")
                except Exception:
                    st.caption(f"{ic} {lbl} — {n}")
    with c_acct:
        with st.popover(f"👤 {user['username']}", use_container_width=True):
            st.markdown(f"**{user['username']}**")
            st.caption(f"{i18n.t('role')}: {user['role']}")
            try:
                st.page_link("pages/E_My_Profile.py",
                             label="👤 " + i18n.t("profile"))
            except Exception:
                pass
            if st.button(i18n.t("sign_out"), key="tb_signout",
                         use_container_width=True):
                auth.logout()
                st.rerun()

    if q:
        ql = q.lower().strip()
        res = [(p, th, en) for p, ic, th, en, cap in NAV
               if (cap is None or auth.has_capability(cap))
               and (ql in th.lower() or ql in en.lower())]
        if res:
            rc = st.columns(min(len(res), 4))
            for i, (p, th, en) in enumerate(res[:4]):
                lab = th if lang == "th" else en
                if rc[i].button(lab, key=f"tbr_{p}", use_container_width=True):
                    try:
                        st.switch_page(p)
                    except Exception:
                        pass
        else:
            st.caption("— no matching module —")
    st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)


def _help_panel():
    from lib import help_content
    st.markdown(f"**{i18n.t('help')}**")
    hq = st.text_input("hq", key="help_q",
                       placeholder=i18n.t("help_search"),
                       label_visibility="collapsed")
    rows = help_content.HELP
    if hq:
        ql = hq.lower()
        rows = [(t_, b) for (t_, b) in rows if ql in t_.lower() or ql in b.lower()]
    if not rows:
        st.caption("— no matching topic —")
    for title, body in rows[:12]:
        with st.expander(title):
            st.write(body)


@st.dialog("ประกาศ · Announcement")
def _show_announcement(a):
    import streamlit as _st
    import base64 as _b64
    fit = a.get("media_fit") or "width"
    style = {
        "width": "width:100%;height:auto;",
        "contain": "max-width:100%;max-height:68vh;object-fit:contain;"
                   "display:block;margin:0 auto;",
        "original": "max-width:100%;height:auto;",
    }.get(fit, "width:100%;height:auto;")
    mt = a.get("media_type"); data = a.get("media_data")
    mime = a.get("media_mime") or "image/png"; url = a.get("media_url")
    if mt == "image" and data:
        _st.markdown(f'<img src="data:{mime};base64,{data}" '
                     f'style="{style}border-radius:10px"/>',
                     unsafe_allow_html=True)
    elif mt == "image" and url:
        _st.markdown(f'<img src="{url}" style="{style}border-radius:10px"/>',
                     unsafe_allow_html=True)
    elif mt == "video" and data:
        try:
            _st.video(_b64.b64decode(data))
        except Exception:
            pass
    elif mt == "video" and url:
        _st.video(url)
    elif mt == "pdf" and data:
        _st.download_button("📄 เปิด/ดาวน์โหลดเอกสาร PDF · open PDF",
                            _b64.b64decode(data), file_name="announcement.pdf",
                            mime="application/pdf", use_container_width=True)
    elif mt == "pdf" and url:
        _st.markdown(f"📄 [เอกสาร PDF · open PDF]({url})")
    if a.get("title"):
        _st.markdown(f"### {a['title']}")
    if a.get("body"):
        _st.write(a["body"])
    user = auth.current_user() or {}
    from lib import announce_db
    if a.get("require_accept"):
        items = a.get("consent_list") or \
            ["ข้าพเจ้าได้อ่านและยอมรับ · I have read and accept"]
        ticks = [_st.checkbox(lbl, key=f"ann_cb_{a['id']}_{i}")
                 for i, lbl in enumerate(items)]
        ok = all(ticks)
        if _st.button("ยอมรับ · Accept", disabled=not ok, type="primary",
                      use_container_width=True):
            announce_db.ack(a["id"], user.get("username", "?"), accepted=True)
            _st.rerun()
        if not ok:
            _st.caption("กรุณาติ๊กให้ครบทุกช่องเพื่อยอมรับ · "
                        "tick every box to accept.")
    else:
        if _st.button("รับทราบ · Got it", type="primary",
                      use_container_width=True):
            announce_db.ack(a["id"], user.get("username", "?"), accepted=True)
            _st.rerun()


def _announcements():
    user = auth.current_user()
    if not user:
        return
    try:
        from lib import announce_db
        a = announce_db.pending_for(user["username"])
        if a and not st.session_state.get(f"_ann_shown_{a['id']}"):
            # for 'always'/'once' we only auto-open once per session run-loop
            if a["mode"] != "until_accept":
                st.session_state[f"_ann_shown_{a['id']}"] = True
            _show_announcement(a)
    except Exception:
        pass

def _sidebar():
    # The sidebar (logo + module/function menu + account footer) is rendered
    # entirely by app.py as one ordered custom menu, so nothing is drawn here.
    return



_HELP_ITEMS = """<div class="help-item"><b>Home / หน้าหลัก</b><div>หน้าหลักแสดงโมดูลที่คุณมีสิทธิ์ใช้งาน คลิกการ์ดเพื่อเข้าใช้งาน / The home page shows the modules you can access — click a card to enter.</div></div><div class="help-item"><b>Reports / รายงาน</b><div>รายงานชั่วโมงทำงาน (Working Hour Report): สรุปกำลังคน ชั่วโมงทำงาน OT และการขาดงาน เลือกกลุ่ม/แผนก ปรับคอลัมน์ และส่งออก Excel/รูปภาพได้ / Working Hour Report: headcount, working hours, OT and absence — pick grouping/department, toggle columns, export to Excel or image.</div></div><div class="help-item"><b>Dashboard / แดชบอร์ด (Attendance)</b><div>เลือกช่วงเวลา เปรียบเทียบสองรอบ และดูค่าบนกราฟ ทุกกราฟมีป้ายค่ากำกับและหน่วย / Pick a period, compare two periods, and read value labels and units on every chart.</div></div><div class="help-item"><b>Leave &amp; OT / ลางาน-โอที</b><div>ยื่นใบลา/ใบโอที ระบบส่งให้ผู้บังคับบัญชาอนุมัติตามลำดับชั้น / Submit leave/OT; it routes to your managers for multi-level approval.</div></div><div class="help-item"><b>Car booking / จองรถ</b><div>จองรถพร้อมแผนที่ ผู้ดูแลจ่ายงานคนขับและคิดค่าน้ำมันตาม cost centre / Book a car with a map; admins dispatch drivers and cost trips.</div></div><div class="help-item"><b>Stationery ERP / เบิกเครื่องเขียน</b><div>เลือกสินค้าจากแคตตาล็อก กรองตามแบรนด์/หมวด สร้าง คำขอสั่งซื้อ / Browse the catalogue, filter by brand/group, raise a PO.</div></div><div class="help-item"><b>Stock / สต๊อก</b><div>เบิกพัสดุจากคลังและติดตามยอดคงเหลือ / Request items from stock and track balances.</div></div><div class="help-item"><b>Permits / ใบขออนุญาต</b><div>ขอใบผ่านเข้า-ออก และนำของออกนอกโรงงาน / Request gate passes and material-removal permits.</div></div><div class="help-item"><b>Training / อบรม</b><div>เรียนหลักสูตร e-Learning ทำแบบทดสอบ และรับใบประกาศ / Take e-learning courses, pass the tests, and get a certificate.</div></div><div class="help-item"><b>System admin / ตั้งค่าระบบ</b><div>จัดการผู้ใช้ บทบาทสิทธิ์ ประกาศ/ป็อปอัพ และการตั้งค่า / Manage users, roles, announcements/pop-ups, and settings.</div></div>"""


def _help_fab():
    if not auth.current_user():
        return
    st.markdown(
        '<details class="help-fab"><summary title="Help">\U0001F4AC</summary>'
        '<div class="help-fab-panel">'
        '<div class="help-fab-head">\U0001F4AC ' + i18n.t("help") + '</div>'
        '<div class="help-fab-sub">\U0001F4D8 ' +
        ("ดาวน์โหลดคู่มือ PDF ฉบับเต็มได้ที่ด้านล่างเมนูซ้าย"
         if i18n.cur_lang() == "th"
         else "Download the full PDF manual from the bottom of the left menu.")
        + '</div>' + _HELP_ITEMS + '</div></details>',
        unsafe_allow_html=True)

def header(title_th, title_en="", subtitle=""):
    """Branded page header: gradient band + logo lockup + title."""
    logo = _logo_b64()
    img = (f'<img src="data:image/png;base64,{logo}"/>' if logo else "")
    en = (f' <span style="color:var(--muted);font-weight:600;font-size:'
          f'1.05rem">· {title_en}</span>' if title_en else "")
    sub = (f'<div style="color:var(--muted);font-size:.86rem;margin-top:2px">'
           f'{subtitle}</div>' if subtitle else "")
    st.markdown('<div class="brand-band"></div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="anca-hero">{img}
      <div style="flex:1">
        <div style="font-weight:800;font-size:1.4rem;color:var(--ink);
         letter-spacing:-.02em">{title_th}{en}</div>{sub}
      </div></div>""", unsafe_allow_html=True)
