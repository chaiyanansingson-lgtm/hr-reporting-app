# lib/print_docs.py
# ============================================================================
# Requirement (12 Jun): the system forms are bilingual TH/EN on screen, but
# Admin can PRINT the filled result back in the ORIGINAL document format:
#   - FM-HR-003 Application for Employment (ANCA bilingual form, 2 pages)
#   - เอกสารแนบท้าย (additional disclosures, per 20260612 version)
#   - สปส.1-03 แบบขึ้นทะเบียนผู้ประกันตน (Thai official form)
#   - ล.ย.01 แบบแจ้งรายการเพื่อการหักลดหย่อน (Thai official form)
#
# Output: A4 HTML faithful to each form's section structure; convert to PDF
# with WeasyPrint (your established pipeline, Sarabun font). If WeasyPrint
# is unavailable, the HTML itself prints correctly from the browser
# (Ctrl+P) at A4.
# ============================================================================

import datetime as dt
import html as _h

CSS = """
@page { size: A4; margin: 14mm 12mm; }
body { font-family: 'Sarabun','TH Sarabun New',sans-serif; font-size: 12.5px;
       color:#111; line-height:1.5; }
h1 { font-size:17px; text-align:center; margin:2px 0 0; }
h2 { font-size:13.5px; background:#e8eef7; border:1px solid #9db3d4;
     padding:2px 8px; margin:10px 0 6px; }
.small { font-size:10.5px; color:#444; }
.v { border-bottom:1px dotted #555; padding:0 6px; font-weight:600;
     min-width:60px; display:inline-block; }
.row { margin:3px 0; }
.cb { font-family:'DejaVu Sans',sans-serif; }
table { border-collapse:collapse; width:100%; margin:4px 0; }
td, th { border:1px solid #777; padding:3px 6px; font-size:11.5px;
         vertical-align:top; }
th { background:#eef2f8; }
.sig { margin-top:18px; display:flex; justify-content:flex-end; }
.sigbox { text-align:center; width:300px; }
.hdrbar { display:flex; justify-content:space-between; align-items:center; }
.formno { font-size:11px; color:#333; }
.pagebreak { page-break-before: always; }
.staffonly { border:1.5px solid #333; padding:6px 10px; width:260px;
             font-size:11.5px; }
.note { font-size:10px; color:#333; margin-top:8px; }
"""


def _e(v):
    return _h.escape(str(v)) if v not in (None, "") else ""


def _cb(checked):
    return '<span class="cb">☑</span>' if checked else \
           '<span class="cb">☐</span>'


def _val(rec, key, width=120):
    return f'<span class="v" style="min-width:{width}px">{_e(rec.get(key))}</span>'


def _is(rec, key, *options):
    v = str(rec.get(key) or "")
    return any(o in v for o in options)


def _doc(title, body):
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{title}</title><style>{CSS}</style></head>"
            f"<body>{body}</body></html>")


# ============================================================ FM-HR-003
def render_application(rec: dict, show_salary=False) -> str:
    rec = rec or {}
    """Filled 'Application for Employment' in the FM-HR-003 Rev.01 layout.
    show_salary=True adds the 'For staff only' box values (Super Admin)."""
    staff_box = f"""
    <div class="staffonly">
      <b>สำหรับเจ้าหน้าที่เท่านั้น / For staff only</b><br>
      Position: {_val(rec,'title',110)}<br>
      Base salary: {_val(rec,'base_salary',90) if show_salary else
                    '<span class="v" style="min-width:90px"></span>'}<br>
      Allowance: {_val(rec,'position_allowance',90) if show_salary else
                  '<span class="v" style="min-width:90px"></span>'}<br>
      Staff id: {_val(rec,'emp_no',90)}
    </div>"""

    body = f"""
    <div class="hdrbar">{staff_box}
      <div style="text-align:right">
        <b>ใบสมัครงาน</b><br><b>Private &amp; Confidential</b></div></div>
    <h1>Application for Employment</h1>
    <div class="row">ตำแหน่งที่ต้องการสมัคร (Position applied for):
      {_val(rec,'position_applied',240)}
      &nbsp; วันที่ (Date): {_val(rec,'_app_date',100)}</div>

    <h2>Personal Details / ประวัติส่วนตัว</h2>
    <div class="row">ชื่อ-สกุล ภาษาไทย: {_val(rec,'emp_name_th',280)}</div>
    <div class="row">Name (English): {_val(rec,'emp_name_en',280)}</div>
    <div class="row">ที่อยู่ที่ติดต่อได้ (Address):
      {_val(rec,'cur_addr_no',90)} ต.{_val(rec,'cur_addr_subdistrict',90)}
      อ.{_val(rec,'cur_addr_district',90)} จ.{_val(rec,'cur_addr_province',90)}
      รหัสไปรษณีย์ (Postcode): {_val(rec,'postcode',60)}</div>
    <div class="row">เบอร์โทรศัพท์ (Mobile): {_val(rec,'mobile',120)}
      &nbsp; E-mail: {_val(rec,'personal_email',180)}</div>
    <div class="row">วัน/เดือน/ปีเกิด (Date of Birth): {_val(rec,'birth_day',110)}
      &nbsp; ศาสนา (Religion): {_val(rec,'religion',90)}
      &nbsp; สัญชาติ (Nationality): {_val(rec,'nationality',80)}</div>
    <div class="row">สถานภาพ (Status):
      {_cb(_is(rec,'marital_status','โสด','Single'))} โสด (Single)
      {_cb(_is(rec,'marital_status','สมรส','Married'))} สมรส (Married)
      {_cb(_is(rec,'marital_status','หย่า','Divorce'))} หย่าร้าง (Divorce)</div>
    <div class="row">กรณีฉุกเฉินติดต่อ (Emergency contact):
      {_val(rec,'emergency_name',170)}
      ความสัมพันธ์ (Relation): {_val(rec,'emergency_relation',100)}<br>
      ที่อยู่ (Address): {_val(rec,'emergency_address',300)}
      เบอร์โทร (Phone): {_val(rec,'emergency_phone',110)}</div>

    <h2>ประวัติการทำงาน / Previous Employment</h2>
    <div class="row" style="white-space:pre-wrap">{_e(rec.get('prev_employment'))}</div>
    <h2>ประวัติการศึกษา / Education</h2>
    <div class="row">วุฒิสูงสุด: {_val(rec,'education',160)}</div>
    <div class="row" style="white-space:pre-wrap">{_e(rec.get('education_history'))}</div>
    <div class="row">คุณสมบัติอื่นๆ/อบรม (Other qualifications):
      <span style="white-space:pre-wrap">{_e(rec.get('other_qualifications'))}</span></div>

    <div class="pagebreak"></div>
    <h2>ประวัติสุขภาพ / Health</h2>
    <div class="row">บาดเจ็บที่กระทบงาน (Injury affecting work):
      {_cb(not rec.get('health_injury'))} ไม่เคย (No)
      {_cb(bool(rec.get('health_injury')))} เคย (Yes):
      {_e(rec.get('health_injury'))}</div>
    <div class="row">เจ็บป่วยสาหัส/ผ่าตัด (Serious illness/operations):
      {_cb(not rec.get('health_illness'))} ไม่เคย
      {_cb(bool(rec.get('health_illness')))} เคย:
      {_e(rec.get('health_illness'))}</div>
    <div class="row">ติดยาเสพติด (Drug addiction):
      {_cb(not rec.get('health_drugs'))} ไม่เคย
      {_cb(bool(rec.get('health_drugs')))} เคย:
      {_e(rec.get('health_drugs'))}</div>
    <div class="row">โรคประจำตัว (Medical problem):
      {_cb(not rec.get('health_chronic'))} ไม่มี
      {_cb(bool(rec.get('health_chronic')))} มี:
      {_e(rec.get('health_chronic'))}</div>
    <div class="row">ยินยอมตรวจสุขภาพ (Medical exam if required):
      {_cb(_is(rec,'health_medical_exam_consent','ยินยอม','Yes'))} ยินยอม (Yes)
      {_cb(_is(rec,'health_medical_exam_consent','ไม่','No'))} ไม่ยินยอม (No)</div>

    <h2>เรื่องทั่วไป / General</h2>
    <div class="row">ใบขับขี่ (Driver licence):
      {_cb(not rec.get('driver_licence'))} ไม่มี (No)
      {_cb(bool(rec.get('driver_licence')))} มี (Yes):
      {_e(rec.get('driver_licence'))}</div>
    <div class="row">เคยถูกเลิกจ้าง (Ever discharged):
      {_cb(not rec.get('ever_discharged'))} ไม่เคย
      {_cb(bool(rec.get('ever_discharged')))} เคย:
      {_e(rec.get('ever_discharged'))}</div>
    <div class="row">เคยต้องคดีอาญา (Criminal record):
      {_cb(not rec.get('criminal_record'))} ไม่เคย
      {_cb(bool(rec.get('criminal_record')))} เคย:
      {_e(rec.get('criminal_record'))}</div>
    <div class="row">ทำงานเป็นกะ (Shift rotation):
      {_cb(_is(rec,'can_shift_work','ได้','Yes'))} ได้
      {_cb(_is(rec,'can_shift_work','ไม่','No'))} ไม่ประสงค์</div>
    <div class="row">กิจกรรมยามว่าง (Hobbies): {_val(rec,'hobbies',260)}</div>
    <div class="row">ความสามารถด้านภาษา (Languages): {_val(rec,'languages',240)}</div>
    <div class="row">เริ่มงานได้ (Able to start):
      {_cb(_is(rec,'start_availability','ทันที','Now'))} ได้ทันที (Now)
      {_cb(_is(rec,'start_availability','15'))} 15 วัน
      {_cb(_is(rec,'start_availability','30'))} 30 วัน
      {_cb(_is(rec,'start_availability','อื่น','Other'))} อื่นๆ</div>

    <div class="note"><b>คำเตือน:</b> โปรดตั้งใจอ่านข้อความต่อไปนี้โดยละเอียดก่อนที่ท่านจะเซ็นชื่อลงในใบสมัคร
    การปิดบังหรือฉ้อฉลคำตอบใดๆ ในใบสมัครนี้ จะเป็นผลให้ท่านหมดสิทธิ์ในการพิจารณาเข้าเป็นพนักงาน
    หรือถูกไล่ออกภายหลังได้รับการแต่งตั้ง<br>
    <b>ATTENTION:</b> Read the following paragraph carefully before signing this application.
    False or dishonest answers to any question may be grounds for rating you ineligible
    for employment or for dismissal after appointment.<br><br>
    ข้าพเจ้าขอรับรองว่าข้อความที่ได้กล่าวมาทั้งหมดในใบสมัครนี้เป็นความจริง สมบูรณ์ และถูกต้องที่สุดเท่าที่ข้าพเจ้าทราบ /
    I CERTIFY that all statements made in this application are true, complete and correct
    to the best of my knowledge and belief and are made in good faith.</div>
    <div class="sig"><div class="sigbox">
      ผู้สมัคร (Applicant) ........................................<br>
      วันที่ (Date) ......./......./.......</div></div>
    <div class="formno">FM-HR-003 Rev.01 (23/03/2017)</div>
    """
    rec = dict(rec)
    rec.setdefault("_app_date", rec.get("created_at", "")[:10])
    return _doc("FM-HR-003 Application", body)


