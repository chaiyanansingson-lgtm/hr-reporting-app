#!/usr/bin/env python3
# scripts/seed_dsd_courses.py
# Loads the five DSD-aligned AMS courses into the live M-Training LMS via the
# real lib.lms_db API (the same schema used in the per-course build sessions).
#
#   python scripts/seed_dsd_courses.py            # create (skips existing)
#   python scripts/seed_dsd_courses.py --replace  # delete + re-create
#
# Course metadata + chapter structure are taken verbatim from the course builds.
# Each course gets a Pre-test (baseline, never blocks) and a Post-test (the DSD
# pass gate). The post-test questions here are GROUNDED in the published chapter
# content but are a compact functional bank — to load the exact bank you filed
# with DSD, drop <code>_testbank.json next to this script (see load_testbank()).
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import lms_db as L          # noqa: E402

ACTOR = "seed:dsd"
HERE = os.path.dirname(os.path.abspath(__file__))


def P(*pages):
    """A 'slides' lesson page list (each entry is one screen of text)."""
    return list(pages)


# Q helpers — mcq1 = single best answer, answer_key = correct option index.
def mcq1(text, options, correct, points=1):
    return {"kind": "mcq1", "text": text, "options": options,
            "answer_key": correct, "points": points}


def mcqN(text, options, correct_list, points=1):
    return {"kind": "mcqN", "text": text, "options": options,
            "answer_key": correct_list, "points": points}


