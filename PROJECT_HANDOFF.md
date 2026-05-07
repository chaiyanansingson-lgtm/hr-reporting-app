# Anca HR Reporting App — Project Handoff Document

**Version:** v11.3
**Last updated:** 2026-05-07
**Live URL:** https://anca-hr-reporting.streamlit.app
**Repo:** https://github.com/chaiyanansingson-lgtm/hr-reporting-app (private)
**Owner:** Chaiyanan Singson (chaiyanan.singson@gmail.com)
**Company:** Anca Manufacturing Solutions (Thailand) Ltd.

---

## 🎯 Purpose of this document

This is a **complete project memory file**. If you (the user) ever:
- Hit a chat token limit and need to start a fresh Claude conversation
- Want to work on a parallel feature in a second chat
- Onboard a new developer or another AI assistant

…you can paste this entire document into the new chat as the **first message**, and Claude will understand the project, the decisions made, the current state, the bugs known, and the roadmap.

**How to use it:**
> "I'm continuing work on my Anca HR Reporting App. Please read this handoff document carefully — it contains the full project context, current state, known bugs, and roadmap. After reading, I'll tell you what to work on next." [paste this file]

---

## 1. Project Vision

### What it is today (v11.3)
A bilingual (Thai/English) internal web application for Anca's HR team to produce monthly absenteeism, OT, and headcount reports. Replaces a manual Excel-based monthly process. Built on Streamlit + SQLite, deployed on Streamlit Community Cloud (free tier).

### What it will become
The current report is **Module 1** ("Manager Module" / โมดูลรายงาน) of a larger **HR system suite**. Future modules planned:
- **Module 2:** Manpower Budget (with separate financial-data access controls)
- **Module 3:** Salary & Compensation (most restricted access)
- **Module 4:** Training records
- **Module 5:** Recruitment / Onboarding pipeline
- **Module 6:** Performance reviews
- **Module N:** TBD — extensible plugin architecture

All modules share a **common private data layer**:
- Employee master (names, IDs, dept, reporting structure)
- Org chart (manager links, dotted-line reports)
- Holiday calendar
- Cost-centre groupings
- Photo gallery (uploaded by admin)
- Working-hour rules (per-shift, per-weekday)

### Design principles
1. **Bilingual everything** — Thai is the default UI language; every new string must be added to both TH and EN in `lib/i18n.py`.
2. **Anca CI palette throughout** — cyan `#009ADE`, purple `#715091`, magenta `#E31D93`, white surfaces, frosted-glass cards.
3. **Personal vs Master settings** — every calculation parameter has both a master value (admin-controlled, applies to everyone) and per-user override (personal what-if). Personal overrides never affect other users.
4. **Defensive UX for non-technical users** — generous tooltips, color-coded callouts, illustrated help panels, prefer toggles/sliders over typing.
5. **Audit trail for everything sensitive** — login attempts, change requests, photo uploads should all be logged.

---

## 2. Current State (v11.3, deployed and working)

### What works
- Login / logout (admin / viewer / manager / trial accounts)
- Bilingual Thai/English UI with toggle (default Thai)
- Sign-up requests (admin reviews, approves/rejects)
- Login audit trail (admin views all sign-in attempts with IP + user-agent)
- Upload data: timesheet, OT (auto-detect dated/legacy formats), leave summary, employee master
- Report page: 5 separate per-leave-type deduction toggles, hours/days unit, top-group/function filters
- Charts page: KPI dashboard with absenteeism / OT / WH / turnover trends, multi-select for leave types and OT multipliers
- Configuration page: 6 tabs (Holidays / Cost Groups / Hour Rules / KPI Targets / Per-Month Overrides / **🎨 Org Chart Style**)
- Personal calculation overrides (per-username, never affects others)
- Org Chart: 4 views (Tree, **🎨 Visual Chart with photos and dept clusters**, Table, By Department)
- Visual Chart features:
  - Photos per employee (admin uploads in Employees page; auto-resized to 200×200 JPEG)
  - Name format "Firstname S. (Nickname)" — first name + initial + nickname
  - Department cluster headers (Visio-style)
  - Solid lines (direct reports) + dashed lines (dotted-line / matrix reports)
  - Color-by-role OR color-by-department (admin customizes both)
- Change requests (manager submits; admin approves)
- Bulk change request via Excel template
- User management (admin add/edit/delete users)
- Bilingual PDF/DOCX user manual delivered (21 pages)

