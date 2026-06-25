# lib/approver_tools.py
# Helpers for the approver review panel: prefilled email (Outlook/mailto) links
# and reminder subject/body text. mailto opens the user's default mail client
# (Outlook for most corporate users); a body can be prefilled but file
# attachments cannot — the printable PDF is offered separately to attach.
import urllib.parse

_LABEL = {"leave": "Leave", "ot": "OT", "shift": "Shift change",
          "timeedit": "Time edit", "time_edit": "Time edit",
          "resign": "Resignation"}


def outlook_mailto(to, subject, body):
    qs = urllib.parse.urlencode({"subject": subject or "", "body": body or ""},
                                quote_via=urllib.parse.quote)
    return f"mailto:{urllib.parse.quote(to or '')}?{qs}"


def outlook_web(to, subject, body):
    qs = urllib.parse.urlencode(
        {"to": to or "", "subject": subject or "", "body": body or ""},
        quote_via=urllib.parse.quote)
    return f"https://outlook.office.com/mail/deeplink/compose?{qs}"


def _detail_line(kind, row):
    if kind == "leave":
        return (f"Type: {row.get('leave_type', '')}  "
                f"Dates: {row.get('date_from', '')} to "
                f"{row.get('date_to', '')} ({row.get('days', '')} day(s))")
    if kind == "ot":
        return (f"Date: {row.get('ot_date', '')}  "
                f"{row.get('time_from', '')}-{row.get('time_to', '')} "
                f"({row.get('hours', '')}h)")
    if kind == "shift":
        return (f"{row.get('current_shift', '')} -> "
                f"{row.get('requested_shift', '')} from "
                f"{row.get('date_from', '')}")
    if kind in ("timeedit", "time_edit"):
        return (f"Work date: {row.get('work_date', '')}  "
                f"in {row.get('req_time_in', '')} / "
                f"out {row.get('req_time_out', '')}")
    return f"Last working day: {row.get('last_working_day', '')}"


def reminder_text(kind, row, recipient_name=""):
    """(subject, body) prefilled for an Outlook reminder about this request."""
    label = _LABEL.get(kind, kind)
    doc = row.get("doc_no") or ""
    subject = f"[AMS HR] {label} request {doc} — {recipient_name}".strip()
    body = "\n".join([
        f"Dear {recipient_name or 'colleague'},",
        "",
        f"This is a reminder regarding the {label} request {doc}.",
        _detail_line(kind, row),
        "",
        f"Reason: {row.get('reason', '') or '-'}",
        "",
        "Please action this request at your earliest convenience.",
        "",
        "Regards,",
        "ANCA Manufacturing Solutions (Thailand) — HR",
    ])
    return subject, body
