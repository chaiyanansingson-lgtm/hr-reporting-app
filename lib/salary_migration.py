"""
lib/salary_migration.py — v11.5 Module 3 Salary & Compensation
Idempotent DB migration. Creates 4 tables:
  - salary_grade           : the 15-grade structure (O1-O3, L1-L12)
  - salary_grade_allowance : default allowance scheme per grade
  - salary_offer           : individual offer calculator records (audit trail)
  - salary_compliance      : statutory rates with effective dates (SSO/PVF/WCF/EWF)

All tables use CREATE TABLE IF NOT EXISTS — safe to run on every startup.
"""
import sqlite3
from typing import Optional


def run_salary_migration(conn: sqlite3.Connection) -> None:
    """Create salary tables if they don't exist. Safe to call repeatedly."""
    cur = conn.cursor()

    # --- 1. Salary grade master ----------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS salary_grade (
            grade_key       TEXT PRIMARY KEY,
            sort_order      INTEGER NOT NULL,
            layer           TEXT NOT NULL,
            track           TEXT NOT NULL,
            band_min        REAL NOT NULL,
            band_mid        REAL NOT NULL,
            band_max        REAL NOT NULL,
            ipe_pc          INTEGER,
            mgmt_ic         TEXT,
            typical_titles  TEXT,
            updated_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_by      TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_salary_grade_sort ON salary_grade(sort_order)")

    # --- 2. Default allowance scheme per grade -------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS salary_grade_allowance (
            grade_key       TEXT NOT NULL,
            allowance_code  TEXT NOT NULL,
            allowance_name  TEXT NOT NULL,
            default_amount  REAL NOT NULL DEFAULT 0,
            is_conditional  INTEGER NOT NULL DEFAULT 0,
            condition_note  TEXT,
            updated_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (grade_key, allowance_code)
        )
    """)

    # --- 3. Offer calculator audit ------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS salary_offer (
            offer_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_ref     TEXT NOT NULL,
            position_title    TEXT NOT NULL,
            proposed_grade    TEXT,
            proposed_gross    REAL NOT NULL,
            base_pct          REAL NOT NULL DEFAULT 0.92,
            sso_employer      REAL,
            pvf_employer      REAL,
            wcf_employer      REAL,
            ewf_employer      REAL,
            fixed_bonus_mos   REAL DEFAULT 1.0,
            kpi_bonus_mos     REAL DEFAULT 1.0,
            annual_benefits   REAL DEFAULT 0,
            severance_accr    REAL,
            total_monthly     REAL,
            total_annual      REAL,
            band_min          REAL,
            band_mid          REAL,
            band_max          REAL,
            penetration       REAL,
            market_p50        REAL,
            notes             TEXT,
            created_by        TEXT,
            created_at        TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_salary_offer_grade ON salary_offer(proposed_grade)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_salary_offer_created ON salary_offer(created_at DESC)")

    # --- 4. Compliance / statutory rates ------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS salary_compliance (
            rule_key        TEXT NOT NULL,
            effective_from  TEXT NOT NULL,
            rate            REAL NOT NULL,
            wage_base_min   REAL,
            wage_base_max   REAL,
            monthly_cap     REAL,
            description     TEXT,
            legal_basis     TEXT,
            updated_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_by      TEXT,
            PRIMARY KEY (rule_key, effective_from)
        )
    """)

    conn.commit()


