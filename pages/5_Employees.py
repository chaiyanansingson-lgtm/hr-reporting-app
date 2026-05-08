"""👥 Employees page - read-only browse of active employees."""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import db
from lib.page_utils import require_login, page_header

st.set_page_config(page_title="Employees", page_icon="👥", layout="wide")
require_login(capability="orgchart.view")
page_header(title_key="employees_title", subtitle_key="employees_subtitle")

emps = db.list_employees(active_only=False)
if not emps:
    st.warning("No employees loaded. Admin must upload a NameList on the Upload Data page.")
    st.stop()

df = pd.DataFrame(emps)
cgs = {c["code"]: (c["department"], c["sg_a_manu"]) for c in db.list_cost_groups()}
df["department"] = df["cost_code"].map(lambda c: cgs.get(c, ("", ""))[0])
df["sg_a_manu"] = df["cost_code"].map(lambda c: cgs.get(c, ("", ""))[1])
df["status"] = df["is_active"].map({1: "Active", 0: "Inactive"})

c1, c2, c3, c4 = st.columns(4)
type_f = c1.multiselect("Type", sorted(df["emp_type"].dropna().unique().tolist()))
din_f = c2.multiselect("Direct/Indirect", sorted(df["d_in"].dropna().unique().tolist()))
dept_f = c3.multiselect("Department", sorted([d for d in df["department"].unique() if d]))
status_f = c4.multiselect("Status", ["Active", "Inactive"], default=["Active"])

flt = df.copy()
if type_f: flt = flt[flt["emp_type"].isin(type_f)]
if din_f: flt = flt[flt["d_in"].isin(din_f)]
if dept_f: flt = flt[flt["department"].isin(dept_f)]
if status_f: flt = flt[flt["status"].isin(status_f)]

st.markdown(f"**{len(flt)}** of {len(df)} employees")
display_cols = ["emp_no", "emp_name", "emp_type", "cost_code", "department",
                "sg_a_manu", "level", "d_in", "status"]
st.dataframe(
    flt[display_cols].rename(columns={
        "emp_no": "Emp #", "emp_name": "Name", "emp_type": "Type",
        "cost_code": "Cost Code", "department": "Function",
        "sg_a_manu": "Group", "level": "Level", "d_in": "Direct/Indirect", "status": "Status",
    }),
    use_container_width=True, hide_index=True,
)

# Summary tiles
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total", len(flt))
m2.metric("Permanent", int((flt["emp_type"] == "PER").sum()))
m3.metric("Contract", int((flt["emp_type"] == "SUB").sum()))
m4.metric("Direct", int((flt["d_in"] == "Direct").sum()))


# ============================================================================
# 📸 Employee photos — admin uploads photos shown on the Visual Org Chart
# ============================================================================
from lib.page_utils import is_manager_or_admin, is_admin

if is_admin():
    st.markdown("---")
    st.markdown("### 📸 Employee photos")

    photo_count = len(db.list_employee_photo_ids())
    st.caption(
        f"Photos appear on the **🌳 Org Chart → 🎨 Visual Chart** view. "
        f"Currently **{photo_count} of {len(emps)} employees** have a photo on file."
    )

    with st.expander("📖 Photo guidelines & recommended size"):
        from lib.photo_utils import get_photo_recommendations
        st.markdown(get_photo_recommendations())

    # Pick employee
    photo_emps = sorted(emps, key=lambda x: (x.get("emp_name") or ""))
    photo_picker_options = {
        f"{e['emp_no']} · {e.get('emp_name', '?')}": e["emp_no"]
        for e in photo_emps
    }
    pp1, pp2 = st.columns([2, 3])
    sel_label = pp1.selectbox(
        "Pick an employee",
        list(photo_picker_options.keys()),
        index=None,
        placeholder="Search by employee number or name...",
        key="photo_emp_picker",
    )

    if sel_label:
        sel_emp_no = photo_picker_options[sel_label]
        existing = db.get_employee_photo(sel_emp_no)

        # Show current photo
        with pp2:
            if existing:
                st.image(existing, caption=f"Current photo (#{sel_emp_no})", width=160)
                if st.button("🗑️ Remove this photo", type="secondary", key="del_photo"):
                    db.delete_employee_photo(sel_emp_no)
                    st.success("Photo removed.")
                    st.rerun()
            else:
                st.info("No photo on file yet for this employee.")

        # Upload control
        st.markdown("**Upload new photo**")
        uploaded = st.file_uploader(
            "Choose an image (JPG/PNG/WebP up to 5MB)",
            type=["jpg", "jpeg", "png", "webp", "bmp", "gif"],
            key="photo_uploader",
        )
        if uploaded is not None:
            try:
                from lib.photo_utils import validate_and_resize_photo
                processed_bytes, info = validate_and_resize_photo(uploaded.read())
                # Preview
                colp1, colp2 = st.columns([1, 2])
                colp1.image(processed_bytes, caption="Preview (after resize)", width=160)
                colp2.success(info)
                if colp2.button("✅ Save this photo", type="primary", key="save_photo"):
                    db.set_employee_photo(sel_emp_no, processed_bytes)
                    st.success(f"Photo saved for #{sel_emp_no}.")
                    st.rerun()
            except ValueError as ve:
                st.error(f"❌ {ve}")
            except Exception as ex:
                st.error(f"❌ Could not process photo: {ex}")


