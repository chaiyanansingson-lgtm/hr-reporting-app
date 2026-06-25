# pages/H_Stationery_ERP.py
# ============================================================================
# Mini ERP — Stationery: OFFICEMATE catalog -> cart -> PO approval ->
# real OFFICEMATE order -> goods received; plus stationery reimbursement
# claims with receipt photo -> approval -> Finance pays.
# ============================================================================
import datetime as dt
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme

from lib.auth import require_capability, current_user, has_capability
from lib import employee_db as edb
from lib import erp_db
from lib import erp_mail
from lib import approval_db as adb
from lib import notify

_theme.inject()
require_capability("erp.browse")

user = current_user()
me = user["username"]
rec = edb.get_record(emp_no=str(user.get("emp_no") or "")) or {}

st.title("🛒 Stationery ERP / ระบบเครื่องเขียน OFFICEMATE")

if "erp_cart" not in st.session_state:
    st.session_state.erp_cart = []   # [{product_code, description, qty, unit_price_thb}]

tabs = st.tabs(["🔎 Catalog", "🧺 Cart & submit PO", "📑 My POs & claims",
                "✅ Approvals", "📦 Purchasing", "💸 Finance",
                "📊 Reports", "⚙️ Catalog admin"])

if "erp_emls" not in st.session_state:
    st.session_state.erp_emls = []   # [(filename, bytes, caption)]


def _submit_carts(cart, purpose):
    """Split the cart per supplier -> one PO each -> open approvals via the
    configured PO line (or Mgr chain) -> notify + build the Outlook .eml
    draft for the L1 approver."""
    prods = {p["product_code"]: p for p in erp_db.search_products(limit=100000)}
    groups = {}
    for l in cart:
        sk = (prods.get(l.get("product_code")) or {}).get("supplier_key") \
            or l.get("supplier_key") or "officemate"
        groups.setdefault(sk, []).append(l)
    results = []
    for sk, lines in groups.items():
        po_no = erp_db.create_po(rec, lines, purpose, me, supplier_key=sk)
        po = next(p for p in erp_db.list_pos() if p["po_no"] == po_no)
        chain = erp_db.resolve_po_chain(rec)
        po["summary"] = (f"{po_no} • {len(lines)} รายการ • "
                         f"{po['total_thb']:,.2f} ฿")
        first = adb.open_approvals("po", po["id"], rec, chain=chain or None)
        cap = f"**{po_no}** ({sk}) — {po['total_thb']:,.2f} ฿"
        if first:
            notify.notify_approver("po", po, first)
            eml = erp_mail.request_eml(po, lines,
                                       first.get("approver_email"),
                                       first["approver_name"],
                                       first["level"], rec)
            st.session_state.erp_emls.append(
                (f"{po_no}_approval_request.eml", eml,
                 cap + f" → L1 {first['approver_name']}"))
        results.append((po_no, sk, first))
    return results

