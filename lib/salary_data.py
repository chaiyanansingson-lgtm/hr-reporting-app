"""
lib/salary_data.py — v11.5 Module 3 Salary & Compensation
Capability-gated data access layer. All reads/writes of salary data go through here.

Follows the v11.4 host app architecture: pages NEVER hit salary_grade / salary_offer
tables directly. They always call functions in this module, which enforce capability
checks via lib.auth.has_capability(username, "salary.*").
"""
import sqlite3
from typing import Optional
import pandas as pd

# NOTE: In the host app, replace these placeholders with the real imports:
#   from lib.db import get_db_conn
#   from lib.auth import has_capability, current_username
# For standalone testing, the test harness can monkey-patch these.

try:
    from lib.db import get_db_conn          # type: ignore
    from lib.auth import has_capability     # type: ignore
except ImportError:
    # Standalone test fallback
    def get_db_conn():
        return sqlite3.connect('data/hr.db')
    def has_capability(username: str, cap: str) -> bool:
        return True  # tests bypass; never use in prod


# Capability tokens used by this module (must be registered in rbac_seed.py)
CAP_VIEW          = 'salary.view'
CAP_UPLOAD        = 'salary.upload'
CAP_EXPORT        = 'salary.export'
CAP_CALC_OFFER    = 'salary.calculate_offer'
CAP_EDIT_BANDS    = 'salary.edit_bands'
CAP_VIEW_AUDIT    = 'salary.view_audit'


class CapabilityError(PermissionError):
    """Raised when a user lacks the required capability for a salary operation."""
    pass


def _require(username: str, cap: str) -> None:
    if not has_capability(username, cap):
        raise CapabilityError(f"User '{username}' lacks capability '{cap}'")


# =============================================================================
# Grade structure
# =============================================================================

def get_all_grades(username: str) -> pd.DataFrame:
    """Return the full 15-grade structure as a DataFrame. Requires salary.view."""
    _require(username, CAP_VIEW)
    with get_db_conn() as conn:
        return pd.read_sql_query("""
            SELECT grade_key, sort_order, layer, track,
                   band_min, band_mid, band_max,
                   ipe_pc, mgmt_ic, typical_titles
            FROM salary_grade
            ORDER BY sort_order
        """, conn)


