#!/usr/bin/env python3
# scripts/seed_scl_video_quiz.py
# Loads the Supply Chain & Logistics in-video quiz into the Video-Quiz engine
# (lib.video_quiz_db) — one vq course per chapter video, each with its
# time-stamped checkpoint questions. Reads scl_invideo_quiz.json sitting next
# to this script.
#
#   python scripts/seed_scl_video_quiz.py            # create (skips existing)
#   python scripts/seed_scl_video_quiz.py --replace  # delete + re-create
#
# YouTube IDs are blank in the source; add each video's ID later in
# อบรม → 📹 วิดีโอ Quiz, or fill youtube_id in the JSON before seeding.
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import video_quiz_db as VQ          # noqa: E402

ACTOR = "seed:scl-vq"
HERE = os.path.dirname(os.path.abspath(__file__))


def seed_quiz(path=None, replace=False):
    """Importable entry for the Admin one-click button. Loads the 8 chapter
    videos + checkpoint questions. Returns a summary dict."""
    path = path or os.path.join(HERE, "scl_invideo_quiz.json")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    data = json.load(open(path, encoding="utf-8"))
    by_title = {c["title"]: c["id"] for c in VQ.list_courses()}
    made = skipped = 0
    titles = []
    for v in data["videos"]:
        title = v["title"]
        if title in by_title:
            if replace:
                VQ.delete_course(by_title[title])
            else:
                skipped += 1
                continue
        cid = VQ.create_course(title, "youtube", v.get("youtube_id", ""),
                               None, None, v.get("pass_pct", 60), ACTOR)
        for q in v["questions"]:
            VQ.add_question(cid, q["t_seconds"], q["qtype"], q["prompt"],
                            q.get("options", []), q["correct"],
                            q.get("points", 1))
        made += 1
        titles.append(title)
    return {"created": made, "skipped": skipped,
            "total": len(data["videos"]), "titles": titles}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--file", default=os.path.join(HERE,
                    "scl_invideo_quiz.json"))
    args = ap.parse_args()
    try:
        res = seed_quiz(args.file, replace=args.replace)
    except FileNotFoundError as e:
        sys.exit(f"Quiz JSON not found: {e}")
    print(f"Done. created {res['created']}, skipped {res['skipped']}. "
          f"Open อบรม → 📹 วิดีโอ Quiz to add the YouTube IDs.")


if __name__ == "__main__":
    main()
