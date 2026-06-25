# Go‑Live Step 1 — Database + Password
**ขั้นตอนก่อนนำข้อมูลจริงเข้าระบบ / Do this before any real HR data goes in.**

These are the two hard blockers. Everything in the code is already done and
tested; what remains below is the part only you can do (your Supabase account,
your password). I never put a real connection string or password in any file.

---

## A. Point the app at Supabase (persistent database)

**Why:** with no database configured the app runs on a temporary SQLite file
that Streamlit Cloud **wipes on every redeploy or sleep**. For HR data that is
not acceptable — you must use Supabase Postgres.

1. **Create the project** — supabase.com → *New project*.
   - Region: **Singapore (ap‑southeast‑1)** — closest to Thailand.
   - Set a **strong database password** and save it somewhere safe.
2. **Copy the connection string** — Supabase → *Project Settings* →
   *Database* → *Connection string* → choose **Session pooler**
   (or *Transaction pooler*). It looks like:
   ```
   postgresql://postgres.<ref>:<PASSWORD>@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```
   ⚠️ Use the **pooler** URL, *not* the “Direct connection”. Streamlit Cloud
   reaches Supabase over IPv4, which only the pooler provides.
3. **Local dev** — copy `.streamlit/secrets.toml.example`
   → `.streamlit/secrets.toml`, and paste your real `DATABASE_URL`.
   (That file is git‑ignored — it can never be committed.)
4. **Streamlit Cloud** — open your app → *Settings* → *Secrets* → paste the
   same TOML (at minimum the `DATABASE_URL = "..."` line) → *Save*. The app
   reboots automatically.
5. **First boot creates all tables** for you (`init_db`). The “temporary
   SQLite” warning disappears once `DATABASE_URL` is set.

**Verified for you on a real Postgres:** full schema build, login, settings
upserts, new‑user creation, and — critically — a **second boot is idempotent**
(an earlier transaction‑abort bug on repeated boots was found and fixed, so the
app will not die on its 2nd run on Cloud).

---

## B. Remove the default password (PDPA)

1. The seeded account is **`superadmin` / `ChangeMe!2026`**.
2. On the **first sign‑in the app now forces a password change** — you cannot
   reach any screen until you set a new one (min 8 characters, the old default
   is rejected). ระบบบังคับเปลี่ยนรหัสผ่านครั้งแรกก่อนใช้งานทุกหน้าจอ.
3. Passwords are stored **hashed** (PBKDF2‑HMAC‑SHA256 + a per‑user salt),
   never in plain text.
4. **All secrets live only in secrets** (Streamlit Cloud → *Secrets*, or the
   local `secrets.toml`) — `DATABASE_URL`, SMTP, the LINE token. **None are in
   the code**, and the new `.gitignore` stops `secrets.toml` and the SQLite
   file from ever being pushed to GitHub.

---

## Order to run it

1. Create the Supabase project → copy the **pooler** URL.
2. Paste `DATABASE_URL` into **Streamlit Cloud → Secrets** → app reboots on
   Postgres (tables auto‑create).
3. Sign in as `superadmin` / `ChangeMe!2026` → **set your new password**
   (forced).
4. *(optional)* create your pilot users in **System Admin → Users**.

After this, the system is safe to hold real data and you can switch on the
modules you want for the pilot.
