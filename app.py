import streamlit as st
import pandas as pd
import plotly.express as px
import os
from db_connector import run_query
from utils import DropoutInterventionSystem

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="RESN | Rural Education Safety Net",
    page_icon="🌾",
    layout="wide"
)

# Initialize the System Logic
@st.cache_resource
def get_system():
    return DropoutInterventionSystem()

system = get_system()

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🚜 RESN Command Center")
page = st.sidebar.radio("Navigate", ["📊 School Dashboard", "🚨 Intervention Console"])

# =========================================================
# PAGE 1: THE HEADMASTER DASHBOARD (Statistics)
# =========================================================
if page == "📊 School Dashboard":
    st.title("📊 School-Level Risk Overview")
    
    # 1. KEY METRICS
    # Fetch live data using SQL
    total_students = run_query("SELECT COUNT(*) as count FROM students").iloc[0]['count']
    
    # Calculate Risk Counts
    # Note: In a real prod app, we'd cache these risk flags in the DB. 
    # For this MVP, we estimate based on our logic (Att < 75 OR Grade < 35)
    risk_sql = """
    SELECT COUNT(DISTINCT s.student_id) as count
    FROM students s
    LEFT JOIN attendance a ON s.student_id = a.student_id
    LEFT JOIN exam_scores e ON s.student_id = e.student_id
    WHERE a.attendance_percent < 75 OR e.score < 35
    """
    at_risk_count = run_query(risk_sql).iloc[0]['count']
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Students Enrolled", total_students)
    col2.metric("Students At Risk", at_risk_count, delta="-5%", delta_color="inverse")
    col3.metric("Scholarships Disbursed", "₹ 12,000", delta="+3000")

    st.markdown("---")

    # 2. VISUALIZATIONS
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📉 Attendance vs. Grades Correlation")
        # Get raw data for scatter plot
        corr_sql = """
        SELECT s.name, a.attendance_percent, AVG(e.score) as avg_score, s.caste_category
        FROM students s
        JOIN attendance a ON s.student_id = a.student_id
        JOIN exam_scores e ON s.student_id = e.student_id
        GROUP BY s.student_id, s.name, a.attendance_percent, s.caste_category
        """
        df_corr = run_query(corr_sql)
        if not df_corr.empty:
            fig_corr = px.scatter(
                df_corr, x="attendance_percent", y="avg_score", 
                color="caste_category", size="avg_score", hover_data=["name"],
                title="Does Low Attendance cause Low Grades?"
            )
            st.plotly_chart(fig_corr, use_container_width=True)
        else:
            st.info("Not enough data for correlation chart.")

    with col_right:
        st.subheader("⚠️ Risk Factors Distribution")
        risk_dist_sql = """
        SELECT 
            SUM(CASE WHEN seasonal_labor THEN 1 ELSE 0 END) as "Seasonal Labor",
            SUM(CASE WHEN sibling_dropout THEN 1 ELSE 0 END) as "Sibling Dropout",
            SUM(CASE WHEN parent_education_level = 'None' THEN 1 ELSE 0 END) as "Illiterate Parents"
        FROM social_risk
        """
        df_risk = run_query(risk_dist_sql)
        if not df_risk.empty:
            df_melted = df_risk.melt(var_name="Risk Factor", value_name="Count")
            fig_bar = px.bar(df_melted, x="Risk Factor", y="Count", color="Risk Factor", title="Primary Drivers of Dropout")
            st.plotly_chart(fig_bar, use_container_width=True)

# =========================================================
# PAGE 2: THE INTERVENTION CONSOLE (The "Action" Part)
# =========================================================
elif page == "🚨 Intervention Console":
    st.title("🚨 Student Intervention System")
    st.markdown("Select a student to run the **AI Decision Engine**.")

    # 1. SELECT STUDENT
    students_df = run_query("SELECT student_id, name FROM students ORDER BY name")
    student_map = dict(zip(students_df['name'], students_df['student_id']))
    
    col_sel1, col_sel2 = st.columns([2, 1])
    with col_sel1:
        selected_name = st.selectbox("Search Student Name", students_df['name'])
    with col_sel2:
        language = st.selectbox("Target Language for Script", ["Hindi", "English", "Tamil", "Marathi", "Bengali"])

    # 2. ANALYZE BUTTON
    if st.button("🚀 Analyze Risk & Generate Intervention"):
        student_id = student_map[selected_name]
        
        with st.spinner(f"Running AI Analysis for {selected_name}..."):
            # CALL THE BACKEND ORCHESTRATOR
            report = system.process_intervention(student_id, target_language=language)
        
        # 3. DISPLAY RESULTS
        st.markdown("---")
        
        # STATUS HEADER
        status = report['status']
        if "HIGH RISK" in status:
            st.error(f"## Status: {status}")
            st.caption("Immediate Home Visit & Financial Aid Required")
        elif "ACADEMIC WATCH" in status:
            st.warning(f"## Status: {status}")
            st.caption("Teacher attention needed. No financial aid required yet.")
        else:
            st.success(f"## Status: {status}")

        # ACTIONS DISPLAY
        if report['actions']:
            st.subheader("✅ Generated Interventions")
            
            tabs = st.tabs([action['type'].replace("_", " ").upper() for action in report['actions']])
            
            for i, action in enumerate(report['actions']):
                with tabs[i]:
                    
                    # --- A. IF IT IS A SCRIPT ---
                    if action['type'] == 'script':
                        st.markdown(f"### 🗣️ Home Visit Script ({language})")
                        st.info("Read this to the parents:")
                        st.code(action['content'], language=None)
                        st.caption("AI generated based on Parent Literacy Level & Specific Risk Factors.")

                    # --- B. IF IT IS A PDF FILE ---
                    elif action['type'] == 'file':
                        st.markdown("### 📄 Government Scholarship Form")
                        st.write(f"**Matched Scheme:** {action['description']}")
                        
                        # Logic to read file for download button
                        with open(action['path'], "rb") as pdf_file:
                            st.download_button(
                                label="⬇️ Download PDF Application",
                                data=pdf_file,
                                file_name=os.path.basename(action['path']),
                                mime="application/pdf"
                            )

                    # --- C. IF IT IS A TEACHER PLAN ---
                    elif action['type'] == 'teacher_plan':
                        st.markdown("### 👨‍🏫 Remedial Pedagogy Plan")
                        st.markdown(action['content'])
        else:
            st.balloons()
            st.write("No intervention needed at this time.")