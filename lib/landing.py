"""
lib/landing.py — Module hub for the post-login landing page.
v11.4 — RBAC Phase 1 foundation (2026-05-08).

Renders the module-card grid that replaces the old home page content
in app.py. Each card represents a module the user might be able to enter:

  - Accessible cards    Bright, with module icon + name + description and
                        an "Enter" button that navigates to the first page
                        of that module.
  - Locked cards        Grayed out with a 🔒 padlock and a "Coming soon"
                        or "Requires X" tooltip — kept visible so the user
                        knows the module exists.

Visibility logic lives in lib/auth.accessible_modules() — this file is
purely the Streamlit UI layer.

Public function:
    render_module_hub(username, lang='th')
"""
from __future__ import annotations

from typing import Optional
from . import auth
from .i18n import t


# Map module_key -> the page filename users navigate to when entering the module.
MODULE_ENTRY_PAGE = {
    "report":       "pages/1_Report.py",
    "orgchart":     "pages/A_Org_Chart.py",
    "visitor":      "pages/B_Visitor_Portal.py",
    "budget":       None,
    "salary":       None,
    "training":     None,
    "recruitment":  None,
    "performance":  None,
}


def _label(mod: dict, lang: str) -> str:
    if lang.lower().startswith("th"):
        return mod.get("module_name_th") or mod.get("module_name_en") or mod["module_key"]
    return mod.get("module_name_en") or mod.get("module_name_th") or mod["module_key"]


def _description(mod: dict, lang: str) -> str:
    if lang.lower().startswith("th"):
        return mod.get("description_th") or mod.get("description_en") or ""
    return mod.get("description_en") or mod.get("description_th") or ""


def _section_heading(lang: str, kind: str) -> str:
    en_th = {
        "available_modules": ("Your modules",  "โมดูลที่ใช้ได้"),
        "locked_modules":    ("Coming soon",   "เปิดให้ใช้งานเร็ว ๆ นี้"),
        "no_modules":        ("No modules available — please contact your administrator.",
                              "ไม่มีโมดูลที่เข้าถึงได้ — กรุณาติดต่อผู้ดูแลระบบ"),
    }
    en, th = en_th.get(kind, (kind, kind))
    return th if lang.lower().startswith("th") else en


def render_module_hub(username: str, lang: str = "th") -> None:
    """Render the module-card grid on the landing page.
    Call from app.py's render_home() after the brand_band and welcome line."""
    import streamlit as st

    role_key = auth.get_user_role(username)
    role_display = auth.get_role_display(role_key, lang)
    modules = auth.accessible_modules(username)

    _inject_hub_css()

    # Role badge under the welcome line
    role_badge_text = ("บทบาท" if lang.lower().startswith("th") else "Role") + f": _{role_display}_"
    st.caption(role_badge_text)
    st.markdown("&nbsp;")

    if not modules:
        st.info("ℹ️ " + _section_heading(lang, "no_modules"))
        return

    accessible = [m for m in modules if m["accessible"]]
    locked = [m for m in modules if not m["accessible"]]

    if accessible:
        st.markdown(f"### 🟢 {_section_heading(lang, 'available_modules')}")
        _render_card_grid(accessible, lang, locked_grid=False)

    if locked:
        st.markdown("")
        st.markdown(f"### 🔒 {_section_heading(lang, 'locked_modules')}")
        _render_card_grid(locked, lang, locked_grid=True)


def _render_card_grid(modules: list[dict], lang: str, *, locked_grid: bool) -> None:
    import streamlit as st

    cols_per_row = 3
    rows = [modules[i:i + cols_per_row] for i in range(0, len(modules), cols_per_row)]

    for row in rows:
        cols = st.columns(cols_per_row, gap="medium")
        for col, mod in zip(cols, row):
            with col:
                _render_card(mod, lang, locked=locked_grid)


def _render_card(mod: dict, lang: str, *, locked: bool) -> None:
    """Render a single module card. The colored surface is HTML for styling;
    the navigation is a real Streamlit button below for native page routing."""
    import streamlit as st

    icon = mod.get("icon_emoji") or "📦"
    name = _label(mod, lang)
    desc = _description(mod, lang)
    state_class = "anca-mod-card--locked" if locked else "anca-mod-card--active"

    lang_th = lang.lower().startswith("th")
    if locked:
        if mod["is_active"] == 0:
            footer = "เปิดให้ใช้งานเร็ว ๆ นี้" if lang_th else "Coming soon"
        else:
            cap = mod.get("access_capability_key") or f"{mod['module_key']}.access"
            footer = f"ต้องมีสิทธิ์: {cap}" if lang_th else f"Requires: {cap}"
        lock_icon = "🔒"
    else:
        footer = ""
        lock_icon = ""

    card_html = f"""
    <div class="anca-mod-card {state_class}">
        <div class="anca-mod-card__icon">{icon}</div>
        <div class="anca-mod-card__title">{name} {lock_icon}</div>
        <div class="anca-mod-card__desc">{desc}</div>
        <div class="anca-mod-card__footer">{footer}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    btn_label = ("เข้าใช้งาน" if lang_th else "Enter") if not locked else ("🔒 " + ("ล็อก" if lang_th else "Locked"))
    btn_key = f"hub_btn_{mod['module_key']}"
    target_page = MODULE_ENTRY_PAGE.get(mod["module_key"])

    clicked = st.button(
        btn_label,
        key=btn_key,
        disabled=locked or target_page is None,
        use_container_width=True,
    )
    if clicked and target_page:
        st.switch_page(target_page)


# ============================================================================
#  CSS — Anca CI palette: cyan #009ADE / purple #715091 / magenta #E31D93
#  Uses 'anca-mod-card' prefix to avoid clashing with anything in style.py.
# ============================================================================
_HUB_CSS = """
<style>
.anca-mod-card {
    border-radius: 16px;
    padding: 1.4rem 1.2rem 1rem 1.2rem;
    margin-bottom: 0.4rem;
    min-height: 200px;
    background: rgba(255, 255, 255, 0.78);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(0, 154, 222, 0.18);
    box-shadow: 0 4px 16px rgba(113, 80, 145, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.anca-mod-card--active:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 154, 222, 0.18), 0 2px 6px rgba(0, 0, 0, 0.06);
    border-color: rgba(0, 154, 222, 0.4);
}
.anca-mod-card--locked {
    opacity: 0.55;
    background: rgba(243, 244, 246, 0.7);
    border-color: rgba(180, 180, 180, 0.3);
}
.anca-mod-card__icon { font-size: 2.4rem; line-height: 1; margin-bottom: 0.6rem; }
.anca-mod-card__title { font-weight: 700; font-size: 1.05rem; color: #715091; margin-bottom: 0.5rem; }
.anca-mod-card--locked .anca-mod-card__title { color: #6B7280; }
.anca-mod-card__desc { font-size: 0.88rem; color: #374151; line-height: 1.4; min-height: 52px; margin-bottom: 0.5rem; }
.anca-mod-card__footer { font-size: 0.78rem; color: #9CA3AF; font-style: italic; margin-top: 0.5rem; }
</style>
"""


def _inject_hub_css() -> None:
    import streamlit as st
    st.markdown(_HUB_CSS, unsafe_allow_html=True)
