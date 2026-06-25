# lib/notify.py
# ============================================================================
# Email notifications for the approval flow (requirement, 12 Jun):
#   - when a request reaches an approver's level -> email that manager
#   - final approval / rejection                 -> email the requester
#   - REMINDERS: "Send reminders now" button (HR) emails every manager whose
#     queue has items pending longer than N hours; the same function can run
#     daily via GitHub Actions cron (see manual §9) for true automation.
#
# SMTP settings live in .streamlit/secrets.toml — NEVER in code:
#   [smtp]
#   host = "smtp.office365.com"      # or smtp.gmail.com with app password
#   port = 587
#   user = "hr-noreply@anca.com"
#   password = "..."
#   from = "AMS HR System <hr-noreply@anca.com>"
# If [smtp] is missing the app still works — emails are skipped and the UI
# says so, instead of crashing.
# ============================================================================
import smtplib
import datetime as dt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    import streamlit as st
    _SMTP = dict(st.secrets.get("smtp", {}))
except Exception:
    _SMTP = {}

APP_URL = _SMTP.get("app_url", "https://anca-hr-reporting.streamlit.app")

# ---- LINE Messaging API (@529aaynp) ----------------------------------------
# secrets:
#   [line]
#   token = "channel access token"
# The recipient userId comes from users.line_user_id (linked in System Admin
# or My Profile). Push is best-effort: failures never block the workflow.
try:
    import streamlit as _st
    _LINE_TOKEN = dict(_st.secrets.get("line", {})).get("token", "")
except Exception:
    _LINE_TOKEN = ""


def line_configured():
    return bool(_LINE_TOKEN)


