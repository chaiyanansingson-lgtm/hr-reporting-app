"""
lib/salary_engine.py — v11.5 Module 3 Salary & Compensation
Pure calculation engine for offer modeling. No DB, no Streamlit — easy to unit test.

Key calculation: given a gross monthly remuneration and assumptions, return the full
annual employer cost including SSO, PVF, WCF, EWF, bonuses, benefits, and severance accrual.
"""
from dataclasses import dataclass, asdict
from typing import Optional


# Default assumptions for ANCA Manufacturing Solutions (Thailand) — 2026
DEFAULT_ASSUMPTIONS = {
    'base_pct':         0.92,    # base salary as % of gross (L4-L7 standard)
    'months_paid':      12,
    'sso_rate':         0.05,    # statutory 5% each side
    'sso_ceiling':      17500,   # Thailand 2026 ceiling
    'pvf_rate':         0.07,    # ANCA 7% employer contribution
    'wcf_rate':         0.0038,  # ANCA assessed rate (manufacturing low-risk)
    'ewf_rate':         0.0,     # EXEMPT because ANCA has qualifying PVF
    'fixed_bonus_mos':  1.0,     # ANCA L4-L7 practice
    'kpi_bonus_mos':    1.0,     # at-target
    'group_ins_annual': 6000,    # L6 typical IPD+OPD plan
    'checkup_annual':   1500,
    'uniform_annual':   2000,
    'training_annual':  12000,
    'severance_rate':   0.0833,  # 1 month / year accrual
}


@dataclass
class OfferBreakdown:
    """Full breakdown of an offer — monthly and annual."""
    gross_monthly:        float
    base_monthly:         float
    allowance_monthly:    float
    sso_monthly:          float
    pvf_monthly:          float
    wcf_monthly:          float
    ewf_monthly:          float
    fixed_bonus_monthly:  float   # accrual basis
    kpi_bonus_monthly:    float   # accrual basis
    group_ins_monthly:    float
    checkup_uniform_mo:   float
    training_monthly:     float
    severance_monthly:    float   # accrual basis
    total_monthly:        float
    total_annual:         float
    annual_multiplier:    float   # total_annual / (gross × 12)

    # Position context (for band comparison)
    grade_key:            Optional[str] = None
    band_min:             Optional[float] = None
    band_mid:             Optional[float] = None
    band_max:             Optional[float] = None
    band_penetration:     Optional[float] = None   # (gross - min) / (max - min)
    compa_ratio:          Optional[float] = None   # gross / mid

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_text(self) -> str:
        lines = []
        lines.append(f"Gross monthly:           THB {self.gross_monthly:>10,.0f}")
        lines.append(f"  Base salary ({self.base_monthly/self.gross_monthly*100:.0f}%):"
                     f"        THB {self.base_monthly:>10,.0f}")
        lines.append(f"  Allowance ({self.allowance_monthly/self.gross_monthly*100:.0f}%):"
                     f"           THB {self.allowance_monthly:>10,.0f}")
        lines.append(f"")
        lines.append(f"Employer costs (monthly):")
        lines.append(f"  SSO (capped):          THB {self.sso_monthly:>10,.0f}")
        lines.append(f"  PVF (7% of base):      THB {self.pvf_monthly:>10,.0f}")
        lines.append(f"  WCF (0.38%):           THB {self.wcf_monthly:>10,.0f}")
        lines.append(f"  EWF (exempt):          THB {self.ewf_monthly:>10,.0f}")
        lines.append(f"  Fixed bonus accrual:   THB {self.fixed_bonus_monthly:>10,.0f}")
        lines.append(f"  KPI bonus accrual:     THB {self.kpi_bonus_monthly:>10,.0f}")
        lines.append(f"  Benefits + training:   THB {(self.group_ins_monthly + self.checkup_uniform_mo + self.training_monthly):>10,.0f}")
        lines.append(f"  Severance accrual:     THB {self.severance_monthly:>10,.0f}")
        lines.append(f"")
        lines.append(f"TOTAL MONTHLY:           THB {self.total_monthly:>10,.0f}")
        lines.append(f"TOTAL ANNUAL:            THB {self.total_annual:>10,.0f}  ({self.annual_multiplier:.2f}× gross)")
        if self.grade_key:
            lines.append(f"")
            lines.append(f"Band positioning ({self.grade_key}):")
            lines.append(f"  Min / Mid / Max:       THB {self.band_min:,.0f} / {self.band_mid:,.0f} / {self.band_max:,.0f}")
            if self.band_penetration is not None:
                lines.append(f"  Penetration:           {self.band_penetration*100:.1f}%")
            if self.compa_ratio is not None:
                lines.append(f"  Compa-ratio:           {self.compa_ratio*100:.1f}%")
        return "\n".join(lines)