# ---------------------------------------------------------------- catalog
with tabs[0]:
    # ---- white professional catalog: card grid LEFT + sticky cart RIGHT ----
    st.markdown("""<style>
    .erp-card{border:1px solid #E4E8F0;border-radius:14px;background:#fff;
      padding:14px;height:100%;box-shadow:0 1px 3px rgba(15,23,42,.05)}
    .erp-card img{width:100%;height:150px;object-fit:contain;background:#fff}
    .erp-name{font-weight:700;font-size:13.5px;color:#26303E;line-height:1.3;
      min-height:35px;margin-top:8px}
    .erp-meta{font-size:11px;color:#8A93A6;margin:2px 0 6px}
    .erp-code{display:inline-block;font-size:10px;font-weight:700;color:#009ADE;
      background:rgba(0,154,222,.08);padding:1px 8px;border-radius:10px}
    .erp-price{font-size:16px;font-weight:800;color:#715091}
    .cart-box{border:1px solid #E4E8F0;border-radius:14px;background:#fff;
      padding:14px;box-shadow:0 1px 3px rgba(15,23,42,.05)}
    .cart-head{font-weight:800;color:#26303E;border-bottom:2px solid #715091;
      padding-bottom:6px;margin-bottom:8px}
    </style>""", unsafe_allow_html=True)

    main, side = st.columns([3, 1.15], gap="medium")

    with main:
        c1, c2, c3, c4 = st.columns([3, 1.4, 1.4, 1.4])
        q = c1.text_input("🔎 ค้นหา / Search (code, description, brand)")
        cats = ["(ทุกหมวด · all)"] + erp_db.categories()
        cat = c2.selectbox("หมวด · Category", cats)
        grps = ["(ทุกกลุ่ม · all)"] + erp_db.catalogue_groups()
        grp = c3.selectbox("กลุ่ม · Catalogue", grps)
        brs = ["(ทุกแบรนด์ · all)"] + erp_db.brands()
        br = c4.selectbox("แบรนด์ · Brand", brs)
        prods = erp_db.search_products(
            q,
            "" if cat.startswith("(") else cat,
            "" if br.startswith("(") else br,
            "" if grp.startswith("(") else grp,
            limit=60)
        if not prods:
            st.info("ยังไม่มีสินค้าในแคตตาล็อก — Admin นำเข้าไฟล์ได้ที่แท็บ "
                    "Catalog admin / Catalog empty — import in Catalog admin.")
        # 3-wide responsive grid
        for i in range(0, len(prods), 3):
            row = st.columns(3, gap="small")
            for col, p in zip(row, prods[i:i+3]):
                with col:
                    img = erp_db.ofm_image_url(p["product_code"])
                    price = p["price_thb"]
                    col.markdown(
                        f"""<div class="erp-card">
                        <img src="{img}" onerror="this.style.opacity=.15">
                        <div class="erp-name">{p['description'] or p['product_code']}</div>
                        <div class="erp-meta"><span class="erp-code">{p['product_code']}</span>
                        {p['brand'] or ''} {p['color'] or ''} {p['capacity'] or ''}</div>
                        <div class="erp-price">{f"{price:,.2f} ฿" if price else "ราคาสอบถาม"}</div>
                        </div>""", unsafe_allow_html=True)
                    if has_capability("erp.request"):
                        qa, qb = st.columns([1, 1.4])
                        qty = qa.number_input("Qty", 1, 999, 1,
                                              key=f"q{p['product_code']}",
                                              label_visibility="collapsed")
                        if qb.button("🛒 เพิ่ม / Add",
                                     key=f"add{p['product_code']}",
                                     use_container_width=True):
                            cart = st.session_state.erp_cart
                            for l in cart:
                                if l["product_code"] == p["product_code"]:
                                    l["qty"] += qty; break
                            else:
                                cart.append({"product_code": p["product_code"],
                                             "description": p["description"],
                                             "qty": qty,
                                             "unit_price_thb": price})
                            st.rerun()

    with side:
        cart = st.session_state.erp_cart
        st.markdown('<div class="cart-head">🧺 ตะกร้า / Cart '
                    f'({sum(l["qty"] for l in cart)})</div>',
                    unsafe_allow_html=True)
        if not cart:
            st.caption("ยังว่าง — เลือกสินค้าจากด้านซ้าย / empty — add items "
                       "from the catalog")
        total = 0.0
        for i, l in enumerate(cart):
            lt = (l["unit_price_thb"] or 0) * l["qty"]
            total += lt
            a, b = st.columns([3, 1])
            a.markdown(f"<div style='font-size:12px;font-weight:600'>"
                       f"{(l['description'] or l['product_code'])[:38]}</div>"
                       f"<div style='font-size:11px;color:#8A93A6'>"
                       f"×{l['qty']} • {lt:,.2f} ฿</div>",
                       unsafe_allow_html=True)
            if b.button("✕", key=f"rm{i}"):
                cart.pop(i); st.rerun()
        if cart:
            st.markdown(f"<div style='text-align:right;font-size:16px;"
                        f"font-weight:800;color:#715091;border-top:2px solid "
                        f"#E4E8F0;padding-top:8px'>รวม {total:,.2f} ฿</div>",
                        unsafe_allow_html=True)
            purpose = st.text_input("เหตุผล / Purpose", key="side_purpose")
            if st.button("📨 ส่งคำขอสั่งซื้อ / Submit PO request",
                         type="primary", use_container_width=True):
                results = _submit_carts(cart, purpose)
                st.session_state.erp_cart = []
                for po_no, sk, first in results:
                    st.success(f"ส่งแล้ว **{po_no}** ({sk})"
                               + (f" → รออนุมัติ {first['approver_name']}"
                                  if first else " (อนุมัติอัตโนมัติ)"))
        if st.session_state.erp_emls:
            st.markdown("---")
            st.markdown("**📧 Outlook drafts** — คลิกดาวน์โหลดแล้วเปิดไฟล์ "
                        "Outlook จะเด้งพร้อมไฟล์ Excel แนบ กด Send ได้เลย")
            for i, (fn, data, cap) in enumerate(st.session_state.erp_emls):
                st.download_button(f"⬇️ {cap}", data, file_name=fn,
                                   mime="message/rfc822", key=f"eml{i}")
            if st.button("ล้างรายการ / Clear drafts", key="clr_eml"):
                st.session_state.erp_emls = []
                st.rerun()

