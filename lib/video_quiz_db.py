# lib/video_quiz_db.py — interactive video quizzes with questions that pop up
# at specific timestamps while a video plays. Question types (Google-Forms
# style): single choice, multiple choice, true/false, short answer.
import datetime as dt
import json
from lib.db import get_conn, IS_POSTGRES, PH

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS vq_courses (
        id {SERIAL}, title TEXT, video_type TEXT DEFAULT 'youtube',
        youtube_id TEXT, video_data TEXT, video_mime TEXT,
        pass_pct REAL DEFAULT 70, created_by TEXT, created_at TEXT)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS vq_questions (
        id {SERIAL}, course_id INTEGER, t_seconds INTEGER, qtype TEXT,
        prompt TEXT, options TEXT, correct TEXT, points INTEGER DEFAULT 1)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS vq_attempts (
        id {SERIAL}, course_id INTEGER, username TEXT, score REAL,
        max_score REAL, passed INTEGER, taken_at TEXT)""")
    conn.commit()


def create_course(title, video_type, youtube_id, video_data, video_mime,
                  pass_pct, actor):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""INSERT INTO vq_courses (title, video_type, youtube_id,
        video_data, video_mime, pass_pct, created_by, created_at)
        VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
                (title, video_type, youtube_id, video_data, video_mime,
                 float(pass_pct), actor,
                 dt.datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    if IS_POSTGRES:
        cur.execute("SELECT currval(pg_get_serial_sequence('vq_courses','id'))")
        return cur.fetchone()[0]
    return cur.lastrowid


def list_courses():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""SELECT id, title, video_type, youtube_id, video_data,
        video_mime, pass_pct, created_by, created_at FROM vq_courses
        ORDER BY id DESC""")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


def get_course(cid):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""SELECT id, title, video_type, youtube_id, video_data,
        video_mime, pass_pct FROM vq_courses WHERE id=%s""".replace("%s", PH),
                (cid,))
    r = cur.fetchone()
    if not r:
        return None
    cols = ["id", "title", "video_type", "youtube_id", "video_data",
            "video_mime", "pass_pct"]
    return dict(zip(cols, r)) if IS_POSTGRES else dict(r)


def delete_course(cid):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"DELETE FROM vq_courses WHERE id={PH}", (cid,))
    cur.execute(f"DELETE FROM vq_questions WHERE course_id={PH}", (cid,))
    conn.commit()


def add_question(course_id, t_seconds, qtype, prompt, options, correct,
                 points=1):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""INSERT INTO vq_questions (course_id, t_seconds, qtype,
        prompt, options, correct, points) VALUES
        ({PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
                (course_id, int(t_seconds), qtype, prompt,
                 json.dumps(options or []), json.dumps(correct),
                 int(points)))
    conn.commit()


def questions(course_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT id, t_seconds, qtype, prompt, options, correct,
        points FROM vq_questions WHERE course_id={PH}
        ORDER BY t_seconds, id""", (course_id,))
    out = []
    for r in cur.fetchall():
        out.append({"id": r[0], "t_seconds": r[1], "qtype": r[2],
                    "prompt": r[3], "options": json.loads(r[4] or "[]"),
                    "correct": json.loads(r[5]) if r[5] else None,
                    "points": r[6]})
    return out


def delete_question(qid):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"DELETE FROM vq_questions WHERE id={PH}", (qid,))
    conn.commit()


def log_attempt(course_id, username, score, max_score, passed):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""INSERT INTO vq_attempts (course_id, username, score,
        max_score, passed, taken_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH})""",
                (course_id, username, float(score), float(max_score),
                 1 if passed else 0,
                 dt.datetime.now().isoformat(timespec="seconds")))
    conn.commit()