### Critical bugs / known issues
🔴 **B1. Period override appears not to work in Actual mode** — see Section 5.

🟡 **B2. Streamlit Cloud SQLite is ephemeral** — the database resets to whatever's in the GitHub repo on every reboot. Uploaded photos and any new sign-up requests are **lost** when:
   - The app sleeps and restarts (free tier sleeps after ~7 days of inactivity)
   - A new code push triggers redeploy
   - Streamlit Cloud rolls platform updates
   *Mitigation: Migrate to Postgres (Supabase / Render / Railway free tier).*

🟡 **B3. Streamlit Secrets are the only persistent storage for trial-user accounts** — adding a new viewer/manager via the Users page works only until next reboot unless also added to `[extra_users.*]` in Secrets.

🟢 **B4. Logo blurry** — *fixed in v11.3, replace `assets/logo.png` with the v11.3 file (also adds `logo@2x.png` for retina screens).*

---

## 3. Tech Stack

| Layer | Tool | Notes |
|---|---|---|
| Web framework | Streamlit ≥1.32 | Auto-redeploy on `git push main` |
| Database | SQLite | Ephemeral on Streamlit Cloud — see B2 |
| Auth | bcrypt + Streamlit Secrets + custom YAML | Passwords hashed; `[extra_users.X]` in Secrets supports trial accounts |
| Excel I/O | openpyxl + xlsxwriter | Reading uploaded files; writing exported reports |
| Charts | Plotly (interactive) + Kaleido (PNG export) | |
| Visual org chart | Graphviz (system binary on Streamlit Cloud) | Renders DOT to SVG inline |
| Image processing | Pillow ≥10.0 | Photo resize/crop |
| Python | 3.11+ | |

`requirements.txt` contents (canonical):
```
streamlit>=1.32.0
streamlit-authenticator>=0.3.2
pandas>=2.1.0
openpyxl>=3.1.2
xlrd>=2.0.1
xlsxwriter>=3.1.9
plotly>=5.18.0
kaleido==0.2.1
sqlalchemy>=2.0.25
bcrypt>=4.1.0
pyyaml>=6.0.1
matplotlib>=3.8.0
pillow>=10.0.0
```

---

## 4. File Structure (v11.3)

```
hr_app/
├── app.py                    # Login + home page (305 lines)
├── requirements.txt
├── README.md
├── SECURITY_GUIDE.md
├── SYSTEM_FLOW.md
├── USER_MANUAL.md
├── .gitignore                # excludes data/, config/auth.yaml, .streamlit/secrets.toml
├── .streamlit/
│   └── config.toml           # Anca CI theme (cyan/purple/magenta)
├── assets/
│   ├── logo.png              # 350×247 PNG (v11.3 — high quality)
│   └── logo@2x.png           # 700×494 retina version (v11.3)
├── config/
│   ├── __init__.py
│   └── auth_config.py        # bcrypt + Secrets + extra_users bootstrapping
├── data/
│   └── hr.db                 # SQLite (gitignored, ephemeral on Cloud)
├── lib/
│   ├── __init__.py
│   ├── calculations.py       # 591 lines — build_report, standard_working_days_in_period
│   ├── db.py                 # 1008 lines — schema + all helpers (incl v11.3 photo/dotted/styling)
│   ├── exports.py            # 380 lines — to_excel_bytes, to_png_bytes
│   ├── i18n.py               # 265 lines — TR dict ~85 strings, bilingual TH/EN
│   ├── page_utils.py         # 135 lines — require_login, page_header, NAV_ITEMS
│   ├── parsers.py            # 629 lines — all upload-file parsers (timesheet/OT/leave/master)
│   ├── photo_utils.py        # 110 lines (v11.3) — validate_and_resize_photo
│   ├── style.py              # 400 lines — inject_anca_style CSS
│   └── templates.py          # 416 lines — 9 Excel template generators
└── pages/
    ├── 1_Report.py           # 348 lines — main monthly report
    ├── 2_Charts.py           # 265 lines — KPI dashboard
    ├── 3_Upload.py           # 321 lines — admin uploads (4 tabs)
    ├── 4_Configuration.py    # 673 lines (v11.3) — 6 tabs incl 🎨 Org Chart Style
    ├── 5_Employees.py        # 457 lines (v11.3) — directory + photos + dotted-line + change requests
    ├── 6_Users.py            # 67 lines — admin user mgmt
    ├── 7_Change_Requests.py  # 112 lines
    ├── 8_Signup_Review.py    # 137 lines — admin reviews signups
    ├── 9_Login_Audit.py      # 68 lines
    └── A_Org_Chart.py        # 491 lines (v11.3) — 4 tabs incl Visual Chart
```

