# Anca HR Reporting App — Project Handoff Document

**Version:** v11.4
**Last updated:** 2026-05-08
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

### What it is today (v11.4)
A bilingual (Thai/English) internal web application for Anca's HR team to produce monthly absenteeism, OT, and headcount reports. Replaces a manual Excel-based monthly process. Built on Streamlit + SQLite, deployed on Streamlit Community Cloud (free tier). **As of v11.4: capability-based RBAC with 7 roles, module-hub landing page, and Visitor Portal for external guests.**

### What it will become
The current report is **Module 1: Report Module** (โมดูลรายงาน, formerly called "Manager Module") of a larger **HR system suite**. Future modules planned:
- **Module 2:** Manpower Budget (with separate financial-data access controls)
- **Module 3:** Salary & Compensation (most restricted access)
- **Module 4:** Training records
- **Module 5:** Recruitment / Onboarding pipeline
- **Module 6:** Performance reviews
- **Module N:** TBD — extensible plugin architecture

All future modules are already **registered as locked placeholder cards** on the module hub (see `lib/rbac_seed.py` MODULES list). When a future module ships, flip its `is_active` flag to `1` and the card lights up automatically.

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
6. **Capability-based access (v11.4)** — no more `is_admin()` checks. Pages declare a required capability (`report.access`, `system.manage_users`, etc.) and the gate is enforced uniformly.

---

## 2. Current State (v11.4, deployed and working)

### What works
- Login / logout (admin / viewer / manager / trial accounts) — YAML-based via `config/auth_config.py`
- Bilingual Thai/English UI with toggle (default Thai)
- Sign-up requests (admin reviews, approves/rejects)
- Login audit trail
- Upload data: timesheet, OT (auto-detect dated/legacy formats), leave summary, employee master
- Report page: 5 separate per-leave-type deduction toggles, hours/days unit, top-group/function filters
- Charts page: KPI dashboard with absenteeism / OT / WH / turnover trends
- Configuration page: 6 tabs (Holidays / Cost Groups / Hour Rules / KPI Targets / Per-Month Overrides / 🎨 Org Chart Style)
- Personal calculation overrides (per-username, never affects others)
- Org Chart: 4 views (Tree, 🎨 Visual Chart with photos and dept clusters, Table, By Department)
- Change requests (manager submits; admin approves)
- Bulk change request via Excel template
- User management (admin add/edit/delete users)
- Bilingual PDF/DOCX user manual delivered (21 pages)

### v11.4 NEW
- **7-role RBAC** with capability tokens (see Section 15)
- **Module hub landing page** — 3-column card grid in Anca CI colors, frosted-glass styling, locked cards for future modules
- **Visitor Portal** (`pages/B_Visitor_Portal.py`) — external-guest-only safety-standards page
- **Capability-based page guards** — every page declares its required cap; sidebar nav filters automatically
- **Per-user grant/revoke overrides** in DB schema (UI in Session 2)
- **Approval-priority foundation** in DB schema (sequential approval ordering — UI in Session 2)
- **LEGACY_ROLE_MAP fallback** — v11.3 users keep working with their YAML legacy roles automatically mapped to new role keys

### Critical bugs / known issues
🔴 **B1. Period override appears not to work in Actual mode** — see Section 6. Still open.

🟡 **B2. Streamlit Cloud SQLite is ephemeral** — DB resets to whatever's in the GitHub repo on every reboot. Uploaded photos and any new sign-up requests are **lost** when the app sleeps and restarts, a code push triggers redeploy, or Streamlit Cloud rolls platform updates. *Mitigation: Migrate to Postgres (Supabase / Render / Railway free tier).*  
**v11.4 implication:** the `user_roles` table and any per-user capability overrides also reset on every redeploy. The `USER_MIGRATION_MAP` constant in `lib/rbac_seed.py` is the only thing that survives — anyone who needs `super_admin` permanently must be listed there.

🟡 **B3. Streamlit Secrets are the only persistent storage for trial-user accounts** — adding a new viewer/manager via the Users page works only until next reboot unless also added to `[extra_users.*]` in Secrets.

🟢 **B4. Logo blurry** — *fixed in v11.3.*