# ---------------------------------------------------------------- cart
with tabs[1]:
    if not has_capability("erp.request"):
        st.info("Requires erp.request")
    else:
        cart = st.session_state.erp_cart
        if not cart:
            st.caption("ตะกร้าว่าง / Cart is empty — add items from the "
                       "Catalog tab, or add a free-text line below.")
        total = 0.0
        for i, l in enumerate(cart):
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.write(f"`{l['product_code'] or '—'}` {l['description']}")
            c2.write(f"×{l['qty']}")
            lt = (l["unit_price_thb"] or 0) * l["qty"]
            total += lt
            c3.write(f"{lt:,.2f} ฿" if l["unit_price_thb"] else "—")
            if c4.button("🗑️", key=f"del{i}"):
                cart.pop(i); st.rerun()
        with st.expander("➕ เพิ่มรายการนอกแคตตาล็อก / Free-text line"):
            d = st.text_input("Description")
            c1, c2 = st.columns(2)
            qy = c1.number_input("Qty", 1, 999, 1, key="ftqty")
            pr = c2.number_input("Unit price ฿ (0 = unknown)", 0.0,
                                 step=1.0, key="ftpr")
            if st.button("Add line") and d:
                cart.append({"product_code": "", "description": d,
                             "qty": qy, "unit_price_thb": pr or None})
                st.rerun()
        st.markdown(f"### รวม / Total: **{total:,.2f} ฿**")
        purpose = st.text_input("เหตุผล/แผนก / Purpose")
        if st.button("📨 Submit PO request", type="primary",
                     disabled=not cart):
            po_no = erp_db.create_po(rec, cart, purpose, me)
            st.session_state.erp_cart = []
            st.success(f"ส่งคำขอสั่งซื้อแล้ว / PO **{po_no}** submitted for "
                       f"approval.")

        st.divider()
        st.subheader("💸 เบิกคืนเงินค่าเครื่องเขียน / Stationery "
                     "reimbursement")
        if has_capability("erp.reimburse"):
            with st.form("rb_form"):
                c1, c2 = st.columns(2)
                xd = c1.date_input("วันที่ซื้อ / Expense date",
                                   dt.date.today())
                vendor = c2.text_input("ร้านค้า / Vendor",
                                       value="OfficeMate")
                items = st.text_area("รายการที่ซื้อ / Items", height=70)
                amt = st.number_input("จำนวนเงิน ฿ / Amount", 0.0, step=1.0)
                rcpt = st.file_uploader("ใบเสร็จ / Receipt (photo or PDF)",
                                        type=["jpg", "jpeg", "png", "pdf"])
                go = st.form_submit_button("Submit claim", type="primary")
            if go:
                if amt <= 0 or not items.strip():
                    st.error("กรุณาใส่รายการและจำนวนเงิน")
                else:
                    b = rcpt.read() if rcpt else None
                    mime = rcpt.type if rcpt else None
                    cn = erp_db.create_reimbursement(
                        rec, xd, vendor, items, amt, b, mime, me)
                    st.success(f"ส่งคำขอเบิกแล้ว / Claim **{cn}** submitted.")