---

## 5. Database Schema (v11.3)

All tables defined in `lib/db.py`. Schema migrations applied at `init_db()` startup (additive only, never drops columns).

### Core data
- `employees` — emp_no PK, emp_name, emp_type (PER/SUB/TEM), cost_code, level, d_in (Direct/Indirect), is_active
- `employees_extended` — emp_no FK, nickname, name_th, dept_by_location, cost_centre_name, title, manager_name, manager_emp_no, is_mgr_role (Mgr./Sup./Leader), thai_or_expat, joined_date, status, **photo_blob (BLOB, v11.3)**, **dotted_managers (TEXT JSON, v11.3)**
- `managers` — emp_no, manager_name (legacy, used during master import)
- `cost_groups` — code (PK), department, sg_a_manu (top group: SG&A / MANU / MANU Support)
- `holidays` — holiday_date, name
- `hour_config` — config_key, config_value (mon-sun std hours, hours_per_day conversion, OT multipliers)
- `targets` — target_key, target_value (KPI decimals)

### Period data (one row per uploaded month)
- `timesheet` — period, emp_no, work_hours, absent_hours, sick_hours, personal_hours, annual_hours
- `ot_entries` — period, ot_date (NULL for legacy), emp_no, ot_type (1/1.5/2/3), ot_hours
- `upload_log` — audit of all uploads
- `period_overrides` — period (PK), working_days, daily_std_hours

### v11.3 customization
- `org_chart_styling` — category ('dept'/'role'/'level'), key, fill_color, font_color, border_color (PK: category+key)

### Per-user overrides (personal what-if)
- `user_overrides` — username, override_key, override_value (JSON)
  - Keys: `holidays`, `hour_config`, `period_overrides`, `cost_group_tops`

### Workflow / audit
- `change_requests` — manager submits, admin approves/rejects
- `signup_requests` — pending sign-ups for admin review
- `login_audit` — every sign-in attempt with IP + UA

### Resolved-value pattern
Most read functions come in pairs:
- `db.get_holidays()` — master only
- `db.effective_holidays(username)` — applies user override on top of master

This pattern is consistent across holidays / hour_config / period_overrides / cost_group_tops.

---

## 6. ⚠️ Critical bug: B1 — Period override "not working"

### Symptom (reported 2026-05-07)
User set personal overrides:
- April 2026 working_days: 17 → 10
- April 2026 daily_std_hours: 8 → 6.99

The override memo at the bottom of the Excel export confirms both values are saved correctly. But the Total Working Hrs in the report still shows 24,352.2 (unchanged).

### Diagnosis
The override is stored correctly. The user's expected total = 173 employees × 10 days × 6.99 hrs = **12,092.7 hrs**. Observed total = **24,352.2 hrs**.

`24,352.2` is the sum from the **timesheet table** (Actual mode), not the standard-mode formula. Looking at `lib/calculations.py` line 291-298:

```python
if wh_mode == "standard":
    total_wh = total_hc * std_hrs_per_emp * f
    perm_wh = perm_hc * std_hrs_per_emp * f
    cont_wh = cont_hc * std_hrs_per_emp * f
else:
    total_wh = g["work_hours"].sum() * f       # ignores override
    perm_wh = g.loc[g["emp_type"] == "PER", "work_hours"].sum() * f
    cont_wh = g.loc[g["emp_type"] == "SUB", "work_hours"].sum() * f
```

The override only takes effect when `wh_mode == "standard"`. In Actual mode (the default), working hours come straight from the uploaded timesheet — overrides are intentionally ignored.

### User's mental model vs app's
The user's reference Excel (`Actual_working_hours_for_FN__Rev_20260507_.xlsx`, sheet "Apr 26 ") uses **only one formula** for Working Hours:

```
H3 = (D3 × F36 × F37) − IF(F38="Y", W3, 0) − IF(F39="Y", K3, 0)
```

