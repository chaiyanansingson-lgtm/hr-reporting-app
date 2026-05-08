"""
Sign-up Requests page — admin reviews account requests submitted via the sign-up
form on the login page. Approval creates the user account; rejection records
the reason. Every action is audit-logged.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import db
from lib.page_utils import require_login, page_header
from lib.i18n import t
from config import auth_config

st.set_page_config(page_title="Sign-up Requests", page_icon="📝", layout="wide")
require_login(capability="system.manage_users")
page_header(title_key="signup_review_title", subtitle_key="signup_review_subtitle")


def _show_pending(reqs: list[dict]):
    if not reqs:
        st.info(f"No {t('pending_requests').lower()} requests.")
        return

    for r in reqs:
        with st.container(border=True):
            top = st.columns([3, 2, 2])
            top[0].markdown(
                f"**Request #{r['id']}** — `{r['requested_username']}`"
                f" ({r.get('requested_full_name') or '?'})"
            )
            top[1].markdown(f"📧 {r.get('requested_email','')}")
            top[2].markdown(f"<small>{r['submitted_at']}</small>", unsafe_allow_html=True)

            mid = st.columns([1, 1, 1, 1])
            mid[0].markdown(f"**Requested role:** `{r.get('requested_role','viewer')}`")
            mid[1].markdown(f"**Emp #:** `{r.get('requested_emp_no') or '—'}`")
            mid[2].markdown(f"**{t('ip_address')}:** `{r.get('request_ip') or '—'}`")
            mid[3].markdown(f"<small>**{t('user_agent')}:** {(r.get('request_user_agent') or '—')[:50]}</small>",
                            unsafe_allow_html=True)

            st.markdown(f"**Reason:** {r.get('reason') or '(no reason provided)'}")

            # If they gave an emp_no, show whether it matches an active employee
            if r.get('requested_emp_no'):
                emp = db.get_employee_extended(r['requested_emp_no'])
                if emp:
                    st.success(f"✓ Matches active employee: {emp.get('emp_name')} "
                               f"({emp.get('title') or '?'}, {emp.get('dept_by_location') or '?'})")
                else:
                    st.warning(f"⚠ Employee #{r['requested_emp_no']} not found in active employee list.")

            # Action row
            granted_role = st.selectbox(
                t("grant_role"),
                ["viewer", "manager", "admin"],
                index=["viewer", "manager", "admin"].index(r.get("requested_role", "viewer"))
                       if r.get("requested_role") in ("viewer", "manager", "admin") else 0,
                key=f"grant_{r['id']}",
                format_func=lambda x: {"viewer": t("role_viewer"), "manager": t("role_manager"),
                                         "admin": t("role_admin")}[x],
            )
            review_notes = st.text_input(
                t("review_notes"),
                key=f"notes_{r['id']}",
                placeholder="e.g. confirmed via phone with Khun Somchai",
            )
            bot = st.columns([4, 1, 1])
            if bot[1].button(f"✅  {t('approve')}", key=f"appr_{r['id']}",
                              type="primary", use_container_width=True):
                # 1. Create the user account
                ok = auth_config.add_user_from_hash(
                    username=r["requested_username"],
                    name=r.get("requested_full_name") or r["requested_username"],
                    password_hash=r["password_hash"],
                    role=granted_role,
                    email=r.get("requested_email", ""),
                )
                # 2. Mark the request approved
                if ok:
                    db.mark_signup_reviewed(r["id"], st.session_state.username,
                                              "approved", granted_role, review_notes)
                    st.success(
                        f"✅ Approved request #{r['id']}. User `{r['requested_username']}` "
                        f"can now sign in with role `{granted_role}`."
                    )
                    st.rerun()
                else:
                    st.error("Could not create user — username may already exist.")

            if bot[2].button(f"❌  {t('reject')}", key=f"rej_{r['id']}", use_container_width=True):
                db.mark_signup_reviewed(r["id"], st.session_state.username,
                                          "rejected", "", review_notes)
                st.success(f"Rejected request #{r['id']}.")
                st.rerun()


def _show_decided(reqs: list[dict], status: str):
    if not reqs:
        st.info(f"No {status} requests yet.")
        return
    cols = ["id", "submitted_at", "requested_username", "requested_full_name",
            "requested_email", "requested_role", "granted_role",
            "reviewed_by", "reviewed_at", "review_notes", "request_ip"]
    df = pd.DataFrame(reqs)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df = df[cols].rename(columns={
        "id": "ID", "submitted_at": "Submitted",
        "requested_username": "Username", "requested_full_name": "Name",
        "requested_email": "Email", "requested_role": "Requested role",
        "granted_role": "Granted role", "reviewed_by": "Reviewed by",
        "reviewed_at": "Reviewed at", "review_notes": "Notes",
        "request_ip": "IP",
    })
    st.dataframe(df, use_container_width=True, hide_index=True)


pending = db.list_signup_requests(status="pending")
approved = db.list_signup_requests(status="approved")
rejected = db.list_signup_requests(status="rejected")

st.markdown(f"### {t('pending_requests')} ({len(pending)})")
_show_pending(pending)

st.markdown("---")
tab_a, tab_r = st.tabs([f"✅ {t('approved_requests')} ({len(approved)})",
                         f"❌ {t('rejected_requests')} ({len(rejected)})"])
with tab_a:
    _show_decided(approved, "approved")
with tab_r:
    _show_decided(rejected, "rejected")