🟢 **B5. v11.4 init crash: SQLite lock contention** — **fixed 2026-05-08 in v11.4 hotfix.** RBAC migration was running inside the same `with cursor()` block that held a write-lock from `INSERT INTO targets`, causing `CREATE TABLE user_roles` on a second connection to fail silently. Fix: migration now runs BEFORE the with-block, seeding runs AFTER. Plus: every SQL query in `lib/auth.py` is now wrapped in `try/except sqlite3.OperationalError` so a missing table can never crash a page (graceful YAML fallback).

---

## 3. Tech Stack

| Layer | Tool | Notes |
|---|---|---|
| Web framework | Streamlit ≥1.32 | Auto-redeploy on `git push main` |
| Database | SQLite | Ephemeral on Streamlit Cloud — see B2 |
| Auth | bcrypt + Streamlit Secrets + custom YAML | Passwords hashed; users live in `config/auth_config.py` (NOT in DB); `[extra_users.X]` in Secrets supports trial accounts |
| Authorization (v11.4) | Custom capability tokens in SQLite | See `lib/auth.py` resolution order |
| Excel I/O | openpyxl + xlsxwriter | Reading uploaded files; writing exported reports |
| Charts | Plotly (interactive) + Kaleido (PNG export) | |
| Visual org chart | Graphviz (system binary on Streamlit Cloud) | Renders DOT to SVG inline |
| Image processing | Pillow ≥10.0 | Photo resize/crop |
| Python | 3.11+ | |

`requirements.txt` unchanged from v11.3.

---

## 4. File Structure (v11.4)

```
hr_app/
├── app.py                    # Login + module-hub home page (UPDATED v11.4)
├── requirements.txt
├── README.md
├── SECURITY_GUIDE.md
├── SYSTEM_FLOW.md
├── USER_MANUAL.md
├── PROJECT_HANDOFF.md        # ← this file
├── .gitignore                # excludes data/, config/auth.yaml, .streamlit/secrets.toml
├── .streamlit/
│   └── config.toml           # Anca CI theme (cyan/purple/magenta)
├── assets/
│   ├── logo.png              # 350×247 PNG
│   ├── logo@2x.png           # 700×494 retina
│   └── logo_transparent.png  # used by sidebar/login
├── config/
│   ├── __init__.py
│   └── auth_config.py        # bcrypt + Secrets + extra_users bootstrapping
│                             # *** SOURCE OF TRUTH for user accounts ***
├── data/
│   └── hr.db                 # SQLite (gitignored, ephemeral on Cloud)
├── lib/
│   ├── __init__.py
│   ├── auth.py               # NEW v11.4 — capability resolution + page guards (~380 lines)
│   ├── calculations.py       # 591 lines — build_report, standard_working_days_in_period
│   ├── db.py                 # ~1010 lines — schema + helpers (UPDATED v11.4: calls RBAC migration)
│   ├── exports.py            # 380 lines — to_excel_bytes, to_png_bytes
│   ├── i18n.py               # ~310 lines — TR dict ~115 strings (UPDATED v11.4)
│   ├── landing.py            # NEW v11.4 — render_module_hub (~240 lines)
│   ├── page_utils.py         # ~245 lines — require_login, page_header (UPDATED v11.4)
│   ├── parsers.py            # 629 lines — all upload-file parsers
│   ├── photo_utils.py        # 110 lines — validate_and_resize_photo
│   ├── rbac_migration.py     # NEW v11.4 — 7 RBAC tables (~240 lines)
│   ├── rbac_seed.py          # NEW v11.4 — roles, modules, caps, default matrix (~490 lines)
│   ├── style.py              # 400 lines — inject_anca_style CSS
│   └── templates.py          # 416 lines — 9 Excel template generators
└── pages/
    ├── 1_Report.py           # 348 lines — gated by report.access (UPDATED v11.4)
    ├── 2_Charts.py           # 265 lines — gated by report.view_charts (UPDATED v11.4)
    ├── 3_Upload.py           # 321 lines — gated by report.upload (UPDATED v11.4)
    ├── 4_Configuration.py    # 673 lines — gated by report.edit_config (UPDATED v11.4)
    ├── 5_Employees.py        # 457 lines — gated by orgchart.view (UPDATED v11.4)
    ├── 6_Users.py            # 67 lines — gated by system.manage_users (UPDATED v11.4)
    ├── 7_Change_Requests.py  # 112 lines — gated by submit/approve_changes (UPDATED v11.4)
    ├── 8_Signup_Review.py    # 137 lines — gated by system.manage_users (UPDATED v11.4)
    ├── 9_Login_Audit.py      # 68 lines — gated by system.view_audit (UPDATED v11.4)
    ├── A_Org_Chart.py        # 491 lines — gated by orgchart.view (UPDATED v11.4)
    └── B_Visitor_Portal.py   # NEW v11.4 — gated by visitor.access (~85 lines)
```