def seed_salary_grades(conn: sqlite3.Connection, force: bool = False) -> int:
    """Seed the 15-grade structure on first run. Returns rows inserted.
    If force=True, replace all existing rows (use with caution)."""
    cur = conn.cursor()
    if not force:
        cur.execute("SELECT COUNT(*) FROM salary_grade")
        if cur.fetchone()[0] > 0:
            return 0
    else:
        cur.execute("DELETE FROM salary_grade")

    # ANCA 15-grade structure (matches Excel workbook Sheet 4)
    grades = [
        # (grade_key, sort, layer, track, min, mid, max, ipe_pc, mgmt_ic, typical_titles)
        ('O1',  10, 'Operations',       'Direct Labor',     12500,  14250,  16000, 39, 'IC',
         'Welder NPI / Operator Trainee / Production Apprentice'),
        ('O2',  20, 'Operations',       'Direct Labor',     14000,  16500,  19500, 40, 'IC',
         'Welder / Painter / Grinder / Packer / Inspector (Jr) / Production Operator'),
        ('O3',  30, 'Operations',       'Direct Labor',     17000,  21000,  25500, 41, 'IC',
         'Senior Welder / Senior Painter / Floor Leader (Weld/Paint/Pack/Fold)'),
        ('L1',  40, 'Indirect Jr',      'Admin/Support',    16000,  19500,  23500, 41, 'IC',
         'Junior Admin / Driver / Forklift Driver / FG Store / Warehouse / Production Admin'),
        ('L2',  50, 'Indirect',         'Admin/Support',    19000,  23500,  28500, 42, 'IC',
         'Production Admin / Planning Admin / Safety Admin / WO Mapping / HR & Admin'),
        ('L3',  60, 'Indirect',         'Officer',          24000,  30000,  36500, 44, 'IC',
         'Inspector / Direct Material Planner / Indirect Material Control / Maintenance Tech / Purchasing Officer'),
        ('L4',  70, 'Professional',     'Engineer',         30000,  37500,  45500, 46, 'IC',
         'Engineer (Jr) / Design Engineer / BOM Engineer / Logistic Admin / Sales Engineer (Jr)'),
        ('L5',  80, 'Professional',     'Engineer',         36000,  45000,  55000, 48, 'IC',
         'Engineer (Mid) / Design Engineer / Manufacturing Engineer / QC Engineer / Senior Accountant / Safety Officer'),
        ('L6',  90, 'Professional Sr',  'Senior IC',        45000,  55000,  65000, 49, 'IC',
         'Senior Engineer / Senior Design Engineer / NPD / Sr Manufacturing Eng / 🎯 Senior Production Planner / CI Leader'),
        ('L7', 100, 'Management',       'Supervisor',       55000,  67500,  80000, 50, 'Mgmt/IC',
         'Production Supervisor / QC Supervisor / Packing Supervisor / Project Mgmt Supervisor / CNC Shop Leader'),
        ('L8', 110, 'Management',       'Asst Manager',     70000,  87500, 105000, 51, 'Mgmt',
         'Senior Supervisor / Assistant Manager / Supply Chain Asst Manager / Executive Assistant'),
        ('L9', 120, 'Management',       'Dept Manager',     85000, 110000, 135000, 53, 'Mgmt',
         'HR Manager / Finance Manager / Planning Manager / Engineering Manager / Purchasing Manager'),
        ('L10',130, 'Management',       'Sr Manager',      110000, 140000, 170000, 54, 'Mgmt',
         'Mfg Engineering Manager / Maintenance Manager / Quality Manager / Production Manager / Supply Chain Manager'),
        ('L11',140, 'Director',         'Department Dir',  150000, 195000, 240000, 56, 'Mgmt',
         'Operation Director / Business Development Manager / Senior Functional Director'),
        ('L12',150, 'Executive',        'Country GM',      320000, 460000, 600000, 58, 'Exec',
         'General Manager — Country Lead (Thailand)'),
    ]
    cur.executemany("""
        INSERT INTO salary_grade
            (grade_key, sort_order, layer, track, band_min, band_mid, band_max, ipe_pc, mgmt_ic, typical_titles)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, grades)
    conn.commit()
    return len(grades)


def seed_grade_allowances(conn: sqlite3.Connection, force: bool = False) -> int:
    """Seed the default allowance scheme per grade. Matches Excel Sheet 5."""
    cur = conn.cursor()
    if not force:
        cur.execute("SELECT COUNT(*) FROM salary_grade_allowance")
        if cur.fetchone()[0] > 0:
            return 0
    else:
        cur.execute("DELETE FROM salary_grade_allowance")

    # Standardized scheme — payroll codes from ANCA B-PLUS system
    # (grade, code, name_en, amount, conditional, condition_note)
    rows = []
    for grade, transport, housing, meal, medical, comms, position_allow in [
        ('O1', 1700, 1575, 1260, 1000, 500, 0),
        ('O2', 1700, 1575, 1260, 1000, 500, 0),
        ('O3', 1700, 1575, 1260, 1000, 500, 0),
        ('L1', 1700, 1575, 1000, 1000, 500, 0),
        ('L2', 2500, 0,    0,    0,    600, 0),
        ('L3', 4000, 0,    0,    0,    600, 0),
        ('L4', 4000, 0,    0,    0,    600, 0),
        ('L5', 4000, 0,    0,    0,    600, 0),
        ('L6', 4000, 0,    0,    0,    600, 0),
        ('L7', 4600, 0,    0,    0,    600, 0),
        ('L8', 4600, 0,    0,    0,    600, 5000),
        ('L9', 7000, 0,    0,    0,    1000, 0),
        ('L10', 7000, 0,   0,    0,    1000, 0),
        ('L11', 12000, 0,  0,    0,    1500, 0),
        ('L12', 20000, 65000, 0, 0,    2000, 0),
    ]:
        # only insert non-zero amounts. Meal & Medical conditional for L1-L3 (shift workers); not L4+
        if transport > 0: rows.append((grade, '1520', 'Transport (ค่าพาหนะ)', transport, 0, None))
        if housing > 0:   rows.append((grade, '1320', 'Housing (ค่าเช่าบ้าน)', housing,   0, None))
        if meal > 0:      rows.append((grade, '1330', 'Meal — regular shift (ค่าอาหาร ว)', meal, 1, 'Shift workers only'))
        if medical > 0:   rows.append((grade, '1340', 'Medical (ค่ารักษาพยาบาล)', medical, 1, 'Direct labor only'))
        if comms > 0:     rows.append((grade, '1350', 'Utilities/Comms (ค่าน้ำ/ไฟ/โทร)', comms, 0, None))
        if position_allow > 0:
            rows.append((grade, '1230', 'Position Allowance (ค่าตำแหน่ง)', position_allow, 1, 'Specific role assignment'))

    cur.executemany("""
        INSERT INTO salary_grade_allowance
            (grade_key, allowance_code, allowance_name, default_amount, is_conditional, condition_note)
        VALUES (?,?,?,?,?,?)
    """, rows)
    conn.commit()
    return len(rows)


def seed_compliance_rates(conn: sqlite3.Connection, force: bool = False) -> int:
    """Seed Thailand 2026 statutory rates."""
    cur = conn.cursor()
    if not force:
        cur.execute("SELECT COUNT(*) FROM salary_compliance")
        if cur.fetchone()[0] > 0:
            return 0
    else:
        cur.execute("DELETE FROM salary_compliance")

    rows = [
        # (rule_key, effective_from, rate, wage_base_min, wage_base_max, monthly_cap, description, legal_basis)
        ('SSO_EMPLOYER', '2025-01-01', 0.05, 1650, 15000,  750,
         'SSO employer contribution — Phase 0 (pre-2026)',
         'Social Security Act B.E. 2533, Sec 33'),
        ('SSO_EMPLOYER', '2026-01-01', 0.05, 1650, 17500,  875,
         'SSO employer contribution — Phase 1 (2026-2028)',
         'Social Security Act B.E. 2533 amended; Royal Gazette 12-Dec-2025'),
        ('SSO_EMPLOYER', '2029-01-01', 0.05, 1650, 20000, 1000,
         'SSO employer contribution — Phase 2 (2029-2031)',
         'Social Security Act B.E. 2533 amended'),
        ('SSO_EMPLOYER', '2032-01-01', 0.05, 1650, 23000, 1150,
         'SSO employer contribution — Phase 3 (2032+)',
         'Social Security Act B.E. 2533 amended'),
        ('WCF_ANCA',     '2026-01-01', 0.0038, None, None, None,
         'Workmen Compensation Fund — ANCA assessed rate (0.38%, manufacturing low-risk)',
         'Workmen Compensation Act B.E. 2537'),
        ('PVF_ANCA',     '2020-01-01', 0.07, None, None, None,
         'Provident Fund — ANCA employer contribution (7% of base salary). Qualifies as EWF substitute.',
         'Provident Fund Act B.E. 2530'),
        ('EWF_RATE',     '2026-10-01', 0.0025, None, None, None,
         'Employee Welfare Fund — Phase 1 (0.25% from 1-Oct-2026 to 30-Sep-2031). EXEMPT for companies with qualifying PVF.',
         'Labour Protection Act B.E. 2541 §130'),
        ('EWF_RATE',     '2031-10-01', 0.005, None, None, None,
         'Employee Welfare Fund — Phase 2 (0.50% from 1-Oct-2031)',
         'Labour Protection Act B.E. 2541 §130'),
        ('SEVERANCE',    '1998-08-19', 0.0833, None, None, None,
         'Severance accrual basis = 1 month / year (8.33%)',
         'Labour Protection Act B.E. 2541 §118'),
    ]
    cur.executemany("""
        INSERT INTO salary_compliance
            (rule_key, effective_from, rate, wage_base_min, wage_base_max, monthly_cap, description, legal_basis)
        VALUES (?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()
    return len(rows)


def run_full_seed(conn: sqlite3.Connection) -> dict:
    """Run migration + seed everything. Returns counts dict."""
    run_salary_migration(conn)
    return {
        'grades':       seed_salary_grades(conn),
        'allowances':   seed_grade_allowances(conn),
        'compliance':   seed_compliance_rates(conn),
    }
