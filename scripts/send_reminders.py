#!/usr/bin/env python3
# Daily reminder cron — emails every manager with leave/OT approvals
# pending > 24h. Run from GitHub Actions (manual §9) with env vars:
#   DATABASE_URL  (Supabase) and SMTP_* (host/port/user/password/from)
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

# Map env SMTP_* into the notify module (no streamlit secrets in cron)
import lib.notify as notify
notify._SMTP = {
    "host": os.environ.get("SMTP_HOST", ""),
    "port": os.environ.get("SMTP_PORT", "587"),
    "user": os.environ.get("SMTP_USER", ""),
    "password": os.environ.get("SMTP_PASSWORD", ""),
    "from": os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
    "app_url": os.environ.get("APP_URL",
                              "https://anca-hr-reporting.streamlit.app"),
}

from lib import approval_db
approval_db.migrate()
report = notify.send_pending_reminders(min_age_hours=24)
for r in report:
    print(r)
print(f"done — {len(report)} approver(s) reminded")