---

## 5. Database Schema

All tables defined in `lib/db.py` (existing schema) + `lib/rbac_migration.py` (v11.4 additions). Schema migrations applied at `init_db()` startup (additive only, never drops columns).

### Core data (unchanged)
- `employees`, `employees_extended` (with v11.3 photo_blob + dotted_managers), `managers`, `cost_groups`, `holidays`, `hour_config`, `targets`

### Period data (unchanged)
- `timesheet`, `ot_entries`, `upload_log`, `period_overrides`

### v11.3 customization (unchanged)
- `org_chart_styling` — category/key/colors

### v11.3 per-user overrides (unchanged)
- `user_overrides` — username, override_key, override_value (JSON). Keys: `holidays`, `hour_config`, `period_overrides`, `cost_group_tops`

### v11.3 workflow / audit (unchanged)
- `change_requests`, `signup_requests`, `login_audit`

### v11.4 RBAC additions (7 new tables — see Section 15)
- `roles` — 7 role definitions (visitor → super_admin)
- `modules` — 8 modules (3 active, 5 locked placeholders)
- `capabilities` — 18 capability tokens
- `role_capabilities` — default capability set per role (matrix)
- `user_roles` — explicit per-user role-key assignment (Super Admin override + bootstrap)
- `user_capability_overrides` — per-user grant/revoke (Super Admin only)
- `approval_priority` — sequential approval ordering (foundation only — UI in Session 2)

### Resolved-value pattern (still used)
Most read functions come in pairs:
- `db.get_holidays()` — master only
- `db.effective_holidays(username)` — applies user override on top of master

This pattern is consistent across holidays / hour_config / period_overrides / cost_group_tops.

### v11.4 capability resolution pattern (new, lives in `lib/auth.py`)
```
effective_capabilities(username) = (role_default_caps ∪ user_grants) − user_revokes

where role = user_roles.role_key (if row exists)
       OR LEGACY_ROLE_MAP[auth_config.users[username].role]   (YAML fallback)
       OR None                                                 (fails closed)
```

---

## 6. ⚠️ Critical bug: B1 — Period override "not working"

**STATUS:** 🔴 still open. Slated for Session 3.

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
The user's reference Excel (`Actual_working_hours_for_FN__Rev_20260507_.xlsx`, sheet "Apr 26 ") uses **only one formula** for Working Hours — Standard with leave deductions. There is no "actual mode" in their Excel.

### Recommended fix
Two paths:
1. **Auto-switch to Standard mode when an override is active.** Show a banner: "🎛️ Period override active — using Standard formula HC × 10 × 6.99". *Easier, lower regression risk.*
2. **Make overrides apply in Actual mode too.** When the user sets WD/Hrs, replace the timesheet sum with computed standard. *More invasive, may surprise users who genuinely want timesheet data.*

I recommend Path 1. Plus rethinking the default mode — if the user's Excel logic is canonical, default the report to Standard mode and only offer Actual as opt-in.

---

## 7. Calculation Formulas (canonical, from user's Excel)

These are the **target formulas** the system must implement. All cell references are from `Actual_working_hours_for_FN__Rev_20260507_.xlsx`, sheet `Apr 26 `.

### 7.1 Working Hours
```
H3 = (D3 × F36 × F37) − IF(F38="Y", W3, 0) − IF(F39="Y", K3, 0)
```
- `D3` = Total HC | `F36` = Working days | `F37` = Daily std hours
- `F38="Y"` → deduct AL hours | `F39="Y"` → deduct other leave hours
- `W3` = Total AL hours | `K3` = Total absent hours (excl AL)