# ============================================================================
# 🔗 Dotted-line reporting — admin sets additional dotted-line managers
# ============================================================================
if is_admin():
    st.markdown("---")
    st.markdown("### 🔗 Dotted-line reporting (optional)")
    st.caption(
        "By default, each employee has one **direct manager** (set in the Employee Master file, "
        "shown as a solid line on the org chart). You can ALSO assign one or more **dotted-line "
        "managers** here — they'll appear as dashed lines on the chart, indicating advisory or "
        "matrix relationships."
    )

    dotted_emps = sorted(emps, key=lambda x: (x.get("emp_name") or ""))
    dotted_options = {f"{e['emp_no']} · {e.get('emp_name', '?')}": e["emp_no"] for e in dotted_emps}
    dl_emp_label = st.selectbox(
        "Pick the employee whose dotted-line reporting you want to edit",
        list(dotted_options.keys()),
        index=None,
        placeholder="Search by employee number or name...",
        key="dotted_emp_picker",
    )

    if dl_emp_label:
        dl_emp_no = dotted_options[dl_emp_label]
        existing_dotted = db.get_dotted_managers(dl_emp_no)
        emp_no_to_name = {e["emp_no"]: e.get("emp_name", "?") for e in emps}

        # Multi-select for dotted-line managers
        candidate_options = {f"{e['emp_no']} · {e.get('emp_name', '?')}": e["emp_no"]
                             for e in dotted_emps if e["emp_no"] != dl_emp_no}
        # Pre-select existing dotted managers
        default_picks = [k for k, v in candidate_options.items() if v in existing_dotted]

        picks = st.multiselect(
            "Dotted-line managers (additional to the direct manager)",
            list(candidate_options.keys()),
            default=default_picks,
            help="Pick one or more people. They'll appear as dashed lines on the org chart.",
            key="dotted_picks",
        )
        if st.button("💾 Save dotted-line reports", type="primary", key="save_dotted"):
            chosen_emp_nos = [candidate_options[p] for p in picks]
            db.set_dotted_managers(dl_emp_no, chosen_emp_nos)
            if chosen_emp_nos:
                names = ", ".join(emp_no_to_name.get(n, n) for n in chosen_emp_nos)
                st.success(f"✓ Saved {len(chosen_emp_nos)} dotted-line manager(s): {names}")
            else:
                st.success("✓ All dotted-line reports cleared.")


# ============================================================================
# Change Request form (admin & manager only)
# ============================================================================

