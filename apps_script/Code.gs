/*****************************************************************************
 * AMS Car Booking — Apps Script hub  (Code.gs)
 * Connects: the booking page (in the HRM Car Booking module) ⇄ Jira AHA
 * ⇄ Google Sheet (cars/drivers/settings) ⇄ LINE OA @529aaynp.
 *
 * Workflow statuses use YOUR corrected names in all six logic points:
 *   Request → Confirm → On Process → Complete / Cancel
 *
 * SETUP (manual §10):
 *   1. script.google.com → New project → paste this file.
 *   2. Project Settings → Script properties (secrets NEVER go in code):
 *        JIRA_EMAIL  = your Atlassian login email
 *        JIRA_TOKEN  = API token from id.atlassian.com → Security
 *        LINE_TOKEN  = Messaging API channel access token (@529aaynp)
 *        SHEET_ID    = your booking Google Sheet id
 *   3. Fill the F map below with your custom-field ids. Your live ids are
 *      customfield_15673 … customfield_15694 (22 fields) — they were mapped
 *      in your deployed copy; to re-list them call:
 *        https://ancagroup.atlassian.net/rest/api/3/field
 *      Remember your three corrections: ONE combined "Pickup/Dest lat,lng"
 *      text field (not 4 separate ones); Purpose & Priority are PLAIN TEXT
 *      (not dropdowns); Start/End are Jira datetimes (isoDT handles it).
 *   4. Deploy → New deployment → Web app → Execute as Me → Anyone.
 *      Paste the /exec URL into the HRM secrets [car_booking].
 *   5. Jira Automation: when status → Confirm, send web request to
 *      <exec URL>?action=notify&key={{issue.key}}   (GET)
 *****************************************************************************/

const P = PropertiesService.getScriptProperties();
const prop = k => P.getProperty(k);

const JIRA_BASE   = 'https://ancagroup.atlassian.net';
const PROJECT_KEY = 'AHA';
const ISSUE_TYPE  = 'Car Booking';
const BUFFER_MIN  = 30;            // gap between trips on the same car/driver
const TZ          = 'Asia/Bangkok';

/* ---- Jira custom-field map: fill with YOUR ids (see header) ------------- */
const F = {
  staffId:   'customfield_XXXXX',
  staffName: 'customfield_XXXXX',
  department:'customfield_XXXXX',
  purpose:   'customfield_XXXXX',   // plain text
  priority:  'customfield_XXXXX',   // plain text
  date:      'customfield_XXXXX',   // date
  start:     'customfield_XXXXX',   // datetime
  end:       'customfield_XXXXX',   // datetime
  pickup:    'customfield_XXXXX',
  dest:      'customfield_XXXXX',
  latlng:    'customfield_XXXXX',   // ONE combined "Pickup/Dest lat,lng"
  passengers:'customfield_XXXXX',
  km:        'customfield_XXXXX',
  car:       'customfield_XXXXX',
  driver:    'customfield_XXXXX',
  fuelCost:  'customfield_XXXXX'
  // …extend to your full 22-field set (customfield_15673–15694)
};

/* ---------------- helpers ---------------- */
function jiraFetch(path, method, payload) {
  const auth = Utilities.base64Encode(prop('JIRA_EMAIL') + ':' + prop('JIRA_TOKEN'));
  const res = UrlFetchApp.fetch(JIRA_BASE + path, {
    method: method || 'get',
    contentType: 'application/json',
    headers: { Authorization: 'Basic ' + auth, Accept: 'application/json' },
    payload: payload ? JSON.stringify(payload) : undefined,
    muteHttpExceptions: true
  });
  const code = res.getResponseCode();
  const body = res.getContentText();
  if (code >= 300) throw new Error('Jira ' + code + ': ' + body.slice(0, 300));
  return body ? JSON.parse(body) : {};
}

function sheet(name) {
  return SpreadsheetApp.openById(prop('SHEET_ID')).getSheetByName(name);
}

function isoDT(dateStr, hhmm) {           // '2026-06-15','09:00' → Jira ISO
  return dateStr + 'T' + hhmm + ':00.000+0700';
}
function hhmm(iso) {                       // Jira ISO → 'HH:mm'
  return Utilities.formatDate(new Date(iso), TZ, 'HH:mm');
}

function linePush(userId, text) {
  if (!userId) return;
  UrlFetchApp.fetch('https://api.line.me/v2/bot/message/push', {
    method: 'post', contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + prop('LINE_TOKEN') },
    payload: JSON.stringify({ to: userId, messages: [{ type: 'text', text }] }),
    muteHttpExceptions: true
  });
}

/* settings tab: fuel price etc. — NOT hardcoded (your requirement) */
function setting(key, fallback) {
  const vals = sheet('settings').getDataRange().getValues();
  for (const r of vals) if (String(r[0]).trim() === key) return r[1];
  return fallback;
}
/* cars tab: A=plate B=model C=seats D=active E=km/L (per car, editable) */
function carKmPerL(plate) {
  const vals = sheet('cars').getDataRange().getValues();
  for (const r of vals) if (String(r[0]).trim() === plate) return Number(r[4]) || 10;
  return 10;
}
function driverLineId(driverName) {
  const vals = sheet('drivers').getDataRange().getValues();   // A=name B=userId
  for (const r of vals) if (String(r[0]).trim() === driverName) return String(r[1]).trim();
  return '';
}

