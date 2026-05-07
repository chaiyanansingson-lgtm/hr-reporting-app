"""
Authentication helpers.

Storage:
  - Local development: passwords stored in `config/auth.yaml`.
  - Streamlit Cloud: bootstrap admin/viewer passwords come from Streamlit Secrets
    (`[auth] admin_password`, `[auth] viewer_password`), and the working copy
    of users (admins create more, signup approvals create more) lives in
    `config/auth.yaml` which is ephemeral on Cloud — that's expected; admin
    accounts always exist because they're seeded from secrets every boot.

bcrypt is used for password hashing.
"""
from __future__ import annotations
from pathlib import Path
import os
import secrets
import bcrypt
import yaml

try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False

CONFIG_PATH = Path(__file__).resolve().parent / "auth.yaml"


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Streamlit Secrets bootstrap
# ---------------------------------------------------------------------------

def _get_secret(key: str, default: str = "") -> str:
    """Read a value from Streamlit Secrets if available, otherwise env var, otherwise default."""
    if _HAS_STREAMLIT:
        try:
            auth_section = st.secrets.get("auth", {})
            if key in auth_section:
                return str(auth_section[key])
        except (FileNotFoundError, AttributeError, Exception):
            pass
    env_val = os.environ.get(f"AUTH_{key.upper()}")
    if env_val:
        return env_val
    return default


def _bootstrap_admin_password() -> str:
    """Production-safe admin password: from Streamlit Secrets, else default 'admin123'."""
    pw = _get_secret("admin_password", "")
    return pw if pw else "admin123"


def _bootstrap_viewer_password() -> str:
    pw = _get_secret("viewer_password", "")
    return pw if pw else "viewer123"


# ---------------------------------------------------------------------------
# Config file management
# ---------------------------------------------------------------------------

def _bootstrap_extra_users() -> list[dict]:
    """
    Read additional pre-defined users from Streamlit Secrets section [extra_users].

    Format in Streamlit Cloud Secrets:
        [extra_users.trial_user]
        password = "TrialPass123!"
        role     = "viewer"
        name     = "Trial User"
        email    = "trial@example.com"

        [extra_users.john]
        password = "JohnsPass456!"
        role     = "manager"
        name     = "John Smith"
        email    = "john@example.com"

    These users are created (or password-synced) on every app boot, so they
    persist across Cloud restarts. Username is the section key after `extra_users.`
    """
    out = []
    if not _HAS_STREAMLIT:
        return out
    try:
        section = st.secrets.get("extra_users", {})
        if not section:
            return out
        for username, info in section.items():
            if not isinstance(info, dict) and not hasattr(info, "get"):
                continue
            pw = info.get("password", "") if hasattr(info, "get") else getattr(info, "password", "")
            if not pw:
                continue
            out.append({
                "username": str(username).strip().lower(),
                "password": str(pw),
                "role": str(info.get("role", "viewer") if hasattr(info, "get") else "viewer"),
                "name": str(info.get("name", username) if hasattr(info, "get") else username),
                "email": str(info.get("email", "") if hasattr(info, "get") else ""),
            })
    except (FileNotFoundError, AttributeError, Exception):
        pass
    return out


def write_default_config(force: bool = False):
    """Create auth.yaml with seeded admin + viewer if it doesn't exist.

    Called on every app boot. On Cloud, the file gets recreated each restart
    using whatever passwords are in Streamlit Secrets.
    """
    if CONFIG_PATH.exists() and not force:
        # Sync admin/viewer + extra_users passwords with secrets if they've changed
        _sync_with_secrets()
        return

    admin_pw = _bootstrap_admin_password()
    viewer_pw = _bootstrap_viewer_password()
    cookie_key = _get_secret("cookie_key", secrets.token_urlsafe(32))

    usernames = {
        "admin": {
            "name": "Administrator",
            "email": "admin@example.com",
            "password": hash_password(admin_pw),
            "role": "admin",
        },
        "viewer": {
            "name": "Viewer",
            "email": "viewer@example.com",
            "password": hash_password(viewer_pw),
            "role": "viewer",
        },
    }
    # Add any extra_users from Streamlit Secrets (trial accounts, etc.)
    for u in _bootstrap_extra_users():
        usernames[u["username"]] = {
            "name": u["name"],
            "email": u["email"],
            "password": hash_password(u["password"]),
            "role": u["role"],
        }

    config = {
        "credentials": {"usernames": usernames},
        "cookie": {
            "name": "hr_app_auth",
            "key": cookie_key,
            "expiry_days": 1,
        },
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.safe_dump(config, sort_keys=False))


