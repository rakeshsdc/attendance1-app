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

# ------------------- Dashboard Summary -------------------
if st.session_state.role in ["admin", "dept_admin"]:
    st.subheader("📊 Dashboard Overview")
    st.markdown("**📅 Attendance Overview Across All Courses**")
    total_sessions = len(attendance)
    total_students = len(students)
    total_courses = len(courses)
    st.metric("Total Sessions Recorded", total_sessions)
    st.metric("Total Students", total_students)
    st.metric("Total Courses", total_courses)

# ------------------- Edit/Delete Past Attendance -------------------
if st.session_state.role in ["admin", "dept_admin"]:
    st.subheader("✏️ Edit/Delete Attendance Records")
    editable = attendance.copy()
    editable["date"] = pd.to_datetime(editable["date"], errors='coerce')

    selected_date = st.date_input("Select Date to View Records", value=date.today())
    filtered_edit = editable[editable["date"] == pd.to_datetime(selected_date)]

    if filtered_edit.empty:
        st.info("No records found for this date.")
    else:
        row_to_edit = st.selectbox("Select record to edit/delete", filtered_edit.index)
        record = filtered_edit.loc[row_to_edit]
        new_status = st.selectbox("Update Status", ["P", "A", "NSS", "NCC", "Club"], index=["P", "A", "NSS", "NCC", "Club"].index(record["status"]))
        action = st.radio("Action", ["Edit", "Delete"])

        if st.button("Apply Changes"):
            if action == "Edit":
                attendance.loc[row_to_edit, "status"] = new_status
                st.success("Record updated successfully.")
            elif action == "Delete":
                attendance = attendance.drop(index=row_to_edit).reset_index(drop=True)
                st.success("Record deleted successfully.")
            attendance.to_csv("attendance.csv", index=False)
            st.rerun()

# ------------------- Date Filter in Department Reports -------------------
if st.session_state.role in ["admin", "dept_admin"]:
    st.subheader("🏢 Department Course-wise Report")
    selected_course = st.selectbox("Select Course", courses["course_id"].tolist(), key="dept_course")
    from_dt = st.date_input("From Date", value=date.today(), key="dept_from")
    to_dt = st.date_input("To Date", value=date.today(), key="dept_to")

    course_att = attendance[(attendance["course_id"] == selected_course) &
                            (pd.to_datetime(attendance["date"], errors='coerce') >= pd.to_datetime(from_dt)) &
                            (pd.to_datetime(attendance["date"], errors='coerce') <= pd.to_datetime(to_dt))].copy()
    course_att["date"] = pd.to_datetime(course_att["date"], errors='coerce')
    course_att["date_str"] = course_att["date"].dt.strftime("%Y-%m-%d")

    if course_att.empty:
        st.warning("No attendance data for this course and date range.")
    else:
        camp_set = set()
        for _, row in camp_days.iterrows():
            dates = pd.date_range(row["start_date"], row["end_date"]).strftime("%Y-%m-%d")
            for d in dates:
                camp_set.add((row["student_id"], d))
        course_att = course_att[~course_att.apply(lambda x: (x["student_id"], x["date_str"]) in camp_set, axis=1)]

        course_students = enrollment[enrollment["course_id"] == selected_course]["student_id"].tolist()
        enrolled_names = students[students["student_id"].isin(course_students)][["student_id", "name"]]

        summary = course_att.groupby("student_id")["status"].agg([
            ("attended", lambda x: (x != "A").sum()),
            ("total", "count")
        ]).reset_index()
        summary["percent"] = (summary["attended"] / summary["total"] * 100).round(1)

        merged = pd.merge(enrolled_names, summary, on="student_id", how="left").fillna(0)
        merged["attended"] = merged["attended"].astype(int)
        merged["total"] = merged["total"].astype(int)

        st.dataframe(merged)
        st.download_button("📥 Download Department Report", merged.to_csv(index=False), f"dept_{selected_course}.csv")