# ============================================================ เอกสารแนบท้าย
def render_addendum(rec: dict) -> str:
    rec = rec or {}
    qs = [
        ("disclosure_image_disease",
         "1. ท่านมีอาการเจ็บป่วยหรือมีประวัติการป่วยด้วยโรคที่อาจมีผลกระทบต่อภาพลักษณ์ในการทำงาน "
         "เช่น โรคเท้าช้าง โรคติดต่อร้ายแรงหรือโรคเรื้อรังที่ปรากฏอาการเด่นชัดหรือรุนแรง "
         "รวมถึงแต่ไม่จำกัดเพียงวัณโรค โรคซิฟิลิส โรคไวรัสตับอักเสบ หากมีโปรดระบุ:"),
        ("health_chronic",
         "2. ท่านมีอาการเจ็บป่วยหรือมีประวัติการป่วยเรื้อรัง โรคประจำตัว ปัญหาสุขภาพ "
         "ที่อาจมีผลต่อการทำงานหรือความปลอดภัยในการทำงาน หากมีโปรดระบุ:"),
        ("health_illness",
         "3. ท่านเคยประสบอุบัติเหตุ เข้ารับการผ่าตัด ใส่อุปกรณ์ช่วยเหลือทางการแพทย์ "
         "หรือมีความผิดปกติทางร่างกาย หากมีโปรดระบุ:"),
        ("health_drugs",
         "4. ท่านเคยมีประวัติการป่วยพิษสุราเรื้อรัง ใช้สารเสพติด สารเคมีที่มีผลทางประสาท "
         "หรือสารอื่นใดที่ก่อให้เกิดการเสพติดหรือไม่ หากเคยมีโปรดระบุ:"),
        ("disclosure_care_duty",
         "5. ท่านมีหน้าที่ ภาระความรับผิดชอบในการดูแลผู้ป่วย ผู้ป่วยติดเตียง "
         "หรือบุคคลที่มีเงื่อนไขทางสุขภาพ หากมีโปรดระบุ:"),
        ("disclosure_relatives_at_work",
         "6. ท่านมีญาติ พี่น้อง คู่ครอง คู่สมรส หรือผู้ที่มีความเกี่ยวข้องทางสายเลือดอื่นใด "
         "ปฏิบัติงานในหน้างานของสถานประกอบการ หากมีโปรดระบุ:"),
    ]
    items = "".join(
        f'<div class="row"><b>{q}</b><br>'
        f'<span class="v" style="min-width:95%">{_e(rec.get(k)) or "— ไม่มี —"}'
        f'</span></div>' for k, q in qs)
    consent = rec.get("pdpa_consent_at", "")
    body = f"""
    <h1>เอกสารแนบท้าย</h1>
    <h2>ประวัติอื่นๆ</h2>{items}
    <div class="note">ข้าพเจ้ายินยอมเปิดเผยข้อมูลดังกล่าวและยินยอมให้ผู้บริหารข้อมูลรวบรวม จัดเก็บ
    และประมวลผลเพื่อประโยชน์ในการสมัครงานและบริหารการจ้างงาน
    ตามพระราชบัญญัติคุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562 มาตรา 4 ทุกประการ
    (บันทึกความยินยอมในระบบ: {_e(consent)})<br>
    <b>คำรับรอง:</b> ข้าพเจ้าขอรับรองว่าข้อความข้างต้นและเอกสารสมัครงานทั้งหมด
    เป็นความจริงทุกประการ หากปรากฏภายหลังว่าข้าพเจ้าปกปิดข้อเท็จจริง
    หรือแจ้งข้อความอันเป็นเท็จซึ่งถือเป็นการทุจริตต่อหน้าที่หรือจงใจทำให้
    นายจ้างได้รับความเสียหาย ข้าพเจ้ายินยอมให้บริษัทฯ เลิกจ้างได้ทันที
    โดยไม่จ่ายค่าชดเชย ตามพระราชบัญญัติคุ้มครองแรงงาน พ.ศ. 2541
    มาตรา 119(1) และข้อมูลนี้เป็นส่วนหนึ่งของสัญญาจ้างแรงงาน /
    I certify that all statements are true; concealment or false statements
    constitute dishonest conduct permitting immediate dismissal without
    severance pay under the Labour Protection Act B.E. 2541, Section
    119(1).</div>
    <div class="sig"><div class="sigbox">
      ลงนาม .................................................... ผู้สมัคร<br>
      ({_e(rec.get('emp_name_th') or rec.get('emp_name_en'))})</div></div>"""
    return _doc("เอกสารแนบท้าย", body)