Where F36 = working days, F37 = daily std hrs, F38/F39 = AL/other-leave deduction toggles. There is no "actual mode" in their Excel — it's always Standard (HC × WD × Hrs/day) with leave deductions.

### Recommended fix
Two paths:
1. **Auto-switch to Standard mode when an override is active.** Show a banner: "🎛️ Period override active — using Standard formula HC × 10 × 6.99". *Easier, lower regression risk.*
2. **Make overrides apply in Actual mode too.** When the user sets WD/Hrs, replace the timesheet sum with computed standard. *More invasive, may surprise users who genuinely want timesheet data.*

I recommend Path 1. Add to `pages/1_Report.py`:
```python
override_active = bool(db.effective_period_override(period, username))
if override_active and wh_mode == "actual":
    st.warning("🎛️ You have a period override active for this month. "
                "Switch to **Standard mode** above to use it. Currently in Actual mode "
                "(timesheet data) — your override is being ignored.")
```

Plus: rethink the default mode. If the user's Excel logic is the canonical one, **default the report to Standard mode** and only offer Actual as opt-in.

---

## 7. Calculation Formulas (canonical, from user's Excel)

These are the **target formulas** the system must implement. All cell references are from `Actual_working_hours_for_FN__Rev_20260507_.xlsx`, sheet `Apr 26 `.

### 7.1 Working Hours
```
H3 = (D3 × F36 × F37) − IF(F38="Y", W3, 0) − IF(F39="Y", K3, 0)
```
- `D3` = Total HC (sum of permanent + contract + temp)
- `F36` = Working days in month (auto from holidays + master, or user override)
- `F37` = Daily standard hours (auto from hour_config, or user override)
- `F38` = "Y" → deduct AL hours from WH
- `F39` = "Y" → deduct other leave hours from WH
- `W3` = Total AL hours
- `K3` = Total absent hours (excl AL)

In v11 the system has **5 toggles** (AL / Sick / Business / WithoutPay / Include AL in %Absent) instead of just F38/F39 — this is an enhancement over the Excel.

### 7.2 % Absenteeism
```
N3 = (K3 + IF(F40="Y", W3, 0)) / H3
```
- `F40` = "Y" → include AL in absenteeism numerator (currently the 5th toggle)

### 7.3 % OT (rate)
```
V3 = U3 / (H3 + U3)
```
- `U3` = Total OT hours (sum of OT*1, OT*1.5, OT*2, OT*3)
- `H3` = Working Hours from 7.1 above

### 7.4 OT/Absent unit ↔ hour conversion (NOT YET IMPLEMENTED)

⚠️ **This is a roadmap item raised by user 2026-05-07.**

User wants the system to convert OT/Absent hours from raw timesheet uploads using two cases:

**Case 1: OT/Absent on weekend/holiday over 8 hours**
1. Take the raw OT/Absent hours
2. Divide by **shift normal working hours** (e.g. day shift = 07:45–16:25 = 8h40min worth)
3. Store internally as "units" (i.e., fractional shifts)
4. When reporting in hours, multiply units × **daily standard hours** (from F37 or override)

**Case 2: OT/Absent under shift normal hours**
- Use the value directly as hours (no conversion needed).

The bug in the user's current Excel: `X7 = AA7 × $F$37` — meaning `AA7` was already pre-divided by some standard at upload time, and the conversion is brittle. They want the system to handle the conversion natively from raw data.

**Implementation note:** This needs:
- A new admin setting: `shift_normal_hours` (or per-shift table for multi-shift companies)
- Modified parsers in `lib/parsers.py` for OT/leave to detect "weekend/holiday over X hours" rows
- Storage in both `hours` and `units` columns
- Report layer chooses which to display based on user setting

---

## 8. Roadmap (requested by user, 2026-05-07)

### A. Multi-module HR suite architecture
- Refactor current report into **Module 1: Manager Module** (โมดูลรายงาน)
- Establish a **shared data layer** for: employee names, org structure, holidays, cost centres, photos, hour rules
- Add a **module manifest** system: each module is a folder under `pages/` with metadata (name, required role, required data dependencies)
- Sidebar shows only modules the current user has access to
- Each module declares which DB tables it owns vs reads-from-shared

### B. Role-based access control (4-level matrix)

User wants finer-grained roles than current viewer/manager/admin:

