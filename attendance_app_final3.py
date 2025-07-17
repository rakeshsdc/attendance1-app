import streamlit as st
import pandas as pd
import datetime
import os

st.set_page_config(page_title="Attendance Console", layout="wide")
st.title("📝 FYUGP Attendance Console")

# Load data files
students_df = pd.read_csv("students.csv")
courses_df = pd.read_csv("courses.csv")
teachers_df = pd.read_csv("teachers.csv")

# Load or initialize attendance file
attendance_file = "attendance.csv"
if not os.path.exists(attendance_file):
    pd.DataFrame(columns=["date", "hour", "course_id", "student_id", "status", "marked_by", "extra_time", "duration"]).to_csv(attendance_file, index=False)

attendance_df = pd.read_csv(attendance_file)

# Load or initialize camp days file
camp_file = "camp_days.csv"
if not os.path.exists(camp_file):
    pd.DataFrame(columns=["student_id", "start_date", "end_date", "camp_type"]).to_csv(camp_file, index=False)

camp_df = pd.read_csv(camp_file)

# Teacher login
with st.sidebar:
    st.header("👩‍🏫 Teacher Login")
    teacher_id = st.selectbox("Select Teacher", teachers_df["teacher_id"].unique())
    st.session_state.teacher_id = teacher_id
    role = teachers_df.loc[teachers_df["teacher_id"] == teacher_id, "role"].values[0]

# Attendance submission
st.subheader("📅 Submit Attendance")
selected_course = st.selectbox("Select Course", courses_df[courses_df["teacher_id"] == teacher_id]["course_id"].unique())
selected_date = st.date_input("Select Date", datetime.date.today())
selected_hour = st.selectbox("Select Hour", [1, 2, 3, 4, 5, 6])
extra_hour = st.checkbox("Extra Hour")
extra_time = ""  # default
if extra_hour:
    extra_time = st.text_input("Time (e.g., 3:00 PM)")
    duration = st.text_input("Duration (in minutes)", value="60")
else:
    duration = "60"

# Mask already handled hours for the same course and date
already_handled = attendance_df[(attendance_df["date"] == str(selected_date)) & (attendance_df["course_id"] == selected_course)]["hour"].unique().tolist()
if selected_hour in already_handled:
    st.warning(f"Hour {selected_hour} for {selected_course} already has attendance data. Please choose another.")

# Students of the selected course
students = students_df[students_df["course_id"] == selected_course]
updated_status = {}
st.markdown("### 🧑‍🎓 Mark Attendance (Default: Present)")
for _, row in students.iterrows():
    sid = row["student_id"]
    name = row["student_name"]
    default_status = "P"
    status = st.selectbox(f"{name} ({sid})", ["P", "A", "NSS", "NCC", "Club"], index=0, key=f"status_{sid}")
    updated_status[sid] = status

if st.button("✅ Submit Attendance"):
    try:
        new_data = []
        for sid, status in updated_status.items():
            new_data.append({
                "date": selected_date,
                "hour": selected_hour,
                "course_id": selected_course,
                "student_id": sid,
                "status": status,
                "marked_by": teacher_id,
                "extra_time": extra_time,
                "duration": duration
            })

        new_df = pd.DataFrame(new_data)

        try:
            existing = pd.read_csv(attendance_file)
            existing["date"] = pd.to_datetime(existing["date"], errors='coerce')
        except:
            existing = pd.DataFrame(columns=["date", "hour", "course_id", "student_id", "status", "marked_by", "extra_time", "duration"])

        combined = pd.concat([existing, new_df], ignore_index=True)
        combined.to_csv(attendance_file, index=False)
        st.success("✅ Attendance submitted and saved!")
        st.subheader("📊 Submitted Summary")
        try:
            summary = new_df.groupby("status")["student_id"].count().reset_index(name="count")
            st.dataframe(summary)
        except Exception as e:
            st.error(f"❌ Error generating summary: {e}")

    except Exception as e:
        st.error(f"❌ Error while saving attendance: {e}")

# Camp Days Entry
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