# ============================================================ สปส.1-03
def render_sso103(rec: dict, employer: dict | None = None) -> str:
    rec = rec or {}
    employer = employer or {
        "name": "ANCA Manufacturing Solutions (Thailand) Co., Ltd.",
        "account_no": "", "branch_no": "", "signer": "", "signer_title": ""}
    foreigner = bool(rec.get("passport_no") or rec.get("work_permit_no"))
    body = f"""
    <div class="hdrbar"><div></div><div class="formno"><b>สปส.1-03</b></div></div>
    <h1>แบบขึ้นทะเบียนผู้ประกันตน</h1>
    <h2>① ข้อมูลนายจ้าง</h2>
    <div class="row">ชื่อสถานประกอบการ: {_e(employer['name'])}
      &nbsp; เลขที่บัญชี: {_e(employer['account_no'])}
      &nbsp; ลำดับที่สาขา: {_e(employer['branch_no'])}</div>
    <div class="row">วันที่ผู้ประกันตนเข้าทำงาน: {_val(rec,'joined_date',110)}
      &nbsp; ประเภทการจ้าง:
      {_cb(_is(rec,'direct_indirect','Direct'))} รายวัน
      {_cb(_is(rec,'direct_indirect','Indirect'))} รายเดือน</div>
    <h2>② ข้อมูลผู้ประกันตน</h2>
    <div class="row">2.1
      {_cb(_is(rec,'sso_prev_registered','ไม่เคย','Never'))} ไม่เคยขึ้นทะเบียนผู้ประกันตน
      &nbsp; {_cb(_is(rec,'sso_prev_registered','เคย','Yes'))} เคยขึ้นทะเบียนผู้ประกันตน
      &nbsp; ทำงานกับนายจ้างหลายแห่ง: {_e(rec.get('sso_multi_employer'))}</div>
    <div class="row">2.2 ชื่อ-ชื่อสกุล: {_val(rec,'emp_name_th',260)}
      สัญชาติ: {_val(rec,'nationality',90)}
      เกิดวันที่: {_val(rec,'birth_day',110)}</div>
    <div class="row">2.3 เลขประจำตัวประชาชน/เลขที่บัตรประกันสังคม (สำหรับคนต่างด้าว):
      {_val(rec,'id_card',180)}</div>
    <div class="row">2.4 สถานภาพครอบครัว:
      {_cb(_is(rec,'marital_status','โสด','Single'))} 1. โสด
      {_cb(_is(rec,'marital_status','สมรส','Married'))} 2. สมรส
      {_cb(_is(rec,'marital_status','หม้าย','Widow'))} 3. หม้าย
      {_cb(_is(rec,'marital_status','หย่า','Divorce'))} 4. หย่า
      {_cb(_is(rec,'marital_status','แยก','Separated'))} 5. แยกกันอยู่<br>
      บุตรอายุไม่เกิน 6 ปี: {_val(rec,'sso_children_u6',220)}</div>
    <div class="row">2.5 สภาพร่างกาย:
      {_cb(not rec.get('sso_disability'))} 1. ปกติ
      {_cb(bool(rec.get('sso_disability')))} 2. พิการ —
      {_e(rec.get('sso_disability'))}</div>
    <div class="row">2.6 สำหรับคนต่างด้าว:
      {_cb(foreigner)} หนังสือเดินทาง (PASSPORT) เลขที่ {_val(rec,'passport_no',130)}
      และใบอนุญาตทำงาน (WORK PERMIT) เลขที่ {_val(rec,'work_permit_no',130)}</div>
    <div class="row small">ข้าพเจ้าขอรับรองว่าข้อมูลนายจ้างและข้อมูลผู้ประกันตนดังกล่าวข้างต้น
      ถูกต้องตามความเป็นจริงทุกประการ</div>
    <div class="sig"><div class="sigbox">
      ลงชื่อ ........................................ นายจ้าง<br>
      ({_e(employer['signer'])})<br>ตำแหน่ง {_e(employer['signer_title'])}<br>
      วันที่ ..............................</div></div>
    <h2>③ ข้อมูลการเลือก / ขอเปลี่ยนแปลงสถานพยาบาล</h2>
    <div class="row">ข้าพเจ้าขอเลือกสถานพยาบาล &nbsp;
      ลำดับที่ 1. {_val(rec,'hospital_choice_1',170)}
      ลำดับที่ 2. {_val(rec,'hospital_choice_2',170)}
      ลำดับที่ 3. {_val(rec,'hospital_choice_3',170)}</div>
    <div class="row small">ขณะที่ข้าพเจ้าเลือกสถานพยาบาล ข้าพเจ้าไม่ได้นอนรักษาตัวเป็นผู้ป่วยใน
      ณ สถานพยาบาลใด ๆ และข้าพเจ้ายินยอมให้นายจ้างนำข้อมูลการเลือกสถานพยาบาลของข้าพเจ้า
      บันทึกลงในแบบรายการทางอิเล็กทรอนิกส์</div>
    <div class="sig"><div class="sigbox">
      ลงชื่อ ........................................ ผู้ประกันตน<br>
      ({_e(rec.get('emp_name_th'))})<br>วันที่ ..............................</div></div>
    <div class="note">หมายเหตุ: ในการแจ้งขึ้นทะเบียนผู้ประกันตน (สปส.1-03)
      ให้นายจ้างกรอกข้อมูลผู้ประกันตนลงในทะเบียนผู้ประกันตน (สปส.6-07) ทุกครั้ง</div>"""
    return _doc("สปส.1-03", body)