if is_manager_or_admin():
    st.markdown("---")
    st.markdown("### 🔄 Request a change to an employee")
    st.caption(
        "Submit a change request for cost centre, type, level, etc. "
        "Admin will review and approve/reject from the **🔄 Change Requests** page. "
        + ("As an admin, you can also tick the 'Apply immediately' box to skip approval." if is_admin() else "")
    )

    FIELD_LABELS = {
        "cost_code": "Cost Code (Cost Centre)",
        "emp_type":  "Employment Type (PER / SUB / TEM)",
        "d_in":      "Direct / Indirect",
        "level":     "Level (1 / 2 / 3)",
        "emp_name":  "Employee Name",
    }

    with st.form("change_req_form", clear_on_submit=True):
        # ──── Smart employee picker ────
        # Three search fields that filter the same employee list. Type any of:
        # ID / first name / surname — and pick from the narrowed dropdown.
        st.markdown("**Find employee** (type in any of the boxes to narrow the list)")
        s1, s2, s3 = st.columns(3)
        search_id = s1.text_input("Search by ID", key="cr_search_id",
                                    placeholder="e.g. 1021568").strip()
        search_first = s2.text_input("Search by first name", key="cr_search_first",
                                       placeholder="e.g. Nantachai").strip().lower()
        search_last = s3.text_input("Search by last/surname", key="cr_search_last",
                                      placeholder="e.g. Somboot").strip().lower()

        def _matches(e):
            if search_id and search_id not in str(e["emp_no"]):
                return False
            full = (e.get("emp_name") or "").lower()
            # Strip Mr./Ms./Mrs. prefix to make name search natural
            stripped = full
            for px in ("mr.", "ms.", "mrs.", "miss.", "miss", "dr.", "mr ", "ms ", "mrs "):
                if stripped.startswith(px):
                    stripped = stripped[len(px):].strip()
                    break
            if search_first and search_first not in stripped:
                return False
            if search_last:
                # Try last name = last token of stripped name
                tokens = stripped.replace(".", " ").split()
                last_tok = tokens[-1] if tokens else ""
                if search_last not in last_tok and search_last not in stripped:
                    return False
            return True

        filtered = [e for e in emps if _matches(e)]
        if not filtered:
            st.warning("No employees match those filters. Clear one or more boxes.")
            filtered = emps

        cA, cB = st.columns([3, 2])
        emp_options = [f'{e["emp_no"]} — {e["emp_name"]}' for e in filtered]
        emp_pick = cA.selectbox(
            f"Employee  ({len(filtered)} match{'es' if len(filtered) != 1 else ''})",
            emp_options, key="cr_emp_pick",
        )
        emp_no_pick = emp_pick.split(" — ")[0] if emp_pick else None
        emp_record = next((e for e in emps if e["emp_no"] == emp_no_pick), None)

        field_pick = cB.selectbox("Field to change", list(FIELD_LABELS.keys()),
                                   format_func=lambda k: FIELD_LABELS[k])

        # Show current value
        current_val = emp_record.get(field_pick) if emp_record else ""
        st.caption(f"Current value: **`{current_val}`**")

        # New value with smart input by field type
        if field_pick == "emp_type":
            new_val = st.selectbox("New value", ["PER", "SUB", "TEM"])
        elif field_pick == "d_in":
            new_val = st.selectbox("New value", ["Direct", "Indirect"])
        elif field_pick == "level":
            new_val = st.selectbox("New value", [1, 2, 3])
        elif field_pick == "cost_code":
            cg_codes = sorted({c["code"] for c in db.list_cost_groups()})
            new_val = st.selectbox(
                "New cost code",
                cg_codes,
                index=cg_codes.index(str(current_val)) if str(current_val) in cg_codes else 0,
            )
        else:
            new_val = st.text_input("New value")

        reason = st.text_area("Reason for change (required)", height=70)

        apply_now = False
        if is_admin():
            apply_now = st.checkbox(
                "✓ Apply immediately (admin bypass — no approval needed)", value=False,
            )

        submitted = st.form_submit_button("📨 Submit change request", type="primary")
        if submitted:
            if not reason.strip():
                st.error("Reason is required.")
            elif str(new_val) == str(current_val):
                st.warning("New value is identical to the current value.")
            else:
                req_id = db.submit_change_request(
                    emp_no=emp_no_pick,
                    field_name=field_pick,
                    old_value=str(current_val or ""),
                    new_value=str(new_val),
                    reason=reason.strip(),
                    submitted_by=st.session_state.username,
                )
                if apply_now and is_admin():
                    ok = db.approve_change_request(req_id, st.session_state.username,
                                                   "Auto-approved at submission by admin")
                    st.success(
                        f"✅ Change applied immediately (request #{req_id}). "
                        f"`{FIELD_LABELS[field_pick]}` for {emp_no_pick} is now `{new_val}`."
                    )
                else:
                    st.success(
                        f"📨 Submitted change request #{req_id}. "
                        "An admin will review it on the Change Requests page."
                    )
                st.rerun()

    # Show this user's recent submissions
    if not is_admin():
        my_reqs = db.list_change_requests(submitted_by=st.session_state.username)
        if my_reqs:
            st.markdown("##### Your recent submissions")
            mr_df = pd.DataFrame(my_reqs)[
                ["id", "submitted_at", "emp_no", "field_name", "old_value", "new_value",
                 "status", "reviewed_by", "review_notes"]
            ].rename(columns={
                "id": "ID", "submitted_at": "When", "emp_no": "Emp #",
                "field_name": "Field", "old_value": "Old", "new_value": "New",
                "status": "Status", "reviewed_by": "Reviewed by",
                "review_notes": "Review notes",
            })
            st.dataframe(mr_df.head(20), use_container_width=True, hide_index=True)

    # ──── BULK upload of change requests ────
    st.markdown("---")
    st.markdown("### 📤 Bulk submit change requests via Excel")
    st.caption(
        "Submit many change requests in one go. Download the template, fill it in, "
        "and re-upload here. Each row becomes one separate request that follows the "
        "same approval flow as the form above."
    )

    from lib.templates import change_request_bulk_template
    bA, bB = st.columns([1, 4])
    bA.download_button(
        label="📥  Download bulk template",
        data=change_request_bulk_template(),
        file_name="Change_Requests_bulk_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True, key="cr_bulk_dl",
    )

    f = st.file_uploader("Upload filled-in template (.xlsx)", type=["xlsx"],
                          key="cr_bulk_upload")
    if f:
        try:
            bulk_df = pd.read_excel(f, header=2)  # Header is row 3 (index 2) in template
        except Exception:
            try:
                f.seek(0)
                bulk_df = pd.read_excel(f, header=0)
            except Exception as e:
                st.error(f"Could not read file: {e}")
                bulk_df = None

        if bulk_df is not None and not bulk_df.empty:
            # Find columns flexibly
            col_map = {}
            for c in bulk_df.columns:
                lc = str(c).strip().lower()
                if "emp" in lc and "no" in lc: col_map["emp_no"] = c
                elif lc == "field": col_map["field"] = c
                elif "new" in lc and "value" in lc: col_map["new_val"] = c
                elif "reason" in lc: col_map["reason"] = c

            required = {"emp_no", "field", "new_val", "reason"}
            missing = required - col_map.keys()
            if missing:
                st.error(
                    f"Missing required column(s): {missing}. Use the downloaded template "
                    f"as your starting point. Found columns: {list(bulk_df.columns)}"
                )
            else:
                # Validate each row
                emp_lookup = {e["emp_no"]: e for e in emps}
                allowed_fields = set(FIELD_LABELS.keys())
                preview, problems = [], []
                for idx, row in bulk_df.iterrows():
                    emp_no = str(row[col_map["emp_no"]]).strip() if not pd.isna(row[col_map["emp_no"]]) else ""
                    field = str(row[col_map["field"]]).strip() if not pd.isna(row[col_map["field"]]) else ""
                    new_val = str(row[col_map["new_val"]]).strip() if not pd.isna(row[col_map["new_val"]]) else ""
                    reason = str(row[col_map["reason"]]).strip() if not pd.isna(row[col_map["reason"]]) else ""

                    if not emp_no or not field:
                        continue  # skip blank rows silently
                    if emp_no.endswith(".0"): emp_no = emp_no[:-2]
                    if emp_no not in emp_lookup:
                        problems.append(f"Row {idx+2}: emp_no `{emp_no}` not found")
                        continue
                    if field not in allowed_fields:
                        problems.append(f"Row {idx+2}: field `{field}` not in {sorted(allowed_fields)}")
                        continue
                    if len(reason) < 10:
                        problems.append(f"Row {idx+2}: reason too short (need 10+ chars)")
                        continue
                    old_val = emp_lookup[emp_no].get(field, "")
                    if str(new_val) == str(old_val):
                        problems.append(f"Row {idx+2}: new value `{new_val}` same as current — skipping")
                        continue
                    preview.append({
                        "Emp #": emp_no,
                        "Name": emp_lookup[emp_no]["emp_name"],
                        "Field": FIELD_LABELS.get(field, field),
                        "Old": str(old_val),
                        "New": new_val,
                        "Reason": reason[:60],
                        "_emp_no": emp_no, "_field": field,
                        "_new": new_val, "_reason": reason, "_old": str(old_val),
                    })

                if problems:
                    st.warning(f"⚠ Found {len(problems)} issues — those rows will be skipped:")
                    for p in problems[:20]:
                        st.caption(f"  • {p}")
                    if len(problems) > 20:
                        st.caption(f"  …and {len(problems)-20} more")

                if preview:
                    st.success(f"✅ {len(preview)} valid rows ready to submit.")
                    show_df = pd.DataFrame([{k: v for k, v in p.items() if not k.startswith("_")} for p in preview])
                    st.dataframe(show_df, use_container_width=True, hide_index=True)

                    apply_now_bulk = False
                    if is_admin():
                        apply_now_bulk = st.checkbox(
                            "✓ Apply ALL immediately (admin bypass — no approval needed)",
                            key="bulk_apply_now",
                        )

                    if st.button(f"🚀  Submit {len(preview)} change request(s)",
                                  type="primary", key="bulk_cr_submit"):
                        submitted, applied = 0, 0
                        for p in preview:
                            req_id = db.submit_change_request(
                                emp_no=p["_emp_no"], field_name=p["_field"],
                                old_value=p["_old"], new_value=p["_new"],
                                reason=p["_reason"], submitted_by=st.session_state.username,
                            )
                            submitted += 1
                            if apply_now_bulk and is_admin():
                                if db.approve_change_request(
                                    req_id, st.session_state.username,
                                    "Bulk auto-approved at submission by admin"):
                                    applied += 1
                        if apply_now_bulk and is_admin():
                            st.success(f"✅ Submitted {submitted}, applied {applied} immediately.")
                        else:
                            st.success(f"✅ Submitted {submitted} request(s) for admin review.")
                        st.rerun()
                else:
                    st.info("No valid rows to submit yet.")