def calculate_offer(
    gross_monthly: float,
    assumptions: Optional[dict] = None,
    grade_band: Optional[tuple] = None,   # (min, mid, max) optional
    grade_key: Optional[str] = None,
) -> OfferBreakdown:
    """Compute the full breakdown for a single offer.

    Args:
        gross_monthly: total gross monthly remuneration (base + fixed allowance)
        assumptions:   dict overriding DEFAULT_ASSUMPTIONS keys
        grade_band:    optional tuple of (band_min, band_mid, band_max)
        grade_key:     optional grade key (e.g., 'L6') for context

    Returns:
        OfferBreakdown dataclass
    """
    a = dict(DEFAULT_ASSUMPTIONS)
    if assumptions:
        a.update(assumptions)

    # 1. Split gross into base + allowance
    base = gross_monthly * a['base_pct']
    allowance = gross_monthly - base   # = gross × (1 - base_pct)

    # 2. SSO employer — capped at ceiling × rate
    sso_base = min(base, a['sso_ceiling'])
    sso_monthly = sso_base * a['sso_rate']

    # 3. PVF employer — 7% of base (no cap, but tax-advantaged)
    pvf_monthly = base * a['pvf_rate']

    # 4. WCF — applied to gross (industry standard interpretation)
    wcf_monthly = gross_monthly * a['wcf_rate']

    # 5. EWF — applied to gross; ZERO if exempt (ANCA's PVF qualifies)
    ewf_monthly = gross_monthly * a['ewf_rate']

    # 6. Bonuses — accrued monthly (base × months / 12)
    fixed_bonus_monthly = base * a['fixed_bonus_mos'] / 12
    kpi_bonus_monthly   = base * a['kpi_bonus_mos'] / 12

    # 7. Group benefits — annual prorated
    group_ins_monthly = a['group_ins_annual'] / 12
    checkup_uniform_mo = (a['checkup_annual'] + a['uniform_annual']) / 12
    training_monthly = a['training_annual'] / 12

    # 8. Severance — accrual basis (1 month / year = 8.33% of base)
    severance_monthly = base * a['severance_rate']

    # 9. Totals
    total_monthly = (
        gross_monthly + sso_monthly + pvf_monthly + wcf_monthly + ewf_monthly
        + fixed_bonus_monthly + kpi_bonus_monthly
        + group_ins_monthly + checkup_uniform_mo + training_monthly
        + severance_monthly
    )
    months = a['months_paid']
    total_annual = total_monthly * months
    # HR convention: "Annual cost as multiplier of one month's gross"
    # e.g., 935K / 58K = 16.13× — the hire costs us ~16 monthly salaries per year
    multiplier = total_annual / gross_monthly if gross_monthly > 0 else 0

    # Band context
    band_min = band_mid = band_max = pen = compa = None
    if grade_band is not None:
        band_min, band_mid, band_max = grade_band
        if band_max > band_min:
            pen = (gross_monthly - band_min) / (band_max - band_min)
        if band_mid > 0:
            compa = gross_monthly / band_mid

    return OfferBreakdown(
        gross_monthly=gross_monthly,
        base_monthly=base,
        allowance_monthly=allowance,
        sso_monthly=sso_monthly,
        pvf_monthly=pvf_monthly,
        wcf_monthly=wcf_monthly,
        ewf_monthly=ewf_monthly,
        fixed_bonus_monthly=fixed_bonus_monthly,
        kpi_bonus_monthly=kpi_bonus_monthly,
        group_ins_monthly=group_ins_monthly,
        checkup_uniform_mo=checkup_uniform_mo,
        training_monthly=training_monthly,
        severance_monthly=severance_monthly,
        total_monthly=total_monthly,
        total_annual=total_annual,
        annual_multiplier=multiplier,
        grade_key=grade_key,
        band_min=band_min,
        band_mid=band_mid,
        band_max=band_max,
        band_penetration=pen,
        compa_ratio=compa,
    )


def band_status(salary: float, band_min: float, band_max: float, threshold: float = 0.10) -> str:
    """Return status flag for an employee's salary vs their band.
    Returns one of: 'In band', 'Below band', 'Slightly below', 'Above band', 'Slightly above'.
    """
    if salary is None or band_min is None or band_max is None:
        return 'N/A'
    if salary < band_min * (1 - threshold):
        return 'Below band'
    if salary < band_min:
        return 'Slightly below'
    if salary > band_max * (1 + threshold):
        return 'Above band'
    if salary > band_max:
        return 'Slightly above'
    return 'In band'


def compa_label(compa_ratio: Optional[float]) -> str:
    """Return human-readable label for a compa-ratio."""
    if compa_ratio is None:
        return 'N/A'
    if compa_ratio < 0.85:
        return 'Below mid'
    if compa_ratio < 1.10:
        return 'At/Near mid'
    return 'Above mid'


def penetration_label(pen: Optional[float]) -> str:
    """Return human-readable label for band penetration."""
    if pen is None:
        return 'N/A'
    if pen < 0.40:
        return 'Low (1st quartile)'
    if pen < 0.70:
        return 'Healthy (mid)'
    if pen < 0.95:
        return 'Top (4th quartile)'
    return 'At/Above Max'
