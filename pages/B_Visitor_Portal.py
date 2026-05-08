"""
pages/B_Visitor_Portal.py — External Visitor Portal (Safety Standards).
v11.4 — RBAC Phase 1 foundation (2026-05-08).

Per user spec 2026-05-08: the Visitor role is for outer/external guests
who need safety-standard related functions. They MUST NOT see any
company information. Only the Visitor card appears on their landing page,
and only this page is reachable for them by default.

Real safety-standards content is filled in a future session — this file
establishes the route, the capability gate, the i18n shell, and the
Anca CI styling.
"""
import streamlit as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.page_utils import require_login, page_header
from lib import auth
from lib.i18n import t

st.set_page_config(page_title="Visitor Portal", page_icon="🛡️", layout="wide")

# Two-stage gate:
#   1. require_login renders the branded sidebar and stops if not logged in
#   2. require_capability checks the Visitor capability (visitor.access)
require_login(capability="visitor.access")

page_header(title="🛡️ " + t("visitor_portal_title"),
            subtitle=t("visitor_portal_subtitle"))

th = (st.session_state.get("lang") or "th").lower().startswith("th")

# ----------------------------------------------------------------------------
# Sections — placeholders only (no company data exposed)
# ----------------------------------------------------------------------------
sections_th = [
    ("📋 มาตรฐานความปลอดภัย",
     "ข้อกำหนดและขั้นตอนความปลอดภัยทั่วไปสำหรับผู้เยี่ยมชม (อยู่ระหว่างจัดทำ)"),
    ("🚨 ขั้นตอนกรณีฉุกเฉิน",
     "เส้นทางอพยพ จุดรวมพล และเบอร์ติดต่อฉุกเฉิน (อยู่ระหว่างจัดทำ)"),
    ("📝 ลงทะเบียนเข้าพื้นที่",
     "แบบฟอร์มลงทะเบียนผู้เยี่ยมชมและการรับบัตรผ่าน (อยู่ระหว่างจัดทำ)"),
    ("📞 การติดต่อในเหตุการณ์",
     "ช่องทางรายงานเหตุและการติดต่อหน่วยความปลอดภัย (อยู่ระหว่างจัดทำ)"),
]
sections_en = [
    ("📋 Safety Standards",
     "General safety requirements and procedures for visitors (in preparation)."),
    ("🚨 Emergency Procedures",
     "Evacuation routes, assembly points, and emergency contacts (in preparation)."),
    ("📝 Visitor Sign-in",
     "Visitor registration form and access pass issuance (in preparation)."),
    ("📞 Incident Reporting",
     "Channels for reporting incidents and contacting the safety team (in preparation)."),
]
sections = sections_th if th else sections_en

cols = st.columns(2, gap="large")
for i, (title_text, body) in enumerate(sections):
    with cols[i % 2]:
        with st.container(border=True):
            st.markdown(f"### {title_text}")
            st.write(body)
            st.caption("🚧 " + ("เร็ว ๆ นี้" if th else "Coming soon"))

st.divider()
contact_msg = (
    "หากต้องการความช่วยเหลือ กรุณาติดต่อแผนกความปลอดภัย ณ จุดต้อนรับ"
    if th
    else "For assistance, please contact the safety officer at the reception desk."
)
st.info("ℹ️ " + contact_msg)