| Level | Role | Can see | Cannot see |
|---|---|---|---|
| 1 | **Viewer** | Reports & charts (their dept), org chart | Salary, full company data |
| 2 | **Manager (general)** | Their team's reports, change requests | Salary, manpower budget |
| 3 | **Manager (finance / budget owner)** | Manpower budget reports, all charts | Individual salary rates |
| 4 | **Admin (data entry)** | Edit master data (holidays, cost groups, employee master), upload files | Salary, manpower budget, financial data |
| 5 | **Admin (full / HR Director)** | Everything including salary, budget | — |

Implementation sketch:
- Replace current `role` string with `role` + `permissions` (JSON list of capability tokens)
- Capabilities: `view.reports`, `view.salary`, `view.budget`, `edit.master_data`, `edit.salary`, `approve.change_requests`, `manage.users`, `view.audit`, etc.
- Each page checks `has_capability("view.salary")` instead of `is_admin()`
- Admin UI to assign capabilities to users (checkbox grid)

### C. UI redesign for Report and Dashboard pages

User feedback (2026-05-07):
1. **Move filters/calculation settings into a right-side drawer** (currently in expander at top)
2. **The drawer should be interactive** — changes take effect immediately on the table/charts
3. **Add a per-control "apply to current page only / apply globally"** toggle inside each control
4. **Move the summary metrics ABOVE the report table** (currently below it)
5. **Categorize the right drawer** into collapsible sections (e.g., Period / Filters / Calculation / Display) so it doesn't become a long scroll
6. **Export buttons stay at bottom of page** (unchanged)
7. **"Personal overrides applied" banner** should be clearly visible somewhere logical — top of page or pinned in the drawer

For Dashboard: similar drawer structure for chart-control settings.

### D. Dashboard chart parity with `FY2026_HR_Metric_Update_20260506.xlsx` "Chart" sheet

**13 charts** to replicate (line + bar combinations):
- FY20.. trend (annual)
- Monthly Absenteeism By Group
- Monthly Absenteeism By Criterion
- Monthly Overtime By Group
- Monthly Absenteeism — Sales
- Monthly Absenteeism — Engineering
- Monthly Absenteeism — Quality
- Monthly Absenteeism — Production
- Monthly Absenteeism — Maintenance
- Monthly Absenteeism — Supply Chain
- + 3 bar charts (FY202.. variants, untitled)

Each chart must include:
- **Complete value labels at every point** (Plotly: `mode="lines+markers+text"`, `texttemplate="%{y:.2f}%"`)
- **A summary bubble showing comparison: current FY (cumulative) vs current calendar month**
- **FY definition: July (prev calendar year) → June (current calendar year)** (Australian/Anca FY)

User also wants:
- **Bulk historical upload template** — Excel template for admin to upload multiple past FYs of historical data so the dashboard can render multi-year trends without re-uploading each month one at a time

### E. Calculation engine: "Looker Studio / Power BI"-style configurable formulas

User idea: instead of hardcoded formulas, build a **formula builder**:
- Admin defines metrics (Working Hours, %OT, %Absent, etc.) as expressions
- Expression refers to base columns (HC, WD, AL hrs, OT*1 hrs, …) and parameters (toggles)
- Renders dynamically in reports

This is a significant architectural change. It would let users define their own KPIs without code changes. **Effort estimate: 2-3 weeks of focused work.**

Candidate libraries:
- `simpleeval` (safe Python expression evaluator)
- `formulas` (Excel-formula-compatible Python library)
- Build a UI where admin selects: target metric → source columns → operation (sum/avg/ratio) → save

### F. Logo quality fix
✅ Done in v11.3 — replace `assets/logo.png` and add `assets/logo@2x.png`. CSS to update in `lib/style.py` if needed (use `srcset` for retina).

---

## 9. Known data structure of source files

### `Employee_List_MASTER` — Excel file admin uploads
- Sheet: "Headcount Updated"
- Real headers in **row 4**, data starts **row 5**
- 174 employees, 172 manager links resolve cleanly

### Timesheet upload
- Already-parsed by HR; uploaded as Excel
- Per-employee per-month: work hrs, absent hrs, sick hrs, personal hrs, annual hrs

### OT upload (auto-detects format)
- **Dated format** — one row per OT instance with a date column
- **Legacy format** — pre-aggregated monthly per employee

### Leave summary upload
- Per-employee monthly: annual / sick / personal / business / without-pay totals

---

## 10. User preferences and decisions log

