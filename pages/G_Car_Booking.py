# pages/G_Car_Booking.py — Company Car Booking (re-platformed from the
# AMS Car Booking project onto this HRM). Public booking page (form + map);
# approvals only for approvers; the admin CONSOLE (Dispatch / Costing &
# cost-centre allocation / Fleet / Settings) is visible ONLY to car.admin.
import datetime as dt
import streamlit as st
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
import streamlit.components.v1 as components
from lib import theme as _theme
from lib.auth import require_capability, current_user, has_capability
from lib import employee_db as edb
from lib import approval_db as adb
from lib import car_db
from lib import notify

_theme.inject()
require_capability("car.book")

user = current_user(); me = user["username"]
rec = edb.get_record(emp_no=str(user.get("emp_no") or "")) or {}

_theme.header("จองรถบริษัท", "Company Car Booking",
              "จองรถส่วนกลาง • แผนที่เส้นทาง • อนุมัติ • จ่ายงานคนขับ "
              "พร้อมคิดค่าน้ำมันและปันส่วนตาม cost centre")

LOCS = list(car_db.KNOWN_LOCATIONS.keys())

import re as _re
import math as _math
import json as _json

def _parse_coords(text):
    """Parse 'lat,lng' or extract coords from a Google Maps link."""
    if not text:
        return None
    m = _re.search(r'(-?\d{1,2}\.\d{3,})\s*,\s*(-?\d{1,3}\.\d{3,})', text)
    if m:
        try:
            return (float(m.group(1)), float(m.group(2)))
        except Exception:
            return None
    return None

def _haversine(a, b):
    R = 6371.0
    la1, lo1, la2, lo2 = map(_math.radians, [a[0], a[1], b[0], b[1]])
    dla, dlo = la2 - la1, lo2 - lo1
    h = _math.sin(dla / 2) ** 2 + _math.cos(la1) * _math.cos(la2) * _math.sin(dlo / 2) ** 2
    return 2 * R * _math.asin(min(1, _math.sqrt(h)))

def _loc_input(label, key, placeholder=False):
    """Returns (label_text, coords_or_None). Known location OR typed/pasted
    address + coordinates / Google Maps link."""
    opts = (["— เลือก / choose —"] if placeholder else []) + LOCS + \
           ["📍 พิมพ์/วางเอง · type / paste"]
    sel = st.selectbox(label, opts, key=key + "_sel")
    if sel.startswith("📍"):
        name = st.text_input(f"ชื่อสถานที่ · place name ({label})", key=key + "_nm",
                             placeholder="เช่น โรงพยาบาลกรุงเทพระยอง / customer site")
        paste = st.text_input(
            f"วางพิกัด หรือ ลิงก์ Google Maps · paste lat,lng or a Maps link ({label})",
            key=key + "_pc",
            placeholder="13.0292, 101.1234   หรือ   https://maps.google.com/...?q=13.0,101.1")
        co = _parse_coords(paste)
        if paste and not co:
            st.caption("⚠️ อ่านพิกัดไม่ได้ — วางเป็น lat,lng เช่น 13.0292,101.1234 "
                       "หรือเปิด Google Maps แล้วคัดลอกลิงก์ที่มีพิกัด")
        return (name.strip() or "จุดที่กำหนดเอง / Custom"), co
    if placeholder and sel.startswith("—"):
        return "", None
    return sel, car_db.KNOWN_LOCATIONS.get(sel)

_MAP_HTML = """
<div id="map" style="height:320px;border-radius:14px;overflow:hidden;
 border:1px solid #e6eaf1"></div>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
(function(){
  function go(){
    if(!window.L){return setTimeout(go,200);}
    var m=L.map('map',{zoomControl:true});
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {maxZoom:18, attribution:'OpenStreetMap'}).addTo(m);
    function mk(col){return L.divIcon({className:'',html:'<div style="width:16px;'+
      'height:16px;border-radius:50%;background:'+col+';border:3px solid #fff;'+
      'box-shadow:0 0 0 1px rgba(0,0,0,.3)"></div>'});}
    __MARKERS__
    __LINE__
    __FIT__
  }
  go();
})();
</script>
"""

