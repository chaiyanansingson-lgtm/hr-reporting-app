# lib/ot_report_render.py
# ============================================================================
# Renders the "Overtime Paid by Department — A vs B" infographic as PNG / PDF
# using ONLY matplotlib (works on Streamlit Community Cloud — no kaleido, no
# browser, no system binaries). Mirrors the level-meeting layout: title block
# with ANCA wordmark + cycle dates, three summary cards, a horizontal grouped
# bar chart with value labels and change %, and a full comparison table.
# ============================================================================
import io

# ANCA brand palette
BLUE = "#009ADE"
PURPLE = "#715091"
MAGENTA = "#E31D93"
GREEN = "#1B9E55"
RED = "#D62728"
INK = "#1f2733"
GREY = "#6b7280"
CARD_BG = "#f4f7fb"
GRID = "#e6ebf2"

# glyphs as constants (avoid backslashes inside f-string replacement fields,
# which is a SyntaxError on Python < 3.12)
MINUS = "\u2212"
UP = "\u25b2"
DOWN = "\u25bc"


def _fonts():
    from matplotlib import font_manager as fm
    reg = bold = None
    for fp in ("/root/.fonts/Sarabun-Regular.ttf",
               "assets/fonts/Sarabun-Regular.ttf"):
        try:
            fm.fontManager.addfont(fp); reg = fm.FontProperties(fname=fp); break
        except Exception:
            pass
    for fp in ("/root/.fonts/Sarabun-Bold.ttf",
               "assets/fonts/Sarabun-Bold.ttf"):
        try:
            fm.fontManager.addfont(fp); bold = fm.FontProperties(fname=fp); break
        except Exception:
            pass
    return reg, bold


def _thb(v):
    return f"\u0e3f {v:,.0f}"


