# lib/orgchart_export.py
# =============================================================================
# Org-chart export engine (pure-Python; no graphviz / no html2canvas / no
# browser plug-in on the server).
#
# Three export SCOPES the user can pick:
#   - "company"      -> the whole org
#   - "unit"         -> one business unit / department
#   - "report_line"  -> ONE person's reporting line: that person + ALL of
#                       their subordinates (every level) + their ONE manager
#                       shown on top for context (e.g. pick Ekphusit ->
#                       Nicholas on top, Ekphusit, then all 114 below).
#
# Two renderers, both consume the same resolved tree:
#   - build_print_html(...)  -> a self-contained .html that mirrors the
#       interactive HRM chart (same cards / colours / connectors / vertical
#       stacking for big teams) and opens the browser print dialog so the user
#       can Save-as-PDF or print. PIXEL-FAITHFUL to the on-screen chart.
#   - render_images(...)     -> instant PNG / JPG / PDF rendered server-side
#       with matplotlib (beautiful cards, photos, colour bars, elbow
#       connectors, vertical stacking). One click, no extra steps.
# =============================================================================
import base64
import datetime as dt
import html as _html
import io

BLUE, PURPLE, MAGENTA = "#009ADE", "#715091", "#E31D93"
DEPTH_COLORS = [PURPLE, BLUE, MAGENTA, "#16a34a", "#f59e0b",
                "#ef4444", "#0ea5e9", "#8b5cf6"]
STACK_THRESHOLD = 6   # >= this many children, all leaves -> stack vertically


# ----------------------------------------------------------------- helpers
def clean(n):
    s = str(n or "")
    for t in ("Mr.", "Ms.", "Mrs.", "Miss"):
        s = s.replace(t, "")
    return " ".join(s.split())


def _key(r):
    return clean(r.get("emp_name_en")).lower()


def build_index(records):
    """records -> (by_key, children, roots). key = cleaned lower emp_name_en.
    Reporting links come from mgr_name matched to emp_name_en."""
    by_key = {}
    for r in records:
        k = _key(r)
        if k:
            by_key.setdefault(k, r)            # first record wins on dup name
    children = {k: [] for k in by_key}
    roots = []
    for k, r in by_key.items():
        mk = clean(r.get("mgr_name")).lower()
        if mk and mk in by_key and mk != k:
            children[mk].append(r)
        else:
            roots.append(r)
    sk = lambda r: (str(r.get("title") or "z"), str(r.get("emp_no") or ""))
    for k in children:
        children[k].sort(key=sk)
    roots.sort(key=lambda r: str(r.get("emp_no") or ""))
    return by_key, children, roots


def _descendants(key, children):
    out = []
    for c in children.get(key, []):
        ck = _key(c)
        out.append(ck)
        out += _descendants(ck, children)
    return out


def people_for_scope(records, scope, unit=None, focus_emp_no=None,
                     include_manager=True):
    """Resolve a scope into a render plan.

    Returns dict with:
      display_roots : [record, ...]  top nodes to draw
      child_of      : callable(key) -> [child record, ...] (already filtered)
      title         : human label for the header
      members       : [record, ...] everyone that will be drawn
      ctx_key       : key of the context manager (report_line) or None
    """
    by_key, children, roots = build_index(records)

    if scope == "company":
        title = "ทั้งบริษัท / Whole company"
        members = [by_key[k] for k in by_key]
        return dict(display_roots=roots,
                    child_of=lambda k: children.get(k, []),
                    title=title, members=members, ctx_key=None)

    if scope == "unit":
        unit = unit or "—"
        members = [r for r in records if (r.get("dept_location") or "—") == unit]
        mkeys = {_key(r) for r in members}
        u_roots = [r for r in members
                   if clean(r.get("mgr_name")).lower() not in mkeys]
        u_roots.sort(key=lambda r: str(r.get("emp_no") or ""))

        def child_of(k):
            return [c for c in children.get(k, []) if _key(c) in mkeys]
        return dict(display_roots=u_roots, child_of=child_of,
                    title=unit, members=members, ctx_key=None)

    # ---- report_line --------------------------------------------------
    foc = next((r for r in records
                if str(r.get("emp_no")) == str(focus_emp_no)), None)
    if foc is None:
        return dict(display_roots=[], child_of=lambda k: [],
                    title="—", members=[], ctx_key=None)
    fk = _key(foc)
    inc = {fk} | set(_descendants(fk, children))
    mk = clean(foc.get("mgr_name")).lower()
    ctx = by_key.get(mk) if (include_manager and mk in by_key
                             and mk not in inc) else None
    members = [by_key[k] for k in inc] + ([ctx] if ctx else [])
    fname = clean(foc.get("emp_name_en"))

    if ctx:
        # show the manager on top, but ONLY the focus branch underneath
        def child_of(k):
            if k == mk:
                return [foc]
            return [c for c in children.get(k, []) if _key(c) in inc]
        roots_out = [ctx]
        title = (f"สายบังคับบัญชาของ {fname} / {fname}'s reporting line "
                 f"(ภายใต้ / under {clean(ctx.get('emp_name_en'))})")
    else:
        def child_of(k):
            return [c for c in children.get(k, []) if _key(c) in inc]
        roots_out = [foc]
        title = f"สายบังคับบัญชาของ {fname} / {fname}'s reporting line"
    return dict(display_roots=roots_out, child_of=child_of,
                title=title, members=members, ctx_key=(mk if ctx else None))


