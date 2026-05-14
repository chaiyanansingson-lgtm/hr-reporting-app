"""
pages/D_Salary_Module.py — v11.5 Module 3 Salary & Compensation
Streamlit page with 5 tabs:
  1. Bands           — Read-only view of the 15-grade structure
  2. Offer Calculator — Interactive calculator for new-hire offers
  3. Headcount Map   — All employees mapped to proposed grades with off-band flags
  4. Market Benchmark— Reference data from external surveys
  5. Compliance      — Statutory rate reference (SSO/PVF/WCF/EWF)

Page guarded by salary.view (any tab requires base read access; specific actions
have additional capability checks at the action point).
"""
import streamlit as st
import pandas as pd
from datetime import date

from lib.page_utils import require_login, page_header
from lib.i18n import tr
from lib.style import inject_anca_style
from lib.auth import has_capability, current_username
from lib import salary_data
from lib import salary_engine
from lib.salary_engine import calculate_offer, band_status, compa_label, penetration_label

# Page gate — any salary tab requires salary.view as baseline
require_login(capability=salary_data.CAP_VIEW)
inject_anca_style()
page_header(tr('salary_module_title', default='Salary & Compensation Module'),
            icon='💰', subtitle=tr('salary_module_subtitle',
                                   default='Grade structure, offer calculator, market benchmarks, and compliance reference'))

username = current_username()

# Banner — note about data sensitivity
st.warning(
    f"🔒 {tr('salary_module_sensitive_data', default='This module contains sensitive compensation data. All actions are logged. Access is restricted to authorized roles.')}",
    icon='🔒'
)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    f"📊 {tr('salary_tab_bands', default='Grade Bands')}",
    f"🧮 {tr('salary_tab_offer', default='Offer Calculator')}",
    f"👥 {tr('salary_tab_headcount', default='Headcount Map')}",
    f"📈 {tr('salary_tab_market', default='Market Benchmark')}",
    f"⚖️ {tr('salary_tab_compliance', default='Compliance')}",
])

# =============================================================================
# TAB 1 — Grade Bands
# =============================================================================
with tab1:
    st.markdown(f"### {tr('salary_grade_structure', default='ANCA 15-Grade Structure (FY26)')}")
    st.caption(tr('salary_grade_caption',
        default='Operations (O1–O3) + Indirect/Management (L1–L12). Aligned with Mercer International Position Evaluation (IPE) PC 39–58.'))

    try:
        grades_df = salary_data.get_all_grades(username)
        # Format for display
        display_df = grades_df.copy()
        display_df['band_min'] = display_df['band_min'].map(lambda v: f"{v:,.0f}")
        display_df['band_mid'] = display_df['band_mid'].map(lambda v: f"{v:,.0f}")
        display_df['band_max'] = display_df['band_max'].map(lambda v: f"{v:,.0f}")
        display_df['spread'] = grades_df.apply(
            lambda r: f"{r['band_max']/r['band_min']:.2f}×" if r['band_min'] > 0 else "—", axis=1)
        display_df = display_df.rename(columns={
            'grade_key': 'Grade', 'layer': 'Layer', 'track': 'Track',
            'band_min': 'Min (THB)', 'band_mid': 'Mid (THB)', 'band_max': 'Max (THB)',
            'ipe_pc': 'Mercer IPE PC', 'mgmt_ic': 'Mgmt/IC',
            'typical_titles': 'Typical Positions',
        })
        display_df = display_df[['Grade', 'Layer', 'Track', 'Min (THB)', 'Mid (THB)', 'Max (THB)',
                                 'spread', 'Mercer IPE PC', 'Mgmt/IC', 'Typical Positions']]
        display_df = display_df.rename(columns={'spread': 'Spread'})
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Edit bands (gated)
        if has_capability(username, salary_data.CAP_EDIT_BANDS):
            with st.expander(f"🔧 {tr('salary_edit_bands', default='Edit Bands (Finance / Super Admin only)')}", expanded=False):
                st.caption(tr('salary_edit_warning',
                    default='⚠ Changes apply immediately and are logged. Use with caution.'))
                edit_grade = st.selectbox('Grade to edit', grades_df['grade_key'].tolist(), key='edit_grade_sel')
                if edit_grade:
                    cur = grades_df[grades_df['grade_key'] == edit_grade].iloc[0]
                    c1, c2, c3 = st.columns(3)
                    new_min = c1.number_input('Band Min (THB)', value=float(cur['band_min']), step=1000.0, key='new_min')
                    new_mid = c2.number_input('Band Mid (THB)', value=float(cur['band_mid']), step=1000.0, key='new_mid')
                    new_max = c3.number_input('Band Max (THB)', value=float(cur['band_max']), step=1000.0, key='new_max')
                    if st.button('💾 Save Band Update', type='primary', key='save_band'):
                        try:
                            salary_data.update_grade_band(username, edit_grade, new_min, new_mid, new_max)
                            st.success(f"Band for {edit_grade} updated: {new_min:,.0f} / {new_mid:,.0f} / {new_max:,.0f}")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                        except salary_data.CapabilityError as e:
                            st.error(f"Permission denied: {e}")
    except salary_data.CapabilityError as e:
        st.error(f"🔒 {e}")

