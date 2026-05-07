"""Shared utilities for Streamlit pages: auth gate + branded sidebar + header."""
import sys
from pathlib import Path
import base64

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.style import inject_anca_style, brand_band
from lib.i18n import t, init_language, language_toggle, role_label


@st.cache_data
def _logo_b64() -> str:
    p = ROOT / "assets" / "logo_transparent.png"
    if not p.exists():
        p = ROOT / "assets" / "logo.png"
    if not p.exists():
        return ""
    return base64.b64encode(p.read_bytes()).decode("ascii")


# Same nav items as app.py
NAV_ITEMS = [
    ("app.py",                          "nav_home",         "🏠",  None),
    ("pages/1_Report.py",               "nav_report",       "📊",  None),
    ("pages/2_Charts.py",               "nav_charts",       "📈",  None),
    ("pages/A_Org_Chart.py",            "nav_org_chart",    "🌳",  None),
    ("pages/5_Employees.py",            "nav_employees",    "👥",  None),
    ("pages/4_Configuration.py",        "nav_config",       "⚙️",  None),
    ("pages/3_Upload.py",               "nav_upload",       "📤",  ("admin",)),
    ("pages/7_Change_Requests.py",      "nav_change_req",   "🔄",  ("admin", "manager")),
    ("pages/8_Signup_Review.py",        "nav_signup_review","📝",  ("admin",)),
    ("pages/6_Users.py",                "nav_users",        "🔑",  ("admin",)),
    ("pages/9_Login_Audit.py",          "nav_login_audit",  "🛡️",  ("admin",)),
]


def _render_company_badge():
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


def _render_sidebar_nav():
    role = st.session_state.get("role")
    st.sidebar.markdown("##### " + ("เมนู" if st.session_state.get("lang") == "th" else "Menu"))
    for path, key, icon, allowed in NAV_ITEMS:
        if allowed and role not in allowed:
            continue
        st.sidebar.page_link(path, label=f"{icon}  {t(key)}")


def _render_sidebar_footer():
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### " + t("language"))
    language_toggle(container=st.sidebar)

    if st.session_state.get("authenticated"):
        st.sidebar.markdown("---")
        st.sidebar.markdown(
            f"<div style='font-size:0.875rem; color:#6B7280; padding: 6px 4px;'>"
            f"👤 <b>{st.session_state.name}</b><br>"
            f"<code style='font-size:0.75rem;'>{role_label(st.session_state.role)}</code>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.sidebar.button(t("sign_out"), use_container_width=True, key=f"sb_signout_{st.session_state.get('username','')}"):
            for k in ("authenticated", "username", "role", "name"):
                st.session_state[k] = None if k != "authenticated" else False
            st.rerun()


def require_login(admin_only: bool = False, manager_or_admin: bool = False):
    """Auth gate + render branded sidebar."""
    inject_anca_style()
    init_language()

    if not st.session_state.get("authenticated"):
        _render_company_badge()
        _render_sidebar_footer()
        st.error("🔐 " + ("กรุณาเข้าสู่ระบบในหน้าหลักก่อน" if st.session_state.get("lang") == "th"
                            else "Please sign in on the main page first."))
        st.page_link("app.py", label=t("sign_in"), icon="🔐")
        st.stop()

    role = st.session_state.get("role")
    if admin_only and role != "admin":
        _render_company_badge()
        _render_sidebar_nav()
        _render_sidebar_footer()
        st.error("🚫 Admin only.  Your role: `" + str(role) + "`.")
        st.stop()
    if manager_or_admin and role not in ("admin", "manager"):
        _render_company_badge()
        _render_sidebar_nav()
        _render_sidebar_footer()
        st.error("🚫 Manager or admin only.  Your role: `" + str(role) + "`.")
        st.stop()

    # Render the full sidebar
    _render_company_badge()
    _render_sidebar_nav()
    _render_sidebar_footer()


def page_header(title_key: str = None, subtitle_key: str = None,
                title: str = None, subtitle: str = None):
    """Render the branded page header (gradient band + title + subtitle).
    Pass either an i18n key (title_key/subtitle_key) or literal text (title/subtitle)."""
    brand_band()
    final_title = t(title_key) if title_key else (title or "")
    final_subtitle = t(subtitle_key) if subtitle_key else (subtitle or "")
    st.markdown(f"# {final_title}")
    if final_subtitle:
        st.caption(final_subtitle)


def is_admin() -> bool:
    return st.session_state.get("role") == "admin"


def is_manager_or_admin() -> bool:
    return st.session_state.get("role") in ("admin", "manager")