# =============================================================================
# 1) PRINT-READY HTML  (mirrors the interactive chart; opens print dialog)
# =============================================================================
_PRINT_CSS = """
:root{--blue:#009ADE;--purple:#715091;--magenta:#E31D93;--ink:#2b2f3a;
 --ink-soft:#6b7280;--line:#cfd6e4;--card-bd:#e4e8f0;}
*{box-sizing:border-box}
body{margin:0;font-family:'Hanken Grotesk','Noto Sans Thai',Tahoma,
 'Leelawadee UI',sans-serif;color:var(--ink);background:#fff;padding:14mm 12mm}
.head{display:flex;justify-content:space-between;align-items:flex-start;
 border-bottom:3px solid var(--purple);padding-bottom:8px;margin-bottom:6px}
.brand{display:flex;gap:11px;align-items:center}
.logo{width:40px;height:40px;border-radius:11px;display:grid;place-items:center;
 color:#fff;font-weight:800;font-size:21px;flex:none;
 background:linear-gradient(135deg,var(--blue),var(--purple) 55%,var(--magenta))}
h1{font-size:18px;margin:0;font-weight:800;letter-spacing:-.01em}
.sub{font-size:11.5px;color:var(--ink-soft);margin-top:2px}
.legend{border:1px solid var(--card-bd);border-radius:9px;padding:7px 11px;
 font-size:9.5px;line-height:1.7;background:#f8fafd;min-width:215px}
.legend b{font-size:10px}.lg{display:flex;align-items:center;gap:6px}
.kbox{width:10px;height:10px;border-radius:3px;display:inline-block}
.wrap{overflow:visible}
.forest{display:flex;align-items:flex-start;gap:60px;padding:24px 6px 6px}
.tree,.tree ul,.tree li{position:relative;margin:0;padding:0;list-style:none}
.tree ul{display:flex;justify-content:center;padding-top:26px}
.tree li{display:flex;flex-direction:column;align-items:center;padding:26px 12px 0}
.tree li::before,.tree li::after{content:'';position:absolute;top:0;width:50%;
 height:26px;border-top:2px solid var(--line)}
.tree li::after{left:50%;border-left:2px solid var(--line)}
.tree li::before{right:50%;border-right:2px solid var(--line)}
.tree li:only-child::after,.tree li:only-child::before{display:none}
.tree li:only-child{padding-top:26px}
.tree li:first-child::before,.tree li:last-child::after{border:0}
.tree li:last-child::before{border-right:2px solid var(--line)}
.tree ul ul::before{content:'';position:absolute;top:0;left:50%;
 border-left:2px solid var(--line);width:0;height:26px}
/* vertical stack for big leaf teams */
.tree ul.stack{flex-direction:column;align-items:flex-start;padding-top:26px;
 padding-left:44px;gap:0}
.tree ul.stack>li{padding:0 0 12px 0;align-items:flex-start}
.tree ul.stack>li::before,.tree ul.stack>li::after{display:none}
.tree ul.stack::before{content:'';position:absolute;left:20px;top:0;bottom:24px;
 width:2px;background:var(--line)}
.tree ul.stack>li>.node::after{content:'';position:absolute;left:-24px;top:26px;
 width:24px;height:2px;background:var(--line)}
.node{position:relative;width:228px;background:#fff;border:1px solid var(--card-bd);
 border-radius:13px;box-shadow:0 1px 2px rgba(20,30,60,.07),
 0 5px 14px rgba(20,30,60,.06);padding:12px 14px;text-align:left;
 page-break-inside:avoid}
.node::before{content:'';position:absolute;left:0;top:13px;bottom:13px;width:4px;
 border-radius:4px;background:var(--blue)}
.node[data-d="0"]::before{background:var(--purple)}
.node[data-d="1"]::before{background:var(--blue)}
.node[data-d="2"]::before{background:var(--magenta)}
.node[data-d="3"]::before{background:#16a34a}
.node[data-d="4"]::before{background:#f59e0b}
.node[data-d="5"]::before{background:#ef4444}
.node.ctx{border-style:dashed;background:#fafbff}
.head2{display:flex;gap:10px;align-items:flex-start}
.avatar{width:42px;height:42px;border-radius:12px;flex:none;object-fit:cover;
 border:1px solid var(--card-bd);background:#eef1f7}
.avatar.init{display:grid;place-items:center;font-weight:800;font-size:14px;
 color:#fff;background:linear-gradient(135deg,var(--blue),var(--purple))}
.nm{font-weight:700;font-size:13.5px;line-height:1.22}
.lead{font-size:11.5px;color:var(--purple);font-weight:600;margin-top:1px}
.tag{display:inline-block;margin-top:6px;font-size:10px;font-weight:700;
 color:var(--blue);background:rgba(0,154,222,.1);padding:2px 8px;border-radius:20px}
.no{font-size:9.5px;color:var(--ink-soft);margin-top:5px}
.approve{margin-top:18px;border:1px solid var(--card-bd);border-radius:9px;
 padding:8px 13px;font-size:10.5px;display:inline-block;line-height:1.9}
.approve td{padding:1px 10px 1px 0}
.sig{display:inline-block;min-width:150px;border-bottom:1px dotted var(--ink-soft)}
.ctxnote{font-size:9px;color:var(--ink-soft);margin-top:-2px}
@media print{.noprint{display:none}@page{size:A3 landscape;margin:8mm}}
.noprint{position:fixed;top:10px;right:12px;z-index:9}
.noprint button{padding:9px 18px;border:0;border-radius:9px;color:#fff;
 font-weight:700;cursor:pointer;font-size:13px;
 background:linear-gradient(135deg,var(--blue),var(--purple))}
"""