# ============================================================ ล.ย.01
def render_ly01(rec: dict, employer_name="ANCA Manufacturing Solutions "
                                          "(Thailand) Co., Ltd.") -> str:
    rec = rec or {}
    def money(k):
        v = rec.get(k)
        return f"{float(v):,.2f}" if v not in (None, "") else ""
    body = f"""
    <div class="hdrbar"><div></div><div class="formno"><b>ล.ย.01</b></div></div>
    <h1>แบบแจ้งรายการเพื่อการหักลดหย่อน</h1>
    <div class="row">วัน/เดือน/ปีที่แจ้งรายการ: {_val(rec,'_ly_date',120)}</div>
    <div class="row">ชื่อหน่วยงานผู้มีหน้าที่หักภาษี ณ ที่จ่าย: {_e(employer_name)}</div>
    <div class="row">เลขประจำตัวผู้เสียภาษีอากร: {_val(rec,'id_card',180)}</div>
    <div class="row">ผู้มีเงินได้ ชื่อ-ชื่อสกุล: {_val(rec,'emp_name_th',280)}</div>
    <div class="row">ที่อยู่: เลขที่ {_val(rec,'cur_addr_no',80)}
      ตำบล/แขวง {_val(rec,'cur_addr_subdistrict',100)}
      อำเภอ/เขต {_val(rec,'cur_addr_district',100)}
      จังหวัด {_val(rec,'cur_addr_province',100)}
      รหัสไปรษณีย์ {_val(rec,'postcode',60)}</div>
    <table>
      <tr><th style="width:70%">รายการ</th><th>จำนวน / บาท</th></tr>
      <tr><td>1. สถานภาพ:
        {_cb(_is(rec,'marital_status','โสด'))} โสด
        {_cb(_is(rec,'marital_status','สมรส'))} สมรส
        {_cb(_is(rec,'marital_status','หม้าย'))} หม้าย
        {_cb(_is(rec,'marital_status','หย่า'))} หย่าระหว่างปีภาษี</td><td></td></tr>
      <tr><td>2. สถานะการมีเงินได้ของคู่สมรส:
        {_cb(_is(rec,'tax_spouse_income','มีเงินได้','Has'))} มีเงินได้
        {_cb(_is(rec,'tax_spouse_income','ไม่มี','No income'))} ไม่มีเงินได้</td><td></td></tr>
      <tr><td>3. จำนวนบุตรรวม {_e(rec.get('tax_children_total'))} คน —
        บุตรคนละ 30,000 บาท จำนวน {_e(rec.get('tax_children_30k'))} คน;
        บุตร (คนที่สองเป็นต้นไป เกิดในหรือหลังปี พ.ศ. 2561) คนละ 60,000 บาท
        จำนวน {_e(rec.get('tax_children_60k'))} คน</td><td></td></tr>
      <tr><td>4. ค่าอุปการะเลี้ยงดูบิดา/มารดา (คนละ 30,000 บาท)</td>
        <td>{_e(rec.get('tax_parent_care'))}</td></tr>
      <tr><td>5. ค่าอุปการะเลี้ยงดูคนพิการหรือคนทุพพลภาพ (คนละ 60,000 บาท)</td>
        <td>{_e(rec.get('tax_disabled_care'))}</td></tr>
      <tr><td>7. เบี้ยประกันชีวิตที่จ่ายภายในปีภาษี</td>
        <td>{money('tax_life_insurance')}</td></tr>
      <tr><td>8. เบี้ยประกันสุขภาพที่จ่ายภายในปีภาษี (ไม่เกิน 15,000 บาท)</td>
        <td>{money('tax_health_insurance')}</td></tr>
      <tr><td>9. เงินสะสมที่จ่ายเข้ากองทุนสำรองเลี้ยงชีพ (ไม่เกิน 500,000 บาท)</td>
        <td>{'มี (PVD: ' + _e(rec.get('pvd')) + ')' if rec.get('pvd') else ''}</td></tr>
      <tr><td>10. ค่าซื้อหน่วยลงทุนกองทุนรวมเพื่อการเลี้ยงชีพ (RMF)</td>
        <td>{money('tax_rmf')}</td></tr>
      <tr><td>12. ดอกเบี้ยเงินกู้ยืมเพื่อซื้อ เช่าซื้อ หรือสร้างอาคารที่อยู่อาศัย
        (ไม่เกิน 100,000 บาท)</td><td>{money('tax_home_loan_interest')}</td></tr>
      <tr><td>13. เงินสมทบกองทุนประกันสังคมภายในปีภาษี</td><td>หักตามจริงโดยนายจ้าง</td></tr>
      <tr><td>14.-15. เงินบริจาค</td><td>{_e(rec.get('tax_donations'))}</td></tr>
    </table>
    <div class="row small">ขอรับรองว่ารายการที่แสดงไว้เป็นความจริงทุกประการ</div>
    <div class="sig"><div class="sigbox">
      ลงชื่อ ........................................ ผู้มีเงินได้<br>
      ({_e(rec.get('emp_name_th'))})</div></div>
    <div class="note">หมายเหตุ: (1) ปีภาษีหมายถึง เดือนมกราคม – ธันวาคม
      (2) กรณีหักค่าลดหย่อนต้องมีการจ่ายจริงในปีที่แจ้งรายการ
      และต้องแนบสำเนาหลักฐานแสดงสิทธิ
      (3) ให้แจ้งรายการก่อนถูกหักภาษีและทุกครั้งที่มีการเปลี่ยนแปลง</div>"""
    rec = dict(rec)
    rec.setdefault("_ly_date", dt.date.today().isoformat())
    return _doc("ล.ย.01", body)


# ============================================================ PDF
def html_to_pdf(html_str: str) -> bytes | None:
    """WeasyPrint pipeline (Sarabun). Returns None if unavailable —
    caller then offers the HTML for browser printing instead."""
    try:
        from weasyprint import HTML
        return HTML(string=html_str).write_pdf()
    except Exception:
        return None


# ============================================================ ล.ย.01 (FAITHFUL)
def render_ly01_pdf(rec: dict,
                    employer="ANCA Manufacturing Solutions (Thailand) Ltd."):
    rec = rec or {}
    """Fill the REAL fillable ล.ย.01 government PDF with the employee's identity
    data and return PDF bytes. Digits/Latin (tax ID, employer) go in via the
    AcroForm (they render and auto-align in the comb); Thai name + date are
    overlaid with the Sarabun font because the form's field font has no Thai
    glyphs. Deduction lines are left blank for the employee to complete.
    Returns bytes, or None if the template/font is unavailable."""
    import os
    import io
    import datetime as dt
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl_path = os.path.join(root, "assets", "forms", "ly01_template.pdf")
    font_path = os.path.join(root, "assets", "fonts", "Sarabun-Regular.ttf")
    if not (os.path.exists(tpl_path) and os.path.exists(font_path)):
        return None
    try:
        pdfmetrics.registerFont(TTFont("SarabunLY", font_path))
    except Exception:
        pass

    def th_be_date():
        d = dt.date.today()
        return f"{d.day:02d}/{d.month:02d}/{d.year + 543}"

    try:
        r = PdfReader(tpl_path)
        w = PdfWriter(); w.append(r)
        # 1) AcroForm: digits/Latin render fine and the comb auto-aligns
        w.update_page_form_field_values(
            w.pages[0],
            {"1": employer, "2": (rec.get("id_card") or "")},
            auto_regenerate=False)
        # 2) Sarabun overlay for Thai text at the mapped field coordinates
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(595.32, 841.92))
        nm = (rec.get("emp_name_th") or "").strip().split()
        first = nm[0] if nm else ""
        last = " ".join(nm[1:]) if len(nm) > 1 else ""
        c.setFont("SarabunLY", 11)
        c.drawString(66, 730, first)     # Text1.3 given name
        c.drawString(344, 730, last)     # Text1.4 surname
        c.setFont("SarabunLY", 10)
        c.drawString(437, 802, th_be_date())   # declaration date (top right)
        c.save(); buf.seek(0)
        ov = PdfReader(buf).pages[0]
        w.pages[0].merge_page(ov)
        out = io.BytesIO(); w.write(out)
        return out.getvalue()
    except Exception:
        return None


