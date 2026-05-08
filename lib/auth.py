"""
lib/auth.py — Capability resolution + role helpers for Anca HR App.
v11.4 — RBAC Phase 1 foundation (2026-05-08).

Role resolution order for any username:
    1. Explicit row in 'user_roles' table  (Super Admin reassignment, or
        bootstrap from USER_MIGRATION_MAP in rbac_seed.py)
    2. YAML legacy role mapped through LEGACY_ROLE_MAP below
    3. None  (locked out — fails closed)

Effective capability set:
    effective = (role_default_caps  ∪  user_grants)  −  user_revokes

Public API (pure logic — no Streamlit dependency):
    get_user_role(username)              -> Optional[str]
    get_role_capabilities(role_key)      -> set[str]
    get_user_overrides(username)         -> dict[str, str]   ('grant' or 'revoke')
    effective_capabilities(username)     -> set[str]
    has_capability(username, cap_key)    -> bool
    has_any_capability(username, caps)   -> bool
    has_all_capabilities(username, caps) -> bool
    is_super_admin(username)             -> bool
    is_admin_or_above(username)          -> bool
    is_internal_user(username)           -> bool
    accessible_modules(username)         -> list[dict]
    get_role_display(role_key, lang)     -> str

Streamlit helpers (lazy-imported, safe to import this module outside Streamlit):
    require_capability(cap_key)
    require_any_capability(cap_keys)
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterable, Optional


# ============================================================================
#  LEGACY → NEW role mapping
# ============================================================================
# Used for users NOT in the user_roles table — i.e., custom users created
# via the Users page in v11.3, whose YAML role is admin/manager/viewer.
#
# Note: legacy 'admin' (a custom user) maps to NEW 'admin' role (Level 6),
# NOT to 'super_admin'. The default 'admin' username gets super_admin via
# USER_MIGRATION_MAP (in rbac_seed.py) — that's the bootstrap account.
LEGACY_ROLE_MAP = {
    "admin":   "admin",
    "manager": "manager",
    "viewer":  "viewer",
}


def _resolve_db_path() -> str:
    env = os.environ.get("HR_DB_PATH")
    if env:
        return env
    return str(Path(__file__).resolve().parent.parent / "data" / "hr.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_resolve_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================================
#  Pure-logic API
# ============================================================================
def get_user_role(username: str) -> Optional[str]:
    """Return role_key for username following the resolution order in the
    module docstring. Returns None for unknown users (fails closed)."""
    if not username:
        return None

    # 1. Explicit row in user_roles (highest priority)
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT role_key FROM user_roles WHERE username = ?", (username,)
        )
        row = cur.fetchone()
        if row and row["role_key"]:
            return row["role_key"]
    finally:
        conn.close()

    # 2. Fall back to YAML legacy role via auth_config
    try:
        from config import auth_config  # lazy import to avoid circular imports
        for u in auth_config.list_users():
            if u.get("username") == username:
                legacy = u.get("role")
                if legacy in LEGACY_ROLE_MAP:
                    return LEGACY_ROLE_MAP[legacy]
                break
    except Exception:
        pass

    return None


def get_role_capabilities(role_key: str) -> set[str]:
    """All capability keys granted to this role by default."""
    if not role_key:
        return set()
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT capability_key FROM role_capabilities WHERE role_key = ?",
            (role_key,),
        )
        return {r["capability_key"] for r in cur.fetchall()}
    finally:
        conn.close()


def get_user_overrides(username: str) -> dict[str, str]:
    """Returns {capability_key: 'grant' | 'revoke'} for this user."""
    if not username:
        return {}
    conn = _connect()
    try:
        cur = conn.execute(
            """SELECT capability_key, override_type
               FROM user_capability_overrides WHERE username = ?""",
            (username,),
        )
        return {r["capability_key"]: r["override_type"] for r in cur.fetchall()}
    finally:
        conn.close()


def effective_capabilities(username: str) -> set[str]:
    """effective = (role_default_caps ∪ user_grants) − user_revokes"""
    role = get_user_role(username)
    if not role:
        return set()

    base = get_role_capabilities(role)
    overrides = get_user_overrides(username)

    grants = {k for k, v in overrides.items() if v == "grant"}
    revokes = {k for k, v in overrides.items() if v == "revoke"}

    return (base | grants) - revokes


def has_capability(username: str, cap_key: str) -> bool:
    return cap_key in effective_capabilities(username)


def has_any_capability(username: str, cap_keys: Iterable[str]) -> bool:
    caps = effective_capabilities(username)
    return any(k in caps for k in cap_keys)


def has_all_capabilities(username: str, cap_keys: Iterable[str]) -> bool:
    caps = effective_capabilities(username)
    return all(k in caps for k in cap_keys)


# ============================================================================
#  Convenience role predicates
# ============================================================================
def is_super_admin(username: str) -> bool:
    return get_user_role(username) == "super_admin"


def is_admin_or_above(username: str) -> bool:
    return get_user_role(username) in ("admin", "super_admin")


def is_internal_user(username: str) -> bool:
    """True if user has an internal (non-Visitor) role."""
    role = get_user_role(username)
    if not role:
        return False
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT is_external FROM roles WHERE role_key = ?", (role,)
        )
        row = cur.fetchone()
        return bool(row and row["is_external"] == 0)
    finally:
        conn.close()


# ============================================================================
#  Module hub
# ============================================================================
def accessible_modules(username: str) -> list[dict]:
    """Return all visible modules for this user, with an 'accessible' flag.
    See lib/landing.py for how this is rendered as the post-login hub."""
    user_caps = effective_capabilities(username)
    is_internal = is_internal_user(username)

    conn = _connect()
    try:
        cur = conn.execute(
            """SELECT module_key, module_name_en, module_name_th, icon_emoji,
                      sort_order, is_active, is_external_allowed,
                      access_capability_key, description_en, description_th
               FROM modules
               ORDER BY sort_order, module_key"""
        )
        out: list[dict] = []
        for r in cur.fetchall():
            mod = dict(r)

            # Audience filter: internal users don't see Visitor Portal,
            # external (Visitor) users only see external-allowed modules.
            if is_internal and mod["is_external_allowed"] == 1:
                continue
            if (not is_internal) and mod["is_external_allowed"] == 0:
                continue

            if mod["is_active"] == 0:
                mod["accessible"] = False  # locked / coming-soon
            else:
                cap = mod["access_capability_key"] or f"{mod['module_key']}.access"
                mod["accessible"] = cap in user_caps

            out.append(mod)
        return out
    finally:
        conn.close()


# ============================================================================
#  Display helpers
# ============================================================================
def get_role_display(role_key: Optional[str], lang: str = "th") -> str:
    """Return localized role display name. Falls back to the key itself."""
    if not role_key:
        return "—"
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT role_name_en, role_name_th FROM roles WHERE role_key = ?",
            (role_key,),
        )
        row = cur.fetchone()
        if not row:
            return role_key
        return row["role_name_th"] if lang.lower().startswith("th") else row["role_name_en"]
    finally:
        conn.close()


def get_module_display(module_key: str, lang: str = "th") -> str:
    if not module_key:
        return "—"
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT module_name_en, module_name_th FROM modules WHERE module_key = ?",
            (module_key,),
        )
        row = cur.fetchone()
        if not row:
            return module_key
        return row["module_name_th"] if lang.lower().startswith("th") else row["module_name_en"]
    finally:
        conn.close()


# ============================================================================
#  Streamlit page guards (lazy-imported)
# ============================================================================
def _get_session_username() -> Optional[str]:
    """Read current logged-in username from Streamlit session state.
    Matches the auth pattern used in app.py (custom — not streamlit-authenticator)."""
    try:
        import streamlit as st
    except ImportError:
        return None
    return st.session_state.get("username")


def require_capability(cap_key: str, *, redirect_to_hub: bool = True) -> None:
    """Streamlit page guard. Halts page render if user lacks the capability."""
    import streamlit as st

    username = _get_session_username()
    if not username:
        st.error("⚠️ กรุณาเข้าสู่ระบบ / Please log in to continue.")
        st.stop()

    if has_capability(username, cap_key):
        return

    role_key = get_user_role(username)
    lang = (st.session_state.get("lang") or "th").lower()
    role_display = get_role_display(role_key, lang)

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
    st.caption(f"Missing capability: `{cap_key}`")

    if redirect_to_hub:
        if st.button("🏠 " + ("กลับสู่หน้าหลัก" if lang.startswith("th") else "Back to home"),
                      key=f"perm_back_{cap_key}"):
            st.switch_page("app.py")

    st.stop()


def require_any_capability(cap_keys: Iterable[str], *, redirect_to_hub: bool = True) -> None:
    """Variant: allows access if ANY of the listed capabilities are held."""
    import streamlit as st

    username = _get_session_username()
    if not username:
        st.error("⚠️ กรุณาเข้าสู่ระบบ / Please log in to continue.")
        st.stop()

    if has_any_capability(username, cap_keys):
        return

    lang = (st.session_state.get("lang") or "th").lower()
    role_display = get_role_display(get_user_role(username), lang)

    if lang.startswith("th"):
        st.error(f"⛔ ไม่มีสิทธิ์เข้าถึงหน้านี้\n\nบทบาทของคุณ ({role_display}) ไม่มีสิทธิ์ที่จำเป็น")
    else:
        st.error(f"⛔ Permission denied\n\nYour role ({role_display}) does not have access to this page.")
    st.caption(f"Need at least one of: {', '.join(f'`{c}`' for c in cap_keys)}")

    if redirect_to_hub:
        cap_list_key = "_".join(cap_keys)
        if st.button("🏠 " + ("กลับสู่หน้าหลัก" if lang.startswith("th") else "Back to home"),
                      key=f"perm_back_any_{cap_list_key}"):
            st.switch_page("app.py")
    st.stop()
