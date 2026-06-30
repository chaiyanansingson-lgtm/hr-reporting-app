# app.py — AMS HRM entry.
# Routing is driven by st.navigation(position="hidden"); the sidebar menu is a
# CUSTOM accordion built here: the LOGO on top, then each MODULE as an expander
# (main menu) that opens to reveal its FUNCTIONS as links (sub-menu), then the
# account footer. The module that contains the current page is auto-expanded.
import os
import streamlit as st

st.set_page_config(page_title="ANCA (AMS) HR System", page_icon="🟣",
                   layout="wide", initial_sidebar_state="expanded")
# Sub-pages each call st.set_page_config; under st.navigation only the entry
# may. Neutralise their calls so the existing pages run unchanged.
st.set_page_config = lambda *a, **k: None

from lib.db import init_db, IS_POSTGRES
from lib import auth, theme, i18n, nav as navmod

@st.cache_resource
def _boot_db():
    init_db()        # runs once per app process, not on every rerun
    return True
_boot_db()
theme.begin_run()                       # reset once-per-run chrome guard
user = auth.current_user()

# ------------------------------------------------------------------- login
if not user:
    theme.inject()                      # CSS for the login screen
    logo = theme._logo_b64()
    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
    if logo:
        st.markdown(f'<div class="login-logo"><img src="data:image/png;'
                    f'base64,{logo}"/></div>', unsafe_allow_html=True)
    st.markdown('<div class="login-title">ระบบบริหารทรัพยากรบุคคล</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="login-tag">ANCA Manufacturing Solutions '
                '(Thailand) · HR System</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2.2, 1])
    with c2:
        with st.form("login"):
            u = st.text_input("ชื่อผู้ใช้ / Username")
            p = st.text_input("รหัสผ่าน / Password", type="password")
            ok = st.form_submit_button("เข้าสู่ระบบ / Sign in", type="primary",
                                       use_container_width=True)
        if ok:
            if auth.login(u.strip(), p):
                st.rerun()
            else:
                st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง / Invalid credentials")
        st.caption("ครั้งแรก: superadmin / ChangeMe!2026 — เปลี่ยนรหัสทันที / "
                   "First boot: superadmin / ChangeMe!2026 — change it now.")

        with st.expander("📝 สมัครใช้งาน / Request an account"):
            st.caption("ส่งคำขอเปิดบัญชี — ผู้ดูแลระบบจะตรวจสอบและอนุมัติก่อน "
                       "จึงจะเข้าใช้งานได้ / Submit a request; an admin approves "
                       "it before you can sign in.")
            with st.form("signup_form", clear_on_submit=True):
                su_u = st.text_input("ชื่อผู้ใช้ที่ต้องการ / Desired username")
                su_e = st.text_input("อีเมล / Email")
                su_n = st.text_input("ชื่อ-สกุล / Full name")
                su_emp = st.text_input("รหัสพนักงาน (ถ้ามี) / Emp. No. "
                                       "(optional)")
                su_role = st.selectbox(
                    "บทบาทที่ขอ / Requested role",
                    ["viewer", "supervisor", "manager"],
                    format_func=lambda r: {"viewer": "ผู้ดูข้อมูล / Viewer",
                                           "supervisor": "หัวหน้างาน / Supervisor",
                                           "manager": "ผู้จัดการ / Manager"}[r])
                su_p1 = st.text_input("ตั้งรหัสผ่าน / Choose password",
                                      type="password")
                su_p2 = st.text_input("ยืนยันรหัสผ่าน / Confirm password",
                                      type="password")
                su_reason = st.text_area("เหตุผลที่ขอสิทธิ์ / Reason for access",
                                         height=60)
                su_go = st.form_submit_button("ส่งคำขอ / Submit request",
                                              use_container_width=True)
            if su_go:
                if not su_u.strip() or len(su_p1) < 8:
                    st.error("ต้องมีชื่อผู้ใช้ และรหัสผ่านอย่างน้อย 8 ตัวอักษร / "
                             "Username and an 8-character password are required.")
                elif su_p1 != su_p2:
                    st.error("รหัสผ่านไม่ตรงกัน / The two passwords do not match.")
                elif auth.user_exists(su_u) or auth.signup_pending_exists(su_u):
                    st.error("ชื่อผู้ใช้นี้มีอยู่แล้วหรือมีคำขอค้างอยู่ / This "
                             "username already exists or is already pending.")
                else:
                    auth.submit_signup_request(su_u, su_e, su_n, su_p1,
                                               role=su_role, emp_no=su_emp,
                                               reason=su_reason)
                    st.success("ส่งคำขอแล้ว — รอผู้ดูแลระบบอนุมัติ / Request "
                               "submitted; awaiting an admin's approval.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# =================================================================== logged in
# Forced password change on first sign-in: the seeded superadmin (and any
# admin-created temp account) carry must_change_pw=1 until they set their own.
if user.get("must_change_pw"):
    theme.inject()
    _thg = i18n.cur_lang() == "th"
    st.warning("🔐 " + ("ครั้งแรกในระบบ: กรุณาตั้งรหัสผ่านใหม่ก่อนเริ่มใช้งาน"
                        if _thg else
                        "First sign-in: please set a new password to continue."))
    _c1, _c2, _c3 = st.columns([1, 2.2, 1])
    with _c2:
        with st.form("force_pw_change"):
            _np1 = st.text_input("รหัสผ่านใหม่ / New password", type="password")
            _np2 = st.text_input("ยืนยันรหัสผ่านใหม่ / Confirm new password",
                                 type="password")
            _sub = st.form_submit_button("บันทึก / Save", type="primary",
                                         use_container_width=True)
        if _sub:
            if len(_np1) < 8:
                st.error("รหัสผ่านอย่างน้อย 8 ตัวอักษร / Use at least 8 characters.")
            elif _np1 == "ChangeMe!2026":
                st.error("ห้ามใช้รหัสผ่านเริ่มต้น / The default password cannot "
                         "be reused.")
            elif _np1 != _np2:
                st.error("รหัสผ่านไม่ตรงกัน / The two passwords do not match.")
            else:
                auth.set_password(user["username"], _np1)
                st.session_state["user"]["must_change_pw"] = 0
                st.success("ตั้งรหัสผ่านใหม่เรียบร้อย / Password updated.")
                st.rerun()
    st.stop()

_first_by_key = {}


def render_home():
    theme.inject()
    _logo = theme._logo_b64()
    _img = (f'<img src="data:image/png;base64,{_logo}"/>' if _logo else "")
    _th = i18n.cur_lang() == "th"
    st.markdown('<div class="brand-band"></div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="anca-hero">{_img}
      <div style="flex:1">
        <div style="font-weight:800;font-size:1.5rem;color:var(--ink,#1f2937);
         letter-spacing:-.02em">👋 {i18n.t("welcome")}, {user['username']}</div>
        <div style="color:var(--muted,#6b7280);font-size:.9rem;margin-top:3px">
         ANCA Manufacturing Solutions (Thailand) · {'บทบาท' if _th else 'Role'}:
         <code>{user['role']}</code></div>
      </div></div>""", unsafe_allow_html=True)
    if not IS_POSTGRES:
        st.warning("⚠️ กำลังใช้ SQLite ชั่วคราว — ตั้งค่า DATABASE_URL (Supabase) "
                   "ใน secrets เพื่อความถาวร / Running on temporary SQLite; set "
                   "DATABASE_URL for persistent Supabase.")
    st.markdown("""<style>
      div[data-testid="stVerticalBlockBorderWrapper"]:has(.mc){
        min-height:206px;border-radius:14px;}
      .mc{display:flex;flex-direction:column;gap:6px;}
      .mc .ic{font-size:2rem;line-height:1;}
      .mc .t{font-weight:700;font-size:1.05rem;color:var(--ink,#1f2937);}
      .mc .d{font-size:.84rem;color:var(--muted,#6b7280);min-height:40px;
        line-height:1.35;}
      .mc.lk{opacity:.5;}
    </style>""", unsafe_allow_html=True)
    cards = navmod.home_cards()
    open_c = [c for c in cards if c["state"] == "open"]
    rest_c = [c for c in cards if c["state"] != "open"]

    def _grid(items, locked):
        for r in range(0, len(items), 3):
            row = items[r:r + 3]
            cols = st.columns(3, gap="medium")
            for j in range(3):
                if j >= len(row):
                    continue
                c = row[j]
                name = c["th"] if _th else c["en"]
                desc = c["desc_th"] if _th else c["desc_en"]
                with cols[j]:
                    with st.container(border=True):
                        kl = "mc lk" if locked else "mc"
                        st.markdown(
                            f'<div class="{kl}"><div class="ic">{c["icon"]}'
                            f'</div><div class="t">{name}</div>'
                            f'<div class="d">{desc}</div></div>',
                            unsafe_allow_html=True)
                        if not locked:
                            st.page_link(_first_by_key[c["key"]],
                                         label=("เข้าใช้งาน" if _th else "Open")
                                         + "  →")
                        elif c["state"] == "soon":
                            st.button("🔒 เปิดใช้งานเร็วๆนี้" if _th else
                                      "🔒 Coming soon", key=f"lk_{c['key']}",
                                      disabled=True, use_container_width=True)
                        else:
                            st.button("🔒 ไม่มีสิทธิ์เข้าถึง" if _th else
                                      "🔒 No access", key=f"lk_{c['key']}",
                                      disabled=True, use_container_width=True)

    st.markdown(f"### 🟢 {'โมดูลที่ใช้ได้' if _th else 'Available modules'}")
    _grid(open_c, False)
    if rest_c:
        st.write("")
        st.markdown("### 🔒 " + ("เปิดใช้งานเร็วๆนี้ / ยังไม่พร้อมใช้งาน"
                                 if _th else "Coming soon / unavailable"))
        _grid(rest_c, True)


# ---- routing dict for st.navigation + structure for the custom sidebar ----
_home = st.Page(render_home, title="หน้าหลัก / Home", icon="🏠",
                default=True, url_path="home")
_nav = {"  ": [_home]}                  # routing only; menu is custom (below)
_modules_ui = []                        # [(module, [(st.Page, func), ...]), ..]
for _m in navmod.MODULES:
    _vis = navmod.visible_funcs(_m)
    if not _vis:
        continue
    _pages = [st.Page(_f["path"], title=f"{_f['th']} / {_f['en']}",
                      icon=_f["icon"], url_path=_f["url"]) for _f in _vis]
    _nav[f"{_m['icon']} {_m['th']} / {_m['en']}"] = _pages
    _first_by_key[_m["key"]] = _pages[0]
    _modules_ui.append((_m, list(zip(_pages, _vis))))

pg = st.navigation(_nav, position="hidden")     # route, but hide built-in menu
_active = getattr(pg, "url_path", None)

# --------------------------------------------------- custom sidebar (the menu)
_thl = i18n.cur_lang() == "th"
with st.sidebar:
    _logo = theme._logo_b64()
    if _logo:
        st.markdown(
            f'<div style="text-align:center;padding:14px 6px 8px">'
            f'<img src="data:image/png;base64,{_logo}" '
            f'style="width:100%;max-width:200px;height:auto"/>'
            f'<div style="font-weight:800;font-size:.86rem;'
            f'color:var(--ink,#1f2937);margin-top:6px">ANCA Manufacturing '
            f'Solutions</div><div style="font-size:.72rem;'
            f'color:var(--muted,#6b7280)">'
            f'{"ประเทศไทย · HR System" if _thl else "Thailand · HR System"}'
            f'</div></div>', unsafe_allow_html=True)
    st.page_link(_home, label=("หน้าหลัก" if _thl else "Home"),
                 use_container_width=True)
    st.markdown(f'<div class="sb-sec">{"เมนูโมดูล" if _thl else "Modules"}'
                f'</div>', unsafe_allow_html=True)
    for (_m, _pf) in _modules_ui:
        _mname = _m["th"] if _thl else _m["en"]
        _open = any(getattr(_p, "url_path", None) == _active for _p, _f in _pf)
        with st.expander(f"{_m['icon']}  {_mname}", expanded=_open):
            for (_p, _f) in _pf:
                st.page_link(_p, use_container_width=True,
                             label=f"{_f['th'] if _thl else _f['en']}")
    st.markdown("---")
    st.markdown(f"<div class='sb-user'>👤 <b>{user['username']}</b><br>"
                f"<code>{user['role']}</code></div>", unsafe_allow_html=True)
    if st.button("🚪 " + ("ออกจากระบบ" if _thl else "Sign out"),
                 use_container_width=True, key="app_signout"):
        auth.logout()
        st.rerun()
    _mb = theme._manual_bytes()
    if _mb:
        st.download_button("📘 " + ("คู่มือ PDF" if _thl else "Manual (TH/EN)"),
                           _mb, file_name="ANCA_HR_Manual_TH_EN.pdf",
                           mime="application/pdf", use_container_width=True,
                           key="app_manual")

pg.run()