**Default language:** Thai (TH). English is the toggle alternative.

**Default credentials (when no Streamlit Secrets set):**
- `admin / admin123` — full admin
- `viewer / viewer123` — viewer
- `trial / Trial2026!` — trial viewer (only via `[extra_users.trial]` Secret)

**Branding:**
- Cyan `#009ADE` — Anca primary
- Purple `#715091` — Anca secondary
- Magenta `#E31D93` — Anca accent
- White-major frosted-glass UI
- Inter / Sarabun fonts (with Thai fallback to Noto Sans Thai)

**Manager role colors in org chart (default, customizable in Settings):**
- Mgr. → purple #715091
- Sup. → cyan #009ADE
- Leader → magenta #E31D93
- (staff) → light gray #F3F4F6

**Photo specs:**
- Allowed input: JPG, PNG, WebP, BMP, GIF, ≤5 MB
- Auto-processed: cropped to square, resized to 200×200, JPEG q85, capped at 100 KB
- 174 employees × ~30 KB ≈ ~5 MB total DB impact

**Currency / numbers:**
- Decimal commas off (English-style)
- Hours displayed to 1 decimal place
- Percentages to 2 decimal places (e.g. 0.27%)

**Fiscal year:** July 1 (year N-1) → June 30 (year N) — Anca uses Australian FY

**Date format:** ISO `YYYY-MM-DD` everywhere internally; UI may show `DD/MM/YYYY`

---

## 11. Deployment workflow (Windows CMD)

User's local repo: `C:\Users\Gurot\Downloads\20260506\hr_app_v11_complete\hr_app\`

GitHub repo: `https://github.com/chaiyanansingson-lgtm/hr-reporting-app` (private)

Streamlit Cloud watches `main` branch. Auto-redeploys on push (~2 min).

**Standard workflow for code updates:**
```cmd
cd C:\Users\Gurot\Downloads\20260506\hr_app_v11_complete\hr_app
git add .
git commit -m "describe change"
git push
```

**If push is rejected (someone edited on GitHub):**
```cmd
git pull --rebase origin main
git push
```

**Force redeploy if Streamlit Cloud gets stale:**
1. https://share.streamlit.io
2. Find app → ⋮ → Reboot app

**Testing locally:**
```cmd
cd hr_app
python -m streamlit run app.py
```

---

## 12. Things explicitly NOT YET DONE (deferred)

- ❌ Email notifications (need SendGrid/Resend account)
- ❌ Forgot-password flow
- ❌ Postgres migration (still on ephemeral SQLite)
- ❌ 2FA for admin
- ❌ Per-month employee re-assignment manual override
- ❌ Account lockout / rate limiting on signup
- ❌ Module 2 (Manpower Budget) — see roadmap
- ❌ Salary/compensation module — see roadmap
- ❌ Multi-shift support (currently assumes single shift)
- ❌ OT unit↔hour conversion logic (see Section 7.4)
- ❌ Right-drawer UI redesign (Section 8C)
- ❌ All 13 charts from Anca's reference workbook (Section 8D)
- ❌ Looker-style formula builder (Section 8E)
- ❌ Capability-based RBAC (Section 8B)

---

## 13. How to bootstrap a fresh Claude chat

**Paste this entire document** as the first message, then say:

> "Please confirm you've read the handoff doc. Then [INSERT CURRENT TASK]. The most pressing items are:
> 1. Fix the period-override bug (Section 6)
> 2. [NEXT TASK]"

Claude should then:
1. Acknowledge what it's read
2. Ask clarifying questions if any
3. Propose a plan before writing code
4. Confirm scope before making large changes

---

## 14. Files to keep in sync alongside this handoff doc

If you ever ZIP up the project, include alongside this:
- The full `hr_app/` folder (or at minimum `lib/` and `pages/`)
- Latest `requirements.txt`
- Latest `.streamlit/config.toml`
- Sample data files (Employee Master, sample timesheet, sample OT, sample leave)
- The user's reference Excel files (`Actual_working_hours_for_FN__Rev_20260507_.xlsx`, `FY2026_HR_Metric_Update_20260506.xlsx`)
- Anca org Visio file (for visual chart styling reference)
- This handoff document

---

*End of handoff. Last updated 2026-05-07 by Claude Opus 4.7 working with Chaiyanan Singson on the Anca HR Reporting project.*
