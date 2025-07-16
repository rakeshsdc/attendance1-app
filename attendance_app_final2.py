import streamlit as st
import pandas as pd
from datetime import date, datetime

st.set_page_config(page_title="FYUGP Attendance", layout="wide")

# ------------------- Title & Description -------------------
st.title("📘 FYUGP Attendance Management System")
st.markdown("""
Welcome to the **FYUGP Attendance App**.  
✅ Track student attendance across Major, Minor, MDC, and VAC courses.  
✅ Department Admins & Teachers can generate reports.  
✅ Masked hours, camp exemptions, and multi-status attendance included.
""")

# ------------------- Load Data -------------------
@st.cache_data
def load_data():
    students = pd.read_csv("students.csv")
    teachers = pd.read_csv("teachers.csv")
    courses = pd.read_csv("courses.csv")
    enrollment = pd.read_csv("enrollment.csv")
    try:
        attendance = pd.read_csv("attendance.csv")
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
    st.sidebar.header("🔐 Login")
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
    st.sidebar.write(f"👤 {st.session_state.teacher_name} ({st.session_state.role})")
    if st.sidebar.button("🚪 Logout"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

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

# ------------------- Take Attendance (Teachers) -------------------
if st.session_state.role == "teacher":
    st.subheader("📘 Take Attendance")
    assigned_courses = courses[courses["teacher_id"] == st.session_state.teacher_id]
    if assigned_courses.empty:
        st.info("You have no assigned courses.")
    else:
        selected_course = st.selectbox("Select Course", assigned_courses["course_id"].tolist())
        selected_date = st.date_input("Date", value=date.today())

        # Hour masking
        attendance["date"] = pd.to_datetime(attendance["date"])
        taken_hours = attendance[
            (attendance["course_id"] == selected_course) &
            (attendance["date"] == pd.to_datetime(selected_date))
        ]["hour"].tolist()

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
            default_status = {sid: "P" for sid in students_list["student_id"]}
            updated_status = {}

            for _, row in students_list.iterrows():
                status = st.selectbox(
                    f"{row['name']} ({row['student_id']})",
                    ["P", "A", "NSS", "NCC", "Club"],
                    index=0,
                    key=f"{row['student_id']}_{selected_hour}"
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

                new_df = pd.DataFrame(new_data)
                attendance = pd.concat([attendance, new_df], ignore_index=True)
                attendance.to_csv("attendance.csv", index=False)
                st.success("✅ Attendance recorded.")
                st.rerun()
        else:
            st.warning("⚠️ No students enrolled in this course.")

# ------------------- Admin / Dept Admin Reports -------------------
if st.session_state.role in ["admin", "dept_admin"]:
    st.subheader("📊 Reports")
    from_dt = st.date_input("From Date", value=date.today())
    to_dt = st.date_input("To Date", value=date.today())

    attendance["date"] = pd.to_datetime(attendance["date"])
    filtered = attendance[
        (attendance["date"] >= pd.to_datetime(from_dt)) &
        (attendance["date"] <= pd.to_datetime(to_dt))
    ].copy()

    # Remove camp days
    camp_set = set()
    for _, row in camp_days.iterrows():
        dates = pd.date_range(row["start_date"], row["end_date"]).strftime("%Y-%m-%d")
        for d in dates:
            camp_set.add((row["student_id"], d))
    filtered["date_str"] = filtered["date"].dt.strftime("%Y-%m-%d")
    filtered = filtered[~filtered.apply(lambda x: (x["student_id"], x["date_str"]) in camp_set, axis=1)]

    dept_id = st.session_state.department if st.session_state.role == "dept_admin" else None
    if dept_id:
        dept_students = students[students["major_course"] == dept_id]
    else:
        dept_students = students

    final_data = filtered[filtered["student_id"].isin(dept_students["student_id"])]
    if final_data.empty:
        st.info("No attendance records in this range.")
    else:
        summary = final_data.groupby("student_id")["status"].agg([
            ("attended", lambda x: (x != "A").sum()),
            ("total", "count")
        ]).reset_index()
        summary["percent"] = (summary["attended"] / summary["total"] * 100).round(1)
        report = pd.merge(dept_students, summary, on="student_id", how="left").fillna(0)
        report["attended"] = report["attended"].astype(int)
        report["total"] = report["total"].astype(int)

        st.write("### 📋 Consolidated Report")
        st.dataframe(report[["student_id", "name", "total", "attended", "percent"]])
        st.download_button("📥 Download Consolidated", report.to_csv(index=False), "consolidated.csv")

        detailed = pd.merge(final_data, students, on="student_id", how="left")
        st.write("### 📅 Detailed Log")
        st.download_button("📥 Download Log", detailed.to_csv(index=False), "log.csv")