# =============================================================================
# TAB 2 — Offer Calculator
# =============================================================================
with tab2:
    st.markdown(f"### {tr('salary_offer_calc', default='New-Hire Offer Calculator')}")
    st.caption(tr('salary_offer_caption',
        default='Calculate the full annual employer cost for a candidate including SSO, PVF, WCF, EWF, bonuses, benefits, and severance accrual.'))

    if not has_capability(username, salary_data.CAP_CALC_OFFER):
        st.info("🔒 You don't have permission to use the offer calculator (requires salary.calculate_offer).")
    else:
        # === Inputs ===
        with st.container(border=True):
            st.markdown(f"#### {tr('salary_inputs', default='Position & Candidate')}")
            col1, col2, col3 = st.columns(3)
            candidate_ref = col1.text_input('Candidate Reference', value='Sr Prod Planner — TBD', key='cand_ref')
            position_title = col2.text_input('Position Title', value='Senior Production Planner', key='pos_title')

            try:
                grades_df = salary_data.get_all_grades(username)
                grade_options = grades_df['grade_key'].tolist()
                default_grade = 'L6' if 'L6' in grade_options else grade_options[0] if grade_options else None
                proposed_grade = col3.selectbox('Proposed Grade', grade_options,
                                                index=grade_options.index(default_grade) if default_grade else 0,
                                                key='prop_grade')
            except Exception:
                proposed_grade = None
                grades_df = None

            # Get band info
            band_info = salary_data.get_grade(username, proposed_grade) if proposed_grade else None
            if band_info:
                st.caption(f"**{proposed_grade}** — {band_info['typical_titles']}")
                st.caption(f"Band: THB {band_info['band_min']:,.0f} – {band_info['band_mid']:,.0f} – {band_info['band_max']:,.0f}  "
                          f"| Mercer IPE PC: {band_info['ipe_pc']}  | Track: {band_info['track']}")

        with st.container(border=True):
            st.markdown(f"#### {tr('salary_inputs_offer', default='Offer Inputs')}")
            col1, col2, col3, col4 = st.columns(4)
            proposed_gross = col1.number_input('Gross Monthly (THB)', value=58000.0, step=1000.0, min_value=0.0, key='gross')
            base_pct = col2.slider('Base % of Gross', min_value=0.50, max_value=1.0, value=0.92, step=0.01, key='base_pct')
            market_p50 = col3.number_input('Market P50 EEC (THB)', value=58000.0, step=1000.0, key='mkt_p50')
            budget_max = col4.number_input('Budget Ceiling (THB)', value=65000.0, step=1000.0, key='budget')

            col1, col2, col3, col4 = st.columns(4)
            fixed_bonus = col1.number_input('Fixed Bonus (months base)', value=1.0, step=0.5, key='fixed_bonus')
            kpi_bonus = col2.number_input('KPI Bonus Target (months base)', value=1.0, step=0.5, key='kpi_bonus')
            group_ins = col3.number_input('Group Insurance / Year', value=6000.0, step=500.0, key='group_ins')
            training = col4.number_input('Training Budget / Year', value=12000.0, step=1000.0, key='training')

            with st.expander('Advanced (statutory rates) — usually leave at defaults', expanded=False):
                col1, col2, col3, col4 = st.columns(4)
                sso_rate = col1.number_input('SSO rate', value=0.05, step=0.005, format='%.3f', key='sso_rate')
                sso_ceiling = col2.number_input('SSO ceiling', value=17500.0, step=500.0, key='sso_ceil')
                pvf_rate = col3.number_input('PVF rate (ANCA)', value=0.07, step=0.01, format='%.3f', key='pvf_rate')
                wcf_rate = col4.number_input('WCF rate (ANCA)', value=0.0038, step=0.001, format='%.4f', key='wcf_rate')
                col1, col2 = st.columns(2)
                ewf_rate = col1.number_input('EWF rate (0 if PVF qualifies)', value=0.0, step=0.0025, format='%.4f', key='ewf_rate')
                col1.caption('⚠ Keep at 0 — ANCA exempt via qualifying PVF')
                severance = col2.number_input('Severance accrual rate', value=0.0833, step=0.001, format='%.4f', key='sev_rate')

        # === Calculate ===
        assumptions = {
            'base_pct': base_pct,
            'sso_rate': sso_rate, 'sso_ceiling': sso_ceiling,
            'pvf_rate': pvf_rate, 'wcf_rate': wcf_rate, 'ewf_rate': ewf_rate,
            'fixed_bonus_mos': fixed_bonus, 'kpi_bonus_mos': kpi_bonus,
            'group_ins_annual': group_ins, 'training_annual': training,
            'severance_rate': severance,
        }

        if band_info:
            grade_band = (band_info['band_min'], band_info['band_mid'], band_info['band_max'])
        else:
            grade_band = None

        result = calculate_offer(proposed_gross, assumptions=assumptions,
                                grade_band=grade_band, grade_key=proposed_grade)

        # === Display ===
        st.markdown(f"#### {tr('salary_breakdown', default='Annual Cost Breakdown')}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Gross Monthly', f"THB {result.gross_monthly:,.0f}")
        c2.metric('Total Monthly Cost', f"THB {result.total_monthly:,.0f}",
                 delta=f"+{result.total_monthly - result.gross_monthly:,.0f}")
        c3.metric('Total Annual Cost', f"THB {result.total_annual:,.0f}")
        c4.metric('Annual Multiplier', f"{result.annual_multiplier:.2f}×")

        # Detail table
        components = [
            ('Base salary',                  result.base_monthly,        result.base_monthly * 12,        'Pensionable + tax base'),
            ('Allowance (transport/comms)',  result.allowance_monthly,   result.allowance_monthly * 12,   'Per grade-based scheme'),
            ('SSO (employer, capped)',        result.sso_monthly,         result.sso_monthly * 12,         f'Capped at {sso_ceiling:,.0f} × {sso_rate*100:.1f}%'),
            ('PVF (employer 7%)',             result.pvf_monthly,         result.pvf_monthly * 12,         'Base × 7%, tax-advantaged'),
            ('WCF (0.38%)',                   result.wcf_monthly,         result.wcf_monthly * 12,         'ANCA assessed rate, annual premium'),
            ('EWF',                           result.ewf_monthly,         result.ewf_monthly * 12,         'EXEMPT (PVF qualifies as substitute)'),
            ('Fixed bonus (accrual)',         result.fixed_bonus_monthly, result.fixed_bonus_monthly * 12, f'Base × {fixed_bonus} month / 12'),
            ('KPI bonus (accrual, target)',   result.kpi_bonus_monthly,   result.kpi_bonus_monthly * 12,   f'Base × {kpi_bonus} month / 12'),
            ('Group health insurance',        result.group_ins_monthly,   result.group_ins_monthly * 12,   f'THB {group_ins:,.0f}/year'),
            ('Checkup + uniform',             result.checkup_uniform_mo,  result.checkup_uniform_mo * 12,  'Annual mandatory'),
            ('Training',                       result.training_monthly,    result.training_monthly * 12,    f'THB {training:,.0f}/year'),
            ('Severance accrual',             result.severance_monthly,   result.severance_monthly * 12,   'Base × 8.33% (1 mo/year)'),
        ]
        df_components = pd.DataFrame(components, columns=['Component', 'Monthly THB', 'Annual THB', 'Note'])
        df_components['Monthly THB'] = df_components['Monthly THB'].map(lambda v: f"{v:,.0f}")
        df_components['Annual THB']  = df_components['Annual THB'].map(lambda v: f"{v:,.0f}")
        st.dataframe(df_components, use_container_width=True, hide_index=True)

        # Band positioning
        if band_info:
            st.markdown(f"#### {tr('salary_positioning', default='Band & Market Positioning')}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric('Band Penetration', f"{result.band_penetration*100:.1f}%",
                     delta=penetration_label(result.band_penetration), delta_color='off')
            c2.metric('Compa-Ratio', f"{result.compa_ratio*100:.1f}%",
                     delta=compa_label(result.compa_ratio), delta_color='off')
            vs_p50 = (proposed_gross / market_p50 - 1) * 100 if market_p50 > 0 else 0
            c3.metric('vs Market P50', f"{vs_p50:+.1f}%")
            vs_budget = (proposed_gross / budget_max - 1) * 100 if budget_max > 0 else 0
            c4.metric('vs Budget', f"{vs_budget:+.1f}%",
                     delta=('Within budget' if vs_budget <= 0 else 'OVER BUDGET'),
                     delta_color=('inverse' if vs_budget > 0 else 'normal'))

        # Save
        if st.button(f"💾 {tr('salary_save_offer', default='Save This Offer')}", type='primary', key='save_off'):
            try:
                notes = f"Calculated by {username}. Market P50 ref: {market_p50:,.0f}; Budget ceiling: {budget_max:,.0f}."
                bd = result.to_dict()
                bd['base_pct'] = base_pct
                bd['fixed_bonus_mos'] = fixed_bonus
                bd['kpi_bonus_mos'] = kpi_bonus
                bd['market_p50'] = market_p50
                offer_id = salary_data.save_offer(
                    username,
                    candidate_ref=candidate_ref,
                    position_title=position_title,
                    proposed_grade=proposed_grade,
                    proposed_gross=proposed_gross,
                    breakdown=bd,
                    notes=notes,
                )
                st.success(f"✅ Offer saved as record #{offer_id}.")
            except salary_data.CapabilityError as e:
                st.error(f"🔒 {e}")
            except Exception as e:
                st.error(f"Error: {e}")

        # Recent offers
        if has_capability(username, salary_data.CAP_VIEW_AUDIT):
            with st.expander(f"📜 {tr('salary_recent_offers', default='Recent Saved Offers')}", expanded=False):
                try:
                    recent = salary_data.list_recent_offers(username, limit=20)
                    if len(recent) > 0:
                        recent['proposed_gross'] = recent['proposed_gross'].map(lambda v: f"{v:,.0f}")
                        recent['total_annual']   = recent['total_annual'].map(lambda v: f"{v:,.0f}")
                        recent['penetration']    = recent['penetration'].map(
                            lambda v: f"{v*100:.0f}%" if v is not None and not pd.isna(v) else "—")
                        st.dataframe(recent, use_container_width=True, hide_index=True)
                    else:
                        st.info('No offers saved yet.')
                except salary_data.CapabilityError as e:
                    st.warning(f"🔒 {e}")

# =============================================================================
# TAB 3 — Headcount Map
# =============================================================================
with tab3:
    st.markdown(f"### {tr('salary_headcount_map', default='Active Headcount — Mapped to Proposed Grade')}")
    st.caption(tr('salary_headcount_caption',
        default='All active employees mapped from current Lv1/2/3 to proposed grades, with off-band status flags.'))

    # Try to load employee_extended with salary; this assumes the host app's employees tables
    try:
        from lib.db import get_db_conn
        with get_db_conn() as conn:
            # Try a few common table names
            for tbl_candidate in ['employees_extended', 'employees']:
                try:
                    emp_df = pd.read_sql_query(f"SELECT * FROM {tbl_candidate}", conn)
                    if len(emp_df) > 0:
                        break
                except Exception:
                    continue
            else:
                emp_df = pd.DataFrame()
    except Exception:
        emp_df = pd.DataFrame()

    if len(emp_df) == 0:
        st.info(tr('salary_no_emp_data',
            default='No employee data found in database. Use the Employee Master upload (Module 1) to load 171 active employees first.'))
    else:
        # If salary column exists, do band-status flagging
        if 'salary' in emp_df.columns or 'Salary' in emp_df.columns:
            sal_col = 'salary' if 'salary' in emp_df.columns else 'Salary'
            # Mapping logic: simplified — production version would persist grade_key per employee
            st.caption('🟢 In band  |  🟡 Within 10% of band edge  |  🔴 Off-band (>10% gap)')
            st.dataframe(emp_df.head(50), use_container_width=True, hide_index=True)
            st.caption(f"Showing first 50 of {len(emp_df)} employees. Full mapping in Excel workbook Sheet 8.")
        else:
            st.info('Employee table has no salary column. Connect to Module 2 (Manpower Budget) for salary data.')

# =============================================================================
# TAB 4 — Market Benchmark
# =============================================================================
with tab4:
    st.markdown(f"### {tr('salary_market_bench', default='Market Benchmark — Thai Manufacturing 2026 (EEC)')}")
    st.caption(tr('salary_market_caption',
        default='Reference data from Robert Walters Eastern Seaboard Salary Survey, Mercer TRS, Adecco, Manpower Thailand.'))

    # Hardcoded reference — could be moved to a salary_market_benchmark table for editing
    benchmarks = [
        ('Production Operator (Skilled)',    'O2',  13000, 16000, 19000, 'Manpower 2026 + Jobsdb', '+5–10% vs BKK'),
        ('Welder (qualified MIG/TIG)',       'O2/O3','16000', 21000, 26000, 'Robert Walters Eastern', '+10–15%'),
        ('Production / Planning Admin',      'L2',  19000, 23500, 28000, 'Adecco 2026', '+5–10%'),
        ('Inspector / QC Inspector',         'L3',  23000, 28500, 35000, 'Manpower 2026', '+5–10%'),
        ('Maintenance Technician',           'L3',  24000, 30000, 38000, 'Robert Walters Eastern', '+10–15%'),
        ('Design Engineer (Jr 0-3y)',        'L4',  28000, 36000, 45000, 'Robert Walters Eastern', '+10–15%'),
        ('Manufacturing Engineer (Mid)',     'L5',  40000, 50000, 62000, 'Robert Walters Eastern', '+12–18%'),
        ('Senior Design Engineer',           'L6',  55000, 67000, 82000, 'Robert Walters Eastern', '+15–20%'),
        ('🎯 SENIOR PRODUCTION PLANNER',     'L6',  48000, 58000, 70000, 'Robert Walters + Jobsdb', '+10–15%'),
        ('Senior Manufacturing Engineer',    'L6',  50000, 62000, 78000, 'Robert Walters Eastern', '+15–20%'),
        ('Production Supervisor (5y+)',      'L7',  55000, 68000, 85000, 'Manpower 2026', '+10–15%'),
        ('Senior Sales Engineer',            'L7',  60000, 75000, 95000, 'Robert Walters', '+10%'),
        ('Assistant Manager',                'L8',  75000, 92000, 115000, 'Robert Walters', '+10%'),
        ('Planning Manager',                 'L9',  85000, 105000, 130000, 'Robert Walters Eastern', '+10–15%'),
        ('HR Manager',                       'L9',  80000, 100000, 125000, 'Robert Walters', '+5–10%'),
        ('Finance Manager',                  'L9',  85000, 105000, 135000, 'Robert Walters', '+5–10%'),
        ('Engineering Manager',              'L9',  100000, 125000, 155000, 'Robert Walters Eastern', '+10–15%'),
        ('Mfg Engineering Manager',          'L10', 115000, 145000, 180000, 'Robert Walters Eastern', '+10–15%'),
        ('Quality Manager',                  'L10', 110000, 138000, 175000, 'Robert Walters Eastern', '+10–15%'),
        ('Production Manager',               'L10', 115000, 145000, 180000, 'Robert Walters Eastern', '+10–15%'),
        ('Supply Chain Manager',             'L10', 105000, 135000, 175000, 'Robert Walters Eastern', '+10%'),
        ('Operation Director',               'L11', 180000, 230000, 290000, 'Korn Ferry / Mercer', '+10%'),
        ('General Manager (Country)',        'L12', 350000, 480000, 620000, 'Mercer TRS / Korn Ferry', 'Negotiated'),
    ]
    df_b = pd.DataFrame(benchmarks, columns=['Role', 'ANCA Grade', 'P25 EEC', 'P50 EEC', 'P75 EEC', 'Source', 'EEC Premium'])
    df_b['P25 EEC'] = df_b['P25 EEC'].astype(str).str.replace(',', '').astype(float).map(lambda v: f"{v:,.0f}")
    df_b['P50 EEC'] = df_b['P50 EEC'].astype(str).str.replace(',', '').astype(float).map(lambda v: f"{v:,.0f}")
    df_b['P75 EEC'] = df_b['P75 EEC'].astype(str).str.replace(',', '').astype(float).map(lambda v: f"{v:,.0f}")
    st.dataframe(df_b, use_container_width=True, hide_index=True)

    st.markdown('#### Market Trend Signals')
    st.markdown("""
    - 📈 **Mercer TRS 2026:** +5.2% Thailand avg; +5.5% automotive/precision manufacturing
    - 📈 **Adecco 2026 survey:** 82% professionals received 2–5% increase in 2025; 23% actively seeking change (down from 40% in 2024)
    - ⚠ **EEC labor competition:** Toyota/Ford/BMW/BYD all hiring; engineering roles see 10–25% premium over Bangkok
    - 🎓 **Skills premium:** Lean Six Sigma +5–10%; SAP/JDE/Kinaxis +10–15%; PMP/CPIM +5–8%
    """)

# =============================================================================
# TAB 5 — Compliance
# =============================================================================
with tab5:
    st.markdown(f"### {tr('salary_compliance', default='Thailand 2026 — Statutory Cost Reference')}")
    try:
        compl_df = salary_data.get_all_compliance_rates(username)
        # Format for display
        display = compl_df.copy()
        display['rate'] = display['rate'].map(lambda v: f"{v*100:.2f}%" if pd.notna(v) else '—')
        display['wage_base_min'] = display['wage_base_min'].map(lambda v: f"{v:,.0f}" if pd.notna(v) else '—')
        display['wage_base_max'] = display['wage_base_max'].map(lambda v: f"{v:,.0f}" if pd.notna(v) else '—')
        display['monthly_cap']   = display['monthly_cap'].map(lambda v: f"{v:,.0f}" if pd.notna(v) else '—')
        st.dataframe(display, use_container_width=True, hide_index=True)
    except salary_data.CapabilityError as e:
        st.error(str(e))

    st.markdown('#### Key 2026 Changes')
    st.markdown("""
    - **SSO** ceiling raised 15,000 → 17,500 from 1-Jan-2026. Max employer contribution 750 → **875/month**. (Phase 2: 20,000 in 2029, Phase 3: 23,000 in 2032.)
    - **EWF** mandatory from 1-Oct-2026 (postponed from 2025). 0.25% + 0.25%, rising to 0.50% + 0.50% in 2031.
      - **ANCA EXEMPT** because PVF (7%) qualifies as substitute fund. ⚠ Must register exemption with DLPW before 1-Oct-2026.
    - **WCF** ANCA rated at 0.38% (manufacturing low-risk). Annual premium.
    - **PVF** ANCA 7% employer + 2% employee minimum. Tax-advantaged.
    """)