# ============================================================ สปส.1-03 (FAITHFUL)
_TH_MONTHS = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม",
              "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม",
              "พฤศจิกายน", "ธันวาคม"]


def _parse_date(v):
    import datetime as dt
    if not v:
        return None
    s = str(v).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None


def render_sso103_pdf(rec: dict,
                      employer="ANCA Manufacturing Solutions (Thailand) Ltd."):
    rec = rec or {}
    """Overlay the employee's data onto the real สปส.1-03 government PDF (which
    has no fillable fields) using the Sarabun font. Only data-driven fields are
    filled; employment-type / physical / marital tick-boxes are left for HR to
    mark by hand. Returns bytes, or None if template/font unavailable."""
    import os
    import io
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl_path = os.path.join(root, "assets", "forms", "sso103_template.pdf")
    font_path = os.path.join(root, "assets", "fonts", "Sarabun-Regular.ttf")
    if not (os.path.exists(tpl_path) and os.path.exists(font_path)):
        return None
    try:
        pdfmetrics.registerFont(TTFont("SarabunSSO", font_path))
    except Exception:
        pass
    try:
        r = PdfReader(tpl_path); w = PdfWriter(); w.append(r)
        buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=(595.32, 841.92))

        def th(x, y, txt, sz=10):
            c.setFont("SarabunSSO", sz); c.drawString(x, y, str(txt))

        def mark(x, y):
            c.setFont("Helvetica-Bold", 10); c.drawString(x, y, "X")

        # 1) employer name
        th(120, 739, employer, 9)
        # start date (insured began work)
        jd = _parse_date(rec.get("joined_date") or rec.get("joined_date_sub"))
        if jd:
            th(152, 707, f"{jd.day:02d}/{jd.month:02d}/{jd.year + 543}")
        # 2.2 title + name + nationality
        full = (rec.get("emp_name_th") or "").strip()
        title, rest = "", full
        for t in ("นางสาว", "นาง", "นาย"):
            if full.startswith(t):
                title, rest = t, full[len(t):].strip(); break
        parts = rest.split()
        first = parts[0] if parts else ""
        last = " ".join(parts[1:]) if len(parts) > 1 else ""
        if title == "นาย":
            mark(64, 631)
        elif title == "นางสาว":
            mark(110, 631)
        elif title == "นาง":
            mark(160, 631)
        th(248, 631, first)
        th(376, 631, last)
        th(508, 631, (rec.get("nationality") or "ไทย"))
        # birth date
        bd = _parse_date(rec.get("birth_day"))
        if bd:
            th(95, 615, str(bd.day))
            th(165, 615, _TH_MONTHS[bd.month])
            th(235, 615, str(bd.year + 543))
        # 2.3 national ID — 13 digit boxes
        nid = "".join(ch for ch in (rec.get("id_card") or "") if ch.isdigit())
        for i, ch in enumerate(nid[:13]):
            th(367 + i * 16.3, 605, ch, 11)
        c.save(); buf.seek(0)
        w.pages[0].merge_page(PdfReader(buf).pages[0])
        out = io.BytesIO(); w.write(out)
        return out.getvalue()
    except Exception:
        return None


# ============================================================ helpers (faithful)
def _split_th_name(full):
    full = (full or "").strip()
    title = ""
    for t in ("นางสาว", "นาง", "นาย"):
        if full.startswith(t):
            title, full = t, full[len(t):].strip()
            break
    parts = full.split()
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    return title, first, last


def _split_en_name(full):
    parts = (full or "").strip().split()
    if parts and parts[0].rstrip(".").lower() in ("mr", "ms", "mrs", "miss") \
            and len(parts) > 1:
        parts = parts[1:]
    if not parts:
        return "", ""
    first = parts[0]
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    return first, last


def _compose_addr(rec):
    no = (rec.get("cur_addr_no") or "").strip()
    sub = (rec.get("cur_addr_subdistrict") or "").strip()
    dis = (rec.get("cur_addr_district") or "").strip()
    pro = (rec.get("cur_addr_province") or "").strip()
    out = []
    if no:
        out.append(no)
    if sub:
        out.append("ต." + sub)
    if dis:
        out.append("อ." + dis)
    if pro:
        out.append("จ." + pro)
    return " ".join(out)


def _money(v):
    if v in (None, ""):
        return ""
    try:
        f = float(str(v).replace(",", ""))
        return f"{int(f):,}" if f == int(f) else f"{f:,.2f}"
    except Exception:
        return str(v)


def _age_from(bd):
    if not bd:
        return ""
    import datetime as dt
    t = dt.date.today()
    a = t.year - bd.year - ((t.month, t.day) < (bd.month, bd.day))
    return str(a) if 0 < a < 120 else ""


