# HR Reporting App

A Streamlit-based replacement for the brittle Excel HR report.  Replaces:

- Linked Excel formulas that break across files
- Manual cost-centre grouping
- Manual recalculation when holidays / hour rules change
- Per-user Excel licenses

with a small web app that any cloud platform can host for free.

---

## What it does

- **📊 Report** — the monthly HR report (the table from the screenshot), filtered by
  period, group, function, with optional Annual Leave columns.  One-click export
  to Excel and PNG.
- **📈 Charts** — single-period and multi-period charts (FY2026-style trends).
- **📤 Upload Data** *(admin only)* — upload monthly Timesheet / OT / Leave plus
  reference files (NameList, Manager, Cost Group, Holidays).  Re-uploading a
  period replaces it cleanly.
- **⚙️ Configuration** *(admin only)* — edit holidays, cost-group mapping, hour
  rules.  No formulas to break.
- **👥 Employees** — read-only directory of the active workforce.
- **🔑 Users** *(admin only)* — manage app users and passwords.

Roles:
- `admin` can do everything (upload, edit config, manage users)
- `viewer` can view + filter + export, **cannot upload or edit anything**

---

## Quick start (run locally)

```bash
# 1. Install Python 3.10 or newer, then:
pip install -r requirements.txt

# 2. Run
streamlit run app.py
```

Open the URL it prints (default `http://localhost:8501`).

**Default credentials (CHANGE BEFORE GOING LIVE):**
- `admin / admin123` — full access
- `viewer / viewer123` — view-only

After signing in once as admin:
1. Go to **🔑 Users** and change the admin password (or add a new admin and delete `admin`).
2. Open `config/auth.yaml` and change `cookie.key` to a long random string.
3. Go to **📤 Upload Data** and upload the monthly Timesheet to populate the report.

---

## Loading your data

The app expects the same export formats produced by your HRM. They were
inspected from your sample files and the parsers handle:

- Thai Buddhist calendar (e.g. `01/04/2569` → 1 April 2026)
- Multi-row headers
- Sparse employee blocks (emp code only on the first row of a block)

| File                   | Where to upload it           | When            |
|------------------------|------------------------------|-----------------|
| `*Timesheet.xls`       | Upload Data → Timesheet tab  | Monthly         |
| `*OT.xls`              | Upload Data → OT tab         | Monthly (cross-check) |
| `*Leave.xls`           | Upload Data → Leave tab      | Monthly (cross-check) |
| `*NameList.xlsx`       | Upload Data → Reference tab  | When staff changes |
| `*Manager.xlsx`        | Upload Data → Reference tab  | When managers change |
| `*Cost_Group.xlsx`     | Upload Data → Reference tab  | When cost codes change |
| `*Holidays.xlsx`       | Upload Data → Reference tab  | Once per year |

The **Timesheet** is the source of truth — OT and Leave files are kept only as
optional cross-checks and don't need to be uploaded for the report to work.

---

## Deployment

Two paths.  Pick whichever fits.

### Option A — Streamlit Community Cloud (simplest, fully free)