# ---------------------------------------------------------------- my items
with tabs[2]:
    st.subheader("คำขอสั่งซื้อของฉัน / My POs")
    for po in erp_db.list_pos(requester_emp_no=rec.get("emp_no")):
        with st.expander(f"{po['po_no']} • {po['status']} • "
                         f"{(po['total_thb'] or 0):,.2f} ฿"):
            for l in erp_db.po_lines(po["id"]):
                st.write(f"- `{l['product_code'] or '—'}` "
                         f"{l['description']} ×{l['qty']}")
            if po["ofm_order_no"]:
                st.caption(f"OFFICEMATE order: {po['ofm_order_no']}")
    st.subheader("คำขอเบิกของฉัน / My claims")
    mine = erp_db.list_reimbursements(requester_emp_no=rec.get("emp_no"))
    if mine:
        st.dataframe([{"Claim": r["claim_no"], "Date": r["expense_date"],
                       "Vendor": r["vendor"],
                       "Amount ฿": r["amount_thb"], "Status": r["status"]}
                      for r in mine], use_container_width=True)

# ---------------------------------------------------------------- approvals
with tabs[3]:
    if not has_capability("erp.approve"):
        st.info("Requires erp.approve (Manager/Admin)")
    else:
        st.subheader("PO รออนุมัติของฉัน / POs at MY level")
        myq = adb.my_queue("po", rec.get("emp_no")) if rec else []
        if not myq:
            st.caption("ไม่มีรายการที่รอคุณ / nothing at your level")
        for r in myq:
            with st.container(border=True):
                st.markdown(f"**[L{r['my_level']}] {r['po_no']}** — "
                            f"{r['requester_name']} ({r['department']}) • "
                            f"{(r['total_thb'] or 0):,.2f} ฿ • "
                            f"{r['purpose'] or '—'}")
                for l in erp_db.po_lines(r["id"]):
                    st.write(f"- `{l['product_code'] or '—'}` "
                             f"{l['description']} ×{l['qty']}")
                c1, c2, c3 = st.columns([1, 1, 3])
                note = c3.text_input("Note", key=f"pon{r['approval_id']}",
                                     label_visibility="collapsed")
                if c1.button("✅", key=f"poa{r['approval_id']}"):
                    res = adb.act("po", r["approval_id"], True, me, note)
                    if res["next"]:
                        po = next(p for p in erp_db.list_pos()
                                  if p["id"] == r["id"])
                        po["summary"] = po["po_no"]
                        notify.notify_approver("po", po, res["next"])
                        eml = erp_mail.request_eml(
                            po, erp_db.po_lines(po["id"]),
                            res["next"].get("approver_email"),
                            res["next"]["approver_name"],
                            res["next"]["level"])
                        st.session_state.erp_emls.append(
                            (f"{po['po_no']}_L{res['next']['level']}.eml",
                             eml, f"{po['po_no']} → "
                             f"L{res['next']['level']}"))
                    st.rerun()
                if c2.button("❌", key=f"por{r['approval_id']}"):
                    adb.act("po", r["approval_id"], False, me, note)
                    st.rerun()
        st.divider()
        st.subheader("📎 ปิดอนุมัติด้วยหลักฐานอีเมล / Close approval with "
                     "email evidence (admin)")
        st.caption("กรณีอนุมัติกันทางอีเมล: แนบหลักฐาน (screenshot/PDF) "
                   "ระบบจะปิดทุกระดับที่ค้างและตั้งสถานะ approved")
        pend = [p for p in erp_db.list_pos()
                if str(p["status"]).startswith("pending")]
        for po in pend:
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(f"**{po['po_no']}** {po['requester_name']} • "
                     f"{po['status']}")
            ev = c2.file_uploader("หลักฐาน", type=["png", "jpg", "jpeg",
                                  "pdf"], key=f"ev{po['id']}",
                                  label_visibility="collapsed")
            if ev and c3.button("✅ ปิด", key=f"evb{po['id']}"):
                erp_db.po_attach(po["id"], "approve_evidence", ev.read(),
                                 ev.type, me)
                for a in adb.rows_for("po", po["id"]):
                    if a["status"] in ("pending", "waiting"):
                        adb.act("po", a["id"], True, me,
                                "email evidence attached")
                st.rerun()
        st.subheader("คำขอเบิกรออนุมัติ / Claims awaiting approval")
        for r in erp_db.list_reimbursements("submitted"):
            with st.container(border=True):
                st.markdown(f"**{r['claim_no']}** — {r['requester_name']} "
                            f"({r['department']}) • {r['expense_date']} "
                            f"{r['vendor']} • **{r['amount_thb']:,.2f} ฿**"
                            f"<br>{r['items_desc']}", unsafe_allow_html=True)
                b, mime = erp_db.get_receipt(r["id"])
                if b and mime and mime.startswith("image"):
                    st.image(b, width=260, caption="Receipt")
                elif b:
                    st.download_button("📎 Receipt PDF", b,
                                       file_name=f"{r['claim_no']}.pdf",
                                       key=f"rc{r['id']}")
                c1, c2, c3 = st.columns([1, 1, 3])
                note = c3.text_input("Note", key=f"rbn{r['id']}",
                                     label_visibility="collapsed")
                if c1.button("✅", key=f"rba{r['id']}"):
                    erp_db.reimburse_action(r["id"], "approve", me, note)
                    st.rerun()
                if c2.button("❌", key=f"rbr{r['id']}"):
                    erp_db.reimburse_action(r["id"], "reject", me, note)
                    st.rerun()

