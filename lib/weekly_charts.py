# lib/weekly_charts.py
# ---------------------------------------------------------------------------
# Presentation-quality weekly charts (matplotlib → PNG) that reproduce the
# Excel look used in the weekly report:
#   • combo_chart()  – grouped Working/OT(or Leave) hour bars + Prev-week and
#                      This-week % lines + dashed Target, with %-labels on the
#                      This-week line. (images 2 & 3)
#   • per_org_grid() – one small line chart PER department, %-labels boxed
#                      red when over the limit and green when under. (image 4)
# Every builder returns a matplotlib Figure; png_bytes() renders it for the
# Streamlit download button.
# ---------------------------------------------------------------------------
import io
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# palette tuned to the reference images
C_WORK = "#4F6F1F"     # Working-hours bars (olive green)
C_SEC = "#E08214"      # OT / Leave hour bars (orange)
C_PREV = "#9DC3E6"     # previous-week line (light blue)
C_THIS = "#1F3864"     # this-week line (dark navy)
C_TARGET = "#5B8C2A"   # target (green dashed)
LBL_BG = "#E7E0F0"     # this-week %-label box (soft purple)
LBL_TX = "#5B4B8A"
OVER_BG = "#F8CBAD"; OVER_TX = "#B00000"     # over-limit label (red)
UNDER_BG = "#C6E0B4"; UNDER_TX = "#375623"   # under-limit label (green)


def _pct(v, _):
    return f"{v:.0f}%"


def png_bytes(fig, dpi=150):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def combo_chart(depts, working, secondary, this_pct, prev_pct, target,
                title, secondary_label="OT Hrs", prev_label="Prev wk",
                this_label="This wk", pct_axis_max=None):
    """All %-args are already in 0–100. working/secondary are hours."""
    import numpy as np
    n = len(depts)
    x = np.arange(n)
    bw = 0.40
    fig, ax1 = plt.subplots(figsize=(13, 6))

    ax1.bar(x - bw / 2, working, bw, color=C_WORK, label="Working Hrs",
            zorder=2)
    ax1.bar(x + bw / 2, secondary, bw, color=C_SEC, label=secondary_label,
            zorder=2)
    ax1.set_ylabel("Hours", fontsize=11)
    ax1.set_xticks(x)
    ax1.set_xticklabels(depts, fontsize=9.5)
    hmax = max(list(working) + list(secondary) + [1])
    ax1.set_ylim(0, hmax * 1.18)
    ax1.grid(axis="y", color="#E6E6E6", lw=0.8, zorder=0)
    ax1.set_axisbelow(True)

    ax2 = ax1.twinx()
    if prev_pct is not None:
        ax2.plot(x, prev_pct, color=C_PREV, lw=2.6, marker="o", ms=5.5,
                 label=f"{prev_label}", zorder=3)
    ax2.plot(x, this_pct, color=C_THIS, lw=2.8, marker="o", ms=6,
             label=f"{this_label}", zorder=4)
    ax2.axhline(target, color=C_TARGET, ls="--", lw=2.0, label="Target",
                zorder=2)
    for xi, yi in zip(x, this_pct):
        ax2.annotate(f"{yi:.1f}%", (xi, yi), textcoords="offset points",
                     xytext=(0, 13), ha="center", fontsize=8.5,
                     color=LBL_TX, zorder=5,
                     bbox=dict(boxstyle="round,pad=0.28", fc=LBL_BG,
                               ec="none"))
    pmax = pct_axis_max or (max(list(this_pct) +
                                (list(prev_pct) if prev_pct else []) +
                                [target]) * 1.35 + 1)
    ax2.set_ylim(0, pmax)
    ax2.set_ylabel("%", fontsize=11)
    ax2.yaxis.set_major_formatter(FuncFormatter(_pct))

    ax1.set_title(title, fontsize=16, fontweight="bold", pad=14)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc="lower center", ncol=5, frameon=False,
               fontsize=10.5, bbox_to_anchor=(0.5, -0.03))
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    return fig


def per_org_grid(weeks, dept_series, target, title, ncols=3):
    """dept_series: {dept: [pct,...]} aligned to weeks; target & pct in 0–100."""
    import numpy as np
    depts = list(dept_series.keys())
    n = len(depts)
    if n == 0:
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.axis("off")
        ax.text(0.5, 0.5, "no data", ha="center", va="center")
        return fig
    ncols = min(ncols, n)
    nrows = math.ceil(n / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 4.3, nrows * 2.7),
                             squeeze=False)
    x = np.arange(len(weeks))
    for i, dept in enumerate(depts):
        ax = axes[i // ncols][i % ncols]
        ys = dept_series[dept]
        ax.plot(x, ys, color=C_SEC, lw=2.6, marker="o", ms=5.5, zorder=3)
        ax.axhline(target, color=C_TARGET, ls="--", lw=1.4, zorder=1)
        ax.set_title(dept, fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(weeks, fontsize=8.5)
        ax.set_ylim(0, max(list(ys) + [target]) * 1.5 + 1)
        ax.yaxis.set_major_formatter(FuncFormatter(_pct))
        ax.grid(axis="y", color="#EEEEEE", lw=0.7, zorder=0)
        ax.set_axisbelow(True)
        for xi, yi in zip(x, ys):
            over = yi > target
            ax.annotate(f"{yi:.1f}%", (xi, yi), textcoords="offset points",
                        xytext=(0, 11), ha="center", fontsize=8.5,
                        color=OVER_TX if over else UNDER_TX, zorder=4,
                        bbox=dict(boxstyle="round,pad=0.26",
                                  fc=OVER_BG if over else UNDER_BG, ec="none"))
    for j in range(n, nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")
    fig.suptitle(title, fontsize=16, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return fig