# ============================================================ FM-HR-003 (FAITHFUL)
def render_fmhr003_pdf(rec: dict,
                       employer="ANCA Manufacturing Solutions (Thailand) Ltd.",
                       show_salary=False):
    rec = rec or {}
    """Overlay the employee's master data onto the REAL FM-HR-003 (AMS logo)
    2-page application form using the Sarabun font — same technique as
    สปส.1-03. Single-line identity/contact fields, the 'For staff only' box,
    and the data-driven tick-boxes (marital / health / general / shift /
    start availability) are filled; the work-history, education and language
    tables are left blank for completion. Returns bytes, or None if the
    template/font is unavailable."""
    import os
    import io
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl = os.path.join(root, "assets", "forms", "fmhr003_template.pdf")
    font = os.path.join(root, "assets", "fonts", "Sarabun-Regular.ttf")
    if not (os.path.exists(tpl) and os.path.exists(font)):
        return None
    try:
        pdfmetrics.registerFont(TTFont("SarabunFM", font))
    except Exception:
        pass
    W, H = 595.44, 841.92
    try:
        r = PdfReader(tpl)
        w = PdfWriter()
        w.append(r)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(W, H))

        def th(x, y, t, sz=10.5):
            if t in (None, ""):
                return
            c.setFont("SarabunFM", sz)
            c.drawString(x, y, str(t))

        def mark(x, y):
            c.setFont("Helvetica-Bold", 8.5)
            c.drawString(x, y, "X")

        title, th_first, th_last = _split_th_name(rec.get("emp_name_th"))
        en_first, en_last = _split_en_name(rec.get("emp_name_en"))
        bd = _parse_date(rec.get("birth_day"))

        # ---------------- PAGE 0 ----------------
        th(92, 784.9, rec.get("title"), 10)                 # staff: position
        if show_salary:
            th(107, 774.1, _money(rec.get("base_salary")), 10)
            th(102, 763.1, _money(rec.get("position_allowance")), 10)
        th(90, 752.0, rec.get("emp_no"), 10)                # staff: id
        th(220, 653.8, rec.get("position_applied") or rec.get("title"))
        th(470, 653.6, rec.get("_app_date"), 9.5)
        thname = (title + " " + th_first).strip() if title else th_first
        th(175, 595.5, thname)
        th(369, 595.5, th_last)
        th(212, 573.6, en_first)
        th(373, 573.6, en_last)
        th(149, 552.3, _compose_addr(rec), 9.5)
        th(147, 532.8, rec.get("postcode"), 9.5)
        th(288, 532.8, rec.get("mobile"), 9.5)
        th(418, 532.8, rec.get("personal_email"), 9)
        if bd:
            th(167, 510.2, f"{bd.day:02d}/{bd.month:02d}/{bd.year + 543}", 9.5)
        th(338, 510.2, _age_from(bd), 9.5)
        th(471, 510.2, rec.get("religion"), 9.5)
        th(191, 464.1, rec.get("emergency_name"), 9.5)
        th(446, 464.1, rec.get("emergency_relation"), 9.5)
        th(111, 442.3, rec.get("emergency_address"), 9)
        th(425, 442.3, rec.get("emergency_phone"), 9)
        # marital ticks
        if _is(rec, "marital_status", "โสด", "Single", "single"):
            mark(152.8, 486.3)
        if _is(rec, "marital_status", "สมรส", "Married", "married"):
            mark(220.0, 486.9)
        if _is(rec, "marital_status", "หย่า", "Divorce", "divorce"):
            mark(294.4, 486.9)
        # ---- structured tables from the application form (JSON rows) ----
        import json as _json

        def _rows(v):
            try:
                r = _json.loads(v) if v else []
                return r if isinstance(r, list) else []
            except Exception:
                return []

        def cell(x, y, t, sz=7.8, maxw=None):
            t = "" if t is None else str(t)
            if maxw:
                while t and c.stringWidth(t, "SarabunFM", sz) > maxw:
                    t = t[:-1]
            if t:
                c.setFont("SarabunFM", sz)
                c.drawString(x, y, t)

        for i, r in enumerate(_rows(rec.get("prev_employment"))[:3]):
            y = [333, 305, 277][i]
            cell(66, y, r.get("ปีจาก/From"), 7.8, 40)
            cell(111, y, r.get("ปีถึง/To"), 7.8, 30)
            cell(146, y, r.get("บริษัท/Company"), 7.8, 100)
            cell(252, y, r.get("ธุรกิจ/Business"), 7.8, 96)
            cell(352, y, r.get("ตำแหน่ง/Position"), 7.8, 60)
            cell(415, y, r.get("เงินเดือน/Salary"), 7.8, 60)
            cell(479, y, r.get("เหตุที่ออก/Reason"), 7.8, 76)
        for i, r in enumerate(_rows(rec.get("education_history"))[:4]):
            y = [205, 184, 163, 141][i]
            cell(66, y, r.get("ระดับ/Level"), 7.8, 92)
            cell(166, y, r.get("ปีจบ/Year"), 7.8, 82)
            cell(255, y, r.get("สถานศึกษา/Institute"), 7.8, 94)
            cell(355, y, r.get("คณะ-สาขา/Faculty"), 7.8, 100)
            cell(480, y, r.get("เกรด/GPA"), 7.8, 70)
        for i, r in enumerate(_rows(rec.get("other_qualifications"))[:3]):
            y = [99.5, 77.7, 56.1][i]
            cell(135, y, r.get("ประเภท/Type"), 8.5, 120)
            cell(345, y, r.get("สถาบัน/Institute"), 8.5, 100)
            cell(492, y, r.get("ปี/Year"), 8.5, 50)
        c.showPage()

        # ---------------- PAGE 1 ----------------
        def yn(field, yes_xy, no_xy, detail_xy=None):
            v = rec.get(field)
            if v:
                mark(*yes_xy)
                if detail_xy:
                    th(detail_xy[0], detail_xy[1], str(v), 9)
            else:
                mark(*no_xy)

        yn("health_injury", (119.8, 727.9), (58.6, 727.4), (345, 728.0))
        yn("health_illness", (120.4, 695.0), (58.6, 693.8), (345, 694.1))
        yn("health_drugs", (119.8, 661.1), (58.6, 660.0), (345, 660.5))
        yn("health_chronic", (120.4, 628.8), (58.6, 628.8), (345, 627.9))
        if _is(rec, "health_medical_exam_consent", "ยินยอม", "Yes", "yes"):
            mark(58.6, 594.7)
        elif _is(rec, "health_medical_exam_consent", "ไม่", "No", "no"):
            mark(135.4, 595.8)
        if rec.get("driver_licence"):
            mark(116.8, 512.7)
            th(345, 512.9, str(rec.get("driver_licence")), 9)
        else:
            mark(58.6, 512.7)
        yn("ever_discharged", (118.0, 484.5), (58.6, 482.4), (345, 482.9))
        yn("criminal_record", (118.0, 445.8), (58.6, 445.2), (345, 444.2))
        if _is(rec, "can_shift_work", "ได้", "Yes", "yes"):
            mark(59.6, 414.4)
        elif _is(rec, "can_shift_work", "ไม่", "No", "no"):
            mark(116.8, 414.4)
        th(240, 394.6, rec.get("hobbies"), 9.5)
        sa = str(rec.get("start_availability") or "")
        if _is(rec, "start_availability", "ทันที", "Now", "now"):
            mark(60.6, 261.9)
        elif "15" in sa:
            mark(136.7, 260.9)
        elif "30" in sa:
            mark(278.1, 260.9)
        elif _is(rec, "start_availability", "อื่น", "Other", "other"):
            mark(429.1, 261.9)
            th(505, 260.3, sa, 9)
        th(340, 104.1, rec.get("emp_name_th"))
        th(500, 104.1, rec.get("_app_date"), 9.5)
        c.showPage()
        c.save()
        buf.seek(0)
        ov = PdfReader(buf)
        w.pages[0].merge_page(ov.pages[0])
        w.pages[1].merge_page(ov.pages[1])
        out = io.BytesIO()
        w.write(out)
        return out.getvalue()
    except Exception:
        return None


# ============================================================ เอกสารแนบท้าย (FAITHFUL)
def render_addendum_pdf(rec: dict):
    rec = rec or {}
    """Overlay onto the REAL เอกสารแนบท้าย (Additional Document) — the 2-page
    PDPA disclosure that accompanies FM-HR-003. The six disclosure answers and
    the signature are completed by hand; the system prints the applicant's name
    in the '(...)' under the signature. Returns bytes, or None if unavailable."""
    import os
    import io
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl = os.path.join(root, "assets", "forms", "addendum_template.pdf")
    font = os.path.join(root, "assets", "fonts", "Sarabun-Regular.ttf")
    if not (os.path.exists(tpl) and os.path.exists(font)):
        return None
    try:
        pdfmetrics.registerFont(TTFont("SarabunAdd", font))
    except Exception:
        pass
    W, H = 595.56, 842.52
    try:
        r = PdfReader(tpl)
        w = PdfWriter()
        w.append(r)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(W, H))
        c.showPage()                       # page 0 — hand-completed
        name = (rec.get("emp_name_th") or "").strip()
        if name:
            c.setFont("SarabunAdd", 12)
            c.drawCentredString(206.8, 779.0, name)
        c.showPage()
        c.save()
        buf.seek(0)
        ov = PdfReader(buf)
        w.pages[0].merge_page(ov.pages[0])
        w.pages[1].merge_page(ov.pages[1])
        out = io.BytesIO()
        w.write(out)
        return out.getvalue()
    except Exception:
        return None


# ============================================================ FM-HR-031 OT form
# Added for req. 5/6: print the OT requisition (FM-HR-031) and the shift-change
# request as A4 HTML with the AMS letterhead (logo + entity) and DCC footer.
# Both go through html_to_pdf() (WeasyPrint) with the browser-print fallback.
import os as _os
import base64 as _b64
from lib import ot_rules as _otr