# ---------------------------------------------------------------- purchasing
with tabs[4]:
    if not has_capability("erp.purchase"):
        st.info("Requires erp.purchase (Admin)")
    else:
        sups = {x["supplier_key"]: x for x in
                erp_db.list_suppliers(active_only=False)}
        st.subheader("1) อนุมัติแล้ว → ส่งอีเมลหา supplier / Approved → "
                     "send to supplier")
        for po in erp_db.list_pos("approved"):
            c1, c2, c3 = st.columns([3, 1.4, 1])
            sup = sups.get(po.get("supplier_key") or "officemate", {})
            c1.markdown(f"**{po['po_no']}** {po['requester_name']} • "
                        f"{(po['total_thb'] or 0):,.2f} ฿ → "
                        f"**{sup.get('name') or po.get('supplier_key')}**")
            eml = erp_mail.supplier_eml(po, erp_db.po_lines(po["id"]),
                                        sup or {"name": "Supplier",
                                                "email": ""})
            c2.download_button("📧 Outlook draft", eml,
                               file_name=f"{po['po_no']}_RFQ.eml",
                               mime="message/rfc822", key=f"sup{po['id']}")
            if c3.button("ส่งแล้ว ✅", key=f"sent{po['id']}",
                         help="กดเมื่อกด Send ใน Outlook แล้ว"):
                erp_db.po_set_status(po["id"], "sent_to_supplier", me)
                st.rerun()
        st.subheader("2) รอใบเสนอราคา → สั่งจริง / Quotation → place order")
        for po in erp_db.list_pos("sent_to_supplier"):
            c1, c2, c3, c4 = st.columns([2.4, 1.4, 1.4, 1])
            c1.markdown(f"**{po['po_no']}** ({po.get('supplier_key')})")
            qf = c2.file_uploader("ใบเสนอราคา", type=["pdf", "png", "jpg",
                                  "jpeg"], key=f"q{po['id']}",
                                  label_visibility="collapsed")
            ono = c3.text_input("เลขออเดอร์/ใบเสนอราคา",
                                key=f"ono{po['id']}",
                                label_visibility="collapsed",
                                placeholder="Order/Quote no.")
            if c4.button("🛒 Ordered", key=f"ord{po['id']}"):
                if qf:
                    erp_db.po_attach(po["id"], "quotation", qf.read(),
                                     qf.type, me)
                erp_db.po_set_status(po["id"], "ordered", me,
                                     ofm_order_no=ono)
                st.rerun()
        st.subheader("3) รับของรายบรรทัด / Receive per line")
        for po in (erp_db.list_pos("ordered")
                   + erp_db.list_pos("partially_received")):
            with st.expander(f"{po['po_no']} ({po.get('supplier_key')}) — "
                             f"{po['status']} • order "
                             f"{po.get('ofm_order_no') or '—'}"):
                for l in erp_db.po_lines(po["id"]):
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1.4])
                    got = float(l.get("qty_received") or 0)
                    c1.write(f"`{l['product_code'] or '—'}` "
                             f"{l['description']} — สั่ง {l['qty']} • "
                             f"รับแล้ว {got:g} • "
                             f"**{l.get('line_status') or 'open'}**"
                             + (f" ({l.get('cancel_reason')})"
                                if l.get("cancel_reason") else ""))
                    if l.get("line_status") in ("open", "partial"):
                        q_in = c2.number_input("รับ", 0.0,
                                               float(l["qty"]) - got,
                                               float(l["qty"]) - got,
                                               key=f"ri{l['id']}",
                                               label_visibility="collapsed")
                        if c3.button("📦 รับ", key=f"rb{l['id']}"):
                            erp_db.receive_line(l["id"], q_in, me)
                            st.rerun()
                        if c4.button("❌ ยกเลิกแถว", key=f"cl{l['id']}"):
                            erp_db.cancel_line(
                                l["id"], "supplier ไม่มีของ/รอนานเกิน", me)
                            st.rerun()

