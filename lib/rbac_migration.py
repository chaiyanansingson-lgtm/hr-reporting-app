"""
RBAC schema migration for Anca HR App.
v11.4 — RBAC Phase 1 foundation (2026-05-08).

Adds 7 tables to support role-based + capability-based access control.

Idempotent — safe to call on every app start. All migrations are additive
(CREATE TABLE IF NOT EXISTS). Follows the additive pattern in lib/db.py.

User accounts continue to live in config/auth_config.py (YAML). The new
'user_roles' table holds explicit role-key assignments only when they
diverge from the YAML legacy role mapping (Super Admin reassignment, or
the bootstrap rows seeded from USER_MIGRATION_MAP). When a username has
no row in user_roles, lib/auth.get_user_role() falls back to mapping the
YAML legacy role through LEGACY_ROLE_MAP.

Tables added:
  - roles                       7 role definitions (Visitor → Super Admin)
  - modules                     module registry (Report, Visitor Portal, future)
  - capabilities                module-level + action-level capability tokens
  - role_capabilities           default capability set per role
  - user_roles                  explicit per-user role-key assignment
                                 (overrides YAML legacy-role mapping)
  - user_capability_overrides   per-user grant/revoke (Super Admin only)
  - approval_priority           sequential approval ordering (foundation only,
                                 wiring deferred to Session 2)

Usage:
    from lib.rbac_migration import apply_rbac_migration
    apply_rbac_migration()   # call from db.init_db() after existing migrations
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional


def _resolve_db_path(db_path: Optional[str] = None) -> str:
    """Resolve to data/hr.db relative to project root, matching lib/db.py."""
    if db_path:
        return db_path
    env = os.environ.get("HR_DB_PATH")
    if env:
        return env
    # Mirror lib/db.py: <project>/data/hr.db
    return str(Path(__file__).resolve().parent.parent / "data" / "hr.db")


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def apply_rbac_migration(db_path: Optional[str] = None) -> dict:
    """Apply all RBAC schema additions. Idempotent. Returns a summary dict."""
    path = _resolve_db_path(db_path)
    db_dir = os.path.dirname(path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    summary = {"tables_created": [], "already_present": []}

    try:
        # --- 1. roles ---
        existed = _table_exists(conn, "roles")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS roles (
                role_key       TEXT PRIMARY KEY,
                role_name_en   TEXT NOT NULL,
                role_name_th   TEXT NOT NULL,
                rank           INTEGER NOT NULL,
                is_external    INTEGER NOT NULL DEFAULT 0,
                description_en TEXT,
                description_th TEXT,
                created_at     TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        (summary["already_present"] if existed else summary["tables_created"]).append("roles")

        # --- 2. modules ---
        existed = _table_exists(conn, "modules")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS modules (
                module_key             TEXT PRIMARY KEY,
                module_name_en         TEXT NOT NULL,
                module_name_th         TEXT NOT NULL,
                icon_emoji             TEXT,
                sort_order             INTEGER NOT NULL DEFAULT 100,
                is_active              INTEGER NOT NULL DEFAULT 1,
                is_external_allowed    INTEGER NOT NULL DEFAULT 0,
                access_capability_key  TEXT,
                description_en         TEXT,
                description_th         TEXT,
                created_at             TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        (summary["already_present"] if existed else summary["tables_created"]).append("modules")

        # --- 3. capabilities ---
        existed = _table_exists(conn, "capabilities")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capabilities (
                capability_key  TEXT PRIMARY KEY,
                module_key      TEXT,
                capability_type TEXT NOT NULL DEFAULT 'action',
                description_en  TEXT,
                description_th  TEXT,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (module_key) REFERENCES modules(module_key)
            )
            """
        )
        (summary["already_present"] if existed else summary["tables_created"]).append("capabilities")

        # --- 4. role_capabilities (the default matrix) ---
        existed = _table_exists(conn, "role_capabilities")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS role_capabilities (
                role_key       TEXT NOT NULL,
                capability_key TEXT NOT NULL,
                PRIMARY KEY (role_key, capability_key),
                FOREIGN KEY (role_key)       REFERENCES roles(role_key),
                FOREIGN KEY (capability_key) REFERENCES capabilities(capability_key)
            )
            """
        )
        (summary["already_present"] if existed else summary["tables_created"]).append("role_capabilities")

        # --- 5. user_roles (explicit per-user role assignment) ---
        existed = _table_exists(conn, "user_roles")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_roles (
                username        TEXT PRIMARY KEY,
                role_key        TEXT NOT NULL,
                set_by_username TEXT,
                set_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                note            TEXT,
                FOREIGN KEY (role_key) REFERENCES roles(role_key)
            )
            """
        )
        (summary["already_present"] if existed else summary["tables_created"]).append("user_roles")

        # --- 6. user_capability_overrides ---
        existed = _table_exists(conn, "user_capability_overrides")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_capability_overrides (
                username        TEXT NOT NULL,
                capability_key  TEXT NOT NULL,
                override_type   TEXT NOT NULL CHECK(override_type IN ('grant', 'revoke')),
                set_by_username TEXT,
                set_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                note            TEXT,
                PRIMARY KEY (username, capability_key),
                FOREIGN KEY (capability_key) REFERENCES capabilities(capability_key)
            )
            """
        )
        (summary["already_present"] if existed else summary["tables_created"]).append("user_capability_overrides")

        # --- 7. approval_priority (foundation only — UI in Session 2) ---
        existed = _table_exists(conn, "approval_priority")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_priority (
                username        TEXT NOT NULL,
                capability_key  TEXT NOT NULL,
                priority        INTEGER NOT NULL,
                set_by_username TEXT,
                set_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (username, capability_key)
            )
            """
        )
        (summary["already_present"] if existed else summary["tables_created"]).append("approval_priority")

        conn.commit()
    finally:
        conn.close()

    return summary


# CLI entry-point for manual testing
if __name__ == "__main__":
    result = apply_rbac_migration()
    print("RBAC migration summary:")
    for key, items in result.items():
        print(f"  {key}: {items}")
