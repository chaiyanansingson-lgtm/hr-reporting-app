# pages/R_Manual.py — Employees' Manual (serves the bundled handbook PDF)
import os
import streamlit as st
from lib import theme as _theme
from lib.auth import require_capability

require_capability("self.view_profile")
_theme.inject()
st.title("📘 คู่มือพนักงาน / Employees' Manual")

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_pdf = os.path.join(_root, "assets", "manual_th_en.pdf")

if not os.path.exists(_pdf):
    st.info("ยังไม่มีไฟล์คู่มือในระบบ — ผู้ดูแลระบบสามารถอัปโหลดได้ในโมดูล Admin / "
            "No manual uploaded yet; an admin can add it in the Admin module.")
    st.stop()

with open(_pdf, "rb") as fh:
    data = fh.read()

st.caption("คู่มือพนักงานฉบับล่าสุด (ไทย/อังกฤษ) · Latest employee handbook (TH/EN).")
st.download_button("⬇️ ดาวน์โหลดคู่มือ (PDF) / Download manual", data,
                   file_name="AMS_Employees_Manual.pdf", type="primary")

try:
    import fitz
    d = fitz.open(stream=data, filetype="pdf")
    with st.expander(f"พรีวิว · Preview ({d.page_count} หน้า/pages)", expanded=True):
        for i in range(min(d.page_count, 12)):
            png = d[i].get_pixmap(matrix=fitz.Matrix(1.4, 1.4)).tobytes("png")
            st.image(png, use_container_width=True)
        if d.page_count > 12:
            st.caption(f"… อีก {d.page_count - 12} หน้า — ดาวน์โหลดเพื่อดูทั้งหมด / "
                       f"{d.page_count - 12} more pages in the download.")
except Exception:
    st.caption("ดาวน์โหลดเพื่อเปิดอ่าน / Download to view.")
