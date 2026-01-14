import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import date
from db_connector import run_query
from agents.orchestrator import RESNOrchestrator

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="RESN | Rural Education Safety Net",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.5rem; }
    .metric-container { background-color: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); border-top: 4px solid #ccc; text-align: center; height: 100%; }
    .metric-value { font-size: 2.2rem; font-weight: 800; color: #1E293B; }
    .metric-label { font-size: 0.9rem; text-transform: uppercase; color: #64748B; font-weight: 600; }
    .card-blue { border-top-color: #3B82F6; }
    .card-red { border-top-color: #EF4444; }
    .card-green { border-top-color: #10B981; }
    .section-title { font-size: 1.5rem; font-weight: 700; color: #334155; margin-top: 2rem; border-left: 5px solid #1E3A8A; padding-left: 15px; margin-bottom: 1rem; }
    .status-badge { padding: 15px; border-radius: 8px; font-weight: bold; text-align: center; margin-top: 10px; }
    .status-high { background-color: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA; }
    .status-warn { background-color: #FFFBEB; color: #B45309; border: 1px solid #FDE68A; }
    .status-safe { background-color: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; }
</style>
""", unsafe_allow_html=True)

# --- CACHED RESOURCES ---
@st.cache_resource
def get_orchestrator():
    return RESNOrchestrator()

@st.cache_data(ttl=60) # Cache the student list for 1 minute to prevent lag
def get_cached_students():
    df = run_query("SELECT student_id, name FROM students ORDER BY name", return_dict=False)
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame(columns=['student_id', 'name'])

orchestrator = get_orchestrator()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🌾 RESN Platform")
    st.caption("Rural Education Safety Net")
    st.divider()
    page = st.radio("Navigation", ["📊 Dashboard", "🚨 Intervention Center", "📝 Data Entry"])
    
    # Use a simpler query for the sidebar metric to save time
    try:
        count_res = run_query("SELECT COUNT(*) as count FROM students")
        total = count_res[0]['count'] if count_res else 0
        st.metric("Total Students Enrolled", total)
        st.success("🟢 System Online")
    except Exception as e:
        st.error(f"🔴 Connection Error")
        total = 0

# =========================================================
# PAGE 1: DASHBOARD
# =========================================================
if page == "📊 Dashboard":
    st.markdown('<div class="main-header">School Performance Analytics</div>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    
    # Calculate Risk Count
    risk_sql = """
        SELECT COUNT(DISTINCT s.student_id) as count
        FROM students s
        LEFT JOIN attendance a ON s.student_id = a.student_id
        LEFT JOIN exam_scores e ON s.student_id = e.student_id
        WHERE a.attendance_percent < 75 OR (e.score IS NOT NULL AND e.score < 35)
    """
    df_risk_count = run_query(risk_sql, return_dict=False)
    at_risk_count = int(df_risk_count.iloc[0]['count']) if not df_risk_count.empty else 0

    with c1: st.markdown(f'<div class="metric-container card-blue"><div class="metric-value">{total}</div><div class="metric-label">Total Students</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-container card-red"><div class="metric-value">{at_risk_count}</div><div class="metric-label">Needs Attention</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-container card-green"><div class="metric-value">{max(0, total - at_risk_count)}</div><div class="metric-label">On Track</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">📉 Analytics & Trends</div>', unsafe_allow_html=True)
    col_l, col_r = st.columns(2)
    
    with col_l:
        st.markdown("#### Parental Literacy Profile")
        df_risk = run_query("SELECT parent_education_level as factor, COUNT(*) as count FROM social_risk GROUP BY factor", return_dict=False)
        if not df_risk.empty:
            st.plotly_chart(px.pie(df_risk, values='count', names='factor', hole=0.4), use_container_width=True)
        else: st.info("No data available")
            
    with col_r:
        st.markdown("#### Subject Performance Overview")
        df_acad = run_query("SELECT subject, AVG(score) as avg_score FROM exam_scores GROUP BY subject", return_dict=False)
        if not df_acad.empty:
            st.plotly_chart(px.bar(df_acad, x='subject', y='avg_score'), use_container_width=True)
        else: st.info("No data available")

# =========================================================
# PAGE 2: INTERVENTION CENTER
# =========================================================
elif page == "🚨 Intervention Center":
    st.markdown('<div class="main-header">Student Intervention Center</div>', unsafe_allow_html=True)
    
    students_df = get_cached_students()
    
    if not students_df.empty:
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            selected_name = st.selectbox("Select Student", students_df['name'].tolist())
            sid = int(students_df[students_df['name'] == selected_name]['student_id'].values[0])
        with c2:
            lang = st.selectbox("Target Language", ["Hindi", "English", "Bengali", "Marathi", "Tamil"])
        with c3:
            st.write("")
            st.write("")
            run_btn = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

        if run_btn:
            with st.spinner(f"Agents are collaborating on {selected_name}'s case..."):
                try:
                    # Execute the multi-agent pipeline
                    result = orchestrator.run_intervention_pipeline(sid, counseling_lang=lang)
                    
                    analysis = result.get('analysis', {})
                    status = analysis.get('status', 'NORMAL')
                    score = analysis.get('risk_score', 0)
                    
                    # Display Gauge and Status
                    col_gauge, col_details = st.columns([1, 2])
                    with col_gauge:
                        fig = go.Figure(go.Indicator(
                            mode="gauge+number", value=score,
                            title={'text': "Risk Score"},
                            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "red" if score > 60 else "orange"}}
                        ))
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col_details:
                        badge_class = "status-high" if score > 60 else ("status-warn" if score > 40 else "status-safe")
                        st.markdown(f'<div class="status-badge {badge_class}">{status}</div>', unsafe_allow_html=True)
                        st.info(f"**AI Summary:** {analysis.get('summary_for_memory', '')}")

                    # Display Action Cards
                    if result.get('actions'):
                        st.markdown('<div class="section-title">📋 Recommended Actions</div>', unsafe_allow_html=True)
                        for action in result['actions']:
                            with st.expander(f"Action: {action['type'].title()}", expanded=True):
                                if action['type'] == 'finance':
                                    st.success(f"Matched: {action['data'].get('scheme')}")
                                    st.write(action['data'].get('justification'))
                                elif action['type'] == 'counseling':
                                    st.code(action['data'].get('script'), language='text')
                                elif action['type'] == 'academic':
                                    st.markdown(action['data'].get('remedial_plan'))
                except Exception as e:
                    st.error(f"Analysis Failed: {e}")
    else:
        st.info("No student data found. Go to 'Data Entry' to add records.")

# =========================================================
# PAGE 3: DATA ENTRY
# =========================================================
elif page == "📝 Data Entry":
    st.markdown('<div class="main-header">Data Management</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["👤 Manual Entry", "📂 Bulk CSV Upload"])
    
    with tab1:
        with st.form("manual_entry", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Full Name")
                gender = st.selectbox("Gender", ["Male", "Female", "Other"])
                grade = st.number_input("Grade", 1, 12, 9)
                income = st.number_input("Annual Income", 0, 1000000, 50000)
                caste = st.selectbox("Caste", ["General", "OBC", "SC", "ST"])
            with col2:
                attendance = st.slider("Attendance %", 0, 100, 85)
                parent_edu = st.selectbox("Parent Literacy", ["None", "Primary", "Secondary", "Graduate"])
                migrant = st.checkbox("Migrant Worker Family")
                laborer = st.checkbox("Seasonal Laborer")
                dropout = st.checkbox("Sibling Dropout")
            
            if st.form_submit_button("💾 Save Record", type="primary"):
                if name:
                    sid = run_query("INSERT INTO students (name, grade, annual_income, caste_category, gender) VALUES (%s, %s, %s, %s, %s) RETURNING student_id", 
                                   (name, grade, income, caste, gender), is_write=True)
                    if sid:
                        # Correct column names per schema.sql: migrant_family, seasonal_labor
                        run_query("""INSERT INTO social_risk (student_id, parent_education_level, migrant_family, seasonal_labor, sibling_dropout) 
                                     VALUES (%s, %s, %s, %s, %s)""", (sid, parent_edu, migrant, laborer, dropout), is_write=True)
                        run_query("INSERT INTO attendance (student_id, attendance_percent) VALUES (%s, %s)", (sid, attendance), is_write=True)
                        st.cache_data.clear() # Clear cache so Intervention Center sees new data
                        st.success(f"Added Student ID: {sid}")
                        st.rerun()

    with tab2:
        uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            st.dataframe(df.head())
            if st.button("🚀 Process & Upload", type="primary"):
                progress = st.progress(0)
                for idx, row in df.iterrows():
                    # Batch inserts for each student
                    sid = run_query("INSERT INTO students (name, grade, annual_income, caste_category, gender) VALUES (%s, %s, %s, %s, %s) RETURNING student_id", 
                                   (row['name'], row['grade'], row['income'], row['caste'], row['gender']), is_write=True)
                    if sid:
                        run_query("""INSERT INTO social_risk (student_id, parent_education_level, migrant_family, seasonal_labor, sibling_dropout) 
                                     VALUES (%s, %s, %s, %s, %s)""", 
                                  (sid, row['parent_edu'], bool(row.get('is_migrant')), bool(row.get('is_laborer')), bool(row.get('is_sibling_dropout'))), is_write=True)
                        run_query("INSERT INTO attendance (student_id, attendance_percent) VALUES (%s, %s)", (sid, row['attendance']), is_write=True)
                        run_query("INSERT INTO exam_scores (student_id, subject, score) VALUES (%s, 'General', %s)", (sid, row['score']), is_write=True)
                    progress.progress((idx + 1) / len(df))
                
                st.cache_data.clear()
                st.success("Batch Upload Successful!")
                st.rerun()