import streamlit as st
import pandas as pd
from datetime import date, datetime

st.set_page_config(page_title="FYUGP Attendance", layout="wide")

# ------------------- Title & Description -------------------
st.title("\U0001F4D8 FYUGP Attendance Management System")
st.markdown("""
Welcome to the **FYUGP Attendance App**.  
✅ Track student attendance across Major, Minor, MDC, and VAC courses.  
✅ Department Admins & Teachers can generate reports.  
✅ Masked hours, camp exemptions, and multi-status attendance included.  
✅ Edit/Delete past entries, visualize data, and monitor trends.
""")

# ------------------- Load Data -------------------
@st.cache_data
def load_data():
    students = pd.read_csv("students.csv")
    teachers = pd.read_csv("teachers.csv")
    courses = pd.read_csv("courses.csv")
    try:
        enrollment = pd.read_csv("enrollment.csv")
    except:
        enrollment = pd.DataFrame(columns=["student_id", "course_id"])
    try:
        attendance = pd.read_csv("attendance.csv")
        if "student_id" not in attendance.columns:
            attendance.columns = ["date", "hour", "course_id", "student_id", "status", "marked_by", "extra_time", "duration"]
        attendance["date"] = pd.to_datetime(attendance["date"], errors='coerce')
    except:
        attendance = pd.DataFrame(columns=["date", "hour", "course_id", "student_id", "status", "marked_by", "extra_time", "duration"])
    try:
        camp_days = pd.read_csv("camp_days.csv", parse_dates=["start_date", "end_date"])
    except:
        camp_days = pd.DataFrame(columns=["student_id", "start_date", "end_date", "activity"])
    return students, teachers, courses, enrollment, attendance, camp_days

students, teachers, courses, enrollment, attendance, camp_days = load_data()

# ------------------- Login -------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.sidebar.header("\U0001F510 Login")
    email = st.sidebar.text_input("Email").strip().lower()
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        match = teachers[
            (teachers["email"].str.lower().str.strip() == email) &
            (teachers["password"].astype(str).str.strip() == password)
        ]
        if not match.empty:
            user = match.iloc[0]
            st.session_state.logged_in = True
            st.session_state.teacher_id = user["teacher_id"]
            st.session_state.teacher_name = user["name"]
            st.session_state.role = user["role"]
            st.session_state.department = user.get("department", "")
            st.rerun()
        else:
            st.sidebar.error("Invalid credentials")
    st.stop()
