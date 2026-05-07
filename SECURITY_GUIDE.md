# Production Security & Deployment Recommendations

This document explains how to lock down the Streamlit deployment so company HR data stays private, plus the trade-offs of each option.

## TL;DR Recommendation

For a company HR app with ~5–20 users:

1. **Make the GitHub repo private** — keeps source code internal
2. **Set Streamlit app privacy to "Only specific people"** — gates the URL by email
3. **Move hosting from SQLite to a free Postgres database** — keeps data persistent across restarts
4. **Use Streamlit Secrets** for the bootstrap admin password
5. **Rely on the new Sign-up workflow** for adding regular users — admin reviews each request

Doing all of these makes your deployment safe enough for real HR data.

---

## Layer 1 — Source code privacy

### Option A: Public repo (current)
- ✅ Free, easiest to deploy
- ✅ No secrets in the code (`.gitignore` excludes `auth.yaml`, `hr.db`, `secrets.toml`)
- ❌ Anyone can read the source code on GitHub
- ❌ Anyone could clone it and self-host an identical copy
- ⚠️ The code itself doesn't contain employee data, but reveals your business logic

### Option B: Private repo (recommended)
- ✅ Source code is invisible to anyone outside your collaborators
- ✅ Streamlit can still deploy from it (uses a read-only deploy key)
- ✅ Free on GitHub Free plan (unlimited private repos)
- 📋 To switch:
  1. Go to `https://github.com/chaiyanansingson-lgtm/hr-reporting-app/settings`
  2. Scroll to "Danger Zone" → "Change repository visibility" → Make private
  3. Confirm by typing the repo name
  4. The Streamlit deployment continues to work — Streamlit was already authorized to read your private repos when you set up the GitHub App

---

## Layer 2 — App URL privacy

The Streamlit app URL `anca-hr-reporting.streamlit.app` is publicly known. Even with a strong login, anyone could try password-guessing.

### Option A: Public app (default)
- The URL is reachable by anyone on the internet
- Login screen is the only barrier
- ⚠️ Password attempts ARE logged (Login Audit page) but not rate-limited

### Option B: Private app — viewer email allow-list (RECOMMENDED)
Streamlit Community Cloud lets you restrict which Google accounts can even see the login page:

1. Open https://share.streamlit.io/
2. Click your `anca-hr-reporting` app → ⚙️ Settings
3. Go to **Sharing** section
4. Set **"Who can view this app"** to **"Only specific people can view this app"**
5. Add your team members' Google email addresses
6. (Optional) For users without Google accounts, Streamlit sends them a 15-minute single-use link

When set up this way:
- ✅ Random visitors hit a Google sign-in wall — not even your login screen
- ✅ Only listed emails can reach the app
- ✅ Plus the app's own login still applies — defense in depth
- ⚠️ Need to maintain the email list as people join/leave

This is the standard pattern Streamlit recommends for confidential business apps.

---

## Layer 3 — Data persistence (SQLite vs Postgres)

### Option A: Stay on SQLite (current)
- ✅ Zero setup, works out of the box
- ❌ Data is **wiped** every time the Streamlit container restarts (~weekly + on every code push)
- ❌ Can't scale beyond ~50 concurrent users
- 👎 **Not recommended for production** — admin would need to re-upload monthly data after every restart

### Option B: Free Postgres (RECOMMENDED for go-live)
- ✅ Data persists across restarts forever
- ✅ Multiple users can hit the app simultaneously without locking
- ✅ Free tiers are generous (Supabase 500 MB / 50 K rows / Neon 3 GB)
- 📋 Setup time: ~10 minutes
- 📋 Code change: only `lib/db.py` needs updating to use SQLAlchemy + Postgres

**To switch to Supabase:**

1. Sign up at https://supabase.com (use GitHub login)
2. Create a new project (any region in Asia for low latency)
3. Wait 2 minutes for project to provision
4. Click "Project Settings" → "Database" → copy the **Connection string** (URI format, not direct)
5. In Streamlit Cloud Secrets, add:
   ```toml
   [database]
   url = "postgresql://postgres:YOUR_PASSWORD@db.XXX.supabase.co:5432/postgres"
   ```
6. Tell Claude: "Switch lib/db.py to use Postgres via the `database.url` secret" — I'll update the code (it's about 50 lines of changes, all in one file)

After switching, the data tables stay across restarts and the audit log becomes truly useful.

---

## Layer 4 — Authentication (current setup)

### Bootstrap accounts (admin / viewer)
- Defined in Streamlit Secrets: `[auth] admin_password`, `[auth] viewer_password`
- Re-seeded into the local `auth.yaml` on every app boot
- Changing the secret in Streamlit Cloud immediately changes the live password (next boot)
- ⚠️ **Change the defaults** to strong passwords before going live

### Additional accounts (sign-up workflow)
- New users go to the Sign-up tab on the login screen
- They submit username, email, full name, optional employee number, requested role, reason
- The submission is recorded with their IP address and user-agent
- An admin reviews each request on the **Sign-up Requests** page
- Admin can approve (with chosen role) or reject (with notes)
- Every action is audit-logged with admin's username and review notes

⚠️ **Caveat on SQLite hosting**: signup requests and approved accounts (beyond admin/viewer) are stored in the same `hr.db` file and `auth.yaml` that get wiped on restart. Switch to Postgres before relying on this for real users.

### Login audit
- Every sign-in attempt — successful or not — recorded with:
  - Username (even if user doesn't exist, to detect probing)
  - Success / failure
  - Failure reason (wrong password, user not found, empty fields)
  - IP address (extracted from `X-Forwarded-For` since Streamlit Cloud is behind a proxy)
  - User-agent string (browser/device)
  - Timestamp + role at login
- Visible to admin on **Login Audit** page
- Filters: only admins, only failures, by username, last N rows
- Exportable as CSV

---

## Recommended go-live checklist

Before sharing the URL with the team:

- [ ] Repo set to private on GitHub
- [ ] Streamlit app set to private with email allow-list
- [ ] Streamlit Secrets contain strong `admin_password` and `viewer_password` (not the defaults)
- [ ] Postgres database set up and `database.url` in Streamlit Secrets
- [ ] `lib/db.py` updated to use Postgres (ask Claude when ready)
- [ ] Test sign-in once with admin → verify Login Audit shows your IP
- [ ] Upload Employee MASTER list to populate Org Chart
- [ ] Upload one month of Timesheet + OT to verify Report and Charts pages
- [ ] Optional: invite 1-2 colleagues, walk them through the sign-up flow

---

## What Streamlit Community Cloud sees vs. doesn't

✅ **Streamlit can see:**
- Your code (cloned from GitHub on every deploy)
- Your Streamlit Secrets (passwords, DB URL — encrypted at rest, only decrypted at runtime)
- Public-facing URLs and access logs

❌ **Streamlit does NOT see:**
- Anything stored in your external Postgres (only your app talks to it)
- The `hr.db` SQLite file inside the container is technically on Streamlit's hosts, but is wiped on every restart and not accessible by Streamlit staff outside legitimate maintenance

For HR data, putting it in your own Postgres (Supabase) — not in SQLite on Streamlit's container — is the right pattern.