1. Push this folder to a GitHub repo (don't commit `data/hr.db` or
   `config/auth.yaml` — they're already in `.gitignore`).
2. Go to <https://share.streamlit.io>, sign in with GitHub, click **New app**.
3. Pick the repo, set **Main file path** to `app.py`, click **Deploy**.

The app is live in ~2 minutes.  The URL is technically public, but the app
itself is gated by login and only shows data to authenticated users.

**Important caveat:** Streamlit Community Cloud filesystem is **ephemeral** —
SQLite is reset on each redeploy.  For production, swap to Postgres (see
"Production database" below).  For monthly use during the prototype phase,
re-uploading the Timesheet after each redeploy is acceptable.

### Option B — Render (free tier, persistent disk)

1. Push to GitHub.
2. <https://render.com> → **New** → **Web Service** → connect repo.
3. Settings:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `streamlit run app.py --server.port $PORT --server.headless true`
   - **Health check path:** `/`
   - Add a **Disk** mounted at `/opt/render/project/src/data` (1 GB free)
4. Deploy.

Free instances sleep after 15 minutes of inactivity; first hit takes ~20s to
wake up.  For monthly HR reporting, this is fine.

### Production database (recommended for real deployment)

SQLite is fine while you're prototyping, but for production go with a free
managed Postgres:

- **Supabase** — 500 MB Postgres free, no expiry, never sleeps.
- **Neon** — serverless Postgres, free tier.

To switch, update `lib/db.py` to use `sqlalchemy` against a `DATABASE_URL`
env var and change `get_connection()`/`cursor()`.  All page code is already
written against db helpers, so the swap is contained to that one file.

---

## Security checklist before going live

- [ ] Change the `admin` password (or replace the user) in **🔑 Users**.
- [ ] Change the `viewer` password (or remove the demo user).
- [ ] Open `config/auth.yaml` and replace `cookie.key` with a long random string
  (e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
- [ ] Verify `config/auth.yaml` and `data/hr.db` are **not** in your Git history
  (they're in `.gitignore` but make sure they weren't committed earlier).
- [ ] If you go to Postgres for production, set `DATABASE_URL` as a secret in
  the hosting platform — never check it in.

---

## Project layout

```
hr_app/
├── app.py                          Login + landing page
├── requirements.txt
├── .gitignore
├── .streamlit/config.toml          Theme + server settings
├── README.md                       (this file)
├── config/
│   ├── auth_config.py              Password hashing, user management
│   └── auth.yaml                   (auto-created at first run)
├── data/
│   └── hr.db                       SQLite database (auto-created)
├── lib/
│   ├── db.py                       Schema, connection, helper accessors
│   ├── parsers.py                  HRM file parsers (Buddhist calendar etc.)
│   ├── calculations.py             Report aggregation engine
│   ├── exports.py                  Excel + PNG export
│   └── page_utils.py               require_login() and shared headers
└── pages/
    ├── 1_📊_Report.py             Main monthly report (the table)
    ├── 2_📈_Charts.py             Trend & breakdown charts
    ├── 3_📤_Upload_Data.py        Admin upload page
    ├── 4_⚙️_Configuration.py     Holidays / cost groups / hour rules
    ├── 5_👥_Employees.py          Read-only directory
    └── 6_🔑_Users.py              User management
```

---

## What's NOT yet built (roadmap)

- **Postgres swap** — code is structured for it, but `db.py` still uses sqlite3
  directly.  Moving to SQLAlchemy is a one-file change.
- **SSO** (Microsoft / Google) — currently username + password only.
- **Email notifications** when an upload completes or fails.
- **Audit log** beyond `upload_log`.  Every config change isn't yet tracked.
- **Approvals workflow** — admins can edit cost groups directly without review.
- **Replicating every chart** from `FY2026_HR_Metric_Update.xlsx`.  The Charts
  page covers the core HC / Absenteeism / OT / AL trends; the more bespoke
  visualizations from that file would each be a few extra lines of Plotly.

---

## Troubleshooting

**"No module named 'streamlit'"** — you didn't run `pip install -r requirements.txt`.

**PNG export disabled / button greyed out** — Kaleido is missing.  Run
`pip install kaleido==0.2.1` (the pinned version is the one that reliably works
without a browser dependency).

**"No data loaded yet"** — sign in as admin and upload a Timesheet via Upload Data.

**Login loops back to login** — your `config/auth.yaml` got mangled.  Delete it
and restart; the app will recreate the default admin/viewer users.

**Numbers don't match my old Excel report** — verify on the Configuration page that:
- The cost-group → Function → Top-Group mapping is what you expect
- The hours-per-day conversion is correct
- The OT multipliers are correct
Then check the Report page in **Hours** mode against the raw Timesheet totals.

---

## Credits / how it was built

This app was built collaboratively with Claude using the actual HRM exports
from Anca Manufacturing Solutions Thailand to validate every parser and every
calculation against real numbers (April 2026 closed: 173 active employees,
24,352 working hours, 287.4 AL hours — matching the HRM Leave summary file
exactly).