# =====================================================================
# Course definitions: meta + lessons (chapters) + pre/post test banks.
# =====================================================================
COURSES = [
    # ------------------------------------------------------- 1) QC ----
    dict(
        code="AMS-TRN-QC",
        title_th="หลักสูตรการควบคุมคุณภาพ (QC) สำหรับงานผลิต",
        title_en="Quality Control (QC) Competency Programme",
        purpose=("ยกระดับความสามารถผู้ตรวจสอบคุณภาพให้สอดคล้องกับ ISO "
                 "9001:2015 / ISO 14001:2015 · Upskill QC inspectors to ISO "
                 "9001/14001 practice."),
        pass_pct=60,
        meta=dict(dsd_code="", level="กลาง (Intermediate)",
                  course_group="2. การพัฒนาเทคนิคการทำงาน",
                  course_type="Upskill (≥6 ชม.)",
                  occupation_branch="ช่างอุตสาหการ — การควบคุมคุณภาพ / QC",
                  instructor="",
                  objectives=("อ่านแบบงานและสัญลักษณ์ GD&T; ใช้ตาราง AQL "
                              "ISO 2859-1; ประเมิน Gauge R&R; ตรวจจับข้อบกพร่อง "
                              "งานเคลือบ; วิเคราะห์สาเหตุด้วย 5-Why.")),
        chapters=[
            ("CH1 · การอ่านแบบวิศวกรรม / Engineering Drawing Reading",
             P("มุมมองภาพฉาย (orthographic), เส้นบอกขนาด, สเกล และกรอบชื่อแบบ "
               "(title block). Orthographic views, dimensions, scale and the "
               "title block.",
               "อ่านค่าพิกัดความเผื่อ (tolerance) จากแบบ และระบุมิติวิกฤต "
               "(critical dimension) ที่ต้องตรวจ 100%.")),
            ("CH2 · สัญลักษณ์ GD&T / Geometric Dimensioning & Tolerancing",
             P("สัญลักษณ์ควบคุมรูปทรง-ตำแหน่ง: ความตรง ความเรียบ ความกลม "
               "ตำแหน่ง (position) และ datum. Form, orientation, location "
               "controls and datums.",
               "อ่านกรอบควบคุมคุณลักษณะ (feature control frame) และแปลความ "
               "ค่าพิกัดเชิงเรขาคณิต.")),
            ("CH3 · การชักตัวอย่าง AQL (ISO 2859-1) / Acceptance Sampling",
             P("ระดับการตรวจ (inspection level), ขนาดล็อต → ขนาดตัวอย่าง, "
               "และตัวเลข Ac/Re. Lot size → sample size, accept/reject "
               "numbers from the ISO 2859-1 table.",
               "ตัดสิน ยอมรับ/ปฏิเสธ ล็อต จากจำนวนของเสียที่พบเทียบกับ Ac.")),
            ("CH4 · ความละเอียดเกจและ Gauge R&R / Gauge Resolution & R&R",
             P("กฎ 10:1 ของความละเอียดเครื่องมือวัดเทียบพิกัด; แถบความเผื่อ "
               "(tolerance band). The 10:1 resolution rule vs the tolerance.",
               "แปลผล %Gauge R&R: <10% ยอมรับ, 10-30% มีเงื่อนไข, >30% "
               "ไม่ยอมรับ.")),
            ("CH5 · จุดควบคุมการตรวจ / Inspection Control Points",
             P("ลำดับจุดตรวจ: รับเข้า (IQC) → ระหว่างผลิต (IPQC) → ก่อนส่ง "
               "(OQC). Incoming, in-process and outgoing control points.",
               "บันทึกผลและการชี้บ่งสถานะ (ผ่าน/รอ/ไม่ผ่าน) ในแต่ละจุด.")),
            ("CH6 · ข้อบกพร่องงานเคลือบ / Coating & Surface Defects",
             P("ชนิดข้อบกพร่อง: ฟองอากาศ, รอยย่น, ความหนาฟิล์มไม่สม่ำเสมอ "
               "(DFT). Common paint/coating defects and DFT.",
               "ทดสอบการยึดเกาะ (adhesion / cross-cut) และเกณฑ์ตัดสิน.")),
            ("CH7 · การทวนสอบฉลากกับใบสั่งงาน / Label vs Work Order",
             P("เทียบรหัสชิ้นงาน, รุ่น, จำนวน บนฉลากกับใบสั่งงาน. Match part "
               "number, revision and quantity against the work order.",
               "ตัดสิน PROCEED หรือ STOP & VERIFY เมื่อข้อมูลไม่ตรง.")),
            ("CH8 · การวิเคราะห์สาเหตุด้วย 5-Why / Root Cause (5-Why)",
             P("ถาม 'ทำไม' ต่อเนื่องเพื่อหาสาเหตุที่ระบบ ไม่ใช่อาการ. Drill "
               "from symptom to the system root cause.",
               "เชื่อมโยงสาเหตุรากกับการแก้ไข (corrective) และการป้องกัน "
               "(preventive action).")),
        ],
        pre=[
            mcq1("มุมมองภาพฉาย (orthographic projection) ใช้เพื่ออะไร? / What "
                 "are orthographic views used for?",
                 ["แสดงสีของชิ้นงาน / show colour",
                  "แสดงรูปร่าง 3 มิติบนระนาบ 2 มิติ / show a 3-D part in 2-D",
                  "คำนวณราคา / price the part",
                  "ระบุผู้ผลิต / name the maker"], 1),
            mcq1("ในตาราง ISO 2859-1 ขนาดตัวอย่างขึ้นกับสิ่งใด? / In ISO "
                 "2859-1, sample size depends on…",
                 ["สีงาน / colour", "ขนาดล็อตและระดับการตรวจ / lot size & "
                  "inspection level", "ราคางาน / price", "ชื่อลูกค้า / "
                  "customer"], 1),
            mcq1("%Gauge R&R เท่าใดที่ยอมรับได้? / Which %Gauge R&R is "
                 "acceptable?",
                 ["มากกว่า 30% / >30%", "10-30%", "น้อยกว่า 10% / <10%",
                  "ไม่เกี่ยวข้อง / irrelevant"], 2),
            mcq1("เมื่อฉลากไม่ตรงกับใบสั่งงาน ควรทำอย่างไร? / If the label "
                 "mismatches the work order you should…",
                 ["ส่งต่อทันที / proceed", "หยุดและทวนสอบ / STOP & VERIFY",
                  "ทิ้งงาน / scrap it", "เปลี่ยนฉลากเอง / relabel it"], 1),
            mcq1("5-Why มีเป้าหมายเพื่ออะไร? / The 5-Why technique aims to…",
                 ["หาคนผิด / blame", "หาสาเหตุที่ระบบ / find the system root "
                  "cause", "เพิ่มความเร็ว / speed up", "ลดราคา / cut cost"], 1),
            mcq1("จุดตรวจ IQC หมายถึง / 'IQC' control point means…",
                 ["ตรวจรับเข้า / incoming inspection", "ตรวจก่อนส่ง / "
                  "outgoing", "ตรวจราคา / price check", "ตรวจสี / colour"], 0),
        ],
        post=[
            mcq1("กรอบชื่อแบบ (title block) มักบอกข้อมูลใด? / The title block "
                 "typically gives…",
                 ["สเกล, หน่วย, รุ่นแบบ / scale, units, revision",
                  "สีงาน / colour", "ราคาตลาด / market price",
                  "ชื่อพนักงานตรวจ / inspector name only"], 0),
            mcq1("สัญลักษณ์ 'position' ใน GD&T ควบคุมสิ่งใด? / GD&T 'position' "
                 "controls…",
                 ["น้ำหนัก / weight", "ตำแหน่งของรูเทียบ datum / a feature's "
                  "location to datum", "สี / colour", "ราคา / price"], 1),
            mcq1("ถ้าพบของเสีย 3 ชิ้น และ Ac=2, Re=3 ผลคือ / With 3 "
                 "defectives and Ac=2 Re=3, the lot is…",
                 ["ยอมรับ / accept", "ปฏิเสธ / reject", "ตรวจซ้ำทั้งหมด / "
                  "100% resort", "ไม่ตัดสิน / no decision"], 1),
            mcq1("กฎ 10:1 ของเครื่องมือวัดหมายถึง / The 10:1 gauge rule "
                 "means…",
                 ["เครื่องมือเร็วกว่า 10 เท่า / 10× faster",
                  "ความละเอียดควรละเอียดกว่าพิกัด ~10 เท่า / resolution ~10× "
                  "finer than tolerance", "ราคาถูกกว่า 10 เท่า / 10× cheaper",
                  "ตรวจ 10 ชิ้น / inspect 10 pcs"], 1),
            mcq1("ลำดับจุดควบคุมที่ถูกต้องคือ / The correct control-point "
                 "order is…",
                 ["OQC → IPQC → IQC", "IQC → IPQC → OQC", "IPQC → IQC → OQC",
                  "สุ่มอิสระ / random"], 1),
            mcq1("การทดสอบ cross-cut ใช้วัดสิ่งใดของงานเคลือบ? / A cross-cut "
                 "test measures coating…",
                 ["ความหนา / thickness", "การยึดเกาะ / adhesion", "สี / "
                  "colour", "ราคา / cost"], 1),
            mcqN("ข้อใดเป็นข้อบกพร่องงานเคลือบ (เลือกได้หลายข้อ) / Which are "
                 "coating defects (select all)?",
                 ["ฟองอากาศ / blistering", "รอยย่น / wrinkling",
                  "มิติถูกต้อง / correct size", "ฟิล์มบางเกิน / low DFT"],
                 [0, 1, 3]),
            mcq1("DFT ย่อมาจาก / 'DFT' stands for…",
                 ["Daily Fault Tracking", "Dry Film Thickness",
                  "Defect Free Test", "Data Form Template"], 1),
            mcq1("ถ้ารหัสรุ่น (revision) บนฉลากไม่ตรงใบสั่งงาน ต้อง / If the "
                 "revision on the label differs from the work order you…",
                 ["ส่งต่อ / proceed", "หยุดและทวนสอบกับผู้วางแผน / stop & "
                  "verify with planning", "แก้ฉลากเอง / edit the label",
                  "ทิ้ง / scrap"], 1),
            mcq1("ผลของการวิเคราะห์ 5-Why ที่ดีควรนำไปสู่ / A good 5-Why "
                 "should lead to…",
                 ["การตำหนิ / blame", "การแก้ไขและป้องกันที่ระบบ / corrective "
                  "+ preventive action", "การลดราคา / price cut",
                  "การหยุดสายการผลิตถาวร / permanent stop"], 1),
        ],
    ),
    # ------------------------------------------------ 2) AI Leadership ----
    dict(
        code="AMS-DIGI-001",
        title_th="ภาวะผู้นำยุค AI เพื่อผลิตภาพและการลงมือทำของทีม",
        title_en="AI-Driven Leadership for Team Productivity & Execution",
        purpose=("พัฒนาผู้บริหาร/หัวหน้างานให้ใช้ AI และระบบอัตโนมัติยกระดับ "
                 "ผลิตภาพทีม · Equip managers to use AI & automation to lift "
                 "team productivity."),
        pass_pct=60,
        meta=dict(dsd_code="", level="สูง (Advanced)",
                  course_group="5. เทคโนโลยีสารสนเทศและโปรแกรมคอมพิวเตอร์",
                  course_type="Upskill (≥6 ชม.)",
                  occupation_branch="การประยุกต์ใช้ AI / Applied AI",
                  instructor="",
                  objectives=("ใช้ AI ช่วยสื่อสาร-ตัดสินใจ; เขียน prompt "
                              "อย่างปลอดภัยตาม PDPA; อ่านโค้ด Python พื้นฐาน; "
                              "ออกแบบ automation; ทำ roadmap AI 30/90/365 วัน.")),
        chapters=[
            ("CH1 · พื้นฐานภาวะผู้นำยุค AI / AI Leadership Fundamentals",
             P("Industry 4.0 → 5.0 และอนุกรม AI ⊃ ML ⊃ DL ⊃ GenAI. The "
               "industrial timeline and the AI taxonomy.",
               "จุดแข็ง คน vs AI: AI เป็นเครื่องมือ คนเป็นผู้รับผิดชอบ. "
               "Human-vs-AI strengths; AI is a tool, humans are accountable.")),
            ("CH2 · ทีมสมรรถนะสูง / High-Performance Teams",
             P("พีระมิดพื้นฐานทีม และตาราง RACI (AI = Tool, ไม่เป็น "
               "Accountable). Team foundations and a RACI where AI is never "
               "Accountable.",
               "วงจรการประชุมที่มีประสิทธิภาพ. The meeting lifecycle.")),
            ("CH3 · การลงมือทำและจัดลำดับงาน / Execution & Prioritisation",
             P("เมทริกซ์ Eisenhower 2×2, หลัก Pareto 80/20, วงจร PDCA. "
               "Eisenhower matrix, Pareto, PDCA.",
               "แปลงกลยุทธ์เป็นงานที่ทำได้จริงและติดตามผล.")),
            ("CH4 · วิศวกรรมพรอมป์ / Prompt Engineering",
             P("กายวิภาคพรอมป์ R+T+C+F (Role, Task, Context, Format). The "
               "R+T+C+F prompt anatomy.",
               "กฎความปลอดภัยข้อมูลตาม PDPA: ห้ามใส่ข้อมูลส่วนบุคคล/ความลับ. "
               "PDPA safety: never paste personal or confidential data.")),
            ("CH5 · พื้นฐาน Python (อ่านได้ ไม่ต้องเขียน) / Python Basics "
             "(read-not-write)",
             P("อ่านฟังก์ชันตัวอย่าง check_fatigue ที่ประเมินความล้าจาก OT. "
               "Read an annotated OT-fatigue function.",
               "เข้าใจตัวแปร เงื่อนไข และผลลัพธ์ โดยไม่ต้องเขียนโค้ดเอง.")),
            ("CH6 · ระบบอัตโนมัติและ Low-Code / Automation & Low-Code",
             P("ลำดับ ทริกเกอร์ → เงื่อนไข → การกระทำ (trigger→condition→"
               "action). The automation flow.",
               "เปรียบเทียบเครื่องมือ low-code และเลือกใช้ให้เหมาะงาน.")),
            ("CH7 · การตัดสินใจด้วยข้อมูล / Decision-Making & Analytics",
             P("OEE = Availability × Performance × Quality, อ่านแนวโน้ม KPI "
               "เทียบเป้า. OEE and reading KPI trends vs target.",
               "กับดักข้อมูลที่พบบ่อยและวิธีหลีกเลี่ยง.")),
            ("CH8 · เวิร์กช็อป Roadmap ผู้นำ AI / AI Leadership Roadmap",
             P("ค้นหา pain point, เมทริกซ์ผลกระทบ-ความพยายาม, แผน 30/90/365 "
               "วัน. Pain points, impact-vs-effort, the 30/90/365 horizon.",
               "AI Transformation Canvas และการคำนวณ ROI อย่างง่าย (บาท).")),
        ],
        pre=[
            mcq1("ในการใช้ AI ใครคือผู้รับผิดชอบการตัดสินใจ? / When using AI, "
                 "who is accountable for the decision?",
                 ["AI", "คน/ผู้บริหาร / the human manager", "ผู้ขายซอฟต์แวร์ / "
                  "the vendor", "ไม่มีใคร / no one"], 1),
            mcq1("องค์ประกอบใดอยู่ในกายวิภาคพรอมป์ R+T+C+F? / Which is part of "
                 "the R+T+C+F prompt anatomy?",
                 ["Revenue", "Role-Task-Context-Format", "Risk-Time",
                  "Rate-Total"], 1),
            mcq1("ตาม PDPA สิ่งใดห้ามใส่ในพรอมป์? / Under PDPA, what must you "
                 "NOT paste into a prompt?",
                 ["คำถามทั่วไป / a general question", "ข้อมูลส่วนบุคคล/ความลับ "
                  "/ personal or confidential data", "หัวข้อประชุม / a meeting "
                  "topic", "สูตรคำนวณ / a formula"], 1),
            mcq1("OEE คำนวณจาก / OEE is calculated as…",
                 ["A + P + Q", "Availability × Performance × Quality",
                  "OT × คน / OT × heads", "ราคา ÷ จำนวน / price ÷ qty"], 1),
            mcq1("เมทริกซ์ Eisenhower ใช้จัดลำดับงานตามสิ่งใด? / The "
                 "Eisenhower matrix sorts tasks by…",
                 ["ราคา / price", "ความเร่งด่วน × ความสำคัญ / urgency × "
                  "importance", "สี / colour", "จำนวนคน / headcount"], 1),
            mcq1("ในแผน roadmap '30/90/365' หมายถึงอะไร? / In a roadmap, "
                 "'30/90/365' refers to…",
                 ["ราคา / prices", "ช่วงเวลาเป็นวัน / day horizons",
                  "จำนวนคน / headcounts", "รหัสเครื่อง / machine codes"], 1),
        ],
        post=[
            mcq1("ในตาราง RACI ที่ใช้ AI, AI ควรมีบทบาทใด? / In an AI-aware "
                 "RACI, AI should be…",
                 ["Accountable", "เครื่องมือ/สนับสนุน ไม่ใช่ Accountable / a "
                  "Tool, never Accountable", "ผู้อนุมัติ / the approver",
                  "เจ้าของงบ / the budget owner"], 1),
            mcq1("หลัก Pareto (80/20) แนะนำให้โฟกัสที่ / Pareto (80/20) says "
                 "focus on…",
                 ["ทุกงานเท่ากัน / everything equally", "งานส่วนน้อยที่ให้ผล "
                  "ส่วนใหญ่ / the few causes driving most results",
                  "งานที่ถูกที่สุด / the cheapest tasks", "งานสุดท้าย / the "
                  "last task"], 1),
            mcq1("วงจร PDCA ย่อมาจาก / PDCA stands for…",
                 ["Plan-Do-Check-Act", "Price-Demand-Cost-Audit",
                  "Plan-Deliver-Close-Audit", "Predict-Design-Code-Apply"], 0),
            mcq1("ฟังก์ชัน check_fatigue ในบทเรียนใช้ประเมินสิ่งใด? / The "
                 "check_fatigue example evaluates…",
                 ["ราคาวัตถุดิบ / material price", "ความล้าจากชั่วโมง OT / "
                  "fatigue from OT hours", "อุณหภูมิ / temperature",
                  "จำนวนของเสีย / defect count"], 1),
            mcq1("ลำดับการทำงานของ automation คือ / The automation flow is…",
                 ["action → condition → trigger", "trigger → condition → "
                  "action", "condition → action → trigger", "สุ่ม / random"],
                 1),
            mcq1("AI Transformation Canvas ใช้เพื่ออะไร? / The AI "
                 "Transformation Canvas is used to…",
                 ["คำนวณภาษี / compute tax", "วางแผนนำ AI มาใช้อย่างเป็นระบบ / "
                  "plan an AI initiative", "ออกแบบโลโก้ / design a logo",
                  "จัดตารางกะ / roster shifts"], 1),
            mcqN("ข้อใดเป็น 'กับดักข้อมูล' ที่ควรระวัง (เลือกได้หลายข้อ) / "
                 "Which are data traps to avoid (select all)?",
                 ["สรุปจากตัวอย่างน้อยเกินไป / too-small sample",
                  "สับสนสหสัมพันธ์กับสาเหตุ / correlation ≠ causation",
                  "เทียบกับเป้าเสมอ / always compare to target",
                  "เลือกช่วงเวลาที่เข้าข้างตัวเอง / cherry-picked window"],
                 [0, 1, 3]),
            mcq1("เป้าหมายของบทที่ 8 (capstone) คือ / The Chapter-8 capstone "
                 "asks you to produce…",
                 ["รายงานการเงิน / a finance report", "แผน AI หนึ่งหน้า / a "
                  "credible one-page AI plan", "ใบลา / a leave form",
                  "ผังองค์กร / an org chart"], 1),
            mcq1("DSD นับชั่วโมงเรียนของหลักสูตรนี้จากสิ่งใด? / DSD counts this "
                 "course's hours from…",
                 ["เวลาเปิดหน้าจอ / screen-open time", "เวลาดูวิดีโอจริง / "
                  "actual video watch-time", "จำนวนพรอมป์ / prompts written",
                  "คะแนนสอบ / test score"], 1),
            mcq1("เกณฑ์ผ่านของ DSD สำหรับหลักสูตรนี้คือ / The DSD pass gate "
                 "here is…",
                 ["ดูวิดีโอ 50% / 50% video", "ดูวิดีโอครบ 100% และ Post-test "
                  "≥ 60% / 100% video + post-test ≥60%", "เข้าเรียน 1 ครั้ง / "
                  "one login", "ทำแบบสอบถาม / a survey"], 1),
        ],
    ),
    # ----------------------------------------- 3) Supply Chain & Logistics ----
    dict(
        code="AMS-TRN-SCL",
        title_th="หลักสูตรซัพพลายเชนและโลจิสติกส์",
        title_en="Supply Chain & Logistics Programme",
        purpose=("สร้างความเข้าใจซัพพลายเชนตั้งแต่จัดซื้อถึงส่งมอบ และการวัดผล "
                 "· End-to-end supply-chain literacy from sourcing to "
                 "delivery."),
        pass_pct=60,
        meta=dict(dsd_code="", level="กลาง (Intermediate)",
                  course_group="2. การพัฒนาเทคนิคการทำงาน",
                  course_type="Upskill (≥6 ชม.)",
                  occupation_branch="โลจิสติกส์ — ซัพพลายเชน / Supply Chain",
                  instructor="",
                  objectives=("เข้าใจกระบวนการจัดซื้อ-คลัง-ขนส่ง; วางแผนอุปสงค์; "
                              "อ่าน KPI โลจิสติกส์ (OTD, สินค้าคงคลัง, ต้นทุน).")),
        chapters=[
            ("M1 · พื้นฐานซัพพลายเชน / Supply Chain Fundamentals",
             P("องค์ประกอบและการไหลของสินค้า-ข้อมูล-เงิน (flows). The three "
               "flows: goods, information, cash.",
               "บทบาทของโลจิสติกส์ใน AMS: packing, transport, warehouse.")),
            ("M2 · การจัดซื้อและการจัดหา / Procurement & Sourcing",
             P("วงจรจัดซื้อ: PR → PO → รับของ → จ่ายเงิน. Purchase-to-pay.",
               "การคัดเลือกและประเมินผู้ขาย (supplier evaluation).")),
            ("M3 · การบริหารสินค้าคงคลัง / Inventory Management",
             P("ABC analysis, จุดสั่งซื้อ (reorder point), safety stock. ABC, "
               "reorder point and safety stock.",
               "ต้นทุนการถือครองและการนับสต๊อก (cycle count).")),
            ("M4 · การจัดการคลังสินค้า / Warehousing",
             P("ผังคลัง, การจัดเก็บ, FIFO/FEFO, การหยิบ-แพ็ค. Layout, "
               "put-away, FIFO/FEFO, pick-pack.",
               "ความปลอดภัยและความถูกต้องของสต๊อก (accuracy).")),
            ("M5 · การขนส่งและการกระจายสินค้า / Transportation & Distribution",
             P("รูปแบบการขนส่งและการวางแผนเส้นทาง. Transport modes and route "
               "planning.",
               "เอกสารขนส่งและการส่งมอบตรงเวลา (OTD).")),
            ("M6 · การวางแผนอุปสงค์ / Demand Planning & Forecasting",
             P("วิธีพยากรณ์เบื้องต้นและความคลาดเคลื่อน. Basic forecasting and "
               "error.",
               "เชื่อมโยงแผนอุปสงค์กับการจัดซื้อและคลัง.")),
            ("M7 · ลีนและการวัดผลซัพพลายเชน / Lean & SC Performance",
             P("ความสูญเปล่า 7 ประการ และการปรับปรุงต่อเนื่อง. The 7 wastes "
               "and continuous improvement.",
               "KPI หลัก: OTD, inventory turns, logistics cost %.")),
            ("M8 · ซัพพลายเชนดิจิทัลและกรณีศึกษา / Digital SC & Capstone",
             P("ระบบ ERP/บาร์โค้ดและการมองเห็นข้อมูล (visibility). ERP, "
               "barcoding and visibility.",
               "กรณีศึกษา: ปิดช่องว่าง KPI ของแผนกซัพพลายเชน AMS.")),
        ],
        pre=[
            mcq1("ซัพพลายเชนเกี่ยวข้องกับการไหลของสิ่งใด? / A supply chain "
                 "manages the flow of…",
                 ["สินค้าเท่านั้น / goods only", "สินค้า ข้อมูล และเงิน / "
                  "goods, information and cash", "เงินเท่านั้น / cash only",
                  "คนเท่านั้น / people only"], 1),
            mcq1("วงจร purchase-to-pay เริ่มต้นด้วยเอกสารใด? / Purchase-to-pay "
                 "starts with a…",
                 ["ใบสั่งซื้อ PO / PO", "ใบขอซื้อ PR / purchase requisition",
                  "ใบกำกับภาษี / invoice", "ใบส่งของ / delivery note"], 1),
            mcq1("ABC analysis ใช้จัดกลุ่มสินค้าคงคลังตามสิ่งใด? / ABC "
                 "analysis groups stock by…",
                 ["สี / colour", "มูลค่า/ความสำคัญ / value-importance",
                  "ขนาด / size", "ผู้ขาย / supplier"], 1),
            mcq1("FIFO ในคลังหมายถึง / FIFO in a warehouse means…",
                 ["หยิบของใหม่ก่อน / newest first", "หยิบของเก่าก่อน / first "
                  "in, first out", "หยิบของแพงก่อน / dearest first", "สุ่ม / "
                  "random"], 1),
            mcq1("KPI 'OTD' วัดสิ่งใด? / The KPI 'OTD' measures…",
                 ["ต้นทุน / cost", "การส่งมอบตรงเวลา / on-time delivery",
                  "คุณภาพ / quality", "จำนวนคน / headcount"], 1),
            mcq1("safety stock มีไว้เพื่ออะไร? / Safety stock exists to…",
                 ["ลดราคา / cut price", "กันการขาดสต๊อกจากความผันผวน / buffer "
                  "against variability", "เพิ่มพื้นที่ / add space",
                  "ลดคุณภาพ / lower quality"], 1),
        ],
        post=[
            mcq1("ข้อใดคือเป้าหมายหลักของการบริหารซัพพลายเชน? / A core goal of "
                 "supply-chain management is…",
                 ["เพิ่มสต๊อกให้มากที่สุด / maximise stock", "ส่งมอบให้ถูกต้อง "
                  "ตรงเวลา ต้นทุนเหมาะสม / right goods, on time, at right "
                  "cost", "เพิ่มจำนวนผู้ขาย / maximise suppliers", "ลดคุณภาพ / "
                  "lower quality"], 1),
            mcq1("reorder point ขึ้นกับสิ่งใดเป็นหลัก? / The reorder point "
                 "depends mainly on…",
                 ["สีสินค้า / colour", "อัตราการใช้ × lead time + safety "
                  "stock / usage × lead time + safety stock",
                  "ราคาขาย / sale price", "ชื่อผู้ขาย / supplier name"], 1),
            mcq1("FEFO เหมาะกับสินค้าประเภทใด? / FEFO suits goods that…",
                 ["ไม่มีวันหมดอายุ / never expire", "มีวันหมดอายุ / have an "
                  "expiry date", "ราคาสูง / are expensive", "ขนาดใหญ่ / are "
                  "large"], 1),
            mcq1("inventory turns สูงโดยทั่วไปหมายถึง / High inventory turns "
                 "generally indicate…",
                 ["สต๊อกค้างนาน / slow-moving stock", "การหมุนเวียนสต๊อกที่ดี "
                  "/ efficient stock movement", "คุณภาพต่ำ / low quality",
                  "ต้นทุนขนส่งสูง / high freight"], 1),
            mcq1("เอกสารใดยืนยันการรับสินค้าเข้าคลัง? / Which document confirms "
                 "goods received?",
                 ["PR", "GR / goods-receipt note", "ใบลา / leave form",
                  "WPS"], 1),
            mcq1("ความสูญเปล่า (waste) ในแนวคิดลีนรวมถึงข้อใด? / Lean 'waste' "
                 "includes…",
                 ["การรอคอย / waiting", "การเพิ่มคุณภาพ / adding quality",
                  "การฝึกอบรม / training", "การวางแผน / planning"], 0),
            mcqN("KPI ใดที่ฝ่ายโลจิสติกส์ AMS ติดตาม (เลือกได้หลายข้อ) / Which "
                 "KPIs does AMS logistics track (select all)?",
                 ["OTD ของผู้ขาย / supplier OTD", "มูลค่าสินค้าคงคลัง / "
                  "inventory value", "สีอาคาร / building colour",
                  "ต้นทุนโลจิสติกส์ % / logistics cost %"], [0, 1, 3]),
            mcq1("route planning ที่ดีช่วยลดสิ่งใด? / Good route planning "
                 "reduces…",
                 ["คุณภาพ / quality", "ระยะทาง-เวลา-ต้นทุนขนส่ง / "
                  "distance-time-freight cost", "จำนวนคำสั่งซื้อ / order "
                  "count", "ความปลอดภัย / safety"], 1),
            mcq1("การพยากรณ์อุปสงค์ที่แม่นยำช่วยให้ / Accurate demand "
                 "forecasting helps…",
                 ["เพิ่มของเสีย / add scrap", "วางแผนจัดซื้อและคลังได้ดีขึ้น / "
                  "plan procurement & inventory better", "ลดคุณภาพ / lower "
                  "quality", "เพิ่มราคา / raise prices"], 1),
            mcq1("ระบบ ERP ช่วยซัพพลายเชนด้านใดมากที่สุด? / ERP most helps the "
                 "supply chain with…",
                 ["สีหน้าจอ / screen colour", "การมองเห็นข้อมูลแบบรวมศูนย์ / "
                  "centralised data visibility", "การพักร้อน / holidays",
                  "การออกแบบโลโก้ / logo design"], 1),
        ],
    ),
    # --------------------------------- 4) Finance for Non-Finance Managers ----
    dict(
        code="AMS-FIN-001",
        title_th="การเงินสำหรับผู้บริหารที่ไม่ใช่สายการเงิน",
        title_en="Finance for Non-Finance Managers",
        purpose=("ให้ผู้บริหารอ่านงบการเงิน เข้าใจต้นทุน และตัดสินใจเชิงธุรกิจ "
                 "ด้วยข้อมูลการเงิน · Help managers read statements, understand "
                 "cost and decide with financial data."),
        pass_pct=70,
        meta=dict(dsd_code="", level="สูง (Advanced)",
                  course_group="1. การพัฒนาความรู้",
                  course_type="Upskill (≥6 ชม.)",
                  occupation_branch="บริหารธุรกิจ — การเงิน / Finance",
                  instructor="",
                  objectives=("อ่านงบดุล งบกำไรขาดทุน งบกระแสเงินสด; เข้าใจ "
                              "โครงสร้างต้นทุนการผลิต; ทำงบประมาณ; ประเมินการลงทุน "
                              "และตัดสินใจเชิงธุรกิจ.")),
        chapters=[
            ("M1 · พื้นฐานการเงิน / Finance Fundamentals (0.75 ชม.)",
             P("ภาษาการเงิน: สินทรัพย์ หนี้สิน ส่วนของเจ้าของ รายได้ ค่าใช้จ่าย. "
               "Assets, liabilities, equity, revenue, expense.",
               "ความต่างของกำไรกับกระแสเงินสด. Profit is not cash.")),
            ("M2 · งบการเงิน 3 ฉบับ / Financial Statements (1.25 ชม.)",
             P("งบดุล (Balance Sheet), งบกำไรขาดทุน (P&L), งบกระแสเงินสด "
               "(Cash Flow). The three core statements.",
               "ความเชื่อมโยงระหว่างสามงบ. How the three statements link.")),
            ("M3 · โครงสร้างต้นทุนการผลิต / Manufacturing Cost Structure",
             P("วัตถุดิบทางตรง, ค่าแรงทางตรง, ค่าโสหุ้ยการผลิต (overhead). "
               "Direct material, direct labour, overhead.",
               "ต้นทุนคงที่ vs ผันแปร และจุดคุ้มทุน (break-even).")),
            ("M4 · งบประมาณและการพยากรณ์ / Budgeting & Forecasting",
             P("ประเภทงบประมาณและกระบวนการจัดทำ. Budget types and process.",
               "การวิเคราะห์ผลต่าง (variance: actual vs budget).")),
            ("M5 · KPI และความสามารถทำกำไร / KPI & Profitability",
             P("อัตรากำไรขั้นต้น/สุทธิ, ROA, ROE. Gross/net margin, ROA, ROE.",
               "อ่าน KPI การเงินเทียบเป้าและแนวโน้ม.")),
            ("M6 · การวิเคราะห์การลงทุน / Investment Analysis",
             P("ระยะคืนทุน (payback), NPV และ IRR เบื้องต้น. Payback, NPV, "
               "IRR basics.",
               "ตัดสินใจลงทุนเครื่องจักรด้วยตัวเลข.")),
            ("M7 · การบริหารกระแสเงินสด / Cash Flow Management",
             P("วงจรเงินสด (cash cycle), ลูกหนี้-เจ้าหนี้-สินค้าคงคลัง. The "
               "cash conversion cycle.",
               "เหตุที่ธุรกิจมีกำไรแต่ขาดเงินสด.")),
            ("M8 · การตัดสินใจเชิงธุรกิจ / Business Decision Making",
             P("ต้นทุนเกี่ยวข้อง (relevant cost), make-or-buy, ต้นทุนจม "
               "(sunk cost). Relevant cost, make-or-buy, sunk cost.",
               "ใช้ข้อมูลการเงินประกอบการตัดสินใจของผู้บริหาร.")),
        ],
        pre=[
            mcq1("สมการบัญชีพื้นฐานคือข้อใด? / The basic accounting equation "
                 "is…",
                 ["สินทรัพย์ = หนี้สิน + ส่วนของเจ้าของ / Assets = Liabilities "
                  "+ Equity", "รายได้ = ต้นทุน / Revenue = Cost",
                  "กำไร = เงินสด / Profit = Cash", "ROA = ROE"], 0),
            mcq1("งบใดแสดงฐานะ ณ วันใดวันหนึ่ง? / Which statement shows the "
                 "position at a point in time?",
                 ["งบกำไรขาดทุน / P&L", "งบดุล / Balance Sheet",
                  "งบกระแสเงินสด / Cash Flow", "งบประมาณ / Budget"], 1),
            mcq1("ต้นทุนการผลิตทางตรงรวมถึงข้อใด? / Direct manufacturing cost "
                 "includes…",
                 ["ค่าการตลาด / marketing", "วัตถุดิบทางตรง + ค่าแรงทางตรง / "
                  "direct material + direct labour", "ดอกเบี้ย / interest",
                  "ภาษีเงินได้ / income tax"], 1),
            mcq1("'กำไรไม่เท่ากับเงินสด' เพราะเหตุใด? / 'Profit ≠ cash' "
                 "because…",
                 ["บัญชีผิด / accounting error", "มีรายการค้างรับ-ค้างจ่ายและ "
                  "ค่าเสื่อม / accruals and depreciation differ from cash",
                  "ภาษีสูง / high tax", "ยอดขายต่ำ / low sales"], 1),
            mcq1("จุดคุ้มทุน (break-even) คือจุดที่ / Break-even is where…",
                 ["กำไรสูงสุด / profit is max", "รายได้ = ต้นทุนรวม / revenue "
                  "= total cost", "เงินสด = 0 / cash = 0", "ขายหมด / "
                  "sold-out"], 1),
            mcq1("payback period วัดสิ่งใด? / Payback period measures…",
                 ["กำไรรวม / total profit", "ระยะเวลาคืนทุน / time to recover "
                  "the investment", "ภาษี / tax", "ยอดขาย / sales"], 1),
        ],
        post=[
            mcq1("งบกำไรขาดทุนแสดงสิ่งใด? / The P&L statement shows…",
                 ["ฐานะ ณ วันหนึ่ง / position at a date", "ผลการดำเนินงานช่วง "
                  "เวลาหนึ่ง / performance over a period", "กระแสเงินสดเท่านั้น "
                  "/ cash only", "งบประมาณ / the budget"], 1),
            mcq1("ค่าโสหุ้ยการผลิต (overhead) คือข้อใด? / Manufacturing "
                 "overhead is…",
                 ["วัตถุดิบทางตรง / direct material", "ต้นทุนการผลิตทางอ้อม "
                  "เช่น ค่าไฟโรงงาน / indirect production cost e.g. factory "
                  "power", "ค่าโฆษณา / advertising", "เงินเดือนฝ่ายขาย / sales "
                  "salary"], 1),
            mcq1("อัตรากำไรขั้นต้น (gross margin) คำนวณจาก / Gross margin "
                 "equals…",
                 ["(รายได้ − ต้นทุนขาย) ÷ รายได้ / (revenue − COGS) ÷ revenue",
                  "กำไรสุทธิ ÷ สินทรัพย์ / net profit ÷ assets",
                  "หนี้สิน ÷ ทุน / debt ÷ equity", "เงินสด ÷ รายได้ / cash ÷ "
                  "revenue"], 0),
            mcq1("NPV ที่เป็นบวกบ่งชี้ว่า / A positive NPV indicates…",
                 ["ขาดทุนแน่นอน / certain loss", "โครงการสร้างมูลค่าเพิ่ม / the "
                  "project adds value", "ต้องกู้เพิ่ม / must borrow more",
                  "ภาษีสูง / high tax"], 1),
            mcq1("การวิเคราะห์ผลต่าง (variance) เปรียบเทียบสิ่งใด? / Variance "
                 "analysis compares…",
                 ["ผู้ขายสองราย / two suppliers", "ผลจริงกับงบประมาณ / actual "
                  "vs budget", "สีสองสี / two colours", "ปีสองปี / two "
                  "calendars"], 1),
            mcq1("วงจรเงินสด (cash conversion cycle) สั้นลงโดยทั่วไปหมายถึง / A "
                 "shorter cash conversion cycle generally means…",
                 ["เงินสดตึงตัวขึ้น / tighter cash", "สภาพคล่องดีขึ้น / better "
                  "liquidity", "กำไรลดลง / lower profit", "ภาษีเพิ่ม / more "
                  "tax"], 1),
            mcqN("ข้อใดเป็นต้นทุนคงที่ (เลือกได้หลายข้อ) / Which are fixed "
                 "costs (select all)?",
                 ["ค่าเช่าโรงงาน / factory rent", "เงินเดือนประจำ / salaried "
                  "pay", "วัตถุดิบต่อหน่วย / material per unit",
                  "ค่าเสื่อมเครื่องจักร / machine depreciation"], [0, 1, 3]),
            mcq1("ในการตัดสินใจ make-or-buy ต้นทุนใดที่ 'ไม่' ควรนำมาคิด? / In "
                 "a make-or-buy decision, which cost is irrelevant?",
                 ["ต้นทุนผันแปรเพิ่ม / incremental variable cost",
                  "ต้นทุนจม (sunk cost) / sunk cost", "ราคาซื้อจากภายนอก / "
                  "outside purchase price", "ค่าขนส่ง / freight"], 1),
            mcq1("ROE วัดผลตอบแทนต่อสิ่งใด? / ROE measures the return on…",
                 ["สินทรัพย์รวม / total assets", "ส่วนของเจ้าของ / "
                  "shareholders' equity", "ยอดขาย / sales", "เงินสด / cash"],
                 1),
            mcq1("ธุรกิจที่มีกำไรแต่ขาดเงินสดมักเกิดจาก / A profitable but "
                 "cash-short business often has…",
                 ["ภาษีต่ำ / low tax", "ลูกหนี้/สต๊อกสูงเกินไป / too much tied "
                  "up in receivables/inventory", "ยอดขายต่ำ / low sales",
                  "ต้นทุนต่ำ / low cost"], 1),
        ],
    ),
    # ------------------------------------------------- 5) Welder Upskilling ----
    dict(
        code="AMS-WELD-001",
        title_th="หลักสูตรยกระดับฝีมือช่างเชื่อม (MAG/GMAW)",
        title_en="Welder Upskilling Programme (MAG/GMAW)",
        purpose=("ยกระดับช่างเชื่อมงานแผ่นโลหะและโครงสร้างด้วยกระบวนการ "
                 "MAG/GMAW ตามมาตรฐาน · Upskill sheet-metal/structural welders "
                 "in MAG/GMAW to standard."),
        pass_pct=60,
        meta=dict(dsd_code="", level="ต้น (Basic)",
                  course_group="2. การพัฒนาเทคนิคการทำงาน",
                  course_type="Upskill (≥6 ชม.)",
                  occupation_branch="ช่างอุตสาหการ — ช่างเชื่อม / Welding",
                  instructor="",
                  objectives=("ทำงานปลอดภัยและใช้ PPE; อ่านแบบและสัญลักษณ์ "
                              "การเชื่อม (ISO 2553/AWS A2.4); ตั้งค่าพารามิเตอร์ "
                              "MAG; ตรวจจับข้อบกพร่อง (ISO 5817); ใช้ WPS.")),
        chapters=[
            ("U1 · ความปลอดภัยและ PPE / Safety & PPE",
             P("อันตรายจากงานเชื่อม: ไฟฟ้า ความร้อน แสง UV ควันเชื่อม. "
               "Electrical, heat, UV-arc and fume hazards.",
               "อุปกรณ์ป้องกันส่วนบุคคล (PPE) และการระบายอากาศ.")),
            ("U2 · พื้นฐานการอ่านแบบ / Engineering Drawing Fundamentals",
             P("ภาพฉาย เส้นชนิดต่าง ๆ และมิติ. Orthographic views, line types, "
               "dimensions.",
               "อ่านตำแหน่งและขนาดของแนวเชื่อมจากแบบ.")),
            ("U3 · สัญลักษณ์การเชื่อม / Welding Symbols (ISO 2553 / AWS A2.4)",
             P("กายวิภาคสัญลักษณ์: เส้นอ้างอิง ลูกศร หาง และสัญลักษณ์รอยเชื่อม. "
               "Reference line, arrow, tail and weld symbol.",
               "ตำแหน่งรอบ ๆ เส้นอ้างอิงบอกด้านลูกศร/ตรงข้าม.")),
            ("U4 · วัสดุและกระบวนการ / Materials & Processes",
             P("เหล็กกล้าและการเชื่อมแบบต่าง ๆ; โฟกัส GMAW/MAG สำหรับงานแผ่น. "
               "Steels and processes; MAG focus for sheet metal.",
               "ลวดเชื่อมและแก๊สปกคลุม (shielding gas).")),
            ("U5 · อุปกรณ์และพารามิเตอร์ MAG / MAG Equipment & Parameters",
             P("วงจรเครื่องเชื่อม MAG, แรงดัน-กระแส-ความเร็วป้อนลวด. The MAG "
               "circuit; voltage, current, wire-feed speed.",
               "ผลของพารามิเตอร์ต่อแนวเชื่อม (penetration, bead).")),
            ("U6 · ข้อบกพร่องและการตรวจพินิจ / Defects & Visual Inspection "
             "(ISO 5817)",
             P("ข้อบกพร่อง: รูพรุน, เชื่อมไม่ติด, undercut, spatter. Porosity, "
               "lack of fusion, undercut, spatter.",
               "เกณฑ์ระดับคุณภาพตาม ISO 5817 (B/C/D).")),
            ("U7 · ระบบคุณภาพและ WPS ที่ AMS / Quality & WPS at AMS",
             P("WPS คืออะไรและใช้อย่างไรหน้างาน. What a WPS is and how to "
               "follow it.",
               "การชี้บ่งและบันทึกผลงานเชื่อมตามระบบคุณภาพ.")),
            ("U8 · ทบทวนและทดสอบหลังเรียน / Review & Post-test",
             P("ทบทวนความปลอดภัย แบบ สัญลักษณ์ พารามิเตอร์ และข้อบกพร่อง. "
               "Review safety, drawings, symbols, parameters and defects.",
               "เตรียมความพร้อมสำหรับการประเมินภาคปฏิบัติ.")),
        ],
        pre=[
            mcq1("อันตรายเฉพาะของงานเชื่อม MAG รวมถึงข้อใด? / A hazard specific "
                 "to MAG welding includes…",
                 ["เสียงเพลง / music", "แสง UV จากอาร์กและควันเชื่อม / UV arc "
                  "light and fume", "ฝุ่นกระดาษ / paper dust", "น้ำท่วม / "
                  "flood"], 1),
            mcq1("ในสัญลักษณ์การเชื่อม ส่วนใดชี้ไปยังตำแหน่งรอยเชื่อม? / In a "
                 "weld symbol, which part points to the joint?",
                 ["หาง / the tail", "ลูกศร / the arrow", "เส้นอ้างอิง / the "
                  "reference line", "ตัวเลข / the number"], 1),
            mcq1("กระบวนการเชื่อมหลักสำหรับงานแผ่นที่ AMS คือ / The main "
                 "process for sheet metal at AMS is…",
                 ["SMAW (ธูป)", "GMAW/MAG", "TIG เท่านั้น / TIG only",
                  "การบัดกรี / soldering"], 1),
            mcq1("พารามิเตอร์ใดส่งผลต่อการหลอมลึก (penetration) ของ MAG? / "
                 "Which MAG parameter affects penetration?",
                 ["สีเครื่อง / machine colour", "กระแสและความเร็วป้อนลวด / "
                  "current and wire-feed speed", "ยี่ห้อถุงมือ / glove brand",
                  "อุณหภูมิห้อง / room temperature"], 1),
            mcq1("ISO 5817 เกี่ยวข้องกับสิ่งใด? / ISO 5817 relates to…",
                 ["ราคาลวดเชื่อม / wire price", "ระดับคุณภาพ/ข้อบกพร่องรอยเชื่อม "
                  "/ weld quality levels & imperfections", "สีโรงงาน / factory "
                  "colour", "เวลาพัก / break time"], 1),
            mcq1("WPS ใช้เพื่ออะไร? / A WPS is used to…",
                 ["คำนวณเงินเดือน / compute pay", "กำหนดวิธีเชื่อมที่ผ่านการ "
                  "รับรอง / specify the qualified welding procedure",
                  "สั่งวัตถุดิบ / order material", "จองรถ / book a car"], 1),
        ],
        post=[
            mcq1("ก่อนเริ่มงานเชื่อมควรทำสิ่งใดด้านความปลอดภัยเป็นอันดับแรก? / "
                 "Before welding, the first safety step is to…",
                 ["เปิดเพลง / play music", "ตรวจ PPE และการระบายอากาศ / check "
                  "PPE and ventilation", "เพิ่มกระแสสูงสุด / max the current",
                  "ถอดถุงมือ / remove gloves"], 1),
            mcq1("สัญลักษณ์รอยเชื่อมที่อยู่ 'ใต้' เส้นอ้างอิงหมายถึงด้านใด? / A "
                 "weld symbol BELOW the reference line means…",
                 ["ด้านลูกศร (arrow side) / arrow side", "ด้านตรงข้าม / other "
                  "side", "ทั้งสองด้านเสมอ / always both", "ไม่มีความหมาย / no "
                  "meaning"], 0),
            mcq1("แก๊สปกคลุม (shielding gas) ใน MAG ทำหน้าที่ใด? / In MAG, the "
                 "shielding gas…",
                 ["เพิ่มสี / adds colour", "ปกป้องบ่อหลอมจากอากาศ / protects "
                  "the weld pool from air", "ลดราคา / cuts cost",
                  "เพิ่มน้ำหนัก / adds weight"], 1),
            mcq1("undercut คือข้อบกพร่องลักษณะใด? / Undercut is a defect "
                 "that…",
                 ["ผิวเรียบสมบูรณ์ / a perfect surface", "ร่องกินเนื้อขอบแนว "
                  "เชื่อม / a groove eroded at the weld toe", "สีผิดเพี้ยน / "
                  "wrong colour", "ขนาดใหญ่เกิน / oversize part"], 1),
            mcq1("รูพรุน (porosity) มักเกิดจากสาเหตุใด? / Porosity is often "
                 "caused by…",
                 ["แก๊สปกคลุมไม่พอ/ผิวสกปรก / poor gas shielding or dirty "
                  "surface", "กระแสต่ำเกินเสมอ / always low current",
                  "ถุงมือผิดสี / wrong glove colour", "ห้องเย็น / cold "
                  "room"], 0),
            mcq1("ความเร็วป้อนลวด (wire-feed speed) สัมพันธ์โดยตรงกับสิ่งใด? / "
                 "Wire-feed speed directly affects…",
                 ["สีอาร์ก / arc colour", "กระแสเชื่อมและอัตราการเติมเนื้อ / "
                  "welding current and deposition", "ราคาลวด / wire price",
                  "อุณหภูมิห้อง / room temperature"], 1),
            mcqN("ข้อใดเป็นข้อบกพร่องของรอยเชื่อม (เลือกได้หลายข้อ) / Which are "
                 "weld defects (select all)?",
                 ["รูพรุน / porosity", "เชื่อมไม่ติด / lack of fusion",
                  "แนวเชื่อมสมบูรณ์ / a sound bead", "undercut"], [0, 1, 3]),
            mcq1("ระดับคุณภาพ B ตาม ISO 5817 หมายถึง / Quality level 'B' in "
                 "ISO 5817 means…",
                 ["คุณภาพต่ำสุด / the lowest quality", "ข้อกำหนดเข้มงวดที่สุด / "
                  "the most stringent requirement", "ไม่ตรวจ / no inspection",
                  "เฉพาะงานสี / paint only"], 1),
            mcq1("หากพารามิเตอร์จริงต่างจาก WPS ช่างควร / If actual parameters "
                 "differ from the WPS, the welder should…",
                 ["เชื่อมต่อไป / keep welding", "หยุดและแจ้ง/ปรับให้ตรง WPS / "
                  "stop and correct to the WPS", "เพิ่มกระแสสองเท่า / double "
                  "the current", "เปลี่ยนลวดเอง / swap wire freely"], 1),
            mcq1("การชี้บ่ง (identification) งานเชื่อมมีไว้เพื่ออะไร? / Weld "
                 "identification exists to…",
                 ["เพิ่มความสวยงาม / look nice", "ตรวจสอบย้อนกลับได้ "
                  "(traceability) / enable traceability", "ลดน้ำหนัก / cut "
                  "weight", "เพิ่มราคา / raise price"], 1),
        ],
    ),
]


