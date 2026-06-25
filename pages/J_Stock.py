# pages/J_Stock.py — Stationery stock & issue (§4)
# Admin buys fast-movers INTO STOCK; departments draw instantly:
# request -> L1 approve -> admin hands over -> cost charged to dept.
import datetime as dt
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
from lib import theme as _theme

from lib.auth import require_capability, current_user, has_capability
from lib import employee_db as edb
from lib import approval_db as adb
from lib import stock_db as sdb
from lib import notify

_theme.inject()
require_capability("stock.request")

user = current_user(); me = user["username"]
rec = edb.get_record(emp_no=str(user.get("emp_no") or "")) or {}

st.title("📦 สต๊อกเครื่องเขียน & เบิกของ / Stationery Stock & Issue")

tabs = st.tabs(["🛒 เบิกของ / Request", "🧾 ของฉัน / My requests",
                "✅ อนุมัติ / Approvals", "🏬 คลัง & จ่ายของ / Stock admin",
                "📊 รายงาน / Reports"])

# ------------------------------------------------------------------ request
with tabs[0]:
    items = sdb.list_items(in_stock_only=True)
    if not items:
        st.info("ยังไม่มีของในสต๊อก — แอดมินรับของเข้าที่แท็บ Stock admin / "
                "Stock empty — admin receives goods in Stock admin.")
    else:
        st.caption("เลือกเฉพาะของที่มีในสต๊อก — ได้รับทันทีหลังหัวหน้าอนุมัติ "
                   "ไม่ต้องรอรอบสั่งซื้อ / In-stock items only — handed over "
                   "right after L1 approval.")
        if "stock_cart" not in st.session_state:
            st.session_state.stock_cart = {}
        cart = st.session_state.stock_cart
        for it in items:
            c1, c2, c3 = st.columns([4, 1.2, 1])
            c1.write(f"**{it['description']}** "
                     f"(`{it['product_code'] or '—'}`) — คงเหลือ "
                     f"{it['on_hand']:g} {it['unit']}")
            q = c2.number_input("จำนวน", 0.0, float(it["on_hand"]),
                                float(cart.get(it["id"], 0)), step=1.0,
                                key=f"sq{it['id']}",
                                label_visibility="collapsed")
            if q > 0:
                cart[it["id"]] = q
            elif it["id"] in cart:
                del cart[it["id"]]
        purpose = st.text_input("ใช้ทำอะไร / Purpose")
        n_lines = len(cart)
        if n_lines and st.button(f"📨 ส่งคำขอเบิก {n_lines} รายการ / Submit",
                                 type="primary"):
            if not rec:
                st.error("บัญชียังไม่ผูกรหัสพนักงาน")
            else:
                lines = [{"item_id": k, "qty": v} for k, v in cart.items()]
                iid, doc = sdb.create_issue(rec, lines, purpose, me)
                chain = adb.resolve_chain(rec, max_levels=1)
                iss = sdb.get_issue(iid)
                iss["summary"] = f"{doc} • เบิก {n_lines} รายการ"
                iss["doc_no"] = doc
                first = adb.open_approvals("stock", iid, rec,
                                           chain=chain or None)
                st.session_state.stock_cart = {}
                if first:
                    notify.notify_approver("stock", iss, first)
                    st.success(f"ส่งแล้ว **{doc}** → รออนุมัติ "
                               f"{first['approver_name']}")
                else:
                    st.success(f"**{doc}** อนุมัติอัตโนมัติ — รอรับของ")
                st.rerun()

# ------------------------------------------------------------------ mine
with tabs[1]:
    for iss in sdb.list_issues(requester_emp_no=rec.get("emp_no"))[:15]:
        badge = {"submitted": "🟡", "pending_l1": "🟡", "approved": "🔵",
                 "handed_over": "✅", "rejected": "❌"}.get(iss["status"], "•")
        ls = sdb.issue_lines(iss["id"])
        st.markdown(f"{badge} **{iss['doc_no']}** — "
                    + "; ".join(f"{l['description']}×{l['qty']:g}"
                                for l in ls)
                    + f" — **{iss['status']}**")

# ------------------------------------------------------------------ approve
with tabs[2]:
    if not has_capability("stock.approve"):
        st.info("Requires stock.approve")
    else:
        q = adb.my_queue("stock", rec.get("emp_no")) if rec else []
        if not q:
            st.caption("ไม่มีรายการรออนุมัติ / nothing waiting")
        for r in q:
            ls = sdb.issue_lines(r["id"])
            st.markdown(f"**[L{r['my_level']}] {r['doc_no']}** — "
                        f"{r['requester_name']} ({r['department']})<br>"
                        + "; ".join(f"{l['description']}×{l['qty']:g}"
                                    for l in ls)
                        + f"<br>เหตุผล: {r['purpose'] or '—'}",
                        unsafe_allow_html=True)
            c1, c2, c3 = st.columns([1, 1, 3])
            note = c3.text_input("Note", key=f"sn{r['approval_id']}",
                                 label_visibility="collapsed")
            if c1.button("✅", key=f"sa{r['approval_id']}"):
                adb.act("stock", r["approval_id"], True, me, note)
                st.rerun()
            if c2.button("❌", key=f"sr{r['approval_id']}"):
                adb.act("stock", r["approval_id"], False, me, note)
                st.rerun()