/* ---------------- HTTP entry points ---------------- */
function doPost(e) {
  try {
    const b = JSON.parse(e.postData.contents);
    if (b.action === 'book') return out(book(b));
    return out({ ok: false, error: 'unknown action' });
  } catch (err) { return out({ ok: false, error: String(err) }); }
}

function doGet(e) {
  const a = (e.parameter.action || '').toLowerCase();
  try {
    if (a === 'bookings') return out(listBookings(e.parameter.date));
    if (a === 'summary')  return summaryPage(e.parameter.date);
    if (a === 'notify')   return out(notifyConfirm(e.parameter.key));
    return out({ ok: true, hub: 'AMS Car Booking', actions: ['book(POST)', 'bookings', 'summary', 'notify'] });
  } catch (err) { return out({ ok: false, error: String(err) }); }
}

function out(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/* ---------------- core actions ---------------- */
function book(b) {
  // availability: any non-finished booking overlapping (+buffer) blocks
  const jql = `project=${PROJECT_KEY} AND issuetype="${ISSUE_TYPE}" ` +
              `AND status NOT IN ("Complete","Cancel") AND "${'Date'}"="${b.date}"`;
  // (Refine per-car once a car is assigned at Confirm; at Request stage we
  //  accept and let the admin balance the fleet.)
  const fields = { project: { key: PROJECT_KEY }, issuetype: { name: ISSUE_TYPE },
                   summary: `Car: ${b.staffName} → ${b.dest} (${b.date})` };
  fields[F.staffId]    = b.staffId;
  fields[F.staffName]  = b.staffName;
  fields[F.department] = b.department || '';
  fields[F.purpose]    = b.purpose;                 // plain text
  fields[F.priority]   = b.priority || 'Normal';    // plain text
  fields[F.date]       = b.date;
  fields[F.start]      = isoDT(b.date, b.start);    // datetime fix
  fields[F.end]        = isoDT(b.date, b.end);
  fields[F.pickup]     = b.pickup;
  fields[F.dest]       = b.dest;
  fields[F.latlng]     = b.pickLatLng + ' | ' + b.destLatLng; // ONE field
  fields[F.passengers] = Number(b.passengers) || 1;
  fields[F.km]         = Number(b.km) || 0;
  const created = jiraFetch('/rest/api/3/issue', 'post', { fields });
  return { ok: true, key: created.key };
}

function listBookings(date) {
  const jql = `project=${PROJECT_KEY} AND issuetype="${ISSUE_TYPE}"` +
              (date ? ` AND "Date"="${date}"` : ' AND created >= -14d') +
              ' ORDER BY created DESC';
  const r = jiraFetch('/rest/api/3/search?maxResults=50&jql=' + encodeURIComponent(jql));
  return { ok: true, issues: (r.issues || []).map(i => ({
    key: i.key, status: i.fields.status.name, summary: i.fields.summary })) };
}

/* Jira Automation hits this when status → Confirm */
function notifyConfirm(key) {
  const i = jiraFetch('/rest/api/3/issue/' + key);
  const f = i.fields;
  if (f.status.name !== 'Confirm') return { ok: false, error: 'status is ' + f.status.name };
  const driver = f[F.driver] || '';
  const fuel = Number(setting('fuel_price_thb', 35));
  const kmpl = carKmPerL(String(f[F.car] || ''));
  const cost = ((Number(f[F.km]) || 0) / kmpl * fuel).toFixed(0);
  const msg = `🚗 งานใหม่ (Confirm) ${key}\n` +
              `${f[F.date]} ${hhmm(f[F.start])}-${hhmm(f[F.end])}\n` +
              `${f[F.pickup]} → ${f[F.dest]}\n` +
              `ผู้จอง: ${f[F.staffName]} (${f[F.staffId]})\n` +
              `ระยะทางรวม ~${f[F.km]} กม. • น้ำมันประมาณ ${cost} บาท`;
  linePush(driverLineId(String(driver)), msg);
  return { ok: true, notified: String(driver) };
}

/* daily 07:00 summary to each driver — install a time trigger on this */
function dailySummary() {
  const today = Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd');
  const jql = `project=${PROJECT_KEY} AND issuetype="${ISSUE_TYPE}" ` +
              `AND status IN ("Confirm","On Process") AND "Date"="${today}"`;
  const r = jiraFetch('/rest/api/3/search?maxResults=50&jql=' + encodeURIComponent(jql));
  const byDriver = {};
  (r.issues || []).forEach(i => {
    const d = String(i.fields[F.driver] || '');
    (byDriver[d] = byDriver[d] || []).push(
      `• ${hhmm(i.fields[F.start])} ${i.fields[F.pickup]} → ${i.fields[F.dest]} (${i.key})`);
  });
  Object.keys(byDriver).forEach(d =>
    linePush(driverLineId(d), `📅 ตารางรถวันนี้ (${today})\n` + byDriver[d].join('\n')));
}

function summaryPage(date) {
  const data = listBookings(date || Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd'));
  const rows = data.issues.map(i =>
    `<tr><td>${i.key}</td><td>${i.status}</td><td>${i.summary}</td></tr>`).join('');
  return HtmlService.createHtmlOutput(
    `<h3>AMS Car Bookings</h3><table border=1 cellpadding=6>` +
    `<tr><th>Key</th><th>Status</th><th>Trip</th></tr>${rows}</table>`);
}