def show_map(a, b, alabel, blabel):
    if not a and not b:
        st.caption("🗺️ เลือกจุดรับและปลายทาง (หรือวางพิกัด) เพื่อแสดงแผนที่ · "
                   "choose locations or paste coordinates to see the map")
        return None
    markers = ""
    if a:
        markers += (f"L.marker([{a[0]},{a[1]}],{{icon:mk('#1aa260')}})"
                    f".addTo(m).bindPopup({_json.dumps('Pickup: ' + alabel)});")
    if b:
        markers += (f"L.marker([{b[0]},{b[1]}],{{icon:mk('#E31D93')}})"
                    f".addTo(m).bindPopup({_json.dumps('Destination: ' + blabel)});")
    if a and b:
        line = (f"L.polyline([[{a[0]},{a[1]}],[{b[0]},{b[1]}]],"
                f"{{color:'#009ADE',weight:4,opacity:.85}}).addTo(m);")
        fit = f"m.fitBounds([[{a[0]},{a[1]}],[{b[0]},{b[1]}]],{{padding:[45,45]}});"
    else:
        c = a or b
        line = ""
        fit = f"m.setView([{c[0]},{c[1]}],13);"
    html = (_MAP_HTML.replace("__MARKERS__", markers)
            .replace("__LINE__", line).replace("__FIT__", fit))
    components.html(html, height=340)
    km = None
    if a and b:
        km = round(_haversine(a, b) * 2, 1)
        st.markdown(
            "<div style=\"display:flex;gap:18px;flex-wrap:wrap;background:#fff;"
            "border:1px solid #e6eaf1;border-radius:12px;padding:10px 16px;"
            "margin-top:8px;font-size:13px\">"
            f"<div>📍 <b>{alabel}</b></div><div>→</div>"
            f"<div>🏁 <b>{blabel}</b></div>"
            "<div style=\"margin-left:auto;color:#6b7c90\">ไป-กลับโดยประมาณ "
            f"<b style=\"color:#009ADE\">~{km:g} กม.</b></div></div>",
            unsafe_allow_html=True)
    return km


# ----- dynamic tabs: admin/approver sections hidden from regular staff -----
is_appr = has_capability("car.approve")
is_admin = has_capability("car.admin")
labels = ["📨 จองรถ / Book", "🧾 รายการของฉัน / My bookings"]
if is_appr:
    labels.append("✅ อนุมัติ / Approvals")
if is_admin:
    labels.append("🚦 คอนโซลผู้ดูแล / Admin console")
tabs = st.tabs(labels)
ix = {"book": 0, "mine": 1}
nxt = 2
if is_appr:
    ix["appr"] = nxt; nxt += 1
if is_admin:
    ix["admin"] = nxt; nxt += 1

