"""🔑 Users page (admin only) - manage app login credentials."""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import auth_config
from lib.page_utils import require_login, page_header

st.set_page_config(page_title="Users", page_icon="🔑", layout="wide")
require_login(admin_only=True)
page_header(title_key="users_title", subtitle_key="users_subtitle")

users = auth_config.list_users()
df = pd.DataFrame(users) if users else pd.DataFrame(columns=["username", "name", "role", "email"])

st.markdown("### Existing users")
st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown("---")
st.markdown("### Add a new user")
with st.form("add_user", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    new_user = c1.text_input("Username")
    new_name = c2.text_input("Display name")
    new_email = c3.text_input("Email (optional)")
    c4, c5 = st.columns(2)
    new_pass = c4.text_input("Password", type="password")
    new_role = c5.selectbox("Role", ["viewer", "manager", "admin"],
                             help="**viewer**: view-only.  **manager**: view + can submit "
                             "employee change requests.  **admin**: full access incl. uploads, "
                             "configuration, and approving change requests.")
    if st.form_submit_button("➕ Add user", type="primary"):
        if not new_user or not new_pass:
            st.error("Username and password required.")
        elif auth_config.add_user(new_user.strip(), new_name or new_user, new_pass, new_role, new_email):
            st.success(f"User `{new_user}` added.")
            st.rerun()
        else:
            st.error("That username already exists.")

st.markdown("---")
st.markdown("### Reset a password")
with st.form("change_pw"):
    c1, c2 = st.columns(2)
    target = c1.selectbox("User", [u["username"] for u in users])
    pw = c2.text_input("New password", type="password")
    if st.form_submit_button("🔄 Reset password"):
        if pw and auth_config.change_password(target, pw):
            st.success(f"Password for `{target}` updated.")
        else:
            st.error("Could not update.")

st.markdown("---")
st.markdown("### Remove a user")
with st.form("delete_user"):
    target = st.selectbox("User to remove", [u["username"] for u in users if u["username"] != st.session_state.username])
    confirm = st.checkbox("Yes, I want to permanently remove this user")
    if st.form_submit_button("🗑️ Delete user", type="secondary"):
        if not confirm:
            st.warning("Tick the confirm box first.")
        elif auth_config.delete_user(target):
            st.success(f"User `{target}` deleted.")
            st.rerun()