In v11+ the system has **5 toggles** (AL / Sick / Business / WithoutPay / Include AL in %Absent) — enhancement over the Excel.

### 7.2 % Absenteeism
```
N3 = (K3 + IF(F40="Y", W3, 0)) / H3
```

### 7.3 % OT
```
V3 = U3 / (H3 + U3)
```

### 7.4 OT/Absent unit ↔ hour conversion (NOT YET IMPLEMENTED)

⚠️ Roadmap item (Session 3+).

User wants the system to convert OT/Absent hours from raw timesheet uploads using two cases:

**Case 1: OT/Absent on weekend/holiday over 8 hours** — divide raw hours by **shift normal working hours**, store as fractional shift "units", multiply units × daily standard hours when reporting.

**Case 2: OT/Absent under shift normal hours** — use directly as hours.

Implementation needs: `shift_normal_hours` admin setting, modified parsers, dual `hours`/`units` storage.

---

## 8. Roadmap (status as of 2026-05-08)

### A. Multi-module HR suite architecture — ✅ FOUNDATION DONE in v11.4
- ✅ Module manifest in `lib/rbac_seed.py` (8 modules, 3 active + 5 locked)
- ✅ Module hub landing page filters by capability
- ✅ Each page declares its required capability via `require_login(capability="...")`
- ⏳ Still TBD: shared-data-layer formalization (currently every module reaches into `lib/db.py`)

### B. Role-based access control — ✅ PHASE 1 DONE in v11.4
- ✅ 7 roles instead of original 4-tier sketch (Visitor/Viewer/Supervisor/Manager/Finance/Admin/Super Admin)
- ✅ Capability tokens at both module-level and action-level
- ✅ Per-user grant/revoke override in DB
- ✅ Approval-priority schema (sequential approval) — UI deferred
- ⏳ Phase 2 (Session 2): Super Admin UI for matrix editing + per-user overrides + new-user form
- ⏳ Phase 2 (Session 2): Excel bulk upload for users + role assignments + override sheet

### C. UI redesign for Report and Dashboard pages — ❌ NOT STARTED
1. Move filters/calculation settings into a right-side drawer
2. Drawer should be interactive (changes apply live)
3. Per-control "apply to current page only / globally" toggle
4. Move summary metrics ABOVE the report table
5. Categorize the right drawer (Period / Filters / Calculation / Display)
6. Export buttons stay at bottom
7. "Personal overrides applied" banner clearly visible

For Dashboard: similar drawer structure for chart-control settings.

### D. Dashboard chart parity — ❌ NOT STARTED
**13 charts** to replicate from `FY2026_HR_Metric_Update_20260506.xlsx`:
- FY trend (annual)
- Monthly Absenteeism By Group / By Criterion
- Monthly Overtime By Group
- Monthly Absenteeism — Sales / Engineering / Quality / Production / Maintenance / Supply Chain
- 3 bar charts (FY variants)

Each chart must include: complete value labels, summary bubble (current FY cumulative vs current calendar month), Australian FY definition (July → June).

Plus: bulk historical upload template for multi-year trend backfill.

### E. Looker Studio / Power BI-style configurable formulas — ❌ NOT STARTED
Admin defines metrics as expressions referring to base columns + parameters. **Effort estimate: 2-3 weeks.** Candidate libs: `simpleeval`, `formulas`.

### F. Logo quality fix — ✅ DONE in v11.3

---

## 9. Known data structure of source files (unchanged)

### `Employee_List_MASTER` — Excel admin uploads
- Sheet: "Headcount Updated" — real headers row 4, data row 5
- 174 employees, 172 manager links resolve cleanly

### Timesheet upload — already-parsed, per-employee per-month: work hrs, absent hrs, sick hrs, personal hrs, annual hrs

### OT upload (auto-detects format)
- **Dated format** — one row per OT instance with date column
- **Legacy format** — pre-aggregated monthly per employee

### Leave summary — per-employee monthly: annual / sick / personal / business / without-pay

---

## 10. User preferences and decisions log

### Default language
Thai (TH). English is the toggle alternative.

