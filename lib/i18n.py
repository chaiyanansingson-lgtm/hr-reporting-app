# lib/i18n.py — lightweight Thai/English layer for the app shell.
import streamlit as st
DEFAULT = "th"
TR = {
    "menu": {"th": "เมนู", "en": "Menu"},
    "home": {"th": "หน้าหลัก", "en": "Home"},
    "search_modules": {"th": "ค้นหาเมนู…", "en": "Search modules…"},
    "notifications": {"th": "การแจ้งเตือน", "en": "Notifications"},
    "nothing_pending": {"th": "ไม่มีรายการที่ต้องดำเนินการ 🎉",
                        "en": "Nothing pending 🎉"},
    "pending": {"th": "รออนุมัติ", "en": "pending"},
    "role": {"th": "บทบาท", "en": "Role"},
    "profile": {"th": "โปรไฟล์", "en": "Profile"},
    "sign_out": {"th": "ออกจากระบบ", "en": "Sign out"},
    "language": {"th": "ภาษา", "en": "Language"},
    "help": {"th": "คู่มือการใช้งาน", "en": "Help & manuals"},
    "help_search": {"th": "ค้นหาวิธีใช้…", "en": "Search how-to…"},
    "your_modules": {"th": "โมดูลที่ใช้ได้", "en": "Your modules"},
    "enter": {"th": "เข้าใช้งาน", "en": "Enter"},
    "welcome": {"th": "ยินดีต้อนรับ", "en": "Welcome"},
}


def cur_lang():
    return st.session_state.get("lang", DEFAULT)


def set_lang(l):
    st.session_state["lang"] = l


def t(key):
    return TR.get(key, {}).get(cur_lang(), key)