def _logo_uri():
    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    for n in ("logo_transparent.png", "logo.png"):
        p = _os.path.join(root, "assets", n)
        if _os.path.exists(p):
            return "data:image/png;base64," + \
                _b64.b64encode(open(p, "rb").read()).decode("ascii")
    return ""


def _ams_header(title_th, title_en, form_no, rev="Rev.00", doc_no=None):
    logo = _logo_uri()
    img = (f"<img src='{logo}' style='height:44px'/>" if logo else "")
    doc_line = (f"<br><b style='color:#15294D'>เลขที่/Doc: {_e(doc_no)}</b>"
                if doc_no else "")
    return f"""
    <div style="display:flex;align-items:center;justify-content:space-between;
         border-bottom:2px solid #15294D;padding-bottom:6px;margin-bottom:8px">
      <div style="width:130px">{img}</div>
      <div style="text-align:center;flex:1">
        <div style="font-weight:800;font-size:13.5px;color:#15294D">
          ANCA Manufacturing Solutions (Thailand) Ltd.</div>
        <div style="font-weight:700;font-size:13px;margin-top:2px">{title_th}</div>
        <div style="font-size:11px;color:#333">{title_en}</div>
      </div>
      <div style="width:130px;text-align:right;font-size:11px;color:#333">
        {form_no}<br>{rev}{doc_line}</div>
    </div>"""


def _ams_footer(form_no, rev="Rev.00"):
    return (f"<div style='margin-top:20px;border-top:1px solid #999;"
            f"padding-top:4px;font-size:9.5px;color:#666;display:flex;"
            f"justify-content:space-between'><span>{form_no} {rev} · "
            f"ANCA Manufacturing Solutions (Thailand) Ltd.</span>"
            f"<span>พิมพ์จากระบบ AMS HRM</span></div>")


def _sig_row(*labels):
    cells = "".join(
        f"<div style='text-align:center;width:{int(100/len(labels))}%'>"
        f"<div style='margin-top:34px;border-top:1px dotted #333;"
        f"width:78%;margin-left:auto;margin-right:auto'></div>"
        f"<div style='font-size:11px;margin-top:3px'>{l}</div>"
        f"<div style='font-size:10px;color:#666'>วันที่ / Date ............</div>"
        f"</div>" for l in labels)
    return (f"<div style='display:flex;justify-content:space-between;"
            f"margin-top:18px'>{cells}</div>")


def render_ot_requisition(rec: dict, row: dict, lang="th") -> str:
    """FM-HR-031 — Overtime & Holiday Working Requisition Form (one staff row),
    with the Work Order No. and OT-type columns (req. 5)."""
    rec = rec or {}
    row = row or {}
    name = rec.get("emp_name_en") or rec.get("emp_name_th") or ""
    dept = rec.get("dept_location") or ""
    emp_no = rec.get("emp_no") or row.get("emp_no") or ""
    shift_lbl = _otr.shift_label(row.get("shift"), lang) if row.get("shift") else "—"
    ottype_lbl = _otr.ot_type_label(row.get("ot_type"), lang) \
        if row.get("ot_type") else f"×{row.get('rate', '')}"
    body = _ams_header(
        "แบบคำขอทำงานล่วงเวลาและทำงานในวันหยุด",
        "Overtime &amp; Holiday Working Requisition Form", "FM-HR-031", "Rev.01",
        doc_no=(row or {}).get("doc_no"))
    body += (f"<div class='row'>แผนก (Department): "
             f"<span class='v' style='min-width:220px'>{_e(dept)}</span>"
             f"&nbsp;&nbsp; วันที่ออกเอกสาร (Date): "
             f"<span class='v' style='min-width:110px'>"
             f"{dt.date.today().isoformat()}</span></div>")
    body += f"""
    <table>
      <tr>
        <th style="width:24px">No.</th><th style="width:64px">รหัส<br>Emp&nbsp;ID</th>
        <th>ชื่อ-สกุล / Name</th><th style="width:74px">วันที่<br>Date</th>
        <th style="width:96px">กะ / Shift</th>
        <th style="width:90px">Work&nbsp;Order&nbsp;No.</th>
        <th style="width:150px">ประเภท OT / OT type</th>
        <th style="width:52px">เริ่ม<br>From</th><th style="width:52px">ถึง<br>To</th>
        <th style="width:42px">ชม.<br>Hrs</th>
      </tr>
      <tr>
        <td style="text-align:center">1</td><td>{_e(emp_no)}</td>
        <td>{_e(name)}</td><td style="text-align:center">{_e(row.get('ot_date',''))}</td>
        <td style="font-size:10.5px">{_e(shift_lbl)}</td>
        <td style="text-align:center">{_e(row.get('work_order_no') or '—')}</td>
        <td style="font-size:10.5px">{_e(ottype_lbl)}</td>
        <td style="text-align:center">{_e(row.get('time_from',''))}</td>
        <td style="text-align:center">{_e(row.get('time_to',''))}</td>
        <td style="text-align:center"><b>{_e(row.get('hours',''))}</b></td>
      </tr>
    </table>
    <div class="row">งาน/เหตุผล (Work detail): <span class="v"
       style="min-width:420px">{_e(row.get('reason') or '')}</span></div>
    <div class="small" style="margin-top:6px;line-height:1.55">
      <b>ข้อกำหนด / Notes:</b>
      1) ค่าล่วงเวลา ×1.5 สำหรับหลังเลิกงานวันทำงาน ก่อนเข้างาน และ 8 ชม.แรกในวันหยุด ·
      2) ×3.0 สำหรับชั่วโมงที่เกิน 8 ในวันหยุด ·
      3) พักอย่างน้อย 30 นาทีก่อนเริ่ม OT หลังเลิกงาน ·
      4) ขั้นต่ำ 0.5 ชม. และเป็นทวีคูณของ 0.5 ชม.
    </div>
    """
    body += _sig_row("ผู้ขอ / Requested by", "ผู้บังคับบัญชา / Approved by",
                     "ฝ่ายบุคคล / HR")
    body += _ams_footer("FM-HR-031", "Rev.01")
    return _doc("FM-HR-031 OT Requisition", body)


