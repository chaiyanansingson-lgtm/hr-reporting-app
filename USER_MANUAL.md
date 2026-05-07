# 📖 User Manual — HR Reporting App

**For: trial users / managers / viewers (non-admin)**

This guide shows you how to sign in, view reports, and customize calculations
for your own analysis without affecting other users.

App URL: **https://anca-hr-reporting.streamlit.app**

---

## 1. Signing in

Open the app URL in any browser (Chrome, Edge, Firefox, Safari — all work).

You'll see the login screen with the Anca logo. Two tabs:
- **🔐 Sign in** — use this if you already have an account
- **📝 Sign up** — request a new account (admin must approve)

### Trial account credentials

If admin gave you the trial account:

| Username | Password | Role |
|---|---|---|
| `trial` | `Trial2026!` | viewer |

(Tell admin if you'd like a personal username instead — they can create one for you.)

### Forgot password?

Contact admin. There's no self-service password reset yet.

### Language

The app defaults to Thai. To switch: scroll the **left sidebar** to the bottom
and click the **🇬🇧 EN** button. Click 🇹🇭 ไทย to switch back. Your choice
sticks for your session.

---

## 2. What you can see and do (by role)

### 👁 Viewer role
- ✅ View reports and charts
- ✅ View the employee directory and org chart
- ✅ Customize calculation settings for **your view only** (Personal Mode)
- ✅ Export Excel / PNG
- ❌ Cannot upload data
- ❌ Cannot edit master settings (settings that affect everyone)
- ❌ Cannot submit employee change requests
- ❌ Cannot approve anything

### 👔 Manager role
Everything viewer can do, **PLUS:**
- ✅ Submit employee change requests (e.g. "move John from Cost Center 210 to 212")
- ✅ Bulk-submit change requests via Excel template
- ✅ See your own submitted requests and admin's decisions

### 👑 Admin role (separate from this manual)
Full access including data uploads, master configuration, and approving requests.

---

## 3. The pages in the sidebar

| Page | What it does |
|---|---|
| 🏠 **Home** | Welcome page with quick metrics |
| 📊 **Report** | The main HR report — filterable, downloadable as Excel/PNG |
| 📈 **Dashboard** | Trend charts: absenteeism, OT, turnover vs targets |
| 🌳 **Org Chart** | Company structure: tree view, table, by department |
| 👥 **Employees** | Employee directory + change-request form (manager only) |
| ⚙️ **Configuration** | Settings page — admin sees Master mode, others see Personal mode |

Pages you don't have access to are hidden from your sidebar automatically.

---

## 4. Reading the Report page

When you open **📊 Report**, you'll see:

1. **Filters at top** — pick the period (e.g. 2026-04), unit (Hours / Days),
   which top groups and functions to include.

2. **Working Hours mode** — choose:
   - **Actual** = sum of hours actually clocked from the Timesheet
   - **Standard** = expected hours = headcount × working days × daily standard hours

3. **Deduct from Working Hours** — five toggles. Tick to subtract that leave type:
   - 🟦 Annual Leave
   - 🟦 Sick Leave
   - 🟦 Business Leave
   - 🟦 Without Pay
   - 🟦 Include AL in %Absent (counts AL toward absenteeism rate)

4. **Add leave-type breakdown columns** — multiselect to add per-type columns
   to the table (Sick / Business / Without Pay).

5. **The big table** — with subtotals per top-group and a grand total at the bottom.

6. **Export buttons** — Excel (.xlsx) and PNG image.

If you've changed any personal settings (see next section), the report will show
a yellow "🎛️ Personal calculation overrides ACTIVE" banner above the table.

---

## 5. Personal calculation settings (KEY FEATURE for trial users)

This is what makes the app safe to share. **You can change calculation values
in your view without affecting the master database or any other user.**

### Where

Sidebar → **⚙️ Configuration**

### What you can override

Five tabs, each editable in **Personal Mode**:

#### 📅 Holidays
Add days that count as holidays in YOUR view, or unmark admin holidays as
working days. Useful for what-if scenarios like "what if we work through
Songkran day 5?"

#### 🗂️ Cost Groups
Reassign cost codes to different top groups. Useful for what-if reorganization
scenarios like "what if Painting moved from MANU to MANU Support?"

#### ⏱️ Hour rules
Override the standard hours per weekday (Mon-Sun) or the day-hour conversion
factor. Useful for testing different assumed working schedules.

#### 🎯 KPI Targets
Override the dashed target lines on the Charts page. Each user can have
different absenteeism / OT targets in their view.

#### 📆 Per-Month Overrides
Set custom working days and daily std hours for a specific month, like
the F36/F37 cells in the original Excel report.

### How to use it

1. Open ⚙️ **Configuration**
2. **For non-admin:** the page automatically shows your Personal settings.
   **For admin:** click **"👤 My Personal Settings"** at the top toggle.
3. Go to any tab (e.g. 📅 Holidays)
4. Click in any cell to edit. Add a row by clicking the **+** at the bottom.
   Delete a row by selecting it and pressing Delete.
5. Click the **💾 Save** button below the editor
6. A green confirmation appears
7. Open the **📊 Report** page — it will now use your personal values

### Resetting

On any tab in Personal Mode, you'll see a "Reset" or "Clear my override" button.
Click it to revert that category back to the master values. No effect on other users.

### What gets exported

When you download the **Excel** file with personal overrides active, the file
includes a **memo block** at the bottom listing every difference between your
settings and the master settings. This makes it clear to anyone reading the
file that the numbers are based on your personal what-if assumptions.

---

## 6. Submitting a change request (managers only)

If you're a manager and you spot wrong employee data (wrong cost center,
wrong level, etc.), you can submit a request to fix it.

