# AMS HR System — Complete Package (2026-06-12)

Everything in one place: the Streamlit HRM (Report, Org Chart with photos,
Employee Data with PDPA controls, Leave & OT with 3-level reporting-line
approval + email reminders, Car Booking front door, Stationery ERP for
OFFICEMATE POs and reimbursements, Users & Roles), plus the car-booking
Apps Script hub (apps_script/Code.gs) and the daily reminder cron
(scripts/ + .github_workflow_reminders.yml).

START HERE → **BUILD_MANUAL.pdf** (step-by-step for a beginner, with diagrams).
Quick path: §2 run locally → §3 GitHub → §4 Streamlit Cloud → §5 accounts →
§6 Supabase (critical!) → §7 load MASTER → §9 email → §10 car booking → §11 ERP.

First login: superadmin / ChangeMe!2026  — change it immediately (§5).
Secrets template: .streamlit/secrets.toml.example (never commit real secrets).

Verified in build testing: MASTER V.6 import (190 rows, 43 columns), 3-level
chain on real reporting lines (welder → Amontap Chaisit → Somchai Srijun →
Ekphusit Boonjong), approve & mid-chain-reject lifecycles, reminder digests,
PO PO-2606-001 (228.00 ฿) and claim RB-2606-001 full lifecycles, RBAC
(admin has no salary access), app boots clean.

Two things only you can finish (flagged in the manual):
1. apps_script/Code.gs F map — copy the filled customfield ids from your
   deployed copy (§10 step 4).
2. pages/1_Report.py is a clean baseline — keep your live file if it has
   evolved further (§4 note).
