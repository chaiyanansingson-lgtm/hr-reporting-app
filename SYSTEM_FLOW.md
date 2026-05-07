# HR Reporting System — Complete Flow & Routing Documentation

This document describes every process and decision point in the system, in
plain English, so you can understand the logic and decide what to change.

---

## 1. APPLICATION ENTRY & SESSION FLOW

When a user opens the URL (`https://anca-hr-reporting.streamlit.app`):

```
Browser opens app.py
       |
       v
1. Load CSS theme (Anca CI frosted glass)
2. Initialize language (default Thai)
3. Initialize SQLite database (auto-create tables)
4. Read Streamlit Secrets to ensure admin/viewer accounts
   exist with up-to-date passwords
5. Check session_state.authenticated
       |
       v
   authenticated == True ?
       |
   +---+---+
   |       |
  No      Yes
   |       |
   v       v
render_login()   render_home()
(login screen)   (homepage with metrics)
```

---

## 2. SIGN-IN FLOW (TAB: Sign in)

```
User submits login form: (username, password)
       |
       v
Capture client IP and User-Agent
(from X-Forwarded-For header on Cloud)
       |
       v
Username or password empty?
   |
   +---+----+
   |        |
 EMPTY   NON-EMPTY
   |        |
   v        v
Log: failed,   Look up user in auth.yaml
reason=        |
"empty user    v
or password"   User exists?
   |             |
   |       +-----+-----+
   |       |           |
   |      No         Yes
   |       |           |
   |       v           v
   |  Log: failed,  Verify bcrypt hash
   |  reason="user     |
   |  not found"       v
   |       |        Hash matches?
   |       |             |
   |       |       +-----+-----+
   |       |       |           |
   |       |     No          Yes
   |       |       |           |
   |       |       v           v
   |       |   Log: failed,  Log: SUCCESS,
   |       |   reason="wrong with role
   |       |   password"        |
   |       |       |            v
   |       |       |        Set session:
   |       |       |        - authenticated=True
   |       |       |        - username, role, name
   |       |       |            |
   |       |       |            v
   |       |       |        Redirect to home
   v       v       v
Show "Invalid credentials" error
```

**Audit trail captured for EVERY attempt:**
- Username, success/fail, IP, User-Agent, timestamp, role (if successful), failure reason

---

## 3. SIGN-UP FLOW (TAB: Sign up)

```
User fills signup form:
- username, email, full name, employee #
- requested role (viewer or manager only)
- reason for access (10+ chars required)
- password (8+ chars) + confirm
       |
       v
Validation:
- Username 3+ chars, available
- Email format valid
- Full name not empty
- Reason 10+ chars
- Password 8+ chars, matches confirm
- No pending duplicate request
       |
       v
   Valid?
       |
   +---+---+
   |       |
  No      Yes
   |       |
   v       v
Show     Hash password (bcrypt)
errors,    |
form       v
stays    Capture IP + User-Agent
open       |
           v
       Insert into signup_requests table:
       - status = 'pending'
       - all form fields
       - password_hash (NOT plain password)
       - request_ip, request_user_agent
           |
           v
       Show success message with request ID
           |
           v
       Form clears, user waits for approval
```

**No automatic email is sent yet** — the admin must manually check the
"Signup Requests" page (visible to admin only).

---

## 4. SIGNUP APPROVAL FLOW (admin only)

```
Admin opens Signup Requests page
       |
       v
Display all pending signup requests as cards, with these checks shown:
- Does Emp. No. match active employee?
- Same IP submitted other requests?
- Time submitted, all form fields
       |
       v
   Approve or Reject?
       |
   +---+----+
   |        |
APPROVE   REJECT
   |        |
   v        v
Admin     Admin enters
chooses:  rejection note
- Final     |
  role      v
  (viewer/  Update request:
   mgr/     - status = 'rejected'
   admin)   - reviewed_by = admin
- Approval  - reviewed_at = now
  note      - review_notes = note
   |        |
   v        v
Update    Show "Rejected"
request:
- status = 'approved'
- reviewed_by = admin
- reviewed_at = now
- review_notes = note
- granted_role = chosen
   |
   v
Create user account in auth.yaml:
- username
- name (full name from request)
- email
- password = stored hash
- role = granted_role
   |
   v
Show "Approved — user now exists"
   |
   v
(User can now sign in immediately)
```

**Both approve and reject create permanent audit trail** — `reviewed_by`,
`reviewed_at`, and `review_notes` for every decision.

---

## 5. PAGE ACCESS BY ROLE

```
                        AUTH GATE
                       (every page)
                            |
        +-------------------+-------------------+
        |                   |                   |
     VIEWER             MANAGER               ADMIN
        |                   |                   |
        v                   v                   v
     Can see:            Can see:            Can see:
     ---------           ---------           ---------
     Home                Home                Home
     Report              Report              Report
     Dashboard           Dashboard           Dashboard
     Employees           Employees           Employees
     Org Chart           Org Chart           Org Chart
                         Change Requests     Change Requests
                         (their own)         (all + approve)
                                             Upload Data
                                             Configuration
                                             Users
                                             Signup Requests
                                             Login Audit
```

---

## 6. CHANGE REQUEST FLOW (manager → admin)

```
Manager opens Employees page → "Request a change" form
       |
       v
Pick employee, pick field to change
(Cost Code / Type / Direct-Indirect / Level / Name)
       |
       v
Enter new value + reason for change
       |
       v
Submit → row inserted into change_requests table
(status = 'pending')
       |
       v
Admin opens Change Requests page
       |
   +---+----+
   |        |
APPROVE   REJECT
   |        |
   v        v
Update    Update change_requests
employee  row only:
record    - status='rejected'
AND       - review_notes
change_   |
requests  |
   |        |
   v        v
Manager sees status updated on next visit
```

