"""
test_salary_module.py — Unit tests for Module 3 Salary & Compensation
Run from the hr_app root:  python -m pytest test_salary_module.py -v
Or run standalone:         python test_salary_module.py

Tests cover:
  - DB migration creates all 4 salary tables
  - Seed populates 15 grades + allowance scheme + compliance rates
  - calculate_offer math matches the Excel model
  - Senior Production Planner scenario: 58K gross → ~935K annual
  - SSO ceiling cap works (base above ceiling capped at 875)
  - EWF exempt scenario works (rate = 0)
  - Band penetration & compa-ratio calculations correct
"""
import os
import sys
import sqlite3
import tempfile
import unittest

# Make lib importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import salary_migration, salary_engine


# =============================================================================
# 1. Migration & Seed Tests
# =============================================================================

class TestSalaryMigration(unittest.TestCase):
    """Verify DB schema creation and seeding."""

    def setUp(self):
        self.conn = sqlite3.connect(':memory:')

    def tearDown(self):
        self.conn.close()

    def test_migration_creates_4_tables(self):
        salary_migration.run_salary_migration(self.conn)
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'salary%'")
        tables = sorted(r[0] for r in cur.fetchall())
        self.assertEqual(tables, ['salary_compliance', 'salary_grade',
                                  'salary_grade_allowance', 'salary_offer'])

    def test_migration_is_idempotent(self):
        """Running migration twice should not fail."""
        salary_migration.run_salary_migration(self.conn)
        salary_migration.run_salary_migration(self.conn)
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'salary%'")
        self.assertEqual(cur.fetchone()[0], 4)

    def test_seed_creates_15_grades(self):
        salary_migration.run_salary_migration(self.conn)
        n = salary_migration.seed_salary_grades(self.conn)
        self.assertEqual(n, 15)
        cur = self.conn.cursor()
        cur.execute("SELECT grade_key FROM salary_grade ORDER BY sort_order")
        grades = [r[0] for r in cur.fetchall()]
        self.assertEqual(grades, ['O1','O2','O3','L1','L2','L3','L4','L5','L6','L7','L8','L9','L10','L11','L12'])

    def test_seed_does_not_double_insert(self):
        """Calling seed twice should be a no-op."""
        salary_migration.run_salary_migration(self.conn)
        n1 = salary_migration.seed_salary_grades(self.conn)
        n2 = salary_migration.seed_salary_grades(self.conn)
        self.assertEqual(n1, 15)
        self.assertEqual(n2, 0)  # idempotent

    def test_l6_band_matches_excel(self):
        """L6 band must be 45,000 / 55,000 / 65,000 (Senior Production Planner)"""
        salary_migration.run_salary_migration(self.conn)
        salary_migration.seed_salary_grades(self.conn)
        cur = self.conn.cursor()
        cur.execute("SELECT band_min, band_mid, band_max FROM salary_grade WHERE grade_key = 'L6'")
        mn, md, mx = cur.fetchone()
        self.assertEqual(mn, 45000.0)
        self.assertEqual(md, 55000.0)
        self.assertEqual(mx, 65000.0)

    def test_seed_allowances_creates_rows(self):
        salary_migration.run_salary_migration(self.conn)
        salary_migration.seed_salary_grades(self.conn)
        n = salary_migration.seed_grade_allowances(self.conn)
        self.assertGreater(n, 30)  # should have many rows
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM salary_grade_allowance WHERE grade_key = 'L6'")
        # L6 has Transport (4000) + Comms (600) = 2 rows
        self.assertEqual(cur.fetchone()[0], 2)

    def test_seed_compliance_rates(self):
        salary_migration.run_salary_migration(self.conn)
        n = salary_migration.seed_compliance_rates(self.conn)
        self.assertGreaterEqual(n, 8)
        cur = self.conn.cursor()
        # SSO 2026 must be present with cap 875
        cur.execute("SELECT rate, monthly_cap FROM salary_compliance WHERE rule_key = 'SSO_EMPLOYER' AND effective_from = '2026-01-01'")
        rate, cap = cur.fetchone()
        self.assertAlmostEqual(rate, 0.05)
        self.assertEqual(cap, 875)


# =============================================================================
# 2. Engine Math Tests
# =============================================================================

