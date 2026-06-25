# lib/car_db.py
# ============================================================================
# CAR BOOKING — fully native (§9), replacing the Apps Script + Jira hub.
# Flow:  Staff books -> L1 approval (unified engine, kind="car")
#        -> Admin assigns car + driver (30-min-buffer conflict check)
#        -> status Confirm + LINE push to driver (job + fuel estimate)
#        -> On Process -> Complete / Cancel        (your status names kept)
# Fuel price lives in car_settings; km/L lives per car — both editable in
# the admin tab, never in code (your standing requirement).
# ============================================================================
import datetime as dt

from lib.db import get_conn, IS_POSTGRES, PH
from lib import employee_db as edb

SERIAL = "SERIAL PRIMARY KEY" if IS_POSTGRES else \
         "INTEGER PRIMARY KEY AUTOINCREMENT"

BUFFER_MIN = 30
STATUSES = ["Request", "Confirm", "On Process", "Complete", "Cancel"]


def _ts():
    return dt.datetime.now().isoformat(timespec="seconds")


def migrate():
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS cars (
        id {SERIAL}, plate TEXT UNIQUE NOT NULL, model TEXT,
        seats INTEGER DEFAULT 4, km_per_l REAL DEFAULT 10,
        active INTEGER NOT NULL DEFAULT 1)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS drivers (
        id {SERIAL}, name TEXT UNIQUE NOT NULL, phone TEXT,
        line_user_id TEXT, active INTEGER NOT NULL DEFAULT 1)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS car_settings (
        key TEXT PRIMARY KEY, value TEXT)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS car_bookings (
        id {SERIAL},
        doc_no TEXT UNIQUE,
        requester_emp_no TEXT, requester_name TEXT, department TEXT,
        trip_date TEXT NOT NULL, time_start TEXT NOT NULL,
        time_end TEXT NOT NULL,
        pickup TEXT, destination TEXT, km_round REAL,
        purpose TEXT, priority TEXT DEFAULT 'Normal',
        passengers INTEGER DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'Request',
        approver TEXT, approved_at TEXT, approve_note TEXT,
        car_plate TEXT, driver_name TEXT, fuel_cost_thb REAL,
        created_by TEXT, created_at TEXT,
        completed_at TEXT, cancel_reason TEXT)""")
    # defaults
    ig = "ON CONFLICT (key) DO NOTHING" if IS_POSTGRES else "OR IGNORE"
    if IS_POSTGRES:
        cur.execute("INSERT INTO car_settings (key, value) VALUES "
                    "('fuel_price_thb','35') ON CONFLICT (key) DO NOTHING")
    else:
        cur.execute("INSERT OR IGNORE INTO car_settings (key, value) "
                    "VALUES ('fuel_price_thb','35')")
    # --- costing layer (manual: km/tolls -> fuel -> total -> cost centre) ---
    for ddl in (
        "ALTER TABLE car_bookings ADD COLUMN km_actual REAL",
        "ALTER TABLE car_bookings ADD COLUMN tolls_thb REAL",
        "ALTER TABLE car_bookings ADD COLUMN total_cost_thb REAL",
        "ALTER TABLE car_bookings ADD COLUMN cost_centre TEXT",
        "ALTER TABLE car_bookings ADD COLUMN baht_per_l_used REAL",
        "ALTER TABLE car_bookings ADD COLUMN km_per_l_used REAL",
    ):
        try:
            cur.execute(ddl); conn.commit()
        except Exception:
            conn.rollback() if IS_POSTGRES else None
    cur.execute(f"""CREATE TABLE IF NOT EXISTS car_cost_centres (
        department TEXT PRIMARY KEY, code TEXT, name TEXT)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS car_blocks (
        id {SERIAL}, resource_type TEXT, resource TEXT,
        block_date TEXT, time_start TEXT, time_end TEXT, reason TEXT)""")
    conn.commit()


# ---------------------------------------------------------------- settings
def setting(key, fallback=None):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT value FROM car_settings WHERE key={PH}", (key,))
    r = cur.fetchone()
    return r[0] if r else fallback


def set_setting(key, value):
    conn = get_conn(); cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("""INSERT INTO car_settings (key, value)
                       VALUES (%s,%s) ON CONFLICT (key)
                       DO UPDATE SET value=EXCLUDED.value""", (key, value))
    else:
        cur.execute("INSERT OR REPLACE INTO car_settings (key, value) "
                    "VALUES (?,?)", (key, value))
    conn.commit()


# ---------------------------------------------------------------- fleet
def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) if IS_POSTGRES else dict(r)
            for r in cur.fetchall()]


def list_cars(active_only=True):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM cars" +
                (" WHERE active=1" if active_only else "") +
                " ORDER BY plate")
    return _rows(cur)


def upsert_car(plate, model, seats, km_per_l, active=1):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT id FROM cars WHERE plate={PH}", (plate,))
    if cur.fetchone():
        cur.execute(f"""UPDATE cars SET model={PH}, seats={PH},
                        km_per_l={PH}, active={PH} WHERE plate={PH}""",
                    (model, seats, km_per_l, active, plate))
    else:
        cur.execute(f"""INSERT INTO cars (plate, model, seats, km_per_l,
                        active) VALUES ({PH},{PH},{PH},{PH},{PH})""",
                    (plate, model, seats, km_per_l, active))
    conn.commit()


def list_drivers(active_only=True):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM drivers" +
                (" WHERE active=1" if active_only else "") +
                " ORDER BY name")
    return _rows(cur)


def upsert_driver(name, phone, line_user_id, active=1):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT id FROM drivers WHERE name={PH}", (name,))
    if cur.fetchone():
        cur.execute(f"""UPDATE drivers SET phone={PH}, line_user_id={PH},
                        active={PH} WHERE name={PH}""",
                    (phone, line_user_id, active, name))
    else:
        cur.execute(f"""INSERT INTO drivers (name, phone, line_user_id,
                        active) VALUES ({PH},{PH},{PH},{PH})""",
                    (name, phone, line_user_id, active))
    conn.commit()


# ---------------------------------------------------------------- bookings
def _next_doc():
    conn = get_conn(); cur = conn.cursor()
    ym = dt.date.today().strftime("%y%m")
    cur.execute(f"SELECT COUNT(*) FROM car_bookings WHERE doc_no LIKE {PH}",
                (f"CAR-{ym}-%",))
    return f"CAR-{ym}-{cur.fetchone()[0] + 1:03d}"


def create_booking(requester, trip_date, t_start, t_end, pickup, dest,
                   km_round, purpose, priority, passengers, actor):
    conn = get_conn(); cur = conn.cursor()
    doc = _next_doc()
    cur.execute(
        f"""INSERT INTO car_bookings (doc_no, requester_emp_no,
            requester_name, department, trip_date, time_start, time_end,
            pickup, destination, km_round, purpose, priority, passengers,
            status, created_by, created_at)
            VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},
            {PH},{PH},'Request',{PH},{PH})""",
        (doc, requester.get("emp_no"), requester.get("emp_name_en"),
         requester.get("dept_location"), str(trip_date), str(t_start)[:5],
         str(t_end)[:5], pickup, dest, km_round, purpose, priority,
         passengers, actor, _ts()))
    if IS_POSTGRES:
        cur.execute("SELECT id FROM car_bookings WHERE doc_no=%s", (doc,))
        bid = cur.fetchone()[0]
    else:
        bid = cur.lastrowid
    conn.commit()
    edb._audit(conn, actor, "car_booking_create",
               detail={"doc_no": doc, "date": str(trip_date), "dest": dest})
    conn.commit()
    return bid, doc


def get_booking(booking_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM car_bookings WHERE id={PH}", (booking_id,))
    r = cur.fetchone()
    if not r:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r)) if IS_POSTGRES else dict(r)


def list_bookings(status=None, date=None, requester_emp_no=None, limit=200):
    conn = get_conn(); cur = conn.cursor()
    sql = "SELECT * FROM car_bookings WHERE 1=1"
    args = []
    if status:
        sql += f" AND status={PH}"; args.append(status)
    if date:
        sql += f" AND trip_date={PH}"; args.append(str(date))
    if requester_emp_no:
        sql += f" AND requester_emp_no={PH}"
        args.append(str(requester_emp_no))
    sql += f" ORDER BY trip_date DESC, time_start LIMIT {int(limit)}"
    cur.execute(sql, args)
    return _rows(cur)


def _mins(hhmm):
    h, m = str(hhmm)[:5].split(":")
    return int(h) * 60 + int(m)


def conflicts(trip_date, t_start, t_end, car_plate=None, driver_name=None,
              exclude_id=None):
    """Bookings overlapping (+/- BUFFER_MIN) on the same car or driver,
    in active statuses."""
    out = []
    s = _mins(t_start) - BUFFER_MIN
    e = _mins(t_end) + BUFFER_MIN
    for b in list_bookings(date=str(trip_date)):
        if b["status"] in ("Complete", "Cancel", "rejected"):
            continue
        if exclude_id and b["id"] == exclude_id:
            continue
        same_car = car_plate and b.get("car_plate") == car_plate
        same_drv = driver_name and b.get("driver_name") == driver_name
        if not (same_car or same_drv):
            continue
        bs, be = _mins(b["time_start"]), _mins(b["time_end"])
        if bs < e and be > s:
            out.append(b)
    return out


def fuel_estimate(km_round, car_plate):
    price = float(setting("fuel_price_thb", 35) or 35)
    kmpl = 10.0
    for c in list_cars(active_only=False):
        if c["plate"] == car_plate:
            kmpl = float(c.get("km_per_l") or 10)
            break
    return round((float(km_round or 0) / max(kmpl, 0.1)) * price, 0)


def assign(booking_id, car_plate, driver_name, actor):
    """Admin assigns car + driver -> status Confirm + LINE to driver.
    Returns (ok, message)."""
    b = get_booking(booking_id)
    if not b:
        return False, "booking not found"
    cf = conflicts(b["trip_date"], b["time_start"], b["time_end"],
                   car_plate, driver_name, exclude_id=booking_id)
    if cf:
        return False, ("ชน/ทับเวลา (รวม buffer 30 นาที) กับ " +
                       ", ".join(c["doc_no"] for c in cf))
    fuel = fuel_estimate(b.get("km_round"), car_plate)
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""UPDATE car_bookings SET status='Confirm',
                    car_plate={PH}, driver_name={PH}, fuel_cost_thb={PH}
                    WHERE id={PH}""",
                (car_plate, driver_name, fuel, booking_id))
    conn.commit()
    edb._audit(conn, actor, "car_booking_assign",
               detail={"doc_no": b["doc_no"], "car": car_plate,
                       "driver": driver_name, "fuel_thb": fuel})
    conn.commit()
    # LINE push to driver
    from lib import notify
    drv = next((d for d in list_drivers(False) if d["name"] == driver_name),
               None)
    msg = (f"🚗 งานใหม่ (Confirm) {b['doc_no']}\n"
           f"{b['trip_date']} {b['time_start']}-{b['time_end']}\n"
           f"{b['pickup']} → {b['destination']}\n"
           f"ผู้จอง: {b['requester_name']} ({b['requester_emp_no']})\n"
           f"รถ: {car_plate} • ระยะทางรวม ~{b.get('km_round') or '-'} กม. "
           f"• น้ำมันประมาณ {fuel:,.0f} บาท")
    ok, m = notify.line_push((drv or {}).get("line_user_id"), msg)
    return True, f"Confirm แล้ว • LINE: {m}"


