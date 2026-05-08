"""
Login Audit page (admin only) — shows every sign-in attempt with IP, device,
and outcome. Useful for security review.
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

st.set_page_config(page_title="Login Audit", page_icon="🛡️", layout="wide")
require_login(capability="system.view_audit")
page_header(title_key="audit_title", subtitle_key="audit_subtitle")

# Filters
f1, f2, f3, f4 = st.columns([2, 2, 2, 2])
only_admin = f1.toggle(t("filter_only_admin"), value=False)
only_failures = f2.toggle(t("filter_only_failures"), value=False)
filter_user = f3.text_input("Filter by username", "")
limit = f4.number_input("Show last N rows", min_value=50, max_value=2000,
                          value=200, step=50)

rows = db.get_login_audit(
    limit=int(limit),
    username=filter_user.strip() or None,
    only_admin=only_admin,
    only_failures=only_failures,
)

# Summary metrics
m1, m2, m3, m4 = st.columns(4)
total = len(rows)
successes = sum(1 for r in rows if r["success"])
failures = total - successes
unique_users = len({r["username"] for r in rows if r["username"]})
unique_ips = len({r["ip_address"] for r in rows if r["ip_address"]})
m1.metric("Total events", total)
m2.metric("Successful", successes)
m3.metric("Failed", failures)
m4.metric("Unique users / IPs", f"{unique_users} / {unique_ips}")

if not rows:
    st.info("No login events match the filters.")
    st.stop()

# Build display
df = pd.DataFrame(rows)
df["Status"] = df["success"].apply(lambda s: t("successful") if s else t("failed"))
df["When"] = df["occurred_at"]
df["User"] = df["username"]
df["Role"] = df["role_at_login"].fillna("")
df["IP"] = df["ip_address"]
df["Device"] = df["user_agent"].fillna("").str.slice(0, 60)
df["Reason"] = df["failure_reason"].fillna("")

display = df[["Status", "When", "User", "Role", "IP", "Device", "Reason"]]
st.dataframe(display, use_container_width=True, hide_index=True, height=600)

# Download
csv = display.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download as CSV", data=csv,
                    file_name="login_audit.csv", mime="text/csv")
