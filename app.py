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

# --- CUSTOM CSS (Restored to original style) ---
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.5rem; }
    .sub-header { font-size: 1.1rem; color: #64748B; margin-bottom: 2rem; border-bottom: 1px solid #E2E8F0; padding-bottom: 1rem; }
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

# Initialize Agentic Orchestrator
@st.cache_resource
def get_orchestrator():
    return RESNOrchestrator()

orchestrator = get_orchestrator()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🌾 RESN Platform")
    st.caption("Rural Education Safety Net")
    st.divider()
    page = st.radio("Navigation", ["📊 Dashboard", "🚨 Intervention Center", "📝 Data Entry"])
    
    total = 0 
    try:
        df_total = run_query("SELECT COUNT(*) as count FROM students", return_dict=False)
        if df_total is not None and not df_total.empty:
            total = int(df_total.iloc[0]['count'])
        st.metric("Total Students Enrolled", total)
        st.success("🟢 System Online")
    except Exception as e:
        st.error(f"🔴 Dashboard Error: {str(e)}")

# =========================================================
# PAGE 1: DASHBOARD
# =========================================================
if page == "📊 Dashboard":
    st.markdown('<div class="main-header">School Performance Analytics</div>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    risk_sql = """
        SELECT COUNT(DISTINCT s.student_id) as count
        FROM students s
        LEFT JOIN attendance a ON s.student_id = a.student_id
        LEFT JOIN exam_scores e ON s.student_id = e.student_id
        WHERE a.attendance_percent < 75 OR (e.score IS NOT NULL AND e.score < 35)
    """
    try:
        df_risk_count = run_query(risk_sql, return_dict=False)
        at_risk_count = int(df_risk_count.iloc[0]['count']) if df_risk_count is not None and not df_risk_count.empty else 0
    except Exception as e:
        st.warning(f"Could not calculate at-risk students: {str(e)}")
        at_risk_count = 0

    with c1:
        st.markdown(f'<div class="metric-container card-blue"><div class="metric-value">{total}</div><div class="metric-label">Total Students</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-container card-red"><div class="metric-value">{at_risk_count}</div><div class="metric-label">Needs Attention</div></div>', unsafe_allow_html=True)
    with c3:
        on_track = total - at_risk_count
        st.markdown(f'<div class="metric-container card-green"><div class="metric-value">{max(0, on_track)}</div><div class="metric-label">On Track</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">📉 Analytics & Trends</div>', unsafe_allow_html=True)
    col_l, col_r = st.columns(2)
    
    with col_l:
        st.markdown("#### Parental Literacy Profile")
        try:
            df_risk = run_query("SELECT parent_education_level as factor, COUNT(*) as count FROM social_risk GROUP BY factor", return_dict=False)
            if df_risk is not None and not df_risk.empty:
                fig = px.pie(df_risk, values='count', names='factor', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No parental education data available")
        except Exception as e:
            st.error(f"Error loading chart: {str(e)}")
            
    with col_r:
        st.markdown("#### Subject Performance Overview")
        try:
            df_acad = run_query("SELECT subject, AVG(score) as avg_score FROM exam_scores GROUP BY subject", return_dict=False)
            if df_acad is not None and not df_acad.empty:
                fig = px.bar(df_acad, x='subject', y='avg_score', color='avg_score', color_continuous_scale='Purples')
                fig.update_layout(yaxis_title="Average Score", xaxis_title="Subject")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No exam score data available")
        except Exception as e:
            st.error(f"Error loading chart: {str(e)}")

# =========================================================
# PAGE 2: INTERVENTION CENTER
# =========================================================
elif page == "🚨 Intervention Center":
    st.markdown('<div class="main-header">Student Intervention Center</div>', unsafe_allow_html=True)
    
    try:
        students_df = run_query("SELECT student_id, name FROM students ORDER BY name", return_dict=False)
    except Exception as e:
        st.error(f"Error loading students: {str(e)}")
        students_df = None
    
    if students_df is not None and not students_df.empty:
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
                    result = orchestrator.run_intervention_pipeline(sid, counseling_lang=lang)
                    analysis = result.get('analysis', {})
                    score = analysis.get('risk_score', 0)
                    status = analysis.get('status', 'NORMAL')
                    
                    col_gauge, col_details = st.columns([1, 2])
                    with col_gauge:
                        fig = go.Figure(go.Indicator(
                            mode="gauge+number",
                            value=score,
                            title={'text': "Risk Score"},
                            gauge={
                                'axis': {'range': [0, 100]},
                                'bar': {'color': "red" if score > 60 else ("orange" if score > 40 else "green")},
                                'steps': [
                                    {'range': [0, 40], 'color': "lightgreen"},
                                    {'range': [40, 60], 'color': "lightyellow"},
                                    {'range': [60, 100], 'color': "lightcoral"}
                                ],
                                'threshold': {
                                    'line': {'color': "red", 'width': 4},
                                    'thickness': 0.75,
                                    'value': 60
                                }
                            }
                        ))
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col_details:
                        if "HIGH" in status.upper():
                            st.markdown(f'<div class="status-badge status-high">🚨 {status}</div>', unsafe_allow_html=True)
                        elif "WATCH" in status.upper() or "WARN" in status.upper():
                            st.markdown(f'<div class="status-badge status-warn">⚠️ {status}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="status-badge status-safe">✅ {status}</div>', unsafe_allow_html=True)
                        
                        primary_drivers = analysis.get('primary_drivers', [])
                        if primary_drivers:
                            st.write(f"**Drivers:** {', '.join(primary_drivers)}")
                        
                        summary = analysis.get('summary_for_memory', '')
                        if summary:
                            st.info(f"**Summary:** {summary}")

                    if result.get('actions'):
                        st.markdown('<div class="section-title">📋 Recommended Actions</div>', unsafe_allow_html=True)
                        for action in result['actions']:
                            if action.get('type') == 'finance':
                                with st.expander("💰 Scholarship Application", expanded=True):
                                    action_data = action.get('data', {})
                                    st.success(f"Matched: {action_data.get('scheme', 'N/A')}")
                                    st.write(action_data.get('justification', ''))
                                    pdf_path = action_data.get('pdf_path', '')
                                    if pdf_path and os.path.exists(pdf_path):
                                        with open(pdf_path, "rb") as f:
                                            st.download_button(
                                                "📥 Download PDF",
                                                f,
                                                file_name=os.path.basename(pdf_path),
                                                mime="application/pdf"
                                            )
                            elif action.get('type') == 'counseling':
                                with st.expander(f"🗣️ Counseling Script ({lang})", expanded=True):
                                    script = action.get('data', {}).get('script', '')
                                    st.code(script, language='text')
                            elif action.get('type') == 'academic':
                                with st.expander("👨‍🏫 Teacher Remedial Card", expanded=True):
                                    plan = action.get('data', {}).get('remedial_plan', '')
                                    st.markdown(plan)
                except Exception as e:
                    st.error(f"Error running intervention pipeline: {str(e)}")
                    st.exception(e)

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
                st.subheader("Profile Info")
                name = st.text_input("Full Name")
                gender = st.selectbox("Gender", ["Male", "Female", "Other"])
                grade = st.number_input("Grade", 1, 12, 9)
                income = st.number_input("Annual Income", 0, 10000000, 50000, 1000)
                caste = st.selectbox("Caste", ["General", "OBC", "SC", "ST"])
            with col2:
                st.subheader("Social Factors")
                attendance = st.slider("Attendance %", 0, 100, 85)
                parent_edu = st.selectbox("Parent Literacy", ["None", "Primary", "Secondary", "Graduate"])
                migrant = st.checkbox("Migrant Worker Family")
                laborer = st.checkbox("Seasonal Laborer")
                dropout = st.checkbox("Sibling Dropout")
            
            if st.form_submit_button("💾 Save Record", type="primary"):
                if name.strip():
                    try:
                        # Insert student
                        sid = run_query("""
                            INSERT INTO students (name, grade, annual_income, caste_category, gender) 
                            VALUES (%s, %s, %s, %s, %s) RETURNING student_id
                        """, (name, grade, income, caste, gender), is_write=True)
                        
                        if sid:
                            # Insert social factors
                            run_query("""
                                INSERT INTO social_risk (student_id, parent_education_level, migrant_worker, seasonal_laborer, sibling_dropout)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (sid, parent_edu, migrant, laborer, dropout), is_write=True)
                            
                            # Insert attendance
                            run_query("INSERT INTO attendance (student_id, attendance_percent) VALUES (%s, %s)", (sid, attendance), is_write=True)
                            
                            st.success(f"✅ Successfully added student! ID: {sid}")
                            st.balloons()
                            st.rerun()
                    except Exception as e:
                        st.error(f"Database error: {str(e)}")
                else:
                    st.warning("Please enter a valid name")

    with tab2:
        st.markdown("#### Batch Upload")
        st.caption("Expected columns: `name`, `grade`, `income`, `caste`, `gender`, `parent_edu`, `attendance`, `score`, `is_migrant`, `is_laborer`, `is_sibling_dropout`")
        uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file, on_bad_lines='skip')
                st.write("Preview of data:")
                st.dataframe(df.head(10))
                
                if st.button("🚀 Process & Upload", type="primary"):
                    success_count = 0
                    error_count = 0
                    progress_bar = st.progress(0)
                    
                    for idx, row in df.iterrows():
                        try:
                            # 1. Insert Student Profile
                            sid = run_query("""
                                INSERT INTO students (name, grade, annual_income, caste_category, gender) 
                                VALUES (%s, %s, %s, %s, %s) RETURNING student_id
                            """, (str(row['name']), int(row['grade']), int(row['income']), str(row['caste']), str(row['gender'])), is_write=True)
                            
                            if sid:
                                # 2. Insert Social Factors (Mapping CSV Booleans)
                                run_query("""
                                    INSERT INTO social_risk (student_id, parent_education_level, migrant_worker, seasonal_laborer, sibling_dropout) 
                                    VALUES (%s, %s, %s, %s, %s)
                                """, (sid, str(row['parent_edu']), bool(row.get('is_migrant', False)), 
                                      bool(row.get('is_laborer', False)), bool(row.get('is_sibling_dropout', False))), is_write=True)
                                
                                # 3. Insert Attendance
                                run_query("INSERT INTO attendance (student_id, attendance_percent) VALUES (%s, %s)", 
                                          (sid, float(row['attendance'])), is_write=True)
                                
                                # 4. Insert Score (Academic)
                                run_query("INSERT INTO exam_scores (student_id, subject, score) VALUES (%s, %s, %s)", 
                                          (sid, 'General', float(row['score'])), is_write=True)
                                
                                success_count += 1
                        except Exception:
                            error_count += 1
                        progress_bar.progress((idx + 1) / len(df))
                    
                    st.success(f"✅ Upload Complete! Processed {success_count} records.")
                    if error_count > 0:
                        st.warning(f"⚠️ {error_count} records failed.")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")