# ------------------------------------------------------------------ admin
with tabs[3]:
    if not has_capability("stock.manage"):
        st.info("Requires stock.manage (admin)")
    else:
        st.subheader("จ่ายของที่อนุมัติแล้ว / Hand over approved issues")
        appr = sdb.list_issues(status="approved")
        if not appr:
            st.caption("ไม่มีรายการรอจ่าย / none waiting")
        for iss in appr:
            ls = sdb.issue_lines(iss["id"])
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{iss['doc_no']}** {iss['requester_name']} "
                     f"({iss['department']}) — "
                     + "; ".join(f"{l['description']}×{l['qty']:g}"
                                 for l in ls))
            if c2.button("🤝 จ่ายของ", key=f"ho{iss['id']}"):
                ok, msg = sdb.hand_over(iss["id"], me)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()
        st.divider()
        st.subheader("รับของเข้าสต๊อก / Receive into stock")
        st.caption("ของที่ซื้อผ่าน ERP (PO ที่ flag เข้าสต๊อก) หรือซื้อสด — "
                   "ระบบคิดต้นทุนเฉลี่ยถ่วงน้ำหนักให้")
        all_items = sdb.list_items()
        with st.form("rcv_form"):
            c1, c2, c3, c4 = st.columns([3, 1, 1.4, 1.6])
            iid_sel = c1.selectbox(
                "รายการ", [i["id"] for i in all_items],
                format_func=lambda x: next(
                    f"{i['description']} (เหลือ {i['on_hand']:g})"
                    for i in all_items if i["id"] == x)) \
                if all_items else None
            qn = c2.number_input("จำนวน", 1.0, step=1.0)
            uc = c3.number_input("ราคา/หน่วย ฿", 0.0, step=1.0)
            ref = c4.text_input("อ้างอิง (PO no.)")
            if st.form_submit_button("📥 รับเข้า") and iid_sel:
                sdb.receive(iid_sel, qn, uc, ref, me)
                st.success("รับเข้าแล้ว")
                st.rerun()
        st.subheader("เพิ่ม/แก้รายการ & นับสต๊อก / Items & count")
        with st.form("item_form"):
            c1, c2, c3, c4 = st.columns([1.4, 3, 1, 1])
            pc = c1.text_input("รหัส / Code")
            ds = c2.text_input("ชื่อรายการ / Description")
            un = c3.text_input("หน่วย", value="ชิ้น")
            ml = c4.number_input("จุดสั่งซื้อ (min)", 0.0, step=1.0)
            if st.form_submit_button("💾 Save item") and ds.strip():
                sdb.upsert_item(pc.strip(), ds.strip(), un, ml, me)
                st.rerun()
        if all_items:
            with st.form("count_form"):
                c1, c2, c3 = st.columns([3, 1.2, 1])
                cid = c1.selectbox("นับจริง / Count item",
                                   [i["id"] for i in all_items],
                                   format_func=lambda x: next(
                                       i["description"] for i in all_items
                                       if i["id"] == x))
                cq = c2.number_input("จำนวนที่นับได้", 0.0, step=1.0)
                if st.form_submit_button("⚖️ Adjust"):
                    diff = sdb.adjust(cid, cq, "physical count", me)
                    st.success(f"ปรับแล้ว {diff:+g}")
                    st.rerun()

# ------------------------------------------------------------------ reports
with tabs[4]:
    al = sdb.reorder_alerts()
    if al:
        st.error("🔔 ต่ำกว่าจุดสั่งซื้อ / Below reorder point: "
                 + "; ".join(f"{i['description']} ({i['on_hand']:g}/"
                             f"{i['min_level']:g})" for i in al))
    c1, c2 = st.columns(2)
    c1.metric("มูลค่าสต๊อกคงเหลือ / Stock value",
              f"{sdb.stock_value():,.2f} ฿")
    by_dept = sdb.issue_cost_by("department")
    by_month = sdb.issue_cost_by("month")
    by_item = sdb.issue_cost_by("item")
    if by_dept:
        c2.markdown("**ต้นทุนเบิกตามแผนก / Issue cost by department**")
        c2.bar_chart({r["key"]: r["cost_thb"] for r in by_dept})
    if by_month:
        st.markdown("**รายเดือน / By month**")
        st.bar_chart({r["key"]: r["cost_thb"] for r in by_month})
    if by_item:
        st.markdown("**ตามรายการ (fast movers) / By item**")
        st.dataframe(by_item, use_container_width=True)
    items = sdb.list_items()
    if items:
        st.markdown("**คำแนะนำสั่งซื้อ / Reorder helper** "
                    "(เฉลี่ยการเบิก 3 เดือน × lead time)")
        st.dataframe([{
            "รายการ": i["description"], "คงเหลือ": i["on_hand"],
            "Min": i["min_level"],
            "เฉลี่ยเบิก/เดือน": sdb.usage_monthly_avg(i["id"]),
            "ต้นทุนเฉลี่ย ฿": i["avg_cost"]} for i in items],
            use_container_width=True)