# ---------------------------------------------------------------- finance
with tabs[5]:
    if not has_capability("erp.pay"):
        st.info("Requires erp.pay (Finance)")
    else:
        st.subheader("คำขอเบิกที่อนุมัติแล้ว รอจ่าย / Approved claims "
                     "awaiting payment")
        for r in erp_db.list_reimbursements("approved"):
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(f"**{r['claim_no']}** {r['requester_name']} • "
                        f"**{r['amount_thb']:,.2f} ฿**")
            ref = c2.text_input("Pay ref", key=f"pref{r['id']}",
                                label_visibility="collapsed",
                                placeholder="Transfer ref / payroll batch")
            if c3.button("💸 Paid", key=f"paid{r['id']}"):
                erp_db.reimburse_action(r["id"], "pay", me, pay_ref=ref)
                st.rerun()

# ---------------------------------------------------------------- reports
with tabs[6]:
    if not has_capability("erp.reports"):
        st.info("Requires erp.reports")
    else:
        ss = erp_db.spend_summary()
        c1, c2 = st.columns(2)
        if ss["month"]:
            c1.markdown("**ยอดสั่งซื้อรายเดือน / Spend by month (฿)**")
            c1.bar_chart(ss["month"])
        if ss["department"]:
            c2.markdown("**ตามแผนก / By department (฿)**")
            c2.bar_chart(ss["department"])
        if ss["supplier"]:
            st.markdown("**ตามผู้ขาย / By supplier (฿)**")
            st.bar_chart(ss["supplier"])
        st.divider()
        st.markdown("**งบประมาณ vs ใช้จริง / Budget vs actual**")
        import datetime as _dt
        yr = st.number_input("ปี / Year", 2024, 2030, _dt.date.today().year)
        bva = erp_db.budget_vs_actual(yr)
        if bva:
            st.dataframe(bva, use_container_width=True)
        if has_capability("erp.manage_catalog"):
            c1, c2, c3 = st.columns(3)
            depts = sorted({(r2.get("dept_location") or "—")
                            for r2 in edb.list_records("active")})
            bd = c1.selectbox("แผนก", depts, key="bud_dept")
            bv = c2.number_input("งบ ฿/ปี", 0.0, step=1000.0, key="bud_val")
            if c3.button("💾 Set budget"):
                erp_db.set_budget(yr, bd, bv)
                st.rerun()
        st.divider()
        st.markdown("**ค้างรับ / Ageing (sent>7d, ordered>14d = 🔴)**")
        ag = erp_db.ageing()
        if ag:
            st.dataframe([{"PO": a["po_no"], "Status": a["status"],
                           "Supplier": a["supplier"],
                           "Days": ("🔴 " if a["overdue"] else "")
                           + str(a["days"]),
                           "Total ฿": a["total_thb"]} for a in ag],
                         use_container_width=True)
        else:
            st.caption("ไม่มีรายการค้าง / nothing open")
        # Excel download of all POs
        if st.button("⬇️ ดาวน์โหลดรายงาน Excel / Download Excel report"):
            import io
            from openpyxl import Workbook
            wb = Workbook(); ws = wb.active; ws.title = "POs"
            cols = ["po_no", "created_at", "status", "supplier_key",
                    "requester_emp_no", "requester_name", "department",
                    "purpose", "total_thb", "ofm_order_no"]
            ws.append(cols)
            for p in erp_db.list_pos():
                ws.append([p.get(c) for c in cols])
            buf = io.BytesIO(); wb.save(buf)
            st.download_button("📥 ERP_report.xlsx", buf.getvalue(),
                               file_name="ERP_report.xlsx", key="erp_xls")