def render_comparison(label_a, data_a, label_b, data_b,
                      dept_order, period_a="", period_b="",
                      org_name="ANCA Manufacturing Solutions"):
    """data_a / data_b = {dept: ot}. Returns {'png': bytes, 'pdf': bytes}."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    import numpy as np

    reg, bold = _fonts()
    FB = bold or None
    FR = reg or None

    depts = list(dept_order)
    a = [float(data_a.get(d, 0) or 0) for d in depts]
    b = [float(data_b.get(d, 0) or 0) for d in depts]
    tot_a, tot_b = sum(a), sum(b)
    delta = tot_b - tot_a
    pct = (delta / tot_a * 100) if tot_a else 0.0

    n = len(depts)
    # ---- figure geometry (inches) ----
    W = 13.0
    H_HEAD = 1.7
    H_CARD = 1.7
    H_BARTITLE = 0.5
    H_BAR = 0.46 * n            # bar chart body
    H_GAP = 0.35
    H_TBLHEAD = 0.5
    H_TROW = 0.34
    H_TABLE = H_TROW * (n + 1)  # rows + TOTAL
    H_FOOT = 0.95
    H = (H_HEAD + H_CARD + H_BARTITLE + H_BAR + H_GAP +
         H_TBLHEAD + H_TABLE + H_FOOT + 0.5)

    fig = plt.figure(figsize=(W, H), dpi=150)
    fig.patch.set_facecolor("white")

    def band_top(*used):
        return 1.0 - (sum(used) / H)

    yfrac = lambda inch: inch / H
    xL = 0.045
    xR = 0.965

    # ============================================================ HEADER
    y0 = 1.0 - yfrac(0.30)
    fig.text(xL, y0 - yfrac(0.30),
             f"Overtime Paid by Department \u2014 {label_a} vs {label_b}",
             fontproperties=FB, fontsize=23, color=INK, va="top", weight="bold")
    fig.text(xL, y0 - yfrac(0.92),
             "OT cost by department (THB) \u00b7 Office Staff expanded into "
             "functions", fontproperties=FR, fontsize=12.5, color=GREY,
             va="top")
    # ANCA wordmark + cycles (right)
    fig.text(xR, y0 - yfrac(0.26), org_name, fontproperties=FB, fontsize=13.5,
             color=BLUE, va="top", ha="right", weight="bold")
    if period_a:
        fig.text(xR, y0 - yfrac(0.72), f"{label_a} cycle: {period_a}",
                 fontproperties=FR, fontsize=10, color=GREY, va="top",
                 ha="right")
    if period_b:
        fig.text(xR, y0 - yfrac(1.00), f"{label_b} cycle: {period_b}",
                 fontproperties=FR, fontsize=10, color=GREY, va="top",
                 ha="right")
    # divider
    ax_line = fig.add_axes([xL, band_top(H_HEAD), xR - xL, 0.0008], zorder=1)
    ax_line.axhline(0, color=GRID, lw=1.4); ax_line.axis("off")

    # ============================================================ CARDS
    card_top_in = H_HEAD + 0.18
    card_h_in = H_CARD - 0.30
    cy = 1.0 - yfrac(card_top_in + card_h_in)
    ctop = cy + yfrac(card_h_in)
    cw = (xR - xL - 0.04) / 3.0
    cards = [
        (f"{label_a} TOTAL OT".upper(), _thb(tot_a), period_a, BLUE, INK),
        (f"{label_b} TOTAL OT".upper(), _thb(tot_b), period_b, MAGENTA, INK),
        ("MONTH-ON-MONTH",
         ("+" if delta >= 0 else MINUS) + _thb(abs(delta)),
         (UP if delta >= 0 else DOWN) + f" {abs(pct):.1f}%  vs {label_a}",
         PURPLE, GREEN if delta >= 0 else RED),
    ]
    axc = fig.add_axes([0, 0, 1, 1], zorder=2); axc.axis("off")
    axc.set_xlim(0, 1); axc.set_ylim(0, 1)
    for i, (cap, val, sub, bar, valcol) in enumerate(cards):
        x = xL + i * (cw + 0.02)
        axc.add_patch(FancyBboxPatch(
            (x, cy), cw, yfrac(card_h_in),
            boxstyle="round,pad=0.004,rounding_size=0.010",
            linewidth=0, facecolor=CARD_BG, mutation_aspect=H / W))
        axc.add_patch(plt.Rectangle((x, cy), 0.006, yfrac(card_h_in),
                                    facecolor=bar, edgecolor="none"))
        tx = x + 0.022
        axc.text(tx, ctop - yfrac(0.30), cap, fontproperties=FB, fontsize=10,
                 color=GREY, va="top", weight="bold")
        axc.text(tx, ctop - yfrac(0.74), val, fontproperties=FB, fontsize=19,
                 color=valcol, va="top", weight="bold")
        if sub:
            axc.text(tx, cy + yfrac(0.22), sub, fontproperties=FR,
                     fontsize=9.5, color=GREY, va="bottom")

    # ============================================================ BAR TITLE
    bt_in = H_HEAD + H_CARD + 0.30
    fig.text(xL, 1.0 - yfrac(bt_in),
             "OT paid by department (Office Staff expanded)",
             fontproperties=FB, fontsize=14, color=INK, va="top", weight="bold")
    # legend
    lx = xL
    ly = 1.0 - yfrac(bt_in + 0.34)
    axl = fig.add_axes([0, 0, 1, 1], zorder=3); axl.axis("off")
    axl.set_xlim(0, 1); axl.set_ylim(0, 1)
    axl.add_patch(plt.Rectangle((lx, ly), 0.014, 0.010, facecolor=BLUE,
                                edgecolor="none"))
    axl.text(lx + 0.02, ly + 0.005, label_a, fontproperties=FR, fontsize=10.5,
             va="center", color=INK)
    lx2 = lx + 0.10
    axl.add_patch(plt.Rectangle((lx2, ly), 0.014, 0.010, facecolor=MAGENTA,
                                edgecolor="none"))
    axl.text(lx2 + 0.02, ly + 0.005, label_b, fontproperties=FR, fontsize=10.5,
             va="center", color=INK)

    # ============================================================ BARS
    bars_top_in = bt_in + 0.55
    bars_bottom_in = bars_top_in + H_BAR
    ax = fig.add_axes([0.205, band_top(bars_bottom_in),
                       0.60, yfrac(H_BAR)])
    ax.set_facecolor("white")
    ypos = np.arange(n)[::-1]            # first dept at top
    bw = 0.38
    vmax = max(max(a), max(b), 1.0)
    ax.barh(ypos + bw / 2 + 0.02, a, height=bw, color=BLUE, zorder=3)
    ax.barh(ypos - bw / 2 - 0.02, b, height=bw, color=MAGENTA, zorder=3)
    ax.set_xlim(0, vmax * 1.16)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_yticks(ypos)
    ax.set_yticklabels(depts, fontproperties=FR, fontsize=10.5, color=INK)
    ax.tick_params(axis="y", length=0, pad=6)
    ax.set_xticks([])
    for sp in ("top", "right", "bottom", "left"):
        ax.spines[sp].set_visible(False)
    ax.xaxis.grid(True, color=GRID, lw=0.8, zorder=0)

    lab_off = vmax * 0.012
    for i, (va_, vb_) in enumerate(zip(a, b)):
        yp = ypos[i]
        ax.text(va_ + lab_off, yp + bw / 2 + 0.02, _thb(va_),
                va="center", ha="left", fontsize=8.6, color=INK,
                fontproperties=FR)
        ax.text(vb_ + lab_off, yp - bw / 2 - 0.02, _thb(vb_),
                va="center", ha="left", fontsize=8.6, color=INK,
                fontproperties=FR)
        # change % at far right (figure-level for consistent x)
        ch = vb_ - va_
        cp = (ch / va_ * 100) if va_ else (100.0 if vb_ else 0.0)
        col = GREEN if ch >= 0 else RED
        arr = "\u25b2" if ch >= 0 else "\u25bc"
        ax.text(1.0, (yp - ax.get_ylim()[0]) /
                (ax.get_ylim()[1] - ax.get_ylim()[0]),
                f"{arr} {abs(cp):.1f}%", transform=ax.transAxes,
                va="center", ha="right", fontsize=9.2, color=col,
                fontproperties=FB, weight="bold")

    # ============================================================ TABLE
    tbl_head_in = bars_bottom_in + H_GAP
    axt = fig.add_axes([0, 0, 1, 1], zorder=2); axt.axis("off")
    axt.set_xlim(0, 1); axt.set_ylim(0, 1)
    # columns (figure x)
    cx_dept = xL + 0.005
    cx_a = 0.50
    cx_b = 0.635
    cx_ch = 0.795
    cx_pct = 0.955
    hy = 1.0 - yfrac(tbl_head_in)
    axt.text(cx_dept, hy, "DEPARTMENT", fontproperties=FB, fontsize=9.5,
             color=GREY, va="top", weight="bold")
    for cx, t in ((cx_a, f"{label_a.upper()} (THB)"),
                  (cx_b, f"{label_b.upper()} (THB)"),
                  (cx_ch, "CHANGE (THB)"), (cx_pct, "CHANGE %")):
        axt.text(cx, hy, t, fontproperties=FB, fontsize=9.5, color=GREY,
                 va="top", ha="right", weight="bold")
    axt.add_line(plt.Line2D([xL, xR], [hy - yfrac(0.16)] * 2, color=INK,
                            lw=1.1))

    row_y = tbl_head_in + 0.40
    for i, d in enumerate(depts):
        ry = 1.0 - yfrac(row_y + i * H_TROW)
        if i % 2 == 1:
            axt.add_patch(plt.Rectangle((xL - 0.004, ry - yfrac(H_TROW) +
                                         yfrac(0.06)), xR - xL + 0.008,
                                        yfrac(H_TROW), facecolor="#fafbfd",
                                        edgecolor="none", zorder=1))
        ch = b[i] - a[i]
        cp = (ch / a[i] * 100) if a[i] else (100.0 if b[i] else 0.0)
        col = GREEN if ch >= 0 else RED
        axt.text(cx_dept, ry, d, fontproperties=FR, fontsize=9.6, color=INK,
                 va="top", zorder=2)
        axt.text(cx_a, ry, f"{a[i]:,.0f}", fontproperties=FR, fontsize=9.6,
                 color=INK, va="top", ha="right", zorder=2)
        axt.text(cx_b, ry, f"{b[i]:,.0f}", fontproperties=FR, fontsize=9.6,
                 color=INK, va="top", ha="right", zorder=2)
        sign = "+" if ch >= 0 else "\u2212"
        axt.text(cx_ch, ry, f"{sign}{abs(ch):,.0f}", fontproperties=FB,
                 fontsize=9.6, color=col, va="top", ha="right", zorder=2)
        axt.text(cx_pct, ry, f"{sign}{abs(cp):.1f}%", fontproperties=FB,
                 fontsize=9.6, color=col, va="top", ha="right", zorder=2)
    # TOTAL row
    ry = 1.0 - yfrac(row_y + n * H_TROW)
    axt.add_line(plt.Line2D([xL, xR], [ry + yfrac(0.10)] * 2, color=INK,
                            lw=1.1))
    chT = tot_b - tot_a
    cpT = (chT / tot_a * 100) if tot_a else 0.0
    colT = GREEN if chT >= 0 else RED
    sgn = "+" if chT >= 0 else "\u2212"
    axt.text(cx_dept, ry - yfrac(0.04), "TOTAL", fontproperties=FB,
             fontsize=10.5, color=INK, va="top", weight="bold")
    axt.text(cx_a, ry - yfrac(0.04), f"{tot_a:,.0f}", fontproperties=FB,
             fontsize=10.5, color=INK, va="top", ha="right", weight="bold")
    axt.text(cx_b, ry - yfrac(0.04), f"{tot_b:,.0f}", fontproperties=FB,
             fontsize=10.5, color=INK, va="top", ha="right", weight="bold")
    axt.text(cx_ch, ry - yfrac(0.04), f"{sgn}{abs(chT):,.0f}",
             fontproperties=FB, fontsize=10.5, color=colT, va="top",
             ha="right", weight="bold")
    axt.text(cx_pct, ry - yfrac(0.04), f"{sgn}{abs(cpT):.1f}%",
             fontproperties=FB, fontsize=10.5, color=colT, va="top",
             ha="right", weight="bold")

    # ============================================================ FOOTNOTE
    fy = yfrac(0.62)
    foot = ("Source: Monthly salary reports (OverTime column), reconciled to "
            "payroll totals. Full coverage \u2014 every cost centre mapped.   "
            "Grouping: 18 departments; QC=ASM280, Packing=ASM263, "
            "Warehouse=Supply Chains (ASM270/270.1). Office Staff is split into "
            "Production Support (ME/MTN/Prod), Planning, Engineering "
            "(ASM310+313), Purchasing, Sales, and Finance/HR/Admin.")
    fig.text(xL, fy, foot, fontproperties=FR, fontsize=8.4, color=GREY,
             va="bottom", ha="left", wrap=True)

    png = io.BytesIO(); fig.savefig(png, format="png", facecolor="white",
                                    bbox_inches="tight", pad_inches=0.25)
    pdf = io.BytesIO(); fig.savefig(pdf, format="pdf", facecolor="white",
                                    bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    return {"png": png.getvalue(), "pdf": pdf.getvalue()}