def build_print_html(records, scope, photos=None, unit=None,
                     focus_emp_no=None, include_manager=True,
                     version="", proposed="", approved="", eff_date=None):
    """Self-contained HTML that mirrors the interactive chart and auto-opens
    the print dialog (Save-as-PDF or print)."""
    photos = photos or {}
    plan = people_for_scope(records, scope, unit, focus_emp_no, include_manager)
    child_of = plan["child_of"]

    def initials(name):
        p = clean(name).split()
        return ("".join(w[0] for w in p[:2])).upper() or "?"

    def avatar(r):
        nm = r.get("emp_name_en")
        uri = photos.get(_key(r))
        if uri:
            return f'<img class="avatar" src="{uri}" alt="">'
        return f'<div class="avatar init">{_html.escape(initials(nm))}</div>'

    def node_div(r, depth, is_ctx=False):
        nm = _html.escape(clean(r.get("emp_name_en")))
        nk = _html.escape(r.get("nickname") or "")
        ti = _html.escape(r.get("title") or "")
        tg = _html.escape(r.get("dept_location") or "")
        no = _html.escape(str(r.get("emp_no") or ""))
        cls = "node ctx" if is_ctx else "node"
        h = (f'<div class="{cls}" data-d="{min(depth,5)}"><div class="head2">'
             f'{avatar(r)}<div><div class="nm">{nm}'
             f'{f" ({nk})" if nk else ""}</div>')
        if ti:
            h += f'<div class="lead">{ti}</div>'
        h += '</div></div>'
        if tg:
            h += f'<div class="tag">{tg}</div>'
        if no:
            h += f'<div class="no">#{no}</div>'
        if is_ctx:
            h += ('<div class="ctxnote">ผู้บังคับบัญชา (เพื่อบริบท) / '
                  'manager — for context</div>')
        h += '</div>'
        return h

    def render_li(r, depth):
        is_ctx = (plan["ctx_key"] is not None and _key(r) == plan["ctx_key"])
        kids = child_of(_key(r))
        h = "<li>" + node_div(r, depth, is_ctx)
        if kids:
            leaves = [c for c in kids if not child_of(_key(c))]
            stack = (len(kids) >= STACK_THRESHOLD and len(leaves) == len(kids))
            h += (f'<ul class="stack">' if stack else "<ul>")
            h += "".join(render_li(c, depth + 1) for c in kids)
            h += "</ul>"
        return h + "</li>"

    forest = "".join(f'<div class="tree"><ul>{render_li(r, 0)}</ul></div>'
                     for r in plan["display_roots"])
    if not forest:
        forest = "<p>ไม่มีพนักงานในขอบเขตนี้ / no staff in this scope.</p>"

    ed = eff_date or dt.date.today()
    n = len(plan["members"])
    sub = _html.escape(plan["title"])
    appr = (f'<div class="approve"><table>'
            f'<tr><td>Version:</td><td><b>{_html.escape(version)}</b></td></tr>'
            f'<tr><td>Effective:</td><td>{ed:%d/%m/%Y}</td></tr>'
            f'<tr><td>Proposed by:</td><td><span class="sig">'
            f'{_html.escape(proposed)}</span></td></tr>'
            f'<tr><td>Approved by:</td><td><span class="sig">'
            f'{_html.escape(approved)}</span></td></tr></table></div>')

    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<title>AMS Org Chart — {sub}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700;800&family=Noto+Sans+Thai:wght@400;500;700&display=swap" rel="stylesheet">