### Single request

1. Sidebar → **👥 Employees**
2. Scroll to "🔄 Request a change to an employee" form
3. **Find employee:** type any of:
   - **Search by ID** (e.g. `1021568`)
   - **Search by first name** (e.g. `Nantachai`)
   - **Search by last/surname** (e.g. `Somboot`)
   - The employee dropdown shrinks to matches; pick one
4. Pick the **field to change** (Cost Code / Type / Direct-Indirect / Level / Name)
5. Enter the **new value** and a **reason** (10+ characters required)
6. Click **📨 Submit change request**
7. An admin will review on the **🔄 Change Requests** page; you'll see the
   status (pending / approved / rejected) on your **👥 Employees** page below
   the form.

### Bulk request (many at once)

Same page, scroll further down to "📤 Bulk submit change requests via Excel":

1. Click **📥 Download bulk template** — an Excel file with example rows
2. Fill in your rows (Emp. No., Field, New Value, Reason)
3. Save the file
4. Upload it back at the same place
5. Review the validation summary (rows with issues are flagged and skipped)
6. Click **🚀 Submit N change request(s)**

---

## 7. Org Chart

Sidebar → **🌳 Org Chart**

Three views:
- **Tree** — expandable hierarchy, click any name to see who reports to them
- **Table** — flat list filterable by department, manager, level
- **By Department** — employees grouped by their Dept by Location

Built from the Employee Master file uploaded by admin. If you spot wrong
manager links, submit a change request (see section 6).

---

## 8. Common questions

**Q: I changed something in Configuration but the Report still shows the old numbers.**
A: Make sure you clicked the 💾 Save button. Then open the Report page in a
fresh tab or click Streamlit's **R** key (or browser refresh F5). Personal
overrides apply on next render.

**Q: I want to reset all my personal overrides.**
A: Go to **⚙️ Configuration**, look for "Reset all my personal overrides" or
clear each tab individually with the per-tab Reset button.

**Q: Are my changes visible to other users?**
A: **No.** Personal overrides are per-username and only affect your view of
Reports and Charts. Other users see the admin's master values.

**Q: I uploaded the wrong file by accident.**
A: Only admins can upload data files. If you're a manager and you accidentally
submitted a wrong change request, ask admin to reject it on the
**🔄 Change Requests** page. Once rejected, the employee data is unchanged.

**Q: Can I be logged in on multiple devices?**
A: Yes. Each session is independent — your personal overrides stay tied to
your username, not your device.

**Q: I forgot my password.**
A: Contact admin. They can reset it on the **🔑 Users** page.

**Q: How do I sign out?**
A: Sidebar → bottom → **Sign out** button.

---

## 9. Reporting bugs / requesting features

The app is in active development. If you find anything weird or have ideas:

1. Take a screenshot
2. Email or message admin with the screenshot + a brief description of what
   you were doing when it happened

Common things to check before reporting a bug:
- Refresh the page (F5)
- Sign out and sign back in
- Clear your personal overrides (might be hiding the issue)
- Check you're using the right URL: `https://anca-hr-reporting.streamlit.app`

---

## 10. Security & privacy

- All data lives on Streamlit Community Cloud servers (US-hosted).
- The app uses HTTPS (encrypted connection).
- Every login attempt — successful or failed — is logged with your IP address.
  Admin can view this on the **🛡️ Login Audit** page.
- Personal calculation overrides are stored per-username; they are not shared
  with other users.
- The master employee data is only editable by admin.
- **Do not share your password.** If you suspect someone else has access to
  your account, ask admin to reset your password immediately.

---

*Manual version 11 · Updated for v11 release · Maintained by your friendly
HR Systems team.*