class TestSalaryEngine(unittest.TestCase):
    """Test the pure calculation engine against known reference values."""

    def test_senior_production_planner_58k(self):
        """58,000 gross at default ANCA assumptions → ~935K annual.
        Matches Excel workbook Sheet 7 final calculation."""
        result = salary_engine.calculate_offer(
            gross_monthly=58000,
            grade_band=(45000, 55000, 65000),
            grade_key='L6',
        )
        # Base = 58000 × 0.92 = 53,360
        self.assertAlmostEqual(result.base_monthly, 53360, places=0)
        # Allowance = 58000 × 0.08 = 4,640
        self.assertAlmostEqual(result.allowance_monthly, 4640, places=0)
        # SSO = MIN(53360, 17500) × 5% = 875 (capped)
        self.assertAlmostEqual(result.sso_monthly, 875, places=0)
        # PVF = 53360 × 7% = 3,735.20
        self.assertAlmostEqual(result.pvf_monthly, 3735.2, places=1)
        # WCF = 58000 × 0.38% = 220.40
        self.assertAlmostEqual(result.wcf_monthly, 220.4, places=1)
        # EWF = 0 (exempt)
        self.assertEqual(result.ewf_monthly, 0)
        # Fixed bonus monthly accrual = 53360 / 12 ≈ 4,446.67
        self.assertAlmostEqual(result.fixed_bonus_monthly, 4446.67, places=1)
        # KPI bonus monthly accrual = 53360 / 12 ≈ 4,446.67
        self.assertAlmostEqual(result.kpi_bonus_monthly, 4446.67, places=1)
        # Severance accrual = 53360 × 8.33% ≈ 4,444.89
        self.assertAlmostEqual(result.severance_monthly, 4444.89, places=1)
        # Total annual ~ 935K
        self.assertGreater(result.total_annual, 930000)
        self.assertLess(result.total_annual, 940000)
        # Multiplier
        self.assertAlmostEqual(result.annual_multiplier, 16.13, places=1)
        # Band positioning
        self.assertAlmostEqual(result.band_penetration, 0.65, places=2)
        self.assertAlmostEqual(result.compa_ratio, 58000/55000, places=2)

    def test_sso_cap_below_ceiling(self):
        """Salary BELOW ceiling — SSO is base × 5% (not capped)."""
        result = salary_engine.calculate_offer(gross_monthly=15000)
        # Base = 15000 × 0.92 = 13,800 — below ceiling 17,500
        # SSO = 13,800 × 5% = 690
        self.assertAlmostEqual(result.sso_monthly, 690, places=0)

    def test_sso_cap_above_ceiling(self):
        """Salary ABOVE ceiling — SSO capped at 875."""
        result = salary_engine.calculate_offer(gross_monthly=100000)
        # Base = 92,000 — above ceiling 17,500
        # SSO = min(92000, 17500) × 5% = 875
        self.assertAlmostEqual(result.sso_monthly, 875, places=0)

    def test_ewf_when_not_exempt(self):
        """If company is NOT EWF-exempt, EWF should compute."""
        result = salary_engine.calculate_offer(
            gross_monthly=58000,
            assumptions={'ewf_rate': 0.0025},  # 0.25% (non-exempt scenario)
        )
        # EWF = 58000 × 0.25% = 145
        self.assertAlmostEqual(result.ewf_monthly, 145, places=0)

    def test_calculate_offer_zero_gross(self):
        """Edge case: 0 gross should not crash, multiplier = 0."""
        result = salary_engine.calculate_offer(gross_monthly=0)
        self.assertEqual(result.gross_monthly, 0)
        self.assertEqual(result.annual_multiplier, 0)

    def test_band_status_in_band(self):
        self.assertEqual(salary_engine.band_status(55000, 45000, 65000), 'In band')

    def test_band_status_slightly_below(self):
        # 44000 is below band min (45000) but within 10% threshold (40500–45000)
        self.assertEqual(salary_engine.band_status(44000, 45000, 65000), 'Slightly below')

    def test_band_status_critical_below(self):
        # 40000 is below 45000 × 0.9 = 40,500 → 'Below band'
        self.assertEqual(salary_engine.band_status(40000, 45000, 65000), 'Below band')

    def test_band_status_critical_above(self):
        # 75000 is above 65000 × 1.10 = 71,500 → 'Above band'
        self.assertEqual(salary_engine.band_status(75000, 45000, 65000), 'Above band')

    def test_penetration_label(self):
        self.assertEqual(salary_engine.penetration_label(0.25), 'Low (1st quartile)')
        self.assertEqual(salary_engine.penetration_label(0.50), 'Healthy (mid)')
        self.assertEqual(salary_engine.penetration_label(0.80), 'Top (4th quartile)')
        self.assertEqual(salary_engine.penetration_label(1.0),  'At/Above Max')

    def test_compa_label(self):
        self.assertEqual(salary_engine.compa_label(0.80), 'Below mid')
        self.assertEqual(salary_engine.compa_label(0.95), 'At/Near mid')
        self.assertEqual(salary_engine.compa_label(1.05), 'At/Near mid')
        self.assertEqual(salary_engine.compa_label(1.20), 'Above mid')


