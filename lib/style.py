"""
Anca CI design system — frosted glass, white-major.

Brand colors (from logo):
    Cyan    #009ADE
    Purple  #715091
    Magenta #E31D93

The design uses white as the primary surface, soft pastel-tinted glass for
secondary surfaces, and the brand colors as accents and gradients.
"""
import streamlit as st


_CSS = """
<style>
/* ─── Brand color tokens ─────────────────────────────────────────────── */
:root {
    --brand-cyan:    #009ADE;
    --brand-purple:  #715091;
    --brand-magenta: #E31D93;
    --brand-cyan-15:    rgba(0, 154, 222, 0.15);
    --brand-purple-15:  rgba(113, 80, 145, 0.15);
    --brand-magenta-15: rgba(227, 29, 147, 0.15);
    --ink:           #1F2937;
    --ink-muted:     #6B7280;
    --surface:       #FFFFFF;
    --surface-glass: rgba(255, 255, 255, 0.65);
    --hairline:      rgba(15, 23, 42, 0.08);
}

/* ─── Body & app background — soft pastel field ─────────────────────── */
.stApp {
    background:
        radial-gradient(circle at 8% 10%, rgba(0,154,222,0.10) 0%, transparent 35%),
        radial-gradient(circle at 95% 5%, rgba(227,29,147,0.08) 0%, transparent 40%),
        radial-gradient(circle at 50% 100%, rgba(113,80,145,0.07) 0%, transparent 45%),
        #FFFFFF;
    background-attachment: fixed;
}

/* ─── Typography ────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: "Sarabun", -apple-system, BlinkMacSystemFont, "SF Pro Text",
                 "Inter", "Segoe UI", Roboto, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}
@import url("https://fonts.googleapis.com/css2?family=Sarabun:wght@400;500;600;700&display=swap");

h1, h2, h3, h4 {
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--ink);
}
h1 { font-size: 1.85rem; }
h2 { font-size: 1.4rem; }

/* ─── Block container ───────────────────────────────────────────────── */
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1400px;
}

/* ─── SIDEBAR — frosted glass with logo at top ─────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg,
        rgba(255,255,255,0.85) 0%,
        rgba(245,247,255,0.78) 100%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    backdrop-filter: blur(20px) saturate(180%);
    border-right: 1px solid var(--hairline);
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
    color: var(--ink);
}

/* Hide Streamlit's default page nav (we render our own with bilingual labels) */
[data-testid="stSidebarNav"] { display: none !important; }

/* ─── Buttons — pill shaped with brand gradient on primary ──────────── */
/* Cover ALL Streamlit button variants for max compatibility */
.stButton > button,
.stDownloadButton > button,
.stFormSubmitButton > button,
[data-testid="stFormSubmitButton"] button,
[data-testid="baseButton-primary"],
[data-testid="baseButton-secondary"],
button[kind="primary"],
button[kind="secondary"],
button[kind="primaryFormSubmit"],
button[kind="secondaryFormSubmit"] {
    border-radius: 10px !important;
    font-weight: 500;
    border: 1px solid var(--hairline);
    background: rgba(255,255,255,0.7);
    color: var(--ink) !important;
    -webkit-backdrop-filter: blur(10px);
    backdrop-filter: blur(10px);
    transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 1px 2px rgba(15,23,42,0.04);
    min-height: 38px;
    padding: 8px 16px !important;
    cursor: pointer;
}
.stButton > button:hover,
.stDownloadButton > button:hover,
.stFormSubmitButton > button:hover,
[data-testid="stFormSubmitButton"] button:hover {
    border-color: var(--brand-cyan);
    color: var(--brand-cyan) !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,154,222,0.15);
}
/* Primary buttons - brand gradient
   AGGRESSIVE: target ALL form submit buttons regardless of "kind" attribute.
   Streamlit Cloud sometimes ships builds where button[kind] isn't set, leaving
   the button white-on-white. Targeting by data-testid only is reliable. */
.stFormSubmitButton > button,
[data-testid="stFormSubmitButton"] button,
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"],
button[kind="primary"],
button[kind="primaryFormSubmit"] {
    /* Solid fallback color first (in case gradient fails to render),
       then gradient overrides if the browser supports it */
    background-color: #715091 !important;
    background: linear-gradient(135deg, #009ADE 0%, #715091 60%, #E31D93 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    box-shadow: 0 2px 12px rgba(113,80,145,0.30);
    font-weight: 600 !important;
}
/* Force EVERY descendant element of form-submit buttons to be white,
   overriding any inherited color from the surrounding container */
.stFormSubmitButton > button *,
[data-testid="stFormSubmitButton"] button *,
.stButton > button[kind="primary"] *,
button[kind="primary"] *,
button[kind="primaryFormSubmit"] * {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    fill: #FFFFFF !important;
}
.stFormSubmitButton > button:hover,
[data-testid="stFormSubmitButton"] button:hover,
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover,
button[kind="primaryFormSubmit"]:hover {
    color: #FFFFFF !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(113,80,145,0.45);
    filter: brightness(1.05);
}
/* Make sure button text/labels are visible */
.stButton > button p,
.stFormSubmitButton > button p,
[data-testid="stFormSubmitButton"] button p {
    color: inherit !important;
    margin: 0 !important;
}

/* ─── Inputs — soft frosted background ──────────────────────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea,
.stDateInput > div > div > input {
    border-radius: 10px !important;
    border: 1px solid var(--hairline) !important;
    background: rgba(255,255,255,0.7) !important;
    -webkit-backdrop-filter: blur(8px);
    backdrop-filter: blur(8px);
    color: var(--ink) !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--brand-cyan) !important;
    box-shadow: 0 0 0 3px var(--brand-cyan-15) !important;
}

[data-baseweb="select"] > div {
    border-radius: 10px !important;
    background: rgba(255,255,255,0.7) !important;
    border-color: var(--hairline) !important;
}

/* ─── Tabs ──────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    border-bottom: 1px solid var(--hairline);
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px 10px 0 0;
    padding: 10px 18px;
    color: var(--ink-muted);
    font-weight: 500;
    background: transparent;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--brand-cyan);
}
.stTabs [aria-selected="true"] {
    color: var(--brand-purple) !important;
    background-color: transparent !important;
    border-bottom: 3px solid var(--brand-magenta) !important;
    margin-bottom: -1px;
}

/* ─── Metrics — frosted card style ──────────────────────────────────── */
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.65);
    -webkit-backdrop-filter: blur(14px) saturate(180%);
    backdrop-filter: blur(14px) saturate(180%);
    padding: 16px 20px;
    border-radius: 14px;
    border: 1px solid var(--hairline);
    box-shadow: 0 1px 3px rgba(15,23,42,0.04);
}
[data-testid="stMetricLabel"] {
    font-size: 0.78rem;
    color: var(--ink-muted);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
[data-testid="stMetricValue"] {
    font-size: 1.6rem;
    color: var(--ink);
    font-weight: 700;
    background: linear-gradient(135deg, var(--brand-cyan) 0%, var(--brand-magenta) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* ─── Dataframes ────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--hairline);
    box-shadow: 0 1px 3px rgba(15,23,42,0.04);
}

/* ─── Alert boxes — frosted ─────────────────────────────────────────── */
.stAlert {
    border-radius: 12px;
    border-left-width: 4px;
    background: rgba(255,255,255,0.75) !important;
    -webkit-backdrop-filter: blur(12px);
    backdrop-filter: blur(12px);
}

/* ─── Bordered containers (st.container(border=True)) ───────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--hairline) !important;
    border-radius: 14px !important;
    background: rgba(255,255,255,0.55) !important;
    -webkit-backdrop-filter: blur(16px) saturate(180%);
    backdrop-filter: blur(16px) saturate(180%);
    padding: 4px;
}

/* ─── Code chips ────────────────────────────────────────────────────── */
code {
    background: rgba(0,154,222,0.10);
    color: var(--brand-purple);
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.875em;
    font-weight: 500;
}

/* ─── Captions ──────────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] {
    color: var(--ink-muted);
    font-size: 0.875rem;
    line-height: 1.55;
}

/* ─── Dividers ──────────────────────────────────────────────────────── */
hr {
    border: none;
    border-top: 1px solid var(--hairline);
    margin: 1.5rem 0;
}

/* ─── Toggle & checkbox — brand color when on ───────────────────────── */
[data-testid="stCheckbox"] svg, [data-testid="stToggle"] [data-baseweb="checkbox"] div {
    color: var(--brand-cyan) !important;
}

/* ─── Hide Streamlit's status header ────────────────────────────────── */
header[data-testid="stHeader"] { background: transparent; }
.viewerBadge_container__1QSob, footer { display: none !important; }
[data-testid="stToolbar"] { right: 1rem; }

/* ─── Custom: brand gradient header band on app pages ───────────────── */
.brand-band {
    height: 4px;
    background: linear-gradient(90deg,
        var(--brand-cyan) 0%,
        var(--brand-purple) 50%,
        var(--brand-magenta) 100%);
    border-radius: 3px;
    margin-bottom: 1.5rem;
}

/* ─── Custom: company badge in sidebar ──────────────────────────────── */
.company-badge {
    text-align: center;
    padding: 1.2rem 0.5rem 1.5rem 0.5rem;
    border-bottom: 1px solid var(--hairline);
    margin-bottom: 1rem;
}
.company-badge .name {
    font-weight: 700;
    font-size: 0.95rem;
    color: var(--ink);
    margin-top: 0.6rem;
    letter-spacing: 0.01em;
}
.company-badge .tag {
    font-size: 0.78rem;
    color: var(--ink-muted);
    margin-top: 2px;
}

/* ─── Custom: nav-link buttons in sidebar ───────────────────────────── */
[data-testid="stSidebar"] .stButton > button {
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 10px 14px !important;
    background: transparent !important;
    border: 1px solid transparent !important;
    box-shadow: none !important;
    color: var(--ink) !important;
    font-weight: 500;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(0,154,222,0.08) !important;
    border-color: rgba(0,154,222,0.20) !important;
    color: var(--brand-cyan) !important;
    transform: none !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, rgba(0,154,222,0.15), rgba(227,29,147,0.10)) !important;
    border: 1px solid rgba(113,80,145,0.30) !important;
    color: var(--brand-purple) !important;
    font-weight: 600;
    box-shadow: 0 1px 4px rgba(113,80,145,0.10) !important;
}

/* ─── Login card ────────────────────────────────────────────────────── */
.login-wrapper {
    max-width: 420px;
    margin: 1rem auto 0 auto;
    padding: 2rem 2rem 1rem 2rem;
    background: rgba(255,255,255,0.75);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    backdrop-filter: blur(20px) saturate(180%);
    border: 1px solid var(--hairline);
    border-radius: 18px;
    box-shadow: 0 8px 30px rgba(15,23,42,0.06);
}
.login-logo-wrap {
    text-align: center;
    margin-bottom: 1rem;
}
.login-title {
    text-align: center;
    font-size: 1.3rem;
    font-weight: 700;
    margin: 0;
    background: linear-gradient(135deg, var(--brand-cyan) 0%, var(--brand-purple) 50%, var(--brand-magenta) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.login-tagline {
    text-align: center;
    color: var(--ink-muted);
    font-size: 0.9rem;
    margin-top: 4px;
    margin-bottom: 1.5rem;
}
</style>
"""


def inject_anca_style():
    """Apply the Anca CI frosted-glass theme. Call once per page."""
    st.markdown(_CSS, unsafe_allow_html=True)


def brand_band():
    """Render a thin gradient bar matching the CI colors."""
    st.markdown('<div class="brand-band"></div>', unsafe_allow_html=True)