### Default credentials (when no Streamlit Secrets set)
- `admin / admin123` — full admin → maps to `super_admin` in v11.4 via USER_MIGRATION_MAP
- `viewer / viewer123` — viewer → maps to `viewer` in v11.4
- `trial / Trial2026!` — trial viewer (only via `[extra_users.trial]` Secret) → maps to `visitor` in v11.4

### Branding
- Cyan `#009ADE` (primary) / Purple `#715091` (secondary) / Magenta `#E31D93` (accent)
- White-major frosted-glass UI
- Inter / Sarabun fonts (Thai fallback: Noto Sans Thai)

### Manager role colors in org chart (default, customizable in Settings)
- Mgr. → purple #715091  | Sup. → cyan #009ADE | Leader → magenta #E31D93 | (staff) → light gray #F3F4F6

### Photo specs
- Allowed: JPG, PNG, WebP, BMP, GIF, ≤5 MB
- Auto-processed: cropped square, 200×200, JPEG q85, capped at 100 KB
- 174 employees × ~30 KB ≈ ~5 MB total DB impact

### Currency / numbers
- Decimal commas off (English-style)
- Hours to 1 decimal place
- Percentages to 2 decimal places (e.g. 0.27%)

### Fiscal year
July 1 (year N-1) → June 30 (year N) — Australian/Anca FY

### Date format
ISO `YYYY-MM-DD` everywhere internally; UI may show `DD/MM/YYYY`

### Working agreement (locked-in 2026-05-08)
- **Drop-in files only.** Claude must deliver complete files for direct overwrite — never instructions to manually edit code.
- **Every delivery ends with the standard format:** `📥 DOWNLOAD & DROP` block + `🚀 PUSH COMMAND` block + `🔁 IF PUSH IS REJECTED` block, all using Windows CMD paths.
- **Standard push command:** `cd C:\Users\Gurot\Downloads\20260506\hr_app_v11_complete\hr_app && git add . && git commit -m "..." && git push`
- **Push rejection recovery:** `git pull --rebase origin main && git push`
- **Decision style:** "push hard" — when the user approves a plan, build the maximum scope that fits the session.

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
- ❌ Postgres migration (still on ephemeral SQLite — see B2)
- ❌ 2FA for admin
- ❌ Per-month employee re-assignment manual override
- ❌ Account lockout / rate limiting on signup
- ❌ Module 2 (Manpower Budget) — placeholder card live, content TBD
- ❌ Salary/compensation module — placeholder card live, content TBD
- ❌ Multi-shift support (currently assumes single shift)
- ❌ OT unit↔hour conversion logic (Section 7.4)
- ❌ Right-drawer UI redesign (Section 8C)
- ❌ All 13 charts from Anca's reference workbook (Section 8D)
- ❌ Looker-style formula builder (Section 8E)
- ❌ B1 fix — period override Actual mode bug (Section 6)
- ❌ **Session 2: Super Admin UI for role-capability matrix + per-user overrides + bulk Excel user upload** (see Section 16)
- ❌ Sidebar polish — Streamlit's default `pages/` auto-discovery still shows all page filenames in the sidebar; defense-in-depth via `require_login` is fine for now, but a `st.navigation` refactor could fully hide pages by capability

---

## 13. How to bootstrap a fresh Claude chat

**Paste this entire document** as the first message, then say:

> "Please confirm you've read the handoff doc. Then [INSERT CURRENT TASK]. Remember the working agreement: drop-in files only, end every delivery with the 📥/🚀/🔁 blocks."

Claude should then:
1. Acknowledge what it's read
2. Ask clarifying questions if any (use the planning Q&A pattern: a few quick A/B/C questions before coding)
3. Propose a plan before writing code
4. Confirm scope before making large changes
5. Deliver complete files, never patches

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

## 15. ⚙️ v11.4 RBAC reference (NEW)

### The 7 roles