def set_status(booking_id, status, actor, cancel_reason=""):
    conn = get_conn(); cur = conn.cursor()
    extra = ""
    args = [status]
    if status == "Complete":
        extra = f", completed_at={PH}"
        args.append(_ts())
    if status == "Cancel":
        extra = f", cancel_reason={PH}"
        args.append(cancel_reason)
    args.append(booking_id)
    cur.execute(f"UPDATE car_bookings SET status={PH}{extra} WHERE id={PH}",
                args)
    conn.commit()
    edb._audit(conn, actor, f"car_booking_{status.lower().replace(' ', '_')}",
               detail={"booking_id": booking_id, "reason": cancel_reason})
    conn.commit()


def monthly_report(year_month):
    """[{car, trips, km, fuel}] for 'YYYY-MM' + by-department rows."""
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT car_plate, COUNT(*) AS trips,
                    SUM(km_round) AS km, SUM(fuel_cost_thb) AS fuel
                    FROM car_bookings
                    WHERE trip_date LIKE {PH} AND status='Complete'
                    GROUP BY car_plate""", (f"{year_month}%",))
    by_car = _rows(cur)
    cur.execute(f"""SELECT department, COUNT(*) AS trips,
                    SUM(km_round) AS km, SUM(fuel_cost_thb) AS fuel
                    FROM car_bookings
                    WHERE trip_date LIKE {PH} AND status='Complete'
                    GROUP BY department""", (f"{year_month}%",))
    by_dept = _rows(cur)
    return by_car, by_dept


# ==================================================== COSTING & ALLOCATION
# Known locations for the booking map (lat,lng) — AMS Rayong region.
KNOWN_LOCATIONS = {
    "AMS Pluak Daeng (โรงงาน)": (13.0758, 101.2030),
    "Map Ta Phut Industrial Estate": (12.6807, 101.1450),
    "U-Tapao Airport (สนามบินอู่ตะเภา)": (12.6799, 101.0050),
    "Suvarnabhumi Airport (สุวรรณภูมิ)": (13.6900, 100.7501),
    "Eastern Seaboard Industrial Estate (ESIE)": (13.0030, 101.1180),
    "Amata City Rayong": (13.0470, 101.1230),
    "Laem Chabang Port (ท่าเรือแหลมฉบัง)": (13.0833, 100.8833),
    "Rayong City (ตัวเมืองระยอง)": (12.6810, 101.2570),
    "Pattaya (พัทยา)": (12.9236, 100.8825),
    "Bangkok (กรุงเทพฯ)": (13.7563, 100.5018),
}


def _haversine_km(a, b):
    import math
    R = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = (math.sin((la2 - la1) / 2) ** 2 +
         math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


def distance_km(pickup, dest):
    """Round-trip straight-line estimate between two known locations."""
    a, b = KNOWN_LOCATIONS.get(pickup), KNOWN_LOCATIONS.get(dest)
    if not a or not b:
        return None
    return round(_haversine_km(a, b) * 2 * 1.25, 1)   # ×2 round + 25% roads


# ---------------------------------------------------------------- cost ctrs
def list_cost_centres():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT department, code, name FROM car_cost_centres "
                "ORDER BY department")
    return [{"department": r[0], "code": r[1], "name": r[2]}
            for r in cur.fetchall()]


def upsert_cost_centre(department, code, name):
    conn = get_conn(); cur = conn.cursor()
    if IS_POSTGRES:
        cur.execute("""INSERT INTO car_cost_centres (department, code, name)
                       VALUES (%s,%s,%s) ON CONFLICT (department)
                       DO UPDATE SET code=EXCLUDED.code,
                       name=EXCLUDED.name""", (department, code, name))
    else:
        cur.execute("INSERT OR REPLACE INTO car_cost_centres "
                    "(department, code, name) VALUES (?,?,?)",
                    (department, code, name))
    conn.commit()


def cost_centre_for(department):
    """(code, name) for a department, or ('', department) if unmapped."""
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""SELECT code, name FROM car_cost_centres
                    WHERE department={PH}""", (department or "",))
    r = cur.fetchone()
    return (r[0], r[1]) if r else ("", department or "—")


