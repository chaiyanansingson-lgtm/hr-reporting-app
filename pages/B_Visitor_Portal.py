# pages/B_Visitor_Portal.py
# Landing page for visitors: job application + entrance permit shortcuts.
# (Car booking removed from the visitor scope per v3 — staff module only.)
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme
from lib.auth import require_capability

_theme.inject()
require_capability("visitor.access")

st.title("🚪 Visitor Portal")
st.markdown("""
ยินดีต้อนรับสู่ ANCA Manufacturing Solutions (Thailand)

- 📝 **สมัครงาน / Job application** — เปิดหน้า *Candidate Portal* จากแถบซ้าย
- 🪪 **ขอใบอนุญาตผ่านเข้า-ออก / Entrance permit (ENTRY-CARD)** — แจ้งพนักงานที่ท่านมาติดต่อให้ยื่นคำขอในหน้า *Permits* แล้วรับบัตรที่ป้อม รปภ.

Welcome! Use the left sidebar: *Candidate Portal* to apply for a job, or
ask your AMS contact person to file an ENTRY-CARD in *Permits*; collect it at the security gate.
""")
