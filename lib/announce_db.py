# lib/announce_db.py — admin-configurable pop-ups / announcements + consent.
# Media can be UPLOADED (image/video/pdf, stored as base64) or linked by URL
# (e.g. YouTube). Media is shown responsively (fits desktop/mobile screens).
# Consent: admin sets the body text + any number of tick-box items; the user
# must tick all to accept. Frequency via mode:
#   once         -> show one time per user (first time only)
#   until_accept -> keep showing until the user accepts (consent gate)
#   always       -> show every visit within the date window
import datetime as dt
import json
from lib.db import get_conn, IS_POSTGRES, PH

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"


def _addcol(conn, cur, col, decl):
    try:
        cur.execute(f"ALTER TABLE announcements ADD COLUMN {col} {decl}")
        conn.commit()
    except Exception:
        conn.rollback()


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS announcements (
        id {SERIAL}, title TEXT, body TEXT,
        media_type TEXT DEFAULT 'none', media_url TEXT,
        mode TEXT DEFAULT 'once', require_accept INTEGER DEFAULT 0,
        start_date TEXT, end_date TEXT, active INTEGER DEFAULT 1,
        created_by TEXT, created_at TEXT)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS announcement_acks (
        id {SERIAL}, announcement_id INTEGER, username TEXT,
        accepted INTEGER DEFAULT 0, acked_at TEXT)""")
    conn.commit()
    # new columns (uploaded media + responsive fit + multi-consent)
    _addcol(conn, cur, "media_data", "TEXT")     # base64 (no data: prefix)
    _addcol(conn, cur, "media_mime", "TEXT")     # e.g. image/png, video/mp4
    _addcol(conn, cur, "media_fit", "TEXT")      # width | contain | original
    _addcol(conn, cur, "consent_items", "TEXT")  # JSON list of tick labels


_COLS = ("id, title, body, media_type, media_url, media_data, media_mime, "
         "media_fit, mode, require_accept, consent_items, start_date, "
         "end_date, active, created_by, created_at")


def create(title, body, media_type="none", media_url=None, media_data=None,
           media_mime=None, media_fit="width", mode="once",
           require_accept=False, consent_items=None, start_date=None,
           end_date=None, actor="admin"):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""INSERT INTO announcements (title, body, media_type,
        media_url, media_data, media_mime, media_fit, mode, require_accept,
        consent_items, start_date, end_date, active, created_by, created_at)
        VALUES ({','.join([PH]*14)},1,{PH},{PH})"""
                .replace(",1,", ", 1, ") if False else
                f"""INSERT INTO announcements (title, body, media_type,
        media_url, media_data, media_mime, media_fit, mode, require_accept,
        consent_items, start_date, end_date, active, created_by, created_at)
        VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},1,
        {PH},{PH})""",
                (title, body, media_type or "none", media_url, media_data,
                 media_mime, media_fit or "width", mode,
                 1 if require_accept else 0,
                 json.dumps(consent_items or []),
                 str(start_date) if start_date else None,
                 str(end_date) if end_date else None, actor,
                 dt.datetime.now().isoformat(timespec="seconds")))
    conn.commit()


def list_all():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT {_COLS} FROM announcements ORDER BY id DESC")
    cols = [d[0] for d in cur.description]
    out = []
    for r in cur.fetchall():
        d = dict(zip(cols, r)) if IS_POSTGRES else dict(r)
        try:
            d["consent_list"] = json.loads(d.get("consent_items") or "[]")
        except Exception:
            d["consent_list"] = []
        out.append(d)
    return out


def set_active(aid, active):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"UPDATE announcements SET active={PH} WHERE id={PH}",
                (1 if active else 0, aid))
    conn.commit()


def delete(aid):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"DELETE FROM announcements WHERE id={PH}", (aid,))
    cur.execute(f"DELETE FROM announcement_acks WHERE announcement_id={PH}",
                (aid,))
    conn.commit()


def ack(aid, username, accepted=True):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""INSERT INTO announcement_acks (announcement_id, username,
        accepted, acked_at) VALUES ({PH},{PH},{PH},{PH})""",
                (aid, username, 1 if accepted else 0,
                 dt.datetime.now().isoformat(timespec="seconds")))
    conn.commit()


def _acked(aid, username):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT accepted FROM announcement_acks
        WHERE announcement_id={PH} AND username={PH}
        ORDER BY id DESC LIMIT 1""", (aid, username))
    return cur.fetchone()


def pending_for(username):
    today = dt.date.today().isoformat()
    for a in list_all():
        if not a["active"]:
            continue
        if a["start_date"] and a["start_date"] > today:
            continue
        if a["end_date"] and a["end_date"] < today:
            continue
        seen = _acked(a["id"], username)
        if a["mode"] == "always":
            return a
        if a["mode"] == "until_accept":
            if not seen or not seen[0]:
                return a
            continue
        if not seen:   # once
            return a
    return None


def list_acks(announcement_id=None):
    conn = get_conn(); cur = conn.cursor()
    if announcement_id:
        cur.execute(f"""SELECT k.username, k.accepted, k.acked_at, a.title,
            a.id FROM announcement_acks k JOIN announcements a
            ON a.id=k.announcement_id WHERE k.announcement_id={PH}
            ORDER BY k.id DESC""", (announcement_id,))
    else:
        cur.execute("""SELECT k.username, k.accepted, k.acked_at, a.title,
            a.id FROM announcement_acks k JOIN announcements a
            ON a.id=k.announcement_id ORDER BY k.id DESC""")
    return [{"username": r[0], "accepted": r[1], "acked_at": r[2],
             "title": r[3], "announcement_id": r[4]} for r in cur.fetchall()]