def seed_cost_centres_from_master():
    """Create one row per department seen in the employee master."""
    from lib import employee_db as edb
    seen = sorted({(r.get("dept_location") or "").strip()
                   for r in edb.list_records("active")
                   if (r.get("dept_location") or "").strip()})
    existing = {c["department"] for c in list_cost_centres()}
    n = 0
    for d in seen:
        if d not in existing:
            upsert_cost_centre(d, "", d); n += 1
    return n


# ---------------------------------------------------------------- costing
def cost_trip(booking_id, km_actual, tolls, baht_per_l, km_per_l, actor):
    """The one-line formula from the manual:
       litres = km / km_per_l ; fuel = litres × ฿/L ; total = fuel + tolls
       → allocated to the department's cost centre. Writes to the booking."""
    km_actual = float(km_actual or 0); tolls = float(tolls or 0)
    baht_per_l = float(baht_per_l or 0); km_per_l = float(km_per_l or 1)
    litres = (km_actual / km_per_l) if km_per_l else 0
    fuel = litres * baht_per_l
    total = fuel + tolls
    b = get_booking(booking_id)
    code, name = cost_centre_for((b or {}).get("department"))
    cc = f"{code} {name}".strip()
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""UPDATE car_bookings SET km_actual={PH}, tolls_thb={PH},
                    baht_per_l_used={PH}, km_per_l_used={PH},
                    fuel_cost_thb={PH}, total_cost_thb={PH}, cost_centre={PH}
                    WHERE id={PH}""",
                (km_actual, tolls, baht_per_l, km_per_l, round(fuel, 2),
                 round(total, 2), cc, booking_id))
    conn.commit()
    edb_audit(actor, "car_cost_trip", booking_id,
              {"km": km_actual, "fuel": round(fuel, 2),
               "total": round(total, 2), "cc": cc})
    return {"litres": round(litres, 2), "fuel": round(fuel, 2),
            "total": round(total, 2), "cost_centre": cc}


def edb_audit(actor, action, ref, detail):
    try:
        from lib import employee_db as edb
        conn = get_conn()
        edb._audit(conn, actor, action, detail=detail)
        conn.commit()
    except Exception:
        pass


def allocation_by_cost_centre(date_from=None, date_to=None):
    """Group every costed trip by cost centre: trips, km, litres, fuel,
    tolls, total — the number you hand Finance. Returns (rows, grand)."""
    conn = get_conn(); cur = conn.cursor()
    q = ("SELECT cost_centre, km_actual, km_per_l_used, fuel_cost_thb, "
         "tolls_thb, total_cost_thb FROM car_bookings "
         "WHERE total_cost_thb IS NOT NULL")
    args = []
    if date_from:
        q += f" AND trip_date >= {PH}"; args.append(str(date_from))
    if date_to:
        q += f" AND trip_date <= {PH}"; args.append(str(date_to))
    cur.execute(q, args)
    agg = {}
    for cc, km, kpl, fuel, tolls, total in cur.fetchall():
        cc = cc or "— (ไม่ระบุ)"
        a = agg.setdefault(cc, {"Cost centre": cc, "Trips": 0, "Km": 0.0,
                                "Litres": 0.0, "Fuel ฿": 0.0, "Tolls ฿": 0.0,
                                "Total ฿": 0.0})
        a["Trips"] += 1
        a["Km"] += km or 0
        a["Litres"] += (km or 0) / (kpl or 1)
        a["Fuel ฿"] += fuel or 0
        a["Tolls ฿"] += tolls or 0
        a["Total ฿"] += total or 0
    rows = []
    grand = {"Cost centre": "รวมทั้งสิ้น / GRAND TOTAL", "Trips": 0,
             "Km": 0.0, "Litres": 0.0, "Fuel ฿": 0.0, "Tolls ฿": 0.0,
             "Total ฿": 0.0}
    for a in sorted(agg.values(), key=lambda x: -x["Total ฿"]):
        for k in ("Km", "Litres", "Fuel ฿", "Tolls ฿", "Total ฿"):
            a[k] = round(a[k], 2)
            grand[k] += a[k]
        grand["Trips"] += a["Trips"]
        rows.append(a)
    for k in ("Km", "Litres", "Fuel ฿", "Tolls ฿", "Total ฿"):
        grand[k] = round(grand[k], 2)
    return rows, grand


# ---------------------------------------------------------------- blocks
def add_block(resource_type, resource, block_date, t_start, t_end, reason):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"""INSERT INTO car_blocks (resource_type, resource,
                    block_date, time_start, time_end, reason)
                    VALUES ({PH},{PH},{PH},{PH},{PH},{PH})""",
                (resource_type, resource, str(block_date), t_start, t_end,
                 reason))
    conn.commit()


def list_blocks(block_date=None):
    conn = get_conn(); cur = conn.cursor()
    if block_date:
        cur.execute(f"""SELECT id, resource_type, resource, block_date,
                        time_start, time_end, reason FROM car_blocks
                        WHERE block_date={PH} ORDER BY resource""",
                    (str(block_date),))
    else:
        cur.execute("""SELECT id, resource_type, resource, block_date,
                       time_start, time_end, reason FROM car_blocks
                       ORDER BY block_date DESC""")
    return [{"id": r[0], "resource_type": r[1], "resource": r[2],
             "block_date": r[3], "time_start": r[4], "time_end": r[5],
             "reason": r[6]} for r in cur.fetchall()]


def delete_block(block_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(f"DELETE FROM car_blocks WHERE id={PH}", (block_id,))
    conn.commit()


def _overlap(s1, e1, s2, e2):
    return _mins(s1) < _mins(e2) and _mins(s2) < _mins(e1)


def resource_free(resource_type, resource, trip_date, t_start, t_end,
                  exclude_booking=None):
    """True if a car/driver has no confirmed trip clash AND no block."""
    for b in list_bookings(date=trip_date):
        if exclude_booking and b["id"] == exclude_booking:
            continue
        if b["status"] in ("Cancel", "Request"):
            continue
        who = b.get("car_plate") if resource_type == "car" \
            else b.get("driver_name")
        if who == resource and _overlap(t_start, t_end, b["time_start"],
                                        b["time_end"]):
            return False
    for blk in list_blocks(trip_date):
        if blk["resource_type"] == resource_type and \
                blk["resource"] == resource and \
                _overlap(t_start, t_end, blk["time_start"],
                         blk["time_end"]):
            return False
    return True


def dispatch_day(trip_date):
    """Per-resource view for the dispatch board: each car/driver with its
    day's trips (time bars) and blocks."""
    cars = list_cars(); drivers = list_drivers()
    bks = [b for b in list_bookings(date=trip_date)
           if b["status"] not in ("Cancel",)]
    blocks = list_blocks(trip_date)
    return {"cars": cars, "drivers": drivers, "bookings": bks,
            "blocks": blocks}