# ---------------------------------------------------------------- catalog admin
with tabs[7]:
    if not has_capability("erp.manage_catalog"):
        st.info("Requires erp.manage_catalog (Admin)")
    else:
        st.caption("นำเข้าไฟล์ master จากโปรเจกต์สกัดแคตตาล็อก OfficeMate "
                   "(CSV/XLSX, คอลัมน์ตาม schema ที่ตกลงกัน) / Import the "
                   "extraction master file. Upsert by product_code, so "
                   "re-importing after each extraction session just adds "
                   "the new rows.")
        up = st.file_uploader("Catalog file", type=["csv", "xlsx"])
        if up and st.button("Import", type="primary"):
            try:
                s = erp_db.import_catalog(up.read(), up.name, me)
                st.success(f"Created {s['created']}, updated "
                           f"{s['updated']} products.")
            except Exception as e:
                st.error(f"Import failed: {e}")
        st.caption("รูปสินค้า retail ใช้ URL อัตโนมัติจาก CDN ของ OFM "
                   "(รหัสสินค้า = ชื่อไฟล์รูป) จึงไม่ต้องอัปโหลดรูปเอง")
        st.divider()
        st.subheader("🏪 ผู้ขาย / Suppliers (Makro, Lotus's, HardwareHouse "
                     "พร้อมเพิ่มได้)")
        for sp in erp_db.list_suppliers(active_only=False):
            st.write(f"- **{sp['name']}** (`{sp['supplier_key']}`) • "
                     f"{sp['email'] or 'ไม่มีอีเมล'} • lead "
                     f"{sp['lead_time_days']} วัน")
        with st.form("sup_form"):
            c1, c2, c3, c4 = st.columns(4)
            sk = c1.text_input("key (a-z)", placeholder="makro")
            nm = c2.text_input("ชื่อ / Name", placeholder="Makro")
            em = c3.text_input("อีเมล / Email")
            ld = c4.number_input("Lead (วัน)", 1, 60, 7)
            saved_sup = st.form_submit_button("💾 Save supplier")
        if saved_sup:
            if not sk.strip() or not nm.strip():
                st.error("⛔ กรอก key และชื่อผู้ขายก่อน — 'makro/Makro' "
                         "เป็นเพียงตัวอย่าง / supplier key & name are "
                         "required ('makro'/'Makro' are only placeholders)")
            else:
                try:
                    erp_db.upsert_supplier(sk.strip().lower(), nm.strip(),
                                           em, lead_time_days=ld)
                    st.success(f"✅ บันทึกผู้ขายแล้ว / Saved: "
                               f"{sk.strip().lower()}")
                    st.rerun()
                except Exception:
                    st.error("⛔ บันทึกไม่สำเร็จ — key อาจซ้ำ / could not "
                             "save — key may already exist")
        st.divider()
        if has_capability("erp.config_lines"):
            st.subheader("🧭 สายอนุมัติสั่งซื้อ / PO approval lines "
                         "(≤3 ระดับ ต่อพนักงาน)")
            st.caption("ถ้าไม่ตั้ง ระบบใช้สายบังคับบัญชาจากคอลัมน์ Mgr "
                       "อัตโนมัติ / Falls back to the Mgr-column chain.")
            c1, c2, c3, c4, c5 = st.columns(5)
            t_emp = c1.text_input("Emp No.", key="al_emp")
            t_l1 = c2.text_input("L1 Emp No.", key="al_l1")
            t_l2 = c3.text_input("L2 Emp No.", key="al_l2")
            t_l3 = c4.text_input("L3 Emp No.", key="al_l3")
            if c5.button("💾 Save line") and t_emp.strip():
                erp_db.set_approval_line(t_emp.strip(), t_l1.strip(),
                                         t_l2.strip(), t_l3.strip())
                st.success("Saved")
            up_al = st.file_uploader(
                "Bulk upload (Excel/CSV: Emp No., L1, L2, L3)",
                type=["xlsx", "csv"], key="al_up")
            if up_al and st.button("🚀 Import lines"):
                n = erp_db.import_approval_lines(up_al.read(), me)
                st.success(f"นำเข้า {n} สาย / imported")
