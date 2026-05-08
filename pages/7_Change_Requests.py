"""🔄 Change Requests page.
- Admin: see all requests (filterable by status), approve/reject pending ones.
- Manager: see only own requests (any status).
- Viewer: not allowed.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import db
from lib.page_utils import require_login, page_header, is_admin

st.set_page_config(page_title="Change Requests", page_icon="🔄", layout="wide")
require_login(any_capability=["report.submit_changes", "report.approve_changes"])
page_header(title_key="creq_title", subtitle_key="creq_subtitle")

FIELD_LABELS = {
    "cost_code": "Cost Code",
    "emp_type":  "Employment Type",
    "d_in":      "Direct / Indirect",
    "level":     "Level",
    "emp_name":  "Employee Name",
}


def _show_table(reqs: list[dict], title: str, with_actions: bool = False):
    if not reqs:
        st.info(f"No {title.lower()} requests.")
        return

    st.markdown(f"#### {title}  ({len(reqs)})")

    if with_actions:
        # Render each pending request as an expandable card with Approve / Reject buttons
        for r in reqs:
            with st.container(border=True):
                top = st.columns([3, 2, 2, 1])
                top[0].markdown(
                    f"**Request #{r['id']}** — Employee `{r['emp_no']}` "
                    f"({r.get('emp_name') or '?'})"
                )
                top[1].markdown(f"Field: **{FIELD_LABELS.get(r['field_name'], r['field_name'])}**")
                top[2].markdown(f"Submitted by: `{r['submitted_by']}`")
                top[3].markdown(f"<small>{r['submitted_at']}</small>", unsafe_allow_html=True)

                mid = st.columns([1, 1, 3])
                mid[0].markdown(f"**Old:** `{r['old_value'] or '(empty)'}`")
                mid[1].markdown(f"**New:** `{r['new_value']}`")
                mid[2].markdown(f"**Reason:** {r['reason']}")

                # Action row (admin only)
                if is_admin() and r["status"] == "pending":
                    notes_key = f"notes_{r['id']}"
                    bot = st.columns([4, 1, 1])
                    review_notes = bot[0].text_input(
                        "Review notes (optional)", key=notes_key, label_visibility="collapsed",
                        placeholder="Optional notes for approve/reject...",
                    )
                    if bot[1].button("✅ Approve", key=f"appr_{r['id']}", type="primary",
                                      use_container_width=True):
                        if db.approve_change_request(r["id"], st.session_state.username, review_notes):
                            st.success(f"Approved request #{r['id']} and updated employee record.")
                            st.rerun()
                        else:
                            st.error("Could not apply change.")
                    if bot[2].button("❌ Reject", key=f"rej_{r['id']}", use_container_width=True):
                        if db.reject_change_request(r["id"], st.session_state.username, review_notes):
                            st.success(f"Rejected request #{r['id']}.")
                            st.rerun()
    else:
        cols = ["id", "submitted_at", "emp_no", "emp_name", "field_name",
                "old_value", "new_value", "reason", "status",
                "submitted_by", "reviewed_by", "reviewed_at", "review_notes"]
        df = pd.DataFrame(reqs)
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        df = df[cols].rename(columns={
            "id": "ID", "submitted_at": "Submitted", "emp_no": "Emp #",
            "emp_name": "Name", "field_name": "Field",
            "old_value": "Old", "new_value": "New", "reason": "Reason",
            "status": "Status", "submitted_by": "Submitted by",
            "reviewed_by": "Reviewed by", "reviewed_at": "Reviewed at",
            "review_notes": "Notes",
        })
        st.dataframe(df, use_container_width=True, hide_index=True)


if is_admin():
    pending = db.list_change_requests(status="pending")
    _show_table(pending, "Pending requests", with_actions=True)

    st.markdown("---")
    tab_a, tab_r, tab_all = st.tabs(["✅ Approved", "❌ Rejected", "📋 All"])
    with tab_a:
        _show_table(db.list_change_requests(status="approved"), "Approved")
    with tab_r:
        _show_table(db.list_change_requests(status="rejected"), "Rejected")
    with tab_all:
        _show_table(db.list_change_requests(), "All")
else:
    # Manager view: only their own
    me = st.session_state.username
    _show_table(db.list_change_requests(submitted_by=me), "Your submissions")
    st.caption(
        "💡 To submit a new change request, go to the **👥 Employees** page → "
        "scroll to the bottom → use the *Request a change* form."
    )