else:
    st.sidebar.write(f"\U0001F464 {st.session_state.teacher_name} ({st.session_state.role})")
    if st.sidebar.button("\U0001F6AA Logout"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ------------------- Safe Date Conversion -------------------
if not pd.api.types.is_datetime64_any_dtype(attendance["date"]):
    attendance["date"] = pd.to_datetime(attendance["date"], errors='coerce')
# ------------------- Upload Course Selection (Admin/Dept Admin Only) -------------------
if st.session_state.role in ["admin", "dept_admin"]:
    st.subheader("🔄 Upload Student Course Selection (One Row Format)")

    uploaded_selection = st.file_uploader("Upload `student_course_selection.csv`", type="csv")

    if uploaded_selection:
        try:
            df = pd.read_csv(uploaded_selection)
            df.to_csv("student_course_selection.csv", index=False)

            enrollment_df = df.melt(
                id_vars=["student_id"], 
                value_vars=["major_course", "minor1", "minor2", "mdc", "vac"],
                var_name="course_type", 
                value_name="course_id"
            )[["student_id", "course_id"]].dropna()

            enrollment_df.to_csv("enrollment.csv", index=False)

            st.success("✅ `enrollment.csv` generated successfully!")
            st.download_button("📥 Download enrollment.csv",
                               data=enrollment_df.to_csv(index=False),
                               file_name="enrollment.csv",
                               mime="text/csv")

        except Exception as e:
            st.error(f"❌ Failed to process file: {e}")
# ------------------- Attendance Console for Teacher -------------------
if st.session_state.role in ["teacher", "admin", "dept_admin"]:
    assigned_courses = courses[courses["teacher_id"] == st.session_state.teacher_id]
    if not assigned_courses.empty:
        st.subheader("📘 Take Attendance")
    assigned_courses = courses[courses["teacher_id"] == st.session_state.teacher_id]
    if assigned_courses.empty:
        st.info("You have no assigned courses.")
    else:
        selected_course = st.selectbox("Select Course", assigned_courses["course_id"].tolist())
        selected_date = st.date_input("Date", value=date.today())

        selected_date = pd.to_datetime(selected_date)

        attendance["date"] = pd.to_datetime(attendance["date"], errors='coerce')

        taken_hours = attendance[(attendance["course_id"] == selected_course) &
                                 (attendance["date"] == selected_date)]["hour"].tolist()

        hours = [1, 2, 3, 4, 5, 6]
        available_hours = [h for h in hours if h not in taken_hours]
        selected_hour = st.selectbox("Hour", available_hours + ["Extra Hour"])

        extra_time = ""
        duration = ""
        if selected_hour == "Extra Hour":
            selected_hour = 0
            extra_time = st.text_input("Start Time (e.g., 4:00 PM)")
            duration = st.text_input("Duration (e.g., 1 hour)")

        enrolled_students = enrollment[enrollment["course_id"] == selected_course]["student_id"].tolist()
        students_list = students[students["student_id"].isin(enrolled_students)]

        if not students_list.empty:
            st.write("### Mark Attendance (default is Present)")
            updated_status = {}

            for _, row in students_list.iterrows():
                status = st.selectbox(
                    f"{row['name']} ({row['student_id']})",
                    ["P", "A", "NSS", "NCC", "Club"],
                    index=0,
                    key=f"{row['student_id']}_{selected_hour}_{selected_course}"
                )
                updated_status[row["student_id"]] = status

            if st.button("✅ Submit Attendance"):
                new_data = []
                for sid, status in updated_status.items():
                    new_data.append({
                        "date": selected_date,
                        "hour": selected_hour,
                        "course_id": selected_course,
                        "student_id": sid,
                        "status": status,
                        "marked_by": st.session_state.teacher_id,
                        "extra_time": extra_time,
                        "duration": duration
                    })

                if new_data:
                    new_df = pd.DataFrame(new_data)
                    try:
                        existing = pd.read_csv("attendance.csv")
                        existing["date"] = pd.to_datetime(existing["date"], errors='coerce')
                    except FileNotFoundError:
                        existing = pd.DataFrame(columns=["date", "hour", "course_id", "student_id", "status", "marked_by", "extra_time", "duration"])

                    required_columns = ["date", "hour", "course_id", "student_id", "status", "marked_by", "extra_time", "duration"]
                    for col in required_columns:
                        if col not in existing.columns:
                            existing[col] = None
                    try:
                        combined = pd.concat([existing, new_df], ignore_index=True)
                        combined.to_csv("attendance.csv", index=False)
                        st.success("Attendance submitted successfully!")
                        st.subheader("📊 Attendance Summary (Last Submission)")
                        st.dataframe(new_df)
                    except Exception as e:
                        st.error(f"❌ Error while saving attendance: {e}")

 #Camp Days Entry
st.subheader("🏕️ Camp Days Entry")
camp_student = st.selectbox("Select Student", students_df["student_id"].unique(), key="camp_student")
camp_type = st.selectbox("Camp Type", ["NSS", "NCC"], key="camp_type")
camp_start = st.date_input("Start Date", key="camp_start")
camp_end = st.date_input("End Date", key="camp_end")
if st.button("➕ Add Camp Days"):
    new_camp = pd.DataFrame([[camp_student, camp_start, camp_end, camp_type]], columns=["student_id", "start_date", "end_date", "camp_type"])
    camp_df = pd.concat([camp_df, new_camp], ignore_index=True)
    camp_df.to_csv(camp_file, index=False)
    st.success("✅ Camp days added.")

# Delete Camp Entry
st.subheader("🗑️ Delete Camp Days")
if not camp_df.empty:
    row_to_delete = st.selectbox("Select Entry to Delete", camp_df.index, key="delete_row")
    st.write(camp_df.loc[row_to_delete])
    if st.button("Delete Selected Entry"):
        camp_df = camp_df.drop(index=row_to_delete)
        camp_df.to_csv(camp_file, index=False)
        st.success("✅ Camp day entry deleted.")
else:
    st.info("No camp day entries available to delete.")

# ------------------- Delete Attendance Entry -------------------
if st.session_state.role in ["admin", "dept_admin"]:
    st.subheader("🗑️ Delete Attendance Entry")
    date_filter = st.date_input("Filter by Date to Delete")
    filtered = attendance[attendance["date"] == pd.to_datetime(date_filter)]
    if not filtered.empty:
        selected = st.selectbox("Select Record to Delete", filtered.apply(lambda x: f"{x['student_id']} - {x['status']} ({x['hour']})", axis=1).tolist())
        if st.button("Confirm Delete"):
            idx = filtered.index[filtered.apply(lambda x: f"{x['student_id']} - {x['status']} ({x['hour']})" == selected, axis=1)].tolist()
            if idx:
                attendance.drop(index=idx, inplace=True)
                attendance.to_csv("attendance.csv", index=False)
                st.success("Entry deleted.")

# ------------------- Full Attendance Summary -------------------
st.subheader("📊 Full Attendance Summary")
if not attendance.empty:
    grouped = attendance.groupby(["student_id", "status"]).size().unstack(fill_value=0)
    st.dataframe(grouped)
    st.download_button("📥 Download Attendance Summary", data=grouped.to_csv().encode(), file_name="attendance_summary.csv")
else:
    st.info("No attendance records to display.")