<style>{_PRINT_CSS}</style></head>
<body onload="setTimeout(function(){{window.print()}},350)">
<div class="noprint"><button onclick="window.print()">🖨️ Print / Save as PDF</button></div>
<div class="head"><div class="brand"><div class="logo">A</div><div>
 <h1>ANCA Manufacturing Solutions (Thailand) — Organisation Chart</h1>
 <div class="sub">{sub} · {n} คน / people · {dt.date.today():%d/%m/%Y}</div>
</div></div>
<div class="legend"><b>สัญลักษณ์ / Legend</b>
 <div class="lg"><span class="kbox" style="background:#715091"></span>ผู้บริหาร / Exec
  &nbsp;<span class="kbox" style="background:#009ADE"></span>ผู้จัดการ / Mgr</div>
 <div class="lg"><span class="kbox" style="background:#E31D93"></span>หัวหน้า / Sup
  &nbsp;<span class="kbox" style="background:#16a34a"></span>พนักงาน / Staff</div>
 <div class="lg" style="color:#8a93a6">เส้นประ = การ์ดบริบท / dashed = context card</div>
</div></div>
<div class="wrap"><div class="forest">{forest}</div></div>
{appr}
</body></html>"""


# =============================================================================
# 2) IMAGE RENDERER  (matplotlib -> PNG / JPG / PDF, instant, server-side)
# =============================================================================
def _round_avatar(raw_bytes, px=120, radius_frac=0.28):
    """PIL: square-crop + rounded-corner alpha mask -> RGBA numpy array."""
    from PIL import Image, ImageDraw
    import numpy as np
    im = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s,
                  (h - s) // 2 + s)).resize((px, px), Image.LANCZOS)
    mask = Image.new("L", (px, px), 0)
    d = ImageDraw.Draw(mask)
    r = int(px * radius_frac)
    d.rounded_rectangle([0, 0, px - 1, px - 1], radius=r, fill=255)
    im.putalpha(mask)
    return np.asarray(im)


def _ink(hexcol):
    h = hexcol.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#11161f" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


def render_images(records, scope, photos_bytes=None, unit=None,
                  focus_emp_no=None, include_manager=True, version="",
                  fmts=("png", "jpg", "pdf")):
    """Return {fmt: bytes}. Beautiful cards, photos, colour bars, elbow
    connectors and vertical stacking for big teams. None if nothing to draw."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    from matplotlib.offsetbox import OffsetImage, AnnotationBbox
    from matplotlib import font_manager as fm
    import sys

    for fp in ("/root/.fonts/Sarabun-Regular.ttf",
               "assets/fonts/Sarabun-Regular.ttf"):
        try:
            fm.fontManager.addfont(fp)
            plt.rcParams["font.family"] = "Sarabun"
            break
        except Exception:
            pass

    photos_bytes = photos_bytes or {}
    plan = people_for_scope(records, scope, unit, focus_emp_no, include_manager)
    child_of = plan["child_of"]
    if not plan["display_roots"]:
        return None
    sys.setrecursionlimit(100000)

    # ---- geometry (data units) ----
    BW, BH = 4.0, 1.30           # card width / height
    H_GAP = 0.55                 # gap between sibling subtrees
    ROW_H = 2.35                 # vertical gap between depth levels
    INDENT_X = 1.5               # stack column indent
    STACK_ROW = 1.55             # vertical gap between stacked leaves
    FIRST_DROP = 1.95            # parent -> first stacked child drop

    pos = {}            # key -> (cx, cy)  card CENTRE
    depth_of = {}
    is_stack_parent = set()
    bottom = [0.0]

    def is_leaf(r):
        return not child_of(_key(r))

    def place(r, left_x, y, depth):
        k = _key(r)
        depth_of[k] = depth
        kids = child_of(k)
        if not kids:
            pos[k] = (left_x + BW / 2, y)
            bottom[0] = min(bottom[0], y)
            return left_x + BW
        leaves = [c for c in kids if is_leaf(c)]
        stack = (len(kids) >= STACK_THRESHOLD and len(leaves) == len(kids))
        if stack:
            is_stack_parent.add(k)
            col_left = left_x + INDENT_X
            cy = y - FIRST_DROP
            for c in kids:
                ck = _key(c)
                depth_of[ck] = depth + 1
                pos[ck] = (col_left + BW / 2, cy)
                bottom[0] = min(bottom[0], cy)
                cy -= STACK_ROW
            pos[k] = (left_x + BW / 2, y)
            return left_x + INDENT_X + BW
        cur = left_x
        centres = []
        for c in kids:
            r2 = place(c, cur, y - ROW_H, depth + 1)
            centres.append(pos[_key(c)][0])
            cur = r2 + H_GAP
        pos[k] = ((centres[0] + centres[-1]) / 2, y)
        bottom[0] = min(bottom[0], y)
        return max(cur - H_GAP, left_x + BW)

    cur = 0.0
    for root in plan["display_roots"]:
        rgt = place(root, cur, 0.0, 0)
        cur = rgt + H_GAP * 3

    xs = [p[0] for p in pos.values()]
    min_x, max_x = min(xs) - BW, max(xs) + BW
    span_x = max_x - min_x
    span_y = (0.0 - bottom[0]) + BH + 1.0

    fig_w = max(9.0, span_x * 0.42)
    fig_h = max(5.0, span_y * 0.42)
    # keep the figure within sane raster limits
    scale = min(1.0, 46.0 / fig_w, 46.0 / fig_h)
    fig_w *= scale; fig_h *= scale
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    LINE = "#aab4c8"

    # ---- connectors ----
    for k in list(pos.keys()):
        rec = plan_member(plan, k)
        if rec is None:
            continue
        kids = child_of(k)
        if not kids:
            continue
        px, py = pos[k]
        if k in is_stack_parent:
            spine_x = px - BW / 2 + 0.28
            ys = [pos[_key(c)][1] for c in kids]
            ax.plot([spine_x, spine_x], [py - BH / 2, min(ys)],
                    color=LINE, lw=1.0, zorder=1)
            for c in kids:
                cx, cy = pos[_key(c)]
                ax.plot([spine_x, cx - BW / 2], [cy, cy],
                        color=LINE, lw=1.0, zorder=1)
        else:
            childY = pos[_key(kids[0])][1]
            busY = (py - BH / 2 + childY + BH / 2) / 2
            ax.plot([px, px], [py - BH / 2, busY], color=LINE, lw=1.0, zorder=1)
            cxs = [pos[_key(c)][0] for c in kids]
            ax.plot([min(cxs), max(cxs)], [busY, busY], color=LINE,
                    lw=1.0, zorder=1)
            for c in kids:
                cx, cy = pos[_key(c)]
                ax.plot([cx, cx], [busY, cy + BH / 2], color=LINE,
                        lw=1.0, zorder=1)

    # ---- cards ----
    for k, (cx, cy) in pos.items():
        rec = plan_member(plan, k)
        if rec is None:
            continue
        d = depth_of.get(k, 0)
        bar = DEPTH_COLORS[min(d, len(DEPTH_COLORS) - 1)]
        is_ctx = (plan["ctx_key"] == k)
        # card
        ax.add_patch(FancyBboxPatch(
            (cx - BW / 2, cy - BH / 2), BW, BH,
            boxstyle="round,pad=0.015,rounding_size=0.16",
            fc="#fafbff" if is_ctx else "#ffffff",
            ec="#c9d2e3" if is_ctx else "#dbe1ec",
            lw=1.4 if is_ctx else 1.0, ls="--" if is_ctx else "-", zorder=2))
        # left colour bar
        ax.add_patch(FancyBboxPatch(
            (cx - BW / 2 + 0.07, cy - BH / 2 + 0.16), 0.13, BH - 0.32,
            boxstyle="round,pad=0,rounding_size=0.06",
            fc=bar, ec="none", zorder=3))
        # avatar
        av_cx = cx - BW / 2 + 0.62
        raw = photos_bytes.get(k)
        if raw:
            try:
                arr = _round_avatar(raw)
                ab = AnnotationBbox(OffsetImage(arr, zoom=BH * 0.30),
                                    (av_cx, cy + 0.20), frameon=False, zorder=4)
                ax.add_artist(ab)
            except Exception:
                raw = None
        if not raw:
            ax.add_patch(plt.Circle((av_cx, cy + 0.20), 0.34, fc=bar,
                                     ec="white", lw=1.2, zorder=4))
            nm = clean(rec.get("emp_name_en")).split()
            ini = ("".join(w[0] for w in nm[:2])).upper() or "?"
            ax.text(av_cx, cy + 0.20, ini, ha="center", va="center",
                    fontsize=7.5, color="#ffffff", fontweight="bold", zorder=5)
        # text
        tx = cx - BW / 2 + 1.12
        nm = clean(rec.get("emp_name_en"))
        nk = rec.get("nickname") or ""
        lab = nm + (f"  ({nk})" if nk else "")
        ax.text(tx, cy + 0.36, lab[:30], ha="left", va="center",
                fontsize=7.3, color="#1b2330", fontweight="bold", zorder=5)
        ti = (rec.get("title") or "")
        ax.text(tx, cy + 0.07, str(ti)[:34], ha="left", va="center",
                fontsize=6.2, color=PURPLE, zorder=5)
        tg = (rec.get("dept_location") or "")
        if tg:
            ax.text(tx, cy - 0.24, str(tg)[:30], ha="left", va="center",
                    fontsize=5.8, color=BLUE, zorder=5,
                    bbox=dict(boxstyle="round,pad=0.22", fc="#e8f5fd",
                              ec="none"))
        no = str(rec.get("emp_no") or "")
        if no:
            ax.text(cx + BW / 2 - 0.12, cy - BH / 2 + 0.17, f"#{no}",
                    ha="right", va="center", fontsize=5.0, color="#9aa6bd",
                    zorder=5)

    ax.set_xlim(min_x - 0.4, max_x + 0.4)
    ax.set_ylim(bottom[0] - BH, BH + 2.4)
    ax.axis("off")
    ax.set_title(
        "ANCA Manufacturing Solutions (Thailand) Ltd.  —  "
        f"{plan['title']}   ·   {version}   ·   {len(plan['members'])} people",
        fontsize=11, loc="left", pad=14, color="#26303e", fontweight="bold")

    out = {}
    for fmt in fmts:
        b = io.BytesIO()
        fig.savefig(b, format=fmt, dpi=140, bbox_inches="tight",
                    facecolor="white", pad_inches=0.25)
        out[fmt] = b.getvalue()
    plt.close(fig)
    return out


def plan_member(plan, key):
    idx = plan.get("_member_idx")
    if idx is None:
        idx = {_key(r): r for r in plan["members"]}
        plan["_member_idx"] = idx
    return idx.get(key)