def load_testbank(code):
    """If <code>_testbank.json sits next to this script, return its
    (pre, post) banks in our question shape — lets you drop in the exact bank
    you filed with DSD without touching this file. Returns None if absent."""
    path = os.path.join(HERE, f"{code}_testbank.json")
    if not os.path.exists(path):
        return None
    data = json.load(open(path, encoding="utf-8"))
    return data.get("pre"), data.get("post")


def _seed_test(cid, title, role, pass_pct, qs):
    tid = L.create_test(cid, title, pass_pct, 3, role != "post", role=role)
    for q in qs:
        L.add_question(tid, q["kind"], q["text"], q.get("options"),
                       q["answer_key"], q.get("points", 1))
    return tid


def seed_course(c, replace=False):
    existing = next((x for x in L.list_courses(active_only=False)
                     if x["code"] == c["code"]), None)
    if existing and not replace:
        print(f"  · {c['code']} already exists (id {existing['id']}) — skip")
        return existing["id"]
    if existing and replace:
        # best-effort wipe of the prior copy
        from lib.db import get_conn, PH
        conn = get_conn(); cur = conn.cursor()
        cid0 = existing["id"]
        cur.execute(f"SELECT id FROM lms_tests WHERE course_id={PH}", (cid0,))
        for (tid,) in cur.fetchall():
            cur.execute(f"DELETE FROM lms_questions WHERE test_id={PH}", (tid,))
        for t in ("lms_tests", "lms_lessons", "lms_assignments",
                  "lms_enrollments"):
            cur.execute(f"DELETE FROM {t} WHERE course_id={PH}", (cid0,))
        cur.execute(f"DELETE FROM lms_courses WHERE id={PH}", (cid0,))
        conn.commit()
        print(f"  · {c['code']} removed prior copy (id {cid0})")

    cid = L.create_course(c["code"], c["title_th"], c["title_en"],
                          c["purpose"], c["pass_pct"], ACTOR)
    L.update_course_meta(cid, **c["meta"])

    bank = load_testbank(c["code"])
    pre_qs, post_qs = (bank if bank else (c["pre"], c["post"]))
    src = "filed testbank.json" if bank else "built-in grounded bank"

    # Lesson 1: pre-test
    pre_tid = _seed_test(cid, "แบบทดสอบก่อนเรียน · Pre-test", "pre", 0, pre_qs)
    L.add_lesson(cid, "test", "แบบทดสอบก่อนเรียน · Pre-test", test_id=pre_tid)
    # Lessons 2..n: chapters as slides
    for title, pages in c["chapters"]:
        L.add_lesson(cid, "slides", title, pages=pages)
    # Final lesson: post-test
    post_tid = _seed_test(cid, "แบบทดสอบหลังเรียน · Post-test", "post",
                          c["pass_pct"], post_qs)
    L.add_lesson(cid, "test", "แบบทดสอบหลังเรียน · Post-test",
                 test_id=post_tid)
    print(f"  ✓ {c['code']} → id {cid} · {len(c['chapters'])} chapters · "
          f"pre {len(pre_qs)}Q + post {len(post_qs)}Q · pass {c['pass_pct']}% "
          f"· {src}")
    return cid


def seed_all(replace=False):
    """Importable entry for the Admin one-click button. Returns a summary:
    {"created": [...codes...], "skipped": [...codes...], "total": n}."""
    before = {x["code"] for x in L.list_courses(active_only=False)}
    created, skipped = [], []
    for c in COURSES:
        if c["code"] in before and not replace:
            skipped.append(c["code"])
        else:
            created.append(c["code"])
        seed_course(c, replace=replace)
    return {"created": created, "skipped": skipped, "total": len(COURSES)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replace", action="store_true",
                    help="delete and re-create courses that already exist")
    args = ap.parse_args()
    print("Seeding DSD courses into M-Training LMS…")
    for c in COURSES:
        seed_course(c, replace=args.replace)
    print("Done. Open Admin → ... or Employees → อบรม to assign & enrol.")


if __name__ == "__main__":
    main()
