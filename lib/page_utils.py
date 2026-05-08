"""Shared utilities for Streamlit pages: auth gate + branded sidebar + header.

v11.4 changes:
  - require_login() now accepts capability= and any_capability= for fine-grained
    access checks. Legacy admin_only= and manager_or_admin= still work for
    backward compat.
  - NAV_ITEMS now uses capability strings (or lists of caps) instead of role
    tuples. Sidebar nav filters via lib.auth.has_capability / has_any_capability.
"""
import sys
from pathlib import Path
import base64
from typing import Iterable, Optional

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.style import inject_anca_style, brand_band
from lib.i18n import t, init_language, language_toggle, role_label
from lib import auth as _auth


@st.cache_data
def _logo_b64() -> str:
    p = ROOT / "assets" / "logo_transparent.png"
    if not p.exists():
        p = ROOT / "assets" / "logo.png"
    if not p.exists():
        return ""
    return base64.b64encode(p.read_bytes()).decode("ascii")


# ──────────────────────────── NAV_ITEMS (capability-driven) ────────────────────────────
# Tuple format: (page_path, i18n_key, icon, required_capability_or_None_or_list)
#   None         → visible to all logged-in users
#   "cap.x"      → visible only if user has capability "cap.x"
#   ["a", "b"]   → visible if user has ANY of the listed capabilities
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
    """Return True if this user can see this nav entry."""
    if required is None:
        return True
    if isinstance(required, (list, tuple, set)):
        return _auth.has_any_capability(username, required)
    return _auth.has_capability(username, required)


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
    """Render bilingual nav links, filtered by user capabilities."""
    username = st.session_state.get("username") or ""
    st.sidebar.markdown("##### " + ("เมนู" if st.session_state.get("lang") == "th" else "Menu"))
    for path, key, icon, required in NAV_ITEMS:
        if not _nav_visible(username, required):
            continue
        st.sidebar.page_link(path, label=f"{icon}  {t(key)}")


def _render_sidebar_footer():
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### " + t("language"))
    language_toggle(container=st.sidebar)

    if st.session_state.get("authenticated"):
        username = st.session_state.get("username", "")
        # Show new role_key label (mapped from user_roles or YAML legacy role)
        role_key = _auth.get_user_role(username) or st.session_state.get("role")
        st.sidebar.markdown("---")
        st.sidebar.markdown(
            f"<div style='font-size:0.875rem; color:#6B7280; padding: 6px 4px;'>"
            f"👤 <b>{st.session_state.name}</b><br>"
            f"<code style='font-size:0.75rem;'>{role_label(role_key)}</code>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.sidebar.button(t("sign_out"), use_container_width=True,
                              key=f"sb_signout_{username}"):
            for k in ("authenticated", "username", "role", "name"):
                st.session_state[k] = None if k != "authenticated" else False
            st.rerun()


def require_login(
    *,
    admin_only: bool = False,
    manager_or_admin: bool = False,
    capability: Optional[str] = None,
    any_capability: Optional[Iterable[str]] = None,
):
    """Auth gate + render branded sidebar.

    Access modes (apply in priority order — first one provided wins):
      1. capability="cap.key"           — exact capability required
      2. any_capability=["a", "b"]      — ANY of the listed capabilities required
      3. admin_only=True                — legacy: only legacy 'admin' role
      4. manager_or_admin=True          — legacy: only legacy 'admin' or 'manager' role
      5. (no args)                      — any logged-in user

    The new capability-based modes use lib.auth which respects the user_roles
    table + YAML legacy role mapping + per-user grant/revoke overrides.
    """
    inject_anca_style()
    init_language()

    if not st.session_state.get("authenticated"):
        _render_company_badge()
        _render_sidebar_footer()
        st.error("🔐 " + ("กรุณาเข้าสู่ระบบในหน้าหลักก่อน" if st.session_state.get("lang") == "th"
                            else "Please sign in on the main page first."))
        st.page_link("app.py", label=t("sign_in"), icon="🔐")
        st.stop()

    username = st.session_state.get("username") or ""
    legacy_role = st.session_state.get("role")

    # --- New capability-based checks (priority over legacy) ---
    if capability is not None:
        if not _auth.has_capability(username, capability):
            _render_company_badge()
            _render_sidebar_nav()
            _render_sidebar_footer()
            _render_permission_denied(username, missing_caps=[capability])
            st.stop()
        _render_company_badge()
        _render_sidebar_nav()
        _render_sidebar_footer()
        return

    if any_capability is not None:
        any_caps = list(any_capability)
        if not _auth.has_any_capability(username, any_caps):
            _render_company_badge()
            _render_sidebar_nav()
            _render_sidebar_footer()
            _render_permission_denied(username, missing_caps=any_caps, any_of=True)
            st.stop()
        _render_company_badge()
        _render_sidebar_nav()
        _render_sidebar_footer()
        return

    # --- Legacy role-based checks (backward compat) ---
    if admin_only and legacy_role != "admin":
        _render_company_badge()
        _render_sidebar_nav()
        _render_sidebar_footer()
        st.error("🚫 Admin only.  Your role: `" + str(legacy_role) + "`.")
        st.stop()
    if manager_or_admin and legacy_role not in ("admin", "manager"):
        _render_company_badge()
        _render_sidebar_nav()
        _render_sidebar_footer()
        st.error("🚫 Manager or admin only.  Your role: `" + str(legacy_role) + "`.")
        st.stop()

    # --- All checks passed ---
    _render_company_badge()
    _render_sidebar_nav()
    _render_sidebar_footer()


def _render_permission_denied(username: str, *, missing_caps: list, any_of: bool = False):
    """Render localized permission-denied banner."""
    lang = (st.session_state.get("lang") or "th").lower()
    role_key = _auth.get_user_role(username)
    role_display = _auth.get_role_display(role_key, lang)

    if lang.startswith("th"):
        st.error(
            f"⛔ ไม่มีสิทธิ์เข้าถึงหน้านี้\n\n"
            f"บทบาทของคุณ ({role_display}) ไม่มีสิทธิ์ที่จำเป็น"
        )
    else:
        st.error(
            f"⛔ Permission denied\n\n"
            f"Your role ({role_display}) does not have access to this page."
        )

    if any_of:
        cap_str = ", ".join(f"`{c}`" for c in missing_caps)
        st.caption(("ต้องมีสิทธิ์อย่างน้อยหนึ่งใน: " if lang.startswith("th") else "Need at least one of: ") + cap_str)
    else:
        st.caption(("ต้องมีสิทธิ์: " if lang.startswith("th") else "Missing capability: ") + f"`{missing_caps[0]}`")

    st.page_link("app.py",
                  label="🏠 " + ("กลับสู่หน้าหลัก" if lang.startswith("th") else "Back to home"))


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
    """Backward-compat helper. Checks legacy session_state role for 'admin'."""
    return st.session_state.get("role") == "admin"


def is_manager_or_admin() -> bool:
    """Backward-compat helper. Checks legacy session_state role."""
    return st.session_state.get("role") in ("admin", "manager")