| Rank | role_key | EN | TH | Notes |
|---|---|---|---|---|
| 1 | `visitor` | Visitor | ผู้เยี่ยมชม | External guest. Sees ONLY Visitor Portal — no company data. |
| 2 | `viewer` | Viewer | ผู้ดู | Read-only — Org Chart only by default. |
| 3 | `supervisor` | Supervisor | หัวหน้างาน | **Tweak (2026-05-08):** only `system.login` + `orgchart.view`. Does NOT have `report.submit_changes`. |
| 4 | `manager` | Manager | ผู้จัดการ | Cost-centre manager. Sees Report Module (own dept) + Org Chart. Can submit & approve change requests. |
| 5 | `finance` | Finance Manager | ผู้จัดการฝ่ายการเงิน | Like Manager but `report.view_all` (across all departments). |
| 6 | `admin` | Admin | ผู้ดูแลระบบ | Data entry + user management + audit. Cannot edit role defaults or override per-user caps. |
| 7 | `super_admin` | Super Admin | ผู้ดูแลระบบสูงสุด | **The only role that can:** edit role-capability matrix (`system.manage_roles`), per-user grant/revoke (`system.override_user_caps`). |

### The 8 modules

| module_key | EN | Active? | External-allowed? | Default access cap |
|---|---|---|---|---|
| `report` | Report Module | ✅ | — | `report.access` |
| `orgchart` | Org Chart | ✅ | — | `orgchart.view` |
| `visitor` | Visitor Portal | ✅ | ✅ | `visitor.access` |
| `budget` | Manpower Budget | 🔒 locked | — | `budget.access` |
| `salary` | Salary & Compensation | 🔒 locked | — | `salary.access` |
| `training` | Training Records | 🔒 locked | — | `training.access` |
| `recruitment` | Recruitment | 🔒 locked | — | `recruitment.access` |
| `performance` | Performance Reviews | 🔒 locked | — | `performance.access` |

### The 18 capabilities

**System-wide (6):** `system.login`, `system.manage_users`, `system.manage_roles`, `system.override_user_caps`, `system.bulk_upload_users`, `system.view_audit`

**Report module (9):** `report.access`, `report.view_own_dept`, `report.view_all`, `report.upload`, `report.edit_config`, `report.approve_changes`, `report.submit_changes`, `report.view_charts`, `report.export`

**Org Chart (2):** `orgchart.view`, `orgchart.edit`

**Visitor (1):** `visitor.access`

### Default role-capability matrix (`lib/rbac_seed.py` ROLE_CAPS)

| Role | Caps count | Caps |
|---|---|---|
| visitor | 2 | login, visitor.access |
| viewer | 2 | login, orgchart.view |
| supervisor | 2 | login, orgchart.view |
| manager | 8 | login, report.{access, view_own_dept, approve_changes, submit_changes, view_charts, export}, orgchart.view |
| finance | 8 | login, report.{access, view_all, approve_changes, submit_changes, view_charts, export}, orgchart.view |
| admin | 14 | login, system.{manage_users, bulk_upload_users, view_audit}, report.* (all 8 except own_dept), orgchart.{view, edit} |
| super_admin | 16 | admin's set + system.{manage_roles, override_user_caps} |

**Idempotency note:** the matrix is only seeded for a role if that role has ZERO entries in `role_capabilities`. So Super Admin edits via the (Session 2) UI are preserved across redeploys, even though the seed runs on every startup.

### Role resolution order (`lib/auth.get_user_role()`)

1. **`user_roles` table** — if a row exists for `username`, use its `role_key`. (Source: bootstrap from `USER_MIGRATION_MAP` + Super Admin assignments via Session 2 UI.)
2. **YAML legacy role mapping** — look up the user in `auth_config.list_users()`, take their `role` field, map via `LEGACY_ROLE_MAP`:
   - legacy `admin` → new `admin` (Level 6, **NOT** super_admin — only the bootstrap username gets super_admin)
   - legacy `manager` → new `manager`
   - legacy `viewer` → new `viewer`
3. **None** — fails closed (zero capabilities).

### Bootstrap user_roles (`USER_MIGRATION_MAP` in `lib/rbac_seed.py`)

```python
USER_MIGRATION_MAP = {
    "admin":  "super_admin",   # default v11.3 admin → Super Admin
    "viewer": "viewer",
    "trial":  "visitor",
    # "chaiyanan": "super_admin",  # ← uncomment + edit if your username isn't 'admin'
}
```

**⚠️ Critical:** because Streamlit Cloud's SQLite is ephemeral, if Chaiyanan's actual login username is NOT `admin`, he must add it to this map. Otherwise his role resets to `admin` (Level 6) on every redeploy, and he loses access to the Session 2 role-editor UI.