def _sync_with_secrets():
    """If Streamlit Secrets contain admin/viewer/extra_users passwords that differ
    from the stored hashes, re-hash and update. Also adds any new extra_users that
    weren't in auth.yaml yet. Changing a secret in Cloud immediately changes the
    live login on next boot."""
    try:
        cfg = yaml.safe_load(CONFIG_PATH.read_text())
        users = cfg.get("credentials", {}).get("usernames", {})
        changed = False

        # Sync admin / viewer passwords from top-level secrets
        for uname in ("admin", "viewer"):
            sec_pw = _get_secret(f"{uname}_password", "")
            if not sec_pw:
                continue
            stored = users.get(uname, {})
            if not stored:
                continue
            if not _check(sec_pw, stored.get("password", "")):
                users[uname]["password"] = hash_password(sec_pw)
                changed = True

        # Sync (or add) any extra_users from secrets
        for u in _bootstrap_extra_users():
            uname = u["username"]
            existing = users.get(uname)
            if not existing:
                # New user — add them
                users[uname] = {
                    "name": u["name"], "email": u["email"],
                    "password": hash_password(u["password"]),
                    "role": u["role"],
                }
                changed = True
            else:
                # Sync password if changed; sync role if changed
                if not _check(u["password"], existing.get("password", "")):
                    existing["password"] = hash_password(u["password"])
                    changed = True
                if existing.get("role") != u["role"]:
                    existing["role"] = u["role"]
                    changed = True
                if u["name"] and existing.get("name") != u["name"]:
                    existing["name"] = u["name"]
                    changed = True

        if changed:
            CONFIG_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False))
    except Exception:
        pass


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        write_default_config()
    return yaml.safe_load(CONFIG_PATH.read_text())


def role_of(username: str) -> str | None:
    cfg = load_config()
    user = cfg.get("credentials", {}).get("usernames", {}).get(username)
    return user.get("role") if user else None


# ---------------------------------------------------------------------------
# Verify (used by login)
# ---------------------------------------------------------------------------

def verify(username: str, password: str) -> tuple[bool, dict | None]:
    """Returns (success, user_dict).  Caller is responsible for logging the attempt."""
    cfg = load_config()
    user = cfg.get("credentials", {}).get("usernames", {}).get(username)
    if not user:
        return False, None
    ok = _check(password, user.get("password", ""))
    return ok, (user if ok else None)


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def add_user(username: str, name: str, password: str, role: str, email: str = "") -> bool:
    cfg = load_config()
    users = cfg.setdefault("credentials", {}).setdefault("usernames", {})
    if username in users:
        return False
    users[username] = {
        "name": name,
        "email": email,
        "password": hash_password(password),
        "role": role,
    }
    CONFIG_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return True


def add_user_from_hash(username: str, name: str, password_hash: str,
                       role: str, email: str = "") -> bool:
    """Add a user when we already have the bcrypt hash (e.g. from a signup request)."""
    cfg = load_config()
    users = cfg.setdefault("credentials", {}).setdefault("usernames", {})
    if username in users:
        return False
    users[username] = {
        "name": name,
        "email": email,
        "password": password_hash,
        "role": role,
    }
    CONFIG_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return True


def change_password(username: str, new_password: str) -> bool:
    cfg = load_config()
    user = cfg.get("credentials", {}).get("usernames", {}).get(username)
    if not user:
        return False
    user["password"] = hash_password(new_password)
    CONFIG_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return True


def delete_user(username: str) -> bool:
    cfg = load_config()
    users = cfg.get("credentials", {}).get("usernames", {})
    if username not in users:
        return False
    del users[username]
    CONFIG_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return True


def list_users() -> list[dict]:
    cfg = load_config()
    users = cfg.get("credentials", {}).get("usernames", {})
    return [{"username": u, "name": v.get("name"), "role": v.get("role"),
             "email": v.get("email", "")}
            for u, v in users.items()]


def username_exists(username: str) -> bool:
    cfg = load_config()
    return username in cfg.get("credentials", {}).get("usernames", {})


# ---------------------------------------------------------------------------
# Helper: get client IP from Streamlit context (best-effort)
# ---------------------------------------------------------------------------

def get_client_ip_and_ua() -> tuple[str, str]:
    """Best-effort retrieval of client IP and User-Agent from Streamlit's request context.
    Streamlit sits behind a proxy on Cloud so the real client IP is in X-Forwarded-For.
    """
    if not _HAS_STREAMLIT:
        return "", ""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        from streamlit.runtime import get_instance
        ctx = get_script_run_ctx()
        if ctx is None:
            return "", ""
        runtime = get_instance()
        session_info = runtime._session_mgr.get_session_info(ctx.session_id)
        if session_info is None:
            return "", ""
        request = session_info.client.request
        # Real IP behind proxy
        ip = request.headers.get("X-Forwarded-For", "")
        if ip:
            ip = ip.split(",")[0].strip()
        else:
            ip = getattr(request, "remote_ip", "") or ""
        ua = request.headers.get("User-Agent", "")
        return ip, ua
    except Exception:
        return "", ""


if __name__ == "__main__":
    write_default_config(force=True)
    print(f"Wrote default config to {CONFIG_PATH}")
