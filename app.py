"""
HR Reporting App — main entry.
- Custom branded sidebar with company logo, language toggle, role-aware nav.
- Frosted-glass login page with company branding.
- Bilingual Thai/English (Thai default).

Run with:  streamlit run app.py
"""
import base64
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lib import db
from lib import auth
from lib.landing import render_module_hub
from lib.style import inject_anca_style, brand_band
from lib.i18n import t, init_language, language_toggle, role_label
from config import auth_config


# ──────────────────────────── one-time setup ────────────────────────────
st.set_page_config(
    page_title="HR Reporting · Anca Manufacturing Solutions",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_anca_style()
init_language()
db.init_db()
auth_config.write_default_config(force=False)


# ──────────────────────────── helpers ────────────────────────────
@st.cache_data
def _logo_b64() -> str:
    """Embed the logo as base64 so it renders without a separate HTTP request."""
    p = ROOT / "assets" / "logo_transparent.png"
    if not p.exists():
        p = ROOT / "assets" / "logo.png"
    if not p.exists():
        return ""
    return base64.b64encode(p.read_bytes()).decode("ascii")


def _init_state():
    for k, v in [("authenticated", False), ("username", None),
                 ("role", None), ("name", None)]:
        st.session_state.setdefault(k, v)


_init_state()


# ──────────────────────────── company branding ────────────────────────────
def render_company_badge_sidebar():
    """The company badge that appears at the top of the sidebar."""
    logo = _logo_b64()
    if logo:
        st.sidebar.markdown(
            f"""
            <div class="company-badge">
                <img src="data:image/png;base64,{logo}" style="max-width: 220px; width: 100%; height: auto;" />
                <div class="name">Anca Manufacturing Solutions</div>
                <div class="tag">{t('company_tagline')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            f"""<div class="company-badge">
                  <div class="name">Anca Manufacturing Solutions</div>
                  <div class="tag">{t('company_tagline')}</div>
                </div>""",
            unsafe_allow_html=True,
        )


# ──────────────────────────── sidebar navigation ────────────────────────────
# v11.4: NAV_ITEMS now uses capability strings instead of role tuples.
# Format: (path, i18n_key, icon, required_cap_or_None_or_list_of_caps)
NAV_ITEMS = [
    ("app.py",                          "nav_home",         "🏠",  None),
    ("pages/1_Report.py",               "nav_report",       "📊",  "report.access"),
    ("pages/2_Charts.py",               "nav_charts",       "📈",  "report.view_charts"),
    ("pages/A_Org_Chart.py",            "nav_org_chart",    "🌳",  "orgchart.view"),
    ("pages/5_Employees.py",            "nav_employees",    "👥",  "orgchart.view"),
    ("pages/4_Configuration.py",        "nav_config",       "⚙️",  "report.edit_config"),
    ("pages/3_Upload.py",               "nav_upload",       "📤",  "report.upload"),
    ("pages/7_Change_Requests.py",      "nav_change_req",   "🔄",  ["report.submit_changes", "report.approve_changes"]),
    ("pages/8_Signup_Review.py",        "nav_signup_review","📝",  "system.manage_users"),
    ("pages/6_Users.py",                "nav_users",        "🔑",  "system.manage_users"),
    ("pages/9_Login_Audit.py",          "nav_login_audit",  "🛡️",  "system.view_audit"),
    ("pages/B_Visitor_Portal.py",       "nav_visitor",      "🛡️",  "visitor.access"),
]


def _nav_visible(username: str, required) -> bool:
    if required is None:
        return True
    if isinstance(required, (list, tuple, set)):
        return auth.has_any_capability(username, required)
    return auth.has_capability(username, required)


def render_sidebar_nav():
    """Render bilingual nav links, filtered by user capabilities."""
    username = st.session_state.get("username") or ""
    st.sidebar.markdown("##### " + ("เมนู" if st.session_state.get("lang") == "th" else "Menu"))
    for path, key, icon, required in NAV_ITEMS:
        if not _nav_visible(username, required):
            continue
        st.sidebar.page_link(path, label=f"{icon}  {t(key)}")


def render_sidebar_footer():
    """Language toggle + signed-in info + sign-out at the bottom of the sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### " + t("language"))
    language_toggle(container=st.sidebar)

    if st.session_state.get("authenticated"):
        username = st.session_state.get("username") or ""
        # Show new role_key label (resolved via user_roles table or YAML legacy mapping)
        role_key = auth.get_user_role(username) or st.session_state.get("role")
        st.sidebar.markdown("---")
        st.sidebar.markdown(
            f"<div style='font-size:0.875rem; color:#6B7280; padding: 6px 4px;'>"
            f"👤 <b>{st.session_state.name}</b><br>"
            f"<code style='font-size:0.75rem;'>{role_label(role_key)}</code>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.sidebar.button(t("sign_out"), use_container_width=True, key="sb_signout"):
            for k in ("authenticated", "username", "role", "name"):
                st.session_state[k] = None if k != "authenticated" else False
            st.rerun()


# ──────────────────────────── login screen ────────────────────────────
def render_login():
    render_company_badge_sidebar()
    render_sidebar_footer()  # language toggle visible even before login

    # Center the login card with a 3-column layout (1:2:1 ratio)
    spacer_l, center, spacer_r = st.columns([1, 2, 1])
    with center:
        # Use a native bordered container instead of raw HTML wrapper
        # (raw HTML divs around Streamlit components don't always contain them
        #  on Cloud and can cause invisible buttons due to inherited backgrounds)
        with st.container(border=True):
            logo = _logo_b64()
            if logo:
                st.markdown(
                    f'<div style="text-align:center; padding: 8px 0 12px 0;">'
                    f'<img src="data:image/png;base64,{logo}" '
                    f'style="max-width: 260px; width: 80%; height: auto;" />'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                f'<h2 class="login-title">{t("app_title")}</h2>'
                f'<div class="login-tagline">Anca Manufacturing Solutions {t("company_tagline")}</div>',
                unsafe_allow_html=True,
            )

            # Two tabs: Sign in / Sign up
            tab_in, tab_up = st.tabs([f"🔐  {t('sign_in')}", f"📝  {t('sign_up')}"])

            # ─────────── Sign in tab ───────────
            with tab_in:
                with st.form("login_form", clear_on_submit=False):
                    u = st.text_input(t("username"), key="login_u")
                    p = st.text_input(t("password"), type="password", key="login_p")
                    ok = st.form_submit_button(t("sign_in"), type="primary",
                                                use_container_width=True)
                st.caption(t("default_login_hint"))

                if ok:
                    ip, ua = auth_config.get_client_ip_and_ua()
                    username_clean = (u or "").strip()
                    if not username_clean or not p:
                        db.log_login_attempt(username_clean, False, ip, ua,
                                              failure_reason="empty username or password")
                        st.error(t("invalid_credentials"))
                    else:
                        success, user = auth_config.verify(username_clean, p)
                        if success:
                            role = user.get("role", "viewer")
                            db.log_login_attempt(username_clean, True, ip, ua, role=role)
                            st.session_state.authenticated = True
                            st.session_state.username = username_clean
                            st.session_state.role = role
                            st.session_state.name = user.get("name", username_clean)
                            st.rerun()
                        else:
                            reason = ("user not found" if not auth_config.username_exists(username_clean)
                                      else "wrong password")
                            db.log_login_attempt(username_clean, False, ip, ua, failure_reason=reason)
                            st.error(t("invalid_credentials"))

            # ─────────── Sign up tab ───────────
            with tab_up:
                st.caption(t("signup_hint"))
                with st.form("signup_form", clear_on_submit=True):
                    su_username = st.text_input(t("signup_username"),
                                                 help=t("signup_username_help"))
                    su_email = st.text_input(t("signup_email"))
                    su_full_name = st.text_input(t("signup_full_name"))
                    su_emp_no = st.text_input(t("signup_emp_no"),
                                               help=t("signup_emp_no_help"))
                    su_role = st.selectbox(t("signup_requested_role"),
                                            ["viewer", "manager"],
                                            format_func=lambda r: {"viewer": t("role_viewer"),
                                                                    "manager": t("role_manager")}[r])
                    su_reason = st.text_area(t("signup_reason"),
                                              help=t("signup_reason_help"), height=80)
                    col1, col2 = st.columns(2)
                    su_pw1 = col1.text_input(t("signup_password"), type="password")
                    su_pw2 = col2.text_input(t("signup_password_confirm"), type="password")
                    su_ok = st.form_submit_button(f"📨  {t('signup_submit')}",
                                                   type="primary", use_container_width=True)

                if su_ok:
                    _handle_signup_submission(su_username, su_email, su_full_name,
                                                su_emp_no, su_role, su_reason,
                                                su_pw1, su_pw2)


def _handle_signup_submission(username, email, full_name, emp_no, role,
                               reason, pw1, pw2):
    """Validate and persist a signup request."""
    username = (username or "").strip().lower()
    email = (email or "").strip()
    full_name = (full_name or "").strip()

    # Validation
    errors = []
    if not username or len(username) < 3:
        errors.append(t("err_username_too_short"))
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        errors.append(t("err_invalid_email"))
    if not full_name:
        errors.append(t("err_name_required"))
    if not reason or len(reason.strip()) < 10:
        errors.append(t("err_reason_too_short"))
    if not pw1 or len(pw1) < 8:
        errors.append(t("err_password_too_short"))
    if pw1 != pw2:
        errors.append(t("err_passwords_dont_match"))

    if auth_config.username_exists(username):
        errors.append(t("err_username_taken"))

    conflict = db.signup_username_already_exists_or_pending(username)
    if conflict:
        errors.append(conflict)

    if errors:
        for e in errors:
            st.error(e)
        return

    # Persist
    ip, ua = auth_config.get_client_ip_and_ua()
    pw_hash = auth_config.hash_password(pw1)
    req_id = db.submit_signup_request(
        username=username, email=email, full_name=full_name,
        password_hash=pw_hash, requested_role=role,
        emp_no=emp_no, reason=reason, ip=ip, user_agent=ua,
    )
    st.success(f"✅ {t('signup_success')}  (#{req_id})")
    st.info(t("signup_pending_info"))


# ──────────────────────────── home / landing ────────────────────────────
def render_home():
    render_company_badge_sidebar()
    render_sidebar_nav()
    render_sidebar_footer()

    brand_band()
    st.markdown(f"## 👋 {t('welcome')}, **{st.session_state.name}**")
    st.caption(t("home_intro"))
    st.markdown("")

    # v11.4: render the module hub (replaces the old quick-metrics + period table)
    username = st.session_state.get("username") or ""
    lang = st.session_state.get("lang", "th")
    render_module_hub(username, lang)


# ──────────────────────────── route ────────────────────────────
if not st.session_state.authenticated:
    render_login()
else:
    render_home()