# =============================================================================
# 3. Integration Test — Run full end-to-end
# =============================================================================

class TestEndToEnd(unittest.TestCase):
    """Full migration + seed + calculation + save."""

    def test_full_workflow(self):
        # Use a temp DB file
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
            db_path = tf.name
        try:
            conn = sqlite3.connect(db_path)
            counts = salary_migration.run_full_seed(conn)
            self.assertEqual(counts['grades'], 15)
            self.assertGreater(counts['allowances'], 30)
            self.assertGreaterEqual(counts['compliance'], 8)
            # Compute an offer
            result = salary_engine.calculate_offer(58000, grade_band=(45000, 55000, 65000), grade_key='L6')
            self.assertGreater(result.total_annual, 930000)
            self.assertLess(result.total_annual, 940000)
            conn.close()
        finally:
            os.unlink(db_path)


# =============================================================================
# Print-style standalone runner (in addition to unittest)
# =============================================================================

def print_demo():
    """Run all calculations and print to console — useful for visual inspection."""
    print("=" * 78)
    print("ANCA Salary Module 3 — Demo Run")
    print("=" * 78)

    # 1. Sr Production Planner @ 58K
    print("\n📋 Scenario 1: Senior Production Planner — 58,000 THB gross monthly")
    print("-" * 78)
    r = salary_engine.calculate_offer(58000, grade_band=(45000, 55000, 65000), grade_key='L6')
    print(r.summary_text())

    # 2. Compare alternatives
    print("\n📋 Scenario 2: Alternative offers")
    print("-" * 78)
    print(f"{'Offer':>8} | {'Annual Cost':>15} | {'Multiplier':>10} | {'Penetration':>11} | {'Compa':>6}")
    print("-" * 78)
    for offer_amt in [50000, 55000, 58000, 60000, 65000]:
        r = salary_engine.calculate_offer(offer_amt, grade_band=(45000, 55000, 65000), grade_key='L6')
        print(f"{offer_amt:>8,} | THB {r.total_annual:>11,.0f} | {r.annual_multiplier:>9.2f}× | "
              f"{r.band_penetration*100:>10.1f}% | {r.compa_ratio*100:>5.1f}%")

    # 3. EWF exempt vs not
    print("\n📋 Scenario 3: EWF Exempt vs Not Exempt (impact for 58K hire)")
    print("-" * 78)
    r_exempt = salary_engine.calculate_offer(58000, assumptions={'ewf_rate': 0.0})
    r_not    = salary_engine.calculate_offer(58000, assumptions={'ewf_rate': 0.0025})
    diff_yr  = r_not.total_annual - r_exempt.total_annual
    print(f"  EWF EXEMPT (PVF qualifies):       THB {r_exempt.total_annual:,.0f} / year")
    print(f"  EWF NOT exempt (0.25%):           THB {r_not.total_annual:,.0f} / year")
    print(f"  Annual savings per L6 hire:       THB {diff_yr:,.0f}")
    print(f"  Across 171 employees (estimate):  THB {diff_yr * 5:,.0f}  (multiply pro-rata by wage bill)")

    # 4. SSO ceiling impact
    print("\n📋 Scenario 4: 2025 vs 2026 SSO Ceiling Impact (58K hire)")
    print("-" * 78)
    r_2025 = salary_engine.calculate_offer(58000, assumptions={'sso_ceiling': 15000})
    r_2026 = salary_engine.calculate_offer(58000, assumptions={'sso_ceiling': 17500})
    sso_diff = (r_2026.sso_monthly - r_2025.sso_monthly) * 12
    print(f"  2025 SSO ceiling 15,000:          THB {r_2025.sso_monthly:,.0f}/mo  (annual {r_2025.sso_monthly*12:,.0f})")
    print(f"  2026 SSO ceiling 17,500:          THB {r_2026.sso_monthly:,.0f}/mo  (annual {r_2026.sso_monthly*12:,.0f})")
    print(f"  Increase per L6 hire (2026):      THB {sso_diff:,.0f}/year")

    print("\n" + "=" * 78)
    print("✅ Demo complete. To run unit tests: python -m pytest test_salary_module.py -v")
    print("=" * 78)


if __name__ == '__main__':
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == 'demo':
        print_demo()
    else:
        unittest.main(verbosity=2)