# ============================================================ BOOK
with tabs[ix["book"]]:
    if not rec:
        st.warning("บัญชียังไม่ผูกรหัสพนักงาน — แจ้ง HR / Login not linked "
                   "to an Emp. No. (System Admin → Users).")
    else:
        chain = adb.resolve_chain(rec, max_levels=1)
        if chain:
            st.caption(f"ผู้อนุมัติ / Approver: "
                       f"{adb._clean_name(chain[0][1].get('emp_name_en'))}")
        c1, c2, c3 = st.columns(3)
        d = c1.date_input("วันที่เดินทาง / Trip date", dt.date.today())
        t1 = c2.time_input("เวลาออก / Start", dt.time(9, 0))
        t2 = c3.time_input("เวลากลับ / End", dt.time(17, 0))
        st.markdown("**เส้นทาง / Route** — เลือกจากรายการ หรือพิมพ์/วางพิกัด "
                    "หรือ ลิงก์ Google Maps")
        pickup, pickup_co = _loc_input("จุดรับ / Pickup", "pick")
        dest, dest_co = _loc_input("ปลายทาง / Destination", "dest",
                                   placeholder=True)
        est = show_map(pickup_co, dest_co, pickup, dest or "ปลายทาง")
        c6, c7, c8 = st.columns(3)
        km = c6.number_input("ระยะทางไป-กลับ (กม.) / Round-trip km",
                             min_value=0.0, step=5.0, value=float(est or 0.0),
                             help="คำนวณจากพิกัดอัตโนมัติ (เส้นตรง×2) — แก้ไขได้")
        pax = c7.number_input("ผู้โดยสาร / Passengers", 1, 60, 1)
        prio = c8.selectbox("ความเร่งด่วน / Priority", ["Normal", "Urgent"])
        purpose = st.text_input("วัตถุประสงค์ / Purpose *")

        if st.button("📨 ส่งคำขอจอง / Submit booking", type="primary"):
            if not dest or not purpose.strip():
                st.error("กรุณาเลือกปลายทางและกรอกวัตถุประสงค์ / destination "
                         "& purpose required")
            elif t2 <= t1:
                st.error("เวลากลับต้องหลังเวลาออก / end must be after start")
            else:
                bid, doc = car_db.create_booking(
                    rec, d, t1, t2, pickup, dest, km, purpose, prio, pax, me)
                booking = car_db.get_booking(bid)
                booking["summary"] = (f"{d} {str(t1)[:5]}-{str(t2)[:5]} "
                                      f"{pickup} → {dest}")
                booking["doc_no"] = doc
                first = adb.open_approvals("car", bid, rec,
                                           chain=chain or None)
                if first:
                    ok, msg = notify.notify_approver("car", booking, first)
                    st.success(f"✅ จองแล้ว **{doc}** → รออนุมัติ: "
                               f"{first['approver_name']} • {msg}")
                else:
                    st.success(f"✅ จองแล้ว **{doc}** — ส่งให้แอดมินจัดรถได้เลย")

# ============================================================ MY BOOKINGS
with tabs[ix["mine"]]:
    mine = car_db.list_bookings(requester_emp_no=rec.get("emp_no"))
    if not mine:
        st.caption("ยังไม่มีรายการ / none yet")
    for b in mine:
        badge = {"Request": "🟡", "pending_l1": "🟡", "approved": "🔵",
                 "Confirm": "🟢", "On Process": "🚙", "Complete": "✅",
                 "Cancel": "❌", "rejected": "❌"}.get(b["status"], "•")
        with st.container(border=True):
            st.markdown(
                f"{badge} **{b['doc_no']}** • {b['trip_date']} "
                f"{b['time_start']}-{b['time_end']}<br>"
                f"{b['pickup']} → **{b['destination']}** — สถานะ "
                f"**{b['status']}**"
                + (f"<br>🚗 {b['car_plate']} / {b['driver_name']}"
                   if b.get("car_plate") else "")
                + (f" • ค่าน้ำมัน ~{b['fuel_cost_thb']:,.0f}฿"
                   if b.get("fuel_cost_thb") else "")
                + (f" • รวม {b['total_cost_thb']:,.0f}฿"
                   if b.get("total_cost_thb") else ""),
                unsafe_allow_html=True)

# ============================================================ APPROVALS
if is_appr:
    with tabs[ix["appr"]]:
        q = adb.my_queue("car", rec.get("emp_no"))
        if not q:
            st.caption("ไม่มีรายการรออนุมัติของคุณ / nothing waiting")
        for r in q:
            with st.container(border=True):
                st.markdown(
                    f"**[L{r['my_level']}] {r['doc_no']}** — "
                    f"{r['requester_name']} ({r['department']})<br>"
                    f"{r['trip_date']} {r['time_start']}-{r['time_end']} • "
                    f"{r['pickup']} → {r['destination']} • {r['km_round']} "
                    f"กม. • {r['passengers']} คน<br>เหตุผล: {r['purpose']}",
                    unsafe_allow_html=True)
                c1, c2, c3 = st.columns([1, 1, 3])
                note = c3.text_input("Note", key=f"cn{r['approval_id']}",
                                     label_visibility="collapsed")
                if c1.button("✅ Approve", key=f"ca{r['approval_id']}"):
                    res = adb.act("car", r["approval_id"], True, me, note)
                    if res["final"]:
                        reqr = edb.get_record(emp_no=r["requester_emp_no"])
                        notify.notify_requester(
                            "car", {"summary": f"{r['doc_no']} → "
                                    f"{r['destination']}"},
                            (reqr or {}).get("personal_email"), "approved",
                            note, requester_emp_no=r["requester_emp_no"])
                    st.rerun()
                if c2.button("❌ Reject", key=f"cr{r['approval_id']}"):
                    adb.act("car", r["approval_id"], False, me, note)
                    st.rerun()