**Admin shortcut:** the same form has an "Apply immediately" checkbox that
both creates AND auto-approves the change in one step. This still creates an
audit trail.

---

## 7. DATA UPLOAD FLOW (admin only)

```
Admin opens Upload Data page
       |
       v
   +-----+------+----------+----------+
   |     |      |          |          |
Timesheet  OT  Leave   Reference (NameList,
(primary) (auto-      (cross-     Manager,
          detect)     check)      CostGroup,
   |       |          |           Holidays,
   |       |          |           Employee Master)
   v       v          v               v
Parse  Try dated  Parse legacy   Parse Excel
Buddhist format   format only.   by sheet name
BE     first.                    & column name.
dates, If fails →                    |
extract fall back                    v
period.   to legacy              Update tables
   |    summary.                 (employees,
   v       |                     cost_groups,
Replace  +-+-+                   managers,
timesheet|   |                   holidays,
rows for v   v                   employees_extended)
that  Override Cross-check
period. Timesheet only — does
        OT for  NOT change
        that    Timesheet OT.
        period.
       |
       v
Log row in upload_log table
(file_type, file_name, period, rows, by, when)
       |
       v
Show success message + summary
```

---

## 8. REPORT CALCULATION FLOW

```
User opens Report page
       |
       v
Filters & calculation settings:
- Period (e.g. 2026-04)
- Unit (Hours / Days)
- Top group filter (multi-select)
- Function filter (multi-select)
- WH mode (Actual / Standard)
- Deduct AL toggle
- Deduct other leaves toggle
- Include AL in %Absent toggle
- Show AL columns toggle
- Leave-type breakdown multi-select
       |
       v
Pull all timesheet rows for period.
Pull OT entries (if dated format
exists for this period, override
the timesheet's OT columns).
Join with employees + cost_groups.
       |
       v
Compute Working Hours by mode:
   ACTUAL: sum work_hours from
           timesheet for this emp
   STANDARD:
   1. Look up period_overrides for this period
   2. If overridden → use those
      working_days × daily_std
   3. Else → auto-compute from
      holidays + weekday hour cfg
   4. WH = HC × working_days × daily_std
       |
       v
Apply deduction toggles:
- if "deduct AL":  WH -= AL hours
- if "deduct other": WH -= sick+bus+wp
       |
       v
Compute %Absent:
- if "include AL in %Absent":
    %Absent = (Absent + AL) / WH
- else:
    %Absent = Absent / WH
       |
       v
Aggregate by:
- Function (department) — leaf rows
- Top group — subtotal rows
- Grand total — final row
       |
       v
Render styled table + Export buttons
```

---

## 9. ORG CHART FLOW

```
User opens Org Chart page
       |
       v
Load employees_with_extended (JOIN of
employees + employees_extended)
       |
       v
Build hierarchy:
- children_of[mgr_emp_no] = [employees]
- roots = employees with no resolvable
  manager_emp_no
       |
       v
User picks view:
- Tree (expandable)
- Table (flat, filterable)
- By Department
       |
       v
Render selected view
```

---

## 10. CRITICAL POLICIES & SAFETY

### Where passwords live
- **Streamlit Secrets** — `[auth] admin_password`, `[auth] viewer_password`
- These seed `auth.yaml` on every boot. Changing the secret in Streamlit Cloud
  changes the live login on next restart (~2-3 min after redeploy).
- `auth.yaml` is in `.gitignore` and is **ephemeral** on Cloud (recreated each boot).

### What's in audit logs
- **login_audit** — every sign-in attempt, success or fail, with IP and User-Agent
- **signup_requests** — every signup with admin's review decision
- **change_requests** — every employee data change with admin's review decision
- **upload_log** — every file upload with who/what/when

These are append-only — no UI to delete entries (intentional, for forensics).

### What's NOT yet implemented (gaps to fill before going fully live)
1. **Email notification** when signup is submitted/approved/rejected
   - Right now admin must manually check the page
   - Future: integrate SendGrid or Resend (free tiers exist)
2. **Forgot password** flow
3. **Password complexity requirements** (currently just 8+ chars)
4. **Account lockout** after N failed login attempts
5. **Rate limiting** on the signup form (anyone can spam-submit)
6. **2FA** for admin accounts
7. **Persistent storage** — SQLite is wiped on Streamlit Cloud restart;
   Postgres migration recommended before going live with real data
8. **HTTPS-only cookies** — Streamlit Cloud already provides HTTPS, but
   cookie hardening could be improved

---

## 11. EDIT POINTS — WHERE TO CHANGE EACH FLOW

| To change... | Edit this file |
|---|---|
| Login form layout / wording | `app.py` → `render_login()` |
| Sign-up validation rules | `app.py` → `_handle_signup_submission()` |
| Allowed signup roles | `app.py` (look for `["viewer", "manager"]`) |
| Password hash / verify | `config/auth_config.py` |
| What gets logged on login | `lib/db.py` → `log_login_attempt()` |
| Audit log filters | `pages/9_Login_Audit.py` |
| Signup approval logic | `pages/8_Signup_Review.py` |
| Page-by-page role gating | `lib/page_utils.py` → `require_login()` |
| Sidebar menu items | `app.py` and `lib/page_utils.py` → `NAV_ITEMS` list |
| Translation strings (TH/EN) | `lib/i18n.py` → `TR` dict |
| Brand colors / styling | `lib/style.py` |
| Report calculation logic | `lib/calculations.py` |
| File parser for any upload | `lib/parsers.py` |
| Database schema | `lib/db.py` → `_SCHEMA` |
| Org chart rendering | `pages/A_Org_Chart.py` |