### Effective capability formula

```
effective_capabilities(username) = (role_default_caps  ∪  user_grants)  −  user_revokes
```

`user_grants` and `user_revokes` come from the `user_capability_overrides` table. Super Admin edits these via the (Session 2) UI.

### Page guard pattern (v11.4)

```python
# pages/X_SomeFeature.py
from lib.page_utils import require_login

# Single capability:
require_login(capability="report.access")

# ANY of multiple:
require_login(any_capability=["report.submit_changes", "report.approve_changes"])

# Legacy (still works for backward compat):
require_login(admin_only=True)
require_login(manager_or_admin=True)
require_login()  # any logged-in user
```

### Defensive auth (v11.4 hotfix)

Every SQL query in `lib/auth.py` is wrapped in `try/except sqlite3.OperationalError`. If any RBAC table is missing or locked, the function falls back to YAML-derived roles (or empty results) instead of crashing the page. This makes deploys self-healing — even if the migration partially failed, the next deploy will reconcile.

---

## 16. 📋 Session 2 plan (NEXT)

### Goal
Make the v11.4 RBAC system **end-user editable**. Right now, anything beyond the seeded defaults requires SQL. Session 2 ships the UI.

### Deliverables
1. **Role editor page** (`pages/C_Role_Editor.py`, gated by `system.manage_roles` → super_admin only)
   - Matrix view: rows = 7 roles, columns = 18 capabilities, checkboxes
   - Save → writes to `role_capabilities` table
   - Reset-to-default button (re-seeds from `lib/rbac_seed.py` ROLE_CAPS for the chosen role)

2. **Per-user override editor** (extension to `pages/6_Users.py`, gated by `system.override_user_caps` → super_admin only)
   - Pick user → table of all caps with three-state radio: inherit / grant / revoke
   - Save → writes to `user_capability_overrides`
   - Display effective caps preview before save

3. **New-user form upgrade** (`pages/6_Users.py`)
   - Replace 3-role dropdown with full 7-role dropdown
   - On save: write to `auth_config` (YAML) AND `user_roles` table
   - Admin can assign any role EXCEPT super_admin; only Super Admin can grant super_admin

4. **Bulk Excel user upload** (new tab in `pages/6_Users.py`, gated by `system.bulk_upload_users`)
   - Three sheets in template: `users`, `role_assignments`, `capability_overrides`
   - `users` sheet: username, name, email, password, role_key
   - `role_assignments` sheet: username, role_key (for reassigning existing users)
   - `capability_overrides` sheet: username, capability_key, override_type (grant/revoke)
   - Validation + dry-run preview before commit

5. **Approval-priority UI** (extension to `pages/4_Configuration.py` or new tab)
   - For users with `report.approve_changes`: drag-and-drop ordering of approval sequence
   - Writes to `approval_priority` table
   - Wire into `pages/7_Change_Requests.py` so approvals follow the priority order

### Estimated complexity
- Role editor matrix: ~150 lines, 1-2 tool calls
- Per-user override editor: ~120 lines
- New-user form upgrade: ~40 lines (light edit)
- Bulk Excel upload: ~250 lines (the biggest piece — needs a template file + validation logic + dry-run UI)
- Approval-priority UI: ~100 lines + change_requests wiring

Total: ~660 lines across ~3 new + ~3 modified files. Comfortably one focused session.

### Data the next Claude needs from Chaiyanan to start Session 2
- Confirm v11.4 hotfix deployed cleanly and module hub renders (sanity check)
- Confirm his login username (so USER_MIGRATION_MAP can be pre-pended if not `admin`)
- Confirm whether bulk-upload should support **creating** brand-new users (writes to YAML) or only **reassigning roles** for existing users (writes to user_roles only). Bulk-create is more useful but writing to YAML is more invasive.
- Approval priority — is it global per capability (one ordering for all `report.approve_changes` holders), or per-department (different orderings per cost-centre)?

---

*End of handoff. Last updated 2026-05-08 by Claude Opus 4.7 working with Chaiyanan Singson on the Anca HR Reporting project. Continues from v11.3 handoff (2026-05-07). Next: Session 2 — Super Admin UI for RBAC management.*