def render_shift_change(rec: dict, row: dict, lang="th") -> str:
    """Shift Change Request Form — FM-HR-048 (a new AMS DCC form; none existed
    previously). Letterhead + change type + supervisor/manager approval."""
    rec = rec or {}
    row = row or {}
    name = rec.get("emp_name_en") or rec.get("emp_name_th") or \
        row.get("requester_name") or ""
    dept = rec.get("dept_location") or ""
    emp_no = rec.get("emp_no") or row.get("emp_no") or ""
    title = rec.get("title") or ""
    cur_lbl = _otr.shift_label(row.get("current_shift"), lang)
    req_lbl = _otr.shift_label(row.get("requested_shift"), lang)
    is_temp = bool(row.get("date_to"))
    eff = row.get("date_from", "")
    if row.get("date_to"):
        eff += f" → {row.get('date_to')}"
    body = _ams_header("แบบคำขอเปลี่ยนกะการทำงาน",
                       "Shift Change Request Form", "FM-HR-048", "Rev.00",
                       doc_no=(row or {}).get("doc_no"))
    body += f"""
    <table>
      <tr><th style="width:130px">รหัสพนักงาน / Emp ID</th><td>{_e(emp_no)}</td>
          <th style="width:120px">แผนก / Dept</th><td>{_e(dept)}</td></tr>
      <tr><th>ชื่อ-สกุล / Name</th><td>{_e(name)}</td>
          <th>ตำแหน่ง / Position</th><td>{_e(title)}</td></tr>
    </table>
    <h2>รายละเอียดการขอเปลี่ยนกะ / Shift change details</h2>
    <div class="row" style="margin-top:2px">ประเภท / Type:
      &nbsp; {_cb(not is_temp)} ถาวร (Permanent)
      &nbsp;&nbsp; {_cb(is_temp)} ชั่วคราว (Temporary)</div>
    <div class="row">กะปัจจุบัน (Current shift):
       <span class="v" style="min-width:280px">{_e(cur_lbl)}</span></div>
    <div class="row">กะที่ขอเปลี่ยนเป็น (Requested shift):
       <span class="v" style="min-width:280px">{_e(req_lbl)}</span></div>
    <div class="row">มีผลตั้งแต่ (Effective):
       <span class="v" style="min-width:240px">{_e(eff)}</span></div>
    <div class="row">เหตุผล (Reason):
       <span class="v" style="min-width:420px">{_e(row.get('reason') or '')}</span></div>
    <div class="small" style="margin-top:6px">
      กะมาตรฐาน / Standard shifts: กะกลางวัน 07:45–16:25 · กะกลางคืน 23:00–07:40
    </div>
    """
    body += _sig_row("ผู้ขอ / Requested by", "ผู้บังคับบัญชา / Supervisor",
                     "ผู้จัดการ / Manager")
    body += _ams_footer("FM-HR-048", "Rev.00")
    return _doc("Shift Change Request", body)


def render_time_edit(rec: dict, row: dict, lang="th") -> str:
    """Time-edit / time-record request — FM-HR-049 (the DCC template for Time
    Adjustment). Sign-off: supervisor + manager only."""
    rec = rec or {}
    row = row or {}
    name = rec.get("emp_name_en") or rec.get("emp_name_th") or \
        row.get("requester_name") or ""
    dept = rec.get("dept_location") or ""
    emp_no = rec.get("emp_no") or row.get("emp_no") or ""
    title = rec.get("title") or ""
    is_edit = (row.get("doc_type") or "edit") == "edit"
    body = _ams_header("แบบคำขอแก้ไข / ปรับปรุงเวลาทำงาน",
                       "Time Edit / Time Record Request Form",
                       "FM-HR-049", "Rev.00",
                       doc_no=(row or {}).get("doc_no"))
    body += f"""
    <table>
      <tr><th style="width:130px">รหัสพนักงาน / Emp ID</th><td>{_e(emp_no)}</td>
          <th style="width:120px">แผนก / Dept</th><td>{_e(dept)}</td></tr>
      <tr><th>ชื่อ-สกุล / Name</th><td>{_e(name)}</td>
          <th>ตำแหน่ง / Position</th><td>{_e(title)}</td></tr>
    </table>
    <div class="row" style="margin-top:6px">ประเภทเอกสาร / Document type:
      &nbsp; {_cb(is_edit)} ขอแก้ไขเวลาทำงาน (Edit work time)
      &nbsp;&nbsp; {_cb(not is_edit)} ขอบันทึกลงเวลาทำงาน (Record work time)</div>
    <table style="margin-top:6px">
      <tr>
        <th style="width:90px">วันที่ทำงาน<br>Work date</th>
        <th style="width:80px">รหัสกะ<br>Shift</th>
        <th>เวลาที่บันทึกไว้ / Recorded scans</th>
        <th style="width:90px">เวลาเข้าที่ขอ<br>Time in</th>
        <th style="width:90px">เวลาออกที่ขอ<br>Time out</th>
      </tr>
      <tr>
        <td style="text-align:center">{_e(row.get('work_date',''))}</td>
        <td style="text-align:center">{_e(row.get('shift') or '—')}</td>
        <td>{_e(row.get('original_scans') or '—')}</td>
        <td style="text-align:center"><b>{_e(row.get('req_time_in') or '—')}</b></td>
        <td style="text-align:center"><b>{_e(row.get('req_time_out') or '—')}</b></td>
      </tr>
    </table>
    <div class="row">เหตุผล (Reason):
      <span class="v" style="min-width:420px">{_e(row.get('reason') or '')}</span></div>
    """
    body += _sig_row("ผู้บังคับบัญชา / Supervisor", "ผู้จัดการ / Manager")
    body += _ams_footer("FM-HR-049", "Rev.00")
    return _doc("Time Edit Request", body)


def render_leave_requisition(rec: dict, row: dict, lang="th") -> str:
    """Leave request form for a specific leave_requests row (req. 2.5).
    NOTE: assign the official FM-HR number when known."""
    rec = rec or {}
    row = row or {}
    LT = {"annual": "ลาพักร้อน / Annual leave", "sick": "ลาป่วย / Sick leave",
          "business": "ลากิจ / Personal (business) leave",
          "personal": "ลากิจ / Personal leave",
          "maternity": "ลาคลอด / Maternity leave",
          "without_pay": "ลาไม่รับค่าจ้าง / Leave without pay",
          "ordination": "ลาบวช / Ordination leave",
          "military": "ลารับราชการทหาร / Military service leave",
          "other": "อื่นๆ / Other"}
    name = (rec.get("emp_name_en") or rec.get("emp_name_th")
            or row.get("requester_name") or "")
    emp_no = rec.get("emp_no") or row.get("emp_no") or ""
    dept = rec.get("dept_location") or ""
    title = rec.get("title") or ""
    lt = LT.get(row.get("leave_type"), row.get("leave_type") or "—")
    period = {"full": "เต็มวัน / Full day",
              "half_am": "ครึ่งวันเช้า / Morning half",
              "half_pm": "ครึ่งวันบ่าย / Afternoon half"}.get(
                  row.get("period"), row.get("period") or "")
    body = _ams_header("แบบฟอร์มขอลา", "Leave Request Form",
                       "FM-HR-045", "Rev.00",
                       doc_no=(row or {}).get("doc_no"))
    body += f"""
    <table>
      <tr><th style="width:130px">รหัสพนักงาน / Emp ID</th><td>{_e(emp_no)}</td>
          <th style="width:120px">แผนก / Dept</th><td>{_e(dept)}</td></tr>
      <tr><th>ชื่อ-สกุล / Name</th><td>{_e(name)}</td>
          <th>ตำแหน่ง / Position</th><td>{_e(title)}</td></tr>
    </table>
    <table style="margin-top:6px">
      <tr><th style="width:150px">ประเภทการลา / Leave type</th>
          <td colspan="3"><b>{_e(lt)}</b></td></tr>
      <tr><th>ตั้งแต่วันที่ / From</th><td>{_e(row.get('date_from',''))}</td>
          <th style="width:120px">ถึงวันที่ / To</th>
          <td>{_e(row.get('date_to',''))}</td></tr>
      <tr><th>จำนวนวัน / Days</th><td>{_e(row.get('days',''))}</td>
          <th>ช่วงเวลา / Period</th><td>{_e(period)}</td></tr>
    </table>
    <div class="row">เหตุผล / Reason:
      <span class="v" style="min-width:420px">{_e(row.get('reason') or '')}</span>
    </div>
    """
    body += _sig_row("ผู้ขอ / Requested by", "ผู้บังคับบัญชา / Approved by",
                     "ฝ่ายบุคคล / HR")
    body += _ams_footer("FM-HR-045", "Rev.00")
    return _doc("Leave Request", body)