def get_grade(username: str, grade_key: str) -> Optional[dict]:
    """Return one grade as dict, or None if not found."""
    _require(username, CAP_VIEW)
    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT grade_key, layer, track, band_min, band_mid, band_max,
                   ipe_pc, mgmt_ic, typical_titles
            FROM salary_grade WHERE grade_key = ?
        """, (grade_key,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            'grade_key':      row[0],
            'layer':          row[1],
            'track':          row[2],
            'band_min':       row[3],
            'band_mid':       row[4],
            'band_max':       row[5],
            'ipe_pc':         row[6],
            'mgmt_ic':        row[7],
            'typical_titles': row[8],
        }


def update_grade_band(username: str, grade_key: str,
                     band_min: float, band_mid: float, band_max: float) -> None:
    """Update a grade's band. Requires salary.edit_bands (Finance / Super Admin)."""
    _require(username, CAP_EDIT_BANDS)
    if not (band_min <= band_mid <= band_max):
        raise ValueError(f"Bands must be ordered: min ({band_min}) <= mid ({band_mid}) <= max ({band_max})")
    if band_min <= 0:
        raise ValueError("Band min must be > 0")
    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE salary_grade
            SET band_min = ?, band_mid = ?, band_max = ?,
                updated_at = CURRENT_TIMESTAMP, updated_by = ?
            WHERE grade_key = ?
        """, (band_min, band_mid, band_max, username, grade_key))
        if cur.rowcount == 0:
            raise ValueError(f"Grade '{grade_key}' not found")
        conn.commit()


# =============================================================================
# Allowance scheme
# =============================================================================

def get_grade_allowances(username: str, grade_key: str) -> pd.DataFrame:
    """Return all default allowances for a grade."""
    _require(username, CAP_VIEW)
    with get_db_conn() as conn:
        return pd.read_sql_query("""
            SELECT allowance_code, allowance_name, default_amount,
                   is_conditional, condition_note
            FROM salary_grade_allowance
            WHERE grade_key = ?
            ORDER BY allowance_code
        """, conn, params=(grade_key,))


def get_grade_allowance_total(username: str, grade_key: str,
                              include_conditional: bool = False) -> float:
    """Return total monthly fixed-allowance amount for a grade.
    By default excludes conditional (e.g., shift-only) allowances."""
    _require(username, CAP_VIEW)
    with get_db_conn() as conn:
        cur = conn.cursor()
        if include_conditional:
            cur.execute("SELECT COALESCE(SUM(default_amount), 0) FROM salary_grade_allowance WHERE grade_key = ?",
                       (grade_key,))
        else:
            cur.execute("SELECT COALESCE(SUM(default_amount), 0) FROM salary_grade_allowance "
                       "WHERE grade_key = ? AND is_conditional = 0", (grade_key,))
        return float(cur.fetchone()[0])


# =============================================================================
# Offer calculator — save record
# =============================================================================

def save_offer(username: str, *,
               candidate_ref: str,
               position_title: str,
               proposed_grade: Optional[str],
               proposed_gross: float,
               breakdown: dict,
               notes: Optional[str] = None) -> int:
    """Save a new offer calculation to the audit table. Returns offer_id.
    Requires salary.calculate_offer."""
    _require(username, CAP_CALC_OFFER)
    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO salary_offer (
                candidate_ref, position_title, proposed_grade, proposed_gross,
                base_pct, sso_employer, pvf_employer, wcf_employer, ewf_employer,
                fixed_bonus_mos, kpi_bonus_mos, annual_benefits, severance_accr,
                total_monthly, total_annual,
                band_min, band_mid, band_max, penetration,
                market_p50, notes, created_by
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            candidate_ref, position_title, proposed_grade, proposed_gross,
            breakdown.get('base_pct', 0.92),
            breakdown.get('sso_monthly', 0),
            breakdown.get('pvf_monthly', 0),
            breakdown.get('wcf_monthly', 0),
            breakdown.get('ewf_monthly', 0),
            breakdown.get('fixed_bonus_mos', 1.0),
            breakdown.get('kpi_bonus_mos', 1.0),
            (breakdown.get('group_ins_monthly', 0) + breakdown.get('checkup_uniform_mo', 0)
             + breakdown.get('training_monthly', 0)) * 12,
            breakdown.get('severance_monthly', 0),
            breakdown.get('total_monthly', 0),
            breakdown.get('total_annual', 0),
            breakdown.get('band_min'),
            breakdown.get('band_mid'),
            breakdown.get('band_max'),
            breakdown.get('band_penetration'),
            breakdown.get('market_p50'),
            notes, username
        ))
        offer_id = cur.lastrowid
        conn.commit()
        return offer_id


def list_recent_offers(username: str, limit: int = 50) -> pd.DataFrame:
    """List recent offer calculations. Requires salary.view_audit."""
    _require(username, CAP_VIEW_AUDIT)
    with get_db_conn() as conn:
        return pd.read_sql_query("""
            SELECT offer_id, created_at, candidate_ref, position_title,
                   proposed_grade, proposed_gross, total_annual,
                   penetration, created_by, notes
            FROM salary_offer
            ORDER BY created_at DESC
            LIMIT ?
        """, conn, params=(limit,))


# =============================================================================
# Compliance / statutory rates
# =============================================================================

def get_compliance_rate(username: str, rule_key: str, as_of_date: str = None) -> Optional[dict]:
    """Return the effective compliance rate as of a given date (default: today)."""
    _require(username, CAP_VIEW)
    if as_of_date is None:
        import datetime
        as_of_date = datetime.date.today().isoformat()
    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT rule_key, effective_from, rate, wage_base_min, wage_base_max,
                   monthly_cap, description, legal_basis
            FROM salary_compliance
            WHERE rule_key = ? AND effective_from <= ?
            ORDER BY effective_from DESC LIMIT 1
        """, (rule_key, as_of_date))
        row = cur.fetchone()
        if not row:
            return None
        return {
            'rule_key': row[0], 'effective_from': row[1], 'rate': row[2],
            'wage_base_min': row[3], 'wage_base_max': row[4], 'monthly_cap': row[5],
            'description': row[6], 'legal_basis': row[7],
        }


def get_all_compliance_rates(username: str) -> pd.DataFrame:
    _require(username, CAP_VIEW)
    with get_db_conn() as conn:
        return pd.read_sql_query("""
            SELECT rule_key, effective_from, rate, wage_base_min, wage_base_max,
                   monthly_cap, description, legal_basis
            FROM salary_compliance
            ORDER BY rule_key, effective_from
        """, conn)