# ============================================================ ADMIN CONSOLE
if is_admin:
    with tabs[ix["admin"]]:
        a1, a2, a3, a4 = st.tabs([
            "🚦 Dispatch board", "💰 Costing & cost-centre allocation",
            "🚘 Fleet", "⚙️ Settings"])

        # -------------------- DISPATCH --------------------
        with a1:
            day = st.date_input("วันที่ / Date", dt.date.today(),
                                key="disp_day")
            cars = [c["plate"] for c in car_db.list_cars()]
            drvs = [d["name"] for d in car_db.list_drivers()]

            st.markdown("**📥 รออนุมัติแล้ว — จ่ายรถ/คนขับ / Approved, ready "
                        "to dispatch**")
            assignable = [b for b in car_db.list_bookings()
                          if b["status"] == "approved"]
            if not assignable:
                st.caption("ไม่มีรายการรอจ่ายรถ / nothing to dispatch")
            if assignable and (not cars or not drvs):
                st.warning("เพิ่มรถ/คนขับในแท็บ Fleet ก่อน / add cars & "
                           "drivers in the Fleet tab first")
            for b in assignable:
                with st.container(border=True):
                    st.markdown(f"**{b['doc_no']}** {b['trip_date']} "
                                f"{b['time_start']}-{b['time_end']} • "
                                f"{b['requester_name']} → "
                                f"{b['destination']} ({b['km_round']} กม.)")
                    free_cars = [c for c in cars if car_db.resource_free(
                        "car", c, b["trip_date"], b["time_start"],
                        b["time_end"])]
                    free_drvs = [d for d in drvs if car_db.resource_free(
                        "driver", d, b["trip_date"], b["time_start"],
                        b["time_end"])]
                    busy_c = [c for c in cars if c not in free_cars]
                    busy_d = [d for d in drvs if d not in free_drvs]
                    if busy_c or busy_d:
                        st.caption(f"⛔ ไม่ว่าง (ชนเวลา/ติดบล็อก): "
                                   f"รถ {', '.join(busy_c) or '—'} • "
                                   f"คนขับ {', '.join(busy_d) or '—'}")
                    c1, c2, c3 = st.columns([2, 2, 1])
                    if free_cars and free_drvs:
                        plate = c1.selectbox("รถว่าง", free_cars,
                                             key=f"pl{b['id']}",
                                             label_visibility="collapsed")
                        drv = c2.selectbox("คนขับว่าง", free_drvs,
                                           key=f"dr{b['id']}",
                                           label_visibility="collapsed")
                        if c3.button("🟢 Confirm", key=f"as{b['id']}"):
                            ok, msg = car_db.assign(b["id"], plate, drv, me)
                            (st.success if ok else st.error)(msg)
                            if ok:
                                st.rerun()
                    else:
                        st.error("ไม่มีรถ/คนขับว่างในช่วงเวลานี้")

            st.divider()
            st.markdown(f"**🗓️ กระดานจ่ายงาน {day} / Dispatch board "
                        f"(06:00–20:00)**")
            disp = car_db.dispatch_day(str(day))

            def _bar_row(label, trips, blocks):
                S, E = 6 * 60, 20 * 60   # 6:00–20:00 window
                span = E - S
                segs = ""
                for t in trips:
                    ts = max(car_db._mins(t["time_start"]), S)
                    te = min(car_db._mins(t["time_end"]), E)
                    if te <= ts:
                        continue
                    left = 100 * (ts - S) / span
                    w = 100 * (te - ts) / span
                    col = {"Confirm": "#1aa260", "On Process": "#009ADE",
                           "Complete": "#715091",
                           "approved": "#e8920c"}.get(t["status"], "#9aa7b8")
                    segs += (f'<div title="{t["doc_no"]} {t["time_start"]}-'
                             f'{t["time_end"]} {t["destination"]}" '
                             f'style="position:absolute;left:{left}%;'
                             f'width:{w}%;top:3px;bottom:3px;background:{col};'
                             f'border-radius:6px;color:#fff;font-size:10px;'
                             f'padding:2px 5px;overflow:hidden;'
                             f'white-space:nowrap">{t["doc_no"]}</div>')
                for bl in blocks:
                    ts = max(car_db._mins(bl["time_start"]), S)
                    te = min(car_db._mins(bl["time_end"]), E)
                    if te <= ts:
                        continue
                    left = 100 * (ts - S) / span
                    w = 100 * (te - ts) / span
                    segs += (f'<div title="{bl["reason"]}" '
                             f'style="position:absolute;left:{left}%;'
                             f'width:{w}%;top:3px;bottom:3px;'
                             f'background:repeating-linear-gradient(45deg,'
                             f'#cbd5e1,#cbd5e1 6px,#e2e8f0 6px,#e2e8f0 12px);'
                             f'border-radius:6px;font-size:10px;color:#475569;'
                             f'padding:2px 5px;overflow:hidden">🔧</div>')
                return (f'<div style="display:flex;align-items:center;gap:10px;'
                        f'margin:4px 0"><div style="width:120px;font-size:12px;'
                        f'font-weight:600;flex:none">{label}</div>'
                        f'<div style="position:relative;flex:1;height:30px;'
                        f'background:#f1f4f9;border-radius:8px">{segs}</div>'
                        f'</div>')

            rows_html = ""
            for c in disp["cars"]:
                trips = [b for b in disp["bookings"]
                         if b.get("car_plate") == c["plate"]]
                blks = [b for b in disp["blocks"]
                        if b["resource_type"] == "car"
                        and b["resource"] == c["plate"]]
                rows_html += _bar_row(f"🚗 {c['plate']}", trips, blks)
            for d_ in disp["drivers"]:
                trips = [b for b in disp["bookings"]
                         if b.get("driver_name") == d_["name"]]
                blks = [b for b in disp["blocks"]
                        if b["resource_type"] == "driver"
                        and b["resource"] == d_["name"]]
                rows_html += _bar_row(f"👨‍✈️ {d_['name'][:14]}", trips, blks)
            if rows_html:
                st.markdown(f'<div style="background:#fff;border:1px solid '
                            f'#e6eaf1;border-radius:14px;padding:14px">'
                            f'{rows_html}</div>', unsafe_allow_html=True)
            else:
                st.caption("เพิ่มรถ/คนขับเพื่อแสดงกระดาน")

            st.divider()
            st.markdown("**🚙 กำลังวิ่ง / Active trips**")
            for b in car_db.list_bookings():
                if b["status"] not in ("Confirm", "On Process"):
                    continue
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                c1.markdown(f"**{b['doc_no']}** {b['trip_date']} "
                            f"{b['time_start']} → {b['destination']} • "
                            f"{b['car_plate']}/{b['driver_name']} • "
                            f"**{b['status']}**")
                if b["status"] == "Confirm" and c2.button(
                        "🚙 On Process", key=f"op{b['id']}"):
                    car_db.set_status(b["id"], "On Process", me); st.rerun()
                if c3.button("✅ Complete", key=f"cp{b['id']}"):
                    car_db.set_status(b["id"], "Complete", me); st.rerun()
                if c4.button("❌ Cancel", key=f"cc{b['id']}"):
                    car_db.set_status(b["id"], "Cancel", me, "admin cancel")
                    st.rerun()

            with st.expander("🔧 บล็อกรถ/คนขับ (ลา/ซ่อมบำรุง) / Blocks "
                             "(leave / maintenance)"):
                for bl in car_db.list_blocks(str(day)):
                    c1, c2 = st.columns([5, 1])
                    c1.write(f"- {bl['resource_type']} **{bl['resource']}** "
                             f"{bl['time_start']}-{bl['time_end']} • "
                             f"{bl['reason']}")
                    if c2.button("ลบ", key=f"delblk{bl['id']}"):
                        car_db.delete_block(bl["id"]); st.rerun()
                with st.form("blk_add"):
                    c1, c2, c3, c4 = st.columns(4)
                    rt = c1.selectbox("ประเภท", ["car", "driver"])
                    res = c2.selectbox("ทรัพยากร", (cars if rt == "car"
                                                    else drvs) or ["—"])
                    bt1 = c3.time_input("ตั้งแต่", dt.time(8, 0))
                    bt2 = c4.time_input("ถึง", dt.time(17, 0))
                    rsn = st.text_input("เหตุผล / Reason",
                                        value="ซ่อมบำรุง / maintenance")
                    if st.form_submit_button("➕ เพิ่มบล็อก") and res != "—":
                        car_db.add_block(rt, res, str(day),
                                         str(bt1)[:5], str(bt2)[:5], rsn)
                        st.rerun()

        # -------------------- COSTING & ALLOCATION --------------------
        with a2:
            st.markdown("**💰 คิดต้นทุนเที่ยว / Cost a trip** — "
                        "litres = km ÷ km/L • fuel = litres × ฿/L • "
                        "total = fuel + tolls → ปันส่วนเข้า cost centre")
            fuel_price = float(car_db.setting("fuel_price_thb", 35) or 35)
            costable = [b for b in car_db.list_bookings()
                        if b["status"] in ("Confirm", "On Process",
                                           "Complete")]
            if not costable:
                st.caption("ยังไม่มีเที่ยวที่จ่ายรถแล้ว / no dispatched trips")
            else:
                opt = {f"{b['doc_no']} • {b['trip_date']} • "
                       f"{b['destination']} • {b.get('car_plate') or '—'}":
                       b for b in costable}
                pick = st.selectbox("เลือกเที่ยว / Trip", list(opt))
                b = opt[pick]
                car = next((c for c in car_db.list_cars(active_only=False)
                            if c["plate"] == b.get("car_plate")), {})
                code, ccname = car_db.cost_centre_for(b.get("department"))
                c1, c2, c3, c4 = st.columns(4)
                kma = c1.number_input("ระยะทางจริง km", 0.0, 5000.0,
                                      float(b.get("km_actual")
                                            or b.get("km_round") or 0))
                tolls = c2.number_input("ค่าทางด่วน ฿ / Tolls", 0.0, 9999.0,
                                        float(b.get("tolls_thb") or 0))
                bpl = c3.number_input("฿/ลิตร (as at)", 0.0, 100.0,
                                      float(b.get("baht_per_l_used")
                                            or fuel_price))
                kpl = c4.number_input("km/L (รถคันนี้)", 1.0, 40.0,
                                      float(b.get("km_per_l_used")
                                            or car.get("km_per_l") or 10))
                litres = kma / kpl if kpl else 0
                fuel = litres * bpl
                total = fuel + tolls
                st.markdown(f"""<div style="background:#f3eef7;
                  border:1px solid #e2d6ee;border-radius:12px;padding:12px 16px;
                  font-size:14px;color:#4d3566">
                  {kma:g} กม. ÷ {kpl:g} km/L = <b>{litres:.2f} L</b> ×
                  ฿{bpl:g} = <b>฿{fuel:,.2f}</b> น้ำมัน + ฿{tolls:,.0f}
                  ทางด่วน = <b style="color:#715091">฿{total:,.2f}</b> รวม →
                  cost centre <b>{code} {ccname}</b></div>""",
                            unsafe_allow_html=True)
                if st.button("💾 บันทึกต้นทุน / Save costing",
                             type="primary"):
                    r = car_db.cost_trip(b["id"], kma, tolls, bpl, kpl, me)
                    st.success(f"บันทึกแล้ว • รวม ฿{r['total']:,.2f} → "
                               f"{r['cost_centre']}")
                    st.rerun()

            st.divider()
            st.markdown("**📊 ปันส่วนตาม cost centre / Allocation by cost "
                        "centre** — ตัวเลขส่งให้ฝ่ายการเงิน")
            c1, c2 = st.columns(2)
            f_from = c1.date_input("ตั้งแต่ / From", value=None,
                                   key="alloc_from")
            f_to = c2.date_input("ถึง / To", value=None, key="alloc_to")
            rows, grand = car_db.allocation_by_cost_centre(
                str(f_from) if f_from else None,
                str(f_to) if f_to else None)
            if rows:
                st.dataframe(rows + [grand], use_container_width=True)
                import io
                from openpyxl import Workbook
                wb = Workbook(); ws = wb.active; ws.title = "Allocation"
                ws.append(list(rows[0].keys()))
                for r in rows + [grand]:
                    ws.append(list(r.values()))
                buf = io.BytesIO(); wb.save(buf)
                st.download_button("⬇️ ดาวน์โหลด Excel (ส่งการเงิน)",
                                   buf.getvalue(),
                                   file_name="Car_cost_allocation.xlsx")
            else:
                st.caption("ยังไม่มีเที่ยวที่คิดต้นทุนแล้ว / no costed trips "
                           "yet")

        # -------------------- FLEET --------------------
        with a3:
            st.markdown("**🚘 รถ / Cars**")
            for c in car_db.list_cars(active_only=False):
                st.write(f"- **{c['plate']}** {c['model'] or ''} • "
                         f"{c['seats']} ที่นั่ง • {c['km_per_l']} km/L • "
                         f"{'ใช้งาน' if c['active'] else 'ปิด'}")
            with st.form("car_add"):
                c1, c2, c3, c4 = st.columns(4)
                plate = c1.text_input("ทะเบียน / Plate")
                model = c2.text_input("รุ่น / Model")
                seats = c3.number_input("ที่นั่ง", 1, 20, 4)
                kmpl = c4.number_input("km/L", 1.0, 40.0, 10.0)
                if st.form_submit_button("💾 Save car") and plate.strip():
                    car_db.upsert_car(plate.strip(), model, seats, kmpl)
                    st.rerun()
            st.divider()
            st.markdown("**👨‍✈️ คนขับ / Drivers**")
            for d_ in car_db.list_drivers(active_only=False):
                st.write(f"- **{d_['name']}** {d_['phone'] or ''} • LINE: "
                         f"{'✅ linked' if d_['line_user_id'] else '—'}")
            with st.form("drv_add"):
                c1, c2, c3 = st.columns(3)
                nm = c1.text_input("ชื่อ / Name")
                ph = c2.text_input("โทร / Phone")
                lid = c3.text_input("LINE userId (U...)")
                if st.form_submit_button("💾 Save driver") and nm.strip():
                    car_db.upsert_driver(nm.strip(), ph, lid.strip())
                    st.rerun()

        # -------------------- SETTINGS --------------------
        with a4:
            fp = st.number_input("ราคาน้ำมัน ฿/ลิตร / Fuel price", 10.0,
                                 100.0,
                                 float(car_db.setting("fuel_price_thb", 35)
                                       or 35))
            if st.button("💾 Save fuel price"):
                car_db.set_setting("fuel_price_thb", str(fp))
                st.success("Saved")
            st.divider()
            st.markdown("**🏷️ ผัง cost centre (แผนก → รหัส) / Cost-centre "
                        "map**")
            if st.button("↻ ดึงรายชื่อแผนกจากฐานข้อมูลพนักงาน / Seed "
                         "departments from master"):
                n = car_db.seed_cost_centres_from_master()
                st.success(f"เพิ่ม {n} แผนก"); st.rerun()
            for cc in car_db.list_cost_centres():
                c1, c2, c3 = st.columns([3, 1, 2])
                c1.write(cc["department"])
                code = c2.text_input("รหัส", value=cc["code"] or "",
                                     key=f"ccc{cc['department']}",
                                     label_visibility="collapsed")
                nm = c3.text_input("ชื่อ cost centre", value=cc["name"] or "",
                                   key=f"ccn{cc['department']}",
                                   label_visibility="collapsed")
                if c3.button("💾", key=f"ccs{cc['department']}"):
                    car_db.upsert_cost_centre(cc["department"], code, nm)
                    st.rerun()