def line_push(user_id, text):
    """Push a LINE message. Returns (ok, msg). Never raises."""
    if not user_id:
        return False, "no LINE userId linked"
    if not _LINE_TOKEN:
        return False, "LINE token not configured — skipped"
    try:
        import json as _json
        import urllib.request
        req = urllib.request.Request(
            "https://api.line.me/v2/bot/message/push",
            data=_json.dumps({"to": user_id,
                              "messages": [{"type": "text",
                                            "text": text[:4900]}]}).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {_LINE_TOKEN}"})
        urllib.request.urlopen(req, timeout=10)
        return True, "LINE sent"
    except Exception as e:
        return False, f"LINE failed: {e}"



def smtp_configured():
    return all(_SMTP.get(k) for k in ("host", "port", "user", "password"))


def send_email(to, subject, html):
    """Returns (ok, message). Never raises into the page."""
    if not to:
        return False, "no recipient email on file"
    if not smtp_configured():
        return False, "SMTP not configured in secrets — email skipped"
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = _SMTP.get("from", _SMTP["user"])
        msg["To"] = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(_SMTP["host"], int(_SMTP["port"]),
                          timeout=20) as s:
            s.starttls()
            s.login(_SMTP["user"], _SMTP["password"])
            s.send_message(msg)
        return True, f"sent to {to}"
    except Exception as e:
        return False, f"email failed: {e}"


def _wrap(title, body_html):
    return f"""
    <div style="font-family:Arial,'Sarabun',sans-serif;max-width:560px">
      <div style="background:linear-gradient(135deg,#009ADE,#715091);
                  color:#fff;padding:14px 18px;border-radius:10px 10px 0 0">
        <b>ANCA (AMS) Thailand — HR System</b></div>
      <div style="border:1px solid #e4e8f0;border-top:0;padding:16px 18px;
                  border-radius:0 0 10px 10px">
        <h3 style="margin:0 0 10px">{title}</h3>{body_html}
        <p style="margin-top:14px">
          <a href="{APP_URL}" style="background:#715091;color:#fff;
             padding:9px 16px;border-radius:8px;text-decoration:none">
             เปิดระบบ / Open the HR system</a></p>
        <p style="color:#888;font-size:12px">อีเมลอัตโนมัติ กรุณาอย่าตอบกลับ /
           Automated message — please do not reply.</p>
      </div></div>"""


def _req_summary(kind, req):
    if kind == "timeedit":
        return (f"<p><b>{req.get('emp_no')}</b> — แก้ไขเวลา {req.get('work_date')} "
                f"({req.get('req_time_in') or '-'}–{req.get('req_time_out') or '-'})"
                f"<br>เหตุผล: {req.get('reason') or '—'}</p>")
    if kind == "shift":
        return (f"<p><b>{req.get('emp_no')}</b> — เปลี่ยนกะ "
                f"{req.get('current_shift')} → {req.get('requested_shift')} "
                f"({req.get('date_from')}"
                f"{(' → ' + str(req.get('date_to'))) if req.get('date_to') else ''})"
                f"<br>เหตุผล: {req.get('reason') or '—'}</p>")
    if kind not in ("leave", "ot"):
        return (f"<p><b>{req.get('doc_no') or req.get('po_no') or ''}</b> — "
                f"{req.get('summary') or req.get('purpose') or ''}</p>")
    if kind == "leave":
        return (f"<p><b>{req.get('emp_no')}</b> — ลา "
                f"{req.get('leave_type')} "
                f"{req.get('date_from')} → {req.get('date_to')} "
                f"({req.get('days')} วัน)<br>"
                f"เหตุผล: {req.get('reason') or '—'}</p>")
    return (f"<p><b>{req.get('emp_no')}</b> — OT {req.get('ot_date')} "
            f"{req.get('time_from')}–{req.get('time_to')} "
            f"({req.get('hours')} ชม. × {req.get('rate')})<br>"
            f"งาน: {req.get('reason') or '—'}</p>")


KIND_LABELS = {"leave": "การลา / Leave", "ot": "โอที / OT",
               "po": "การสั่งซื้อ / Purchase", "car": "จองรถ / Car booking",
               "permit_out": "นำของออกโรงงาน / Take-out permit",
               "permit_entry": "ผ่านเข้า-ออก / Entry card",
               "stock": "เบิกของ / Stock issue",
               "resign": "การลาออก / Resignation",
               "shift": "เปลี่ยนกะ / Shift change",
               "timeedit": "แก้ไขเวลา / Time edit"}


def _kind_label(kind):
    return KIND_LABELS.get(kind, kind)


def notify_approver(kind, req, approver):
    """Unified channel notify: email + LINE push (both best-effort).
    approver: dict with approver_name / approver_email / level (+ optional
    approver_emp_no for the LINE lookup)."""
    kind_th = _kind_label(kind)
    title = (f"[รออนุมัติ L{approver['level']}] คำขอ{kind_th}")
    body = (f"<p>เรียนคุณ {approver['approver_name']},</p>"
            f"<p>มีคำขอรอการอนุมัติของท่าน (ระดับที่ "
            f"{approver['level']} ในสายบังคับบัญชา) / A request is waiting "
            f"for your level-{approver['level']} approval:</p>"
            + _req_summary(kind, req))
    ok_mail, m1 = send_email(approver.get("approver_email"), title,
                             _wrap(title, body))
    # LINE push to the approver if linked
    m2 = ""
    try:
        from lib.auth import line_id_for_emp
        lid = line_id_for_emp(approver.get("approver_emp_no") or "")
        ok_line, m2 = line_push(
            lid, f"🔔 {title}\nเปิดระบบเพื่ออนุมัติ / Approve here: {APP_URL}")
    except Exception:
        pass
    return ok_mail, f"{m1}" + (f" • {m2}" if m2 else "")


def notify_requester(kind, req, requester_email, final_status, note="",
                     requester_emp_no=None):
    kind_th = _kind_label(kind)
    th = "อนุมัติแล้ว ✅" if final_status == "approved" else "ไม่อนุมัติ ❌"
    title = f"คำขอ{kind_th}ของคุณ: {th}"
    body = (_req_summary(kind, req) +
            (f"<p>หมายเหตุผู้อนุมัติ / Approver note: {note}</p>"
             if note else ""))
    ok, m1 = send_email(requester_email, title, _wrap(title, body))
    if requester_emp_no:
        try:
            from lib.auth import line_id_for_emp
            line_push(line_id_for_emp(requester_emp_no),
                      f"📢 {title}" + (f"\nหมายเหตุ: {note}" if note else ""))
        except Exception:
            pass
    return ok, m1


def send_pending_reminders(min_age_hours=24, remind_gap_hours=24):
    """Email every approver whose queue holds requests pending longer than
    min_age_hours, at most once per remind_gap_hours. Returns a report list.
    Call from the HR button in Leave & OT → Admin, or daily via the
    GitHub Actions cron in scripts/send_reminders.py."""
    from lib import approval_db as adb
    now = dt.datetime.now()
    report = []
    by_approver = {}
    for a in adb.pending_overview():
        key = (a["approver_emp_no"], a["approver_email"],
               a["approver_name"])
        by_approver.setdefault(key, []).append(a)
    for (emp_no, email, name), items in by_approver.items():
        due = []
        for a in items:
            ref = a.get("last_reminded_at") or a.get("requested_at") or ""
            try:
                age = (now - dt.datetime.fromisoformat(ref)).total_seconds()
            except (ValueError, TypeError):
                age = 1e9
            if age >= min_age_hours * 3600:
                due.append(a)
        if not due:
            continue
        lines = "".join(
            f"<li>{a['request_kind'].upper()} — {a['req_emp_no']} "
            f"{a['req_name']} (L{a['level']})</li>" for a in due)
        title = (f"⏰ เตือนความจำ: มี {len(due)} คำขอรอการอนุมัติของท่าน / "
                 f"{len(due)} request(s) awaiting your approval")
        ok, msg = send_email(email, title, _wrap(
            title, f"<p>เรียนคุณ {name},</p><ul>{lines}</ul>"))
        if ok:
            for a in due:
                adb.mark_reminded(a["id"])
        report.append({"approver": name, "email": email,
                       "items": len(due), "result": msg})
    return report
