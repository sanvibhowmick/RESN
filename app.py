import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import date
from db_connector import run_query
from utils import DropoutInterventionSystem

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="RESN | Rural Education Safety Net",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (THEME & READABILITY) ---
st.markdown("""
<style>
    /* Global Font & Spacing */
    html, body, [class*="css"] {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #333333;
    }
    
    /* Header Styling */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A8A; /* Dark Blue */
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #64748B; /* Slate Gray */
        margin-bottom: 2rem;
        border-bottom: 1px solid #E2E8F0;
        padding-bottom: 1rem;
    }
    
    /* Metric Cards - Clean Professional Look */
    .metric-container {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        background-color: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border-top: 4px solid #ccc; /* Default Border */
        height: 100%;
        transition: transform 0.2s;
    }
    .metric-container:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E293B;
        margin-bottom: 5px;
    }
    .metric-label {
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #64748B;
        font-weight: 600;
    }
    
    /* Card Accent Colors */
    .card-blue { border-top-color: #3B82F6; }
    .card-red { border-top-color: #EF4444; }
    .card-green { border-top-color: #10B981; }
    .card-purple { border-top-color: #8B5CF6; }

    /* Section Headers */
    .section-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #334155;
        margin-top: 2rem;
        margin-bottom: 1rem;
        border-left: 5px solid #1E3A8A;
        padding-left: 15px;
    }

    /* Risk Status Badges */
    .status-badge {
        padding: 15px;
        border-radius: 8px;
        font-weight: bold;
        font-size: 1.1rem;
        margin-top: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .status-high { background-color: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA; }
    .status-warn { background-color: #FFFBEB; color: #B45309; border: 1px solid #FDE68A; }
    .status-safe { background-color: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; }

</style>
""", unsafe_allow_html=True)

# Initialize System
@st.cache_resource
def get_system():
    return DropoutInterventionSystem()

system = get_system()

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2602/2602414.png", width=60)
    st.markdown("### 🌾 RESN Platform")
    st.caption("Rural Education Safety Net")
    st.markdown("---")
    
    page = st.radio(
        "Main Navigation",
        ["📊 Dashboard", "🚨 Intervention Center", "📝 Data Entry"],
    )
    st.markdown("---")
    
    # Live Sidebar Stats
    try:
        total_students = run_query("SELECT COUNT(*) as count FROM students").iloc[0]['count']
        st.metric("Total Students Enrolled", total_students)
        st.success("🟢 System Online")
    except Exception as e:
        st.error("🔴 DB Disconnected")
        st.caption(f"Error: {str(e)}")
        total_students = 0

# =========================================================
# PAGE 1: DASHBOARD
# =========================================================
if page == "📊 Dashboard":
    st.markdown('<div class="main-header">School Performance Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Real-time overview of attendance, academic performance, and risk factors.</div>', unsafe_allow_html=True)
    
    # --- METRICS ROW ---
    # Query: Count High Risk students
    risk_sql = """
        SELECT COUNT(DISTINCT s.student_id) as count
        FROM students s
        LEFT JOIN attendance a ON s.student_id = a.student_id
        LEFT JOIN exam_scores e ON s.student_id = e.student_id
        WHERE a.attendance_percent < 75 OR (e.score IS NOT NULL AND e.score < 35)
    """
    
    try:
        at_risk_count = run_query(risk_sql).iloc[0]['count']
    except Exception as e:
        at_risk_count = 0
    
    risk_pct = round((at_risk_count / total_students * 100), 1) if total_students > 0 else 0
    
    # Metrics Layout with clean cards
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown(f"""
        <div class="metric-container card-blue">
            <div class="metric-value">{total_students}</div>
            <div class="metric-label">Total Students</div>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        st.markdown(f"""
        <div class="metric-container card-red">
            <div class="metric-value">{at_risk_count}</div>
            <div class="metric-label">At Risk ({risk_pct}%)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with c3:
        st.markdown(f"""
        <div class="metric-container card-purple">
            <div class="metric-value">₹12k</div>
            <div class="metric-label">Funds Disbursed</div>
        </div>
        """, unsafe_allow_html=True)
    
    with c4:
        st.markdown(f"""
        <div class="metric-container card-green">
            <div class="metric-value">{total_students - at_risk_count}</div>
            <div class="metric-label">On Track</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- CHARTS ---
    st.markdown('<div class="section-title">📉 Analytics & Trends</div>', unsafe_allow_html=True)
    
    col_L, col_R = st.columns(2, gap="medium")
    
    with col_L:
        st.markdown("#### Attendance vs Academic Performance")
        st.caption("Correlation between attendance percentage and average exam scores.")
        
        try:
            df_corr = run_query("""
                SELECT 
                    s.name,
                    a.attendance_percent,
                    COALESCE(AVG(e.score), 0) as avg_score,
                    s.caste_category
                FROM students s
                JOIN attendance a ON s.student_id = a.student_id
                LEFT JOIN exam_scores e ON s.student_id = e.student_id
                GROUP BY s.student_id, s.name, a.attendance_percent, s.caste_category
            """)
            
            if not df_corr.empty:
                fig = px.scatter(
                    df_corr,
                    x="attendance_percent",
                    y="avg_score",
                    color="caste_category",
                    size_max=15,
                    hover_data=["name"],
                    color_discrete_sequence=px.colors.qualitative.Bold
                )
                fig.add_hline(y=35, line_dash="dot", line_color="red", annotation_text="Passing Threshold")
                
                # --- UPDATED BACKGROUND COLOR HERE ---
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)', # Transparent plot area
                    paper_bgcolor='rgba(0,0,0,0)', # Transparent paper area
                    height=400,
                    xaxis_title="Attendance %",
                    yaxis_title="Avg Score",
                    font=dict(family="Segoe UI", size=12, color="#333")
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data available. Please add students in the Data Entry tab.")
        except Exception as e:
            st.error("Error loading performance chart.")
    
    with col_R:
        st.markdown("#### ⚠️ Risk Factor Analysis")
        st.caption("Breakdown of social and economic factors contributing to dropout risk.")
        
        try:
            df_risk = run_query("""
                SELECT 
                    SUM(CASE WHEN seasonal_labor THEN 1 ELSE 0 END) as "Seasonal Labor",
                    SUM(CASE WHEN sibling_dropout THEN 1 ELSE 0 END) as "Sibling Dropout",
                    SUM(CASE WHEN parent_education_level = 'None' THEN 1 ELSE 0 END) as "Illiterate Parents"
                FROM social_risk
            """)
            
            if not df_risk.empty:
                df_melt = df_risk.melt(var_name="Risk Factor", value_name="Count")
                fig = px.bar(
                    df_melt,
                    x="Risk Factor",
                    y="Count",
                    color="Risk Factor",
                    color_discrete_map={
                        "Seasonal Labor": "#F59E0B",
                        "Sibling Dropout": "#EF4444",
                        "Illiterate Parents": "#8B5CF6"
                    }
                )
                # --- UPDATED BACKGROUND COLOR HERE ---
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)', # Transparent plot area
                    paper_bgcolor='rgba(0,0,0,0)', # Transparent paper area
                    showlegend=False,
                    height=400,
                    font=dict(family="Segoe UI", size=12, color="#333")
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No risk profile data available.")
        except Exception as e:
            st.error("Error loading risk chart.")

# =========================================================
# PAGE 2: INTERVENTION CENTER
# =========================================================
elif page == "🚨 Intervention Center":
    st.markdown('<div class="main-header">Student Intervention Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">AI-powered risk assessment and personalized support generation.</div>', unsafe_allow_html=True)
    
    # --- SELECTION ---
    try:
        students_df = run_query("SELECT student_id, name FROM students ORDER BY name")
        
        if not students_df.empty:
            student_map = dict(zip(students_df['name'], students_df['student_id']))
            
            with st.container():
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1: 
                    name = st.selectbox("Select Student", students_df['name'])
                with c2: 
                    lang = st.selectbox("Target Language", ["Hindi", "English", "Tamil", "Marathi", "Bengali"])
                with c3: 
                    st.write("") # Spacer
                    st.write("") # Spacer
                    analyze = st.button("🚀 Generate Risk Report", type="primary", use_container_width=True)
            
            st.divider()

            if analyze:
                sid = student_map[name]
                
                with st.spinner(f"Analyzing academic and social patterns for {name}..."):
                    try:
                        report = system.process_intervention(sid, target_language=lang)
                        
                        # --- RISK GAUGE ---
                        score = report.get('risk_score', 0)
                        
                        col_gauge, col_details = st.columns([1, 2])
                        
                        with col_gauge:
                            fig_gauge = go.Figure(go.Indicator(
                                mode="gauge+number",
                                value=score,
                                title={'text': "Risk Score (0-100)"},
                                gauge={
                                    'axis': {'range': [0, 100]},
                                    'bar': {'color': "#DC2626" if score > 60 else "#F59E0B"},
                                    'steps': [
                                        {'range': [0, 60], 'color': "#E5E7EB"},
                                        {'range': [60, 100], 'color': "#FEE2E2"}
                                    ],
                                    'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 60}
                                }
                            ))
                            # --- UPDATED BACKGROUND COLOR HERE ---
                            fig_gauge.update_layout(
                                height=250, 
                                margin=dict(l=20, r=20, t=30, b=20),
                                plot_bgcolor='rgba(0,0,0,0)', # Transparent
                                paper_bgcolor='rgba(0,0,0,0)', # Transparent
                            )
                            st.plotly_chart(fig_gauge, use_container_width=True)
                        
                        with col_details:
                            st.markdown("#### Assessment Status")
                            status = report.get('status', 'Unknown')
                            
                            if "HIGH RISK" in status:
                                st.markdown(f'<div class="status-badge status-high">🚨 {status}</div>', unsafe_allow_html=True)
                                st.error("Recommended Action: Immediate Home Visit + Financial Intervention")
                            elif "ACADEMIC WATCH" in status:
                                st.markdown(f'<div class="status-badge status-warn">⚠️ {status}</div>', unsafe_allow_html=True)
                                st.warning("Recommended Action: Remedial Classes + Teacher Counseling")
                            else:
                                st.markdown(f'<div class="status-badge status-safe">✅ {status}</div>', unsafe_allow_html=True)
                                st.success("Student is currently meeting attendance and academic requirements.")
                        
                        # --- ACTIONS ---
                        if report.get('actions'):
                            st.markdown('<div class="section-title">📋 Action Plan</div>', unsafe_allow_html=True)
                            
                            for action in report['actions']:
                                if action['type'] == 'script':
                                    with st.expander(f"🗣️ Home Visit Script ({lang})", expanded=True):
                                        st.markdown("**Read this to the parents/guardians:**")
                                        st.code(action['content'], language=None)
                                
                                elif action['type'] == 'file':
                                    with st.expander(f"📄 Generated Form ({action['description']})", expanded=True):
                                        st.info("This application form has been pre-filled based on eligibility.")
                                        if os.path.exists(action['path']):
                                            with open(action['path'], "rb") as f:
                                                st.download_button("📥 Download PDF Application", f, file_name=os.path.basename(action['path']), mime="application/pdf")
                                        else:
                                            st.warning("PDF simulation: File path not found.")
                                
                                elif action['type'] == 'teacher_plan':
                                    with st.expander(f"👨‍🏫 Remedial Plan for Teachers", expanded=True):
                                        st.markdown(action['content'])
                    
                    except Exception as e:
                        st.error(f"Analysis Error: {str(e)}")
        else:
            st.info("No students found. Please use the Data Entry tab to populate the database.")
    
    except Exception as e:
        st.error(f"Error loading students: {e}")

# =========================================================
# PAGE 3: DATA ENTRY
# =========================================================
elif page == "📝 Data Entry":
    st.markdown('<div class="main-header">Data Management</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Add new student records via form or bulk upload.</div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["👤 Single Entry Form", "📂 Bulk CSV Upload"])
    
    # --- TAB 1: MANUAL FORM ---
    with tab1:
        st.markdown("#### Student Registration Form")
        with st.form("student_entry_form", clear_on_submit=True):
            st.caption("Part 1: Demographics")
            c1, c2, c3 = st.columns(3)
            with c1: name = st.text_input("Full Name")
            with c2: gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            with c3: grade = st.number_input("Grade Level", min_value=1, max_value=12, step=1, value=9)
            
            c4, c5 = st.columns(2)
            with c4: caste = st.selectbox("Caste Category", ["General", "OBC", "SC", "ST"])
            with c5: income = st.number_input("Annual Family Income (₹)", min_value=0, step=1000, value=50000)
            
            st.divider()
            st.caption("Part 2: Risk Indicators")
            
            r1, r2, r3 = st.columns(3)
            with r1: labor = st.checkbox("Engaged in Seasonal Labor?")
            with r2: sibling = st.checkbox("Has Sibling Dropout History?")
            with r3: migrant = st.checkbox("Migrant Family?")
            
            parent_edu = st.selectbox("Parents' Education Level", ["None", "Primary", "Secondary", "Graduate"])
            
            st.divider()
            st.caption("Part 3: Academic Baseline")
            att_pct = st.slider("Current Attendance %", 0, 100, 75)
            
            st.write("")
            submitted = st.form_submit_button("💾 Save Record", type="primary", use_container_width=True)
            
            if submitted:
                if name.strip():
                    try:
                        # 1. Insert Student
                        sql_student = """
                            INSERT INTO students (name, grade, annual_income, caste_category, gender)
                            VALUES (%s, %s, %s, %s, %s)
                            RETURNING student_id;
                        """
                        new_id = run_query(sql_student, (name, grade, income, caste, gender), is_write=True)
                        
                        if new_id:
                            # 2. Insert Risk
                            sql_risk = """
                                INSERT INTO social_risk (student_id, seasonal_labor, sibling_dropout, migrant_family, parent_education_level)
                                VALUES (%s, %s, %s, %s, %s)
                            """
                            run_query(sql_risk, (new_id, labor, sibling, migrant, parent_edu), is_write=True)
                            
                            # 3. Insert Attendance
                            sql_att = """
                                INSERT INTO attendance (student_id, month, attendance_percent)
                                VALUES (%s, %s, %s)
                            """
                            run_query(sql_att, (new_id, date.today(), att_pct), is_write=True)
                            
                            st.success(f"✅ Successfully registered {name} (ID: {new_id})")
                        else:
                            st.error("Database insert failed.")
                    except Exception as e:
                        st.error(f"Error saving data: {e}")
                else:
                    st.warning("Please enter a student name.")
    
    # --- TAB 2: BULK CSV UPLOAD ---
    with tab2:
        st.markdown("#### Batch Upload")
        st.info("Ensure CSV follows the format: `name, grade, gender, income, caste, attendance, parent_edu, score`")
        
        # Template
        template_data = pd.DataFrame(
            [["John Doe", 10, "Male", 45000, "General", 85, "Primary", 88]],
            columns=["name", "grade", "gender", "income", "caste", "attendance", "parent_edu", "score"]
        )
        csv_template = template_data.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Download CSV Template",
            data=csv_template,
            file_name="student_upload_template.csv",
            mime="text/csv",
        )
        
        uploaded_file = st.file_uploader("Upload Student CSV", type=["csv"])
        
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                st.write("Preview:")
                st.dataframe(df.head(), use_container_width=True)
                
                if st.button("🚀 Process & Upload", type="primary"):
                    progress_bar = st.progress(0)
                    success_count = 0
                    errors = []
                    
                    for i, row in df.iterrows():
                        try:
                            # 1. Insert Student
                            sql_student = """
                                INSERT INTO students (name, grade, annual_income, caste_category, gender)
                                VALUES (%s, %s, %s, %s, %s)
                                RETURNING student_id;
                            """
                            new_id = run_query(
                                sql_student,
                                (row['name'], int(row['grade']), int(row['income']), row['caste'], row['gender']),
                                is_write=True
                            )
                            
                            if new_id:
                                # 2. Risk
                                run_query(
                                    "INSERT INTO social_risk (student_id, parent_education_level) VALUES (%s, %s)",
                                    (new_id, row['parent_edu']),
                                    is_write=True
                                )
                                # 3. Attendance
                                run_query(
                                    "INSERT INTO attendance (student_id, month, attendance_percent) VALUES (%s, %s, %s)",
                                    (new_id, date.today(), int(row['attendance'])),
                                    is_write=True
                                )
                                # 4. Score
                                run_query(
                                    "INSERT INTO exam_scores (student_id, subject, exam_date, score) VALUES (%s, %s, %s, %s)",
                                    (new_id, 'Math', date.today(), float(row['score'])),
                                    is_write=True
                                )
                                success_count += 1
                        except Exception as e:
                            errors.append(f"Row {i+1} ({row['name']}): {str(e)}")
                        
                        progress_bar.progress((i + 1) / len(df))
                    
                    st.success(f"✅ Upload Complete: {success_count}/{len(df)} records added.")
                    if errors:
                        with st.expander("⚠️ View Errors"):
                            for e in errors: st.error(e)
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

    # --- DATABASE CLEANUP SECTION ---
    st.markdown("---")
    with st.expander("🔧 Database Maintenance"):
        st.warning("Utilities for managing inconsistent data.")
        col_clean1, col_clean2 = st.columns([3, 1])
        with col_clean1:
            st.markdown("**Remove Orphan Records:** Deletes students who have no exam scores (often caused by partial uploads).")
        with col_clean2:
            if st.button("🗑️ Run Cleanup", type="secondary"):
                try:
                    cleanup_query = "SELECT student_id FROM students WHERE student_id NOT IN (SELECT DISTINCT student_id FROM exam_scores)"
                    df_orphans = run_query(cleanup_query)
                    
                    if not df_orphans.empty:
                        orphan_ids = tuple(df_orphans['student_id'].tolist())
                        ids_str = f"({orphan_ids[0]})" if len(orphan_ids) == 1 else str(orphan_ids)
                        
                        run_query(f"DELETE FROM social_risk WHERE student_id IN {ids_str}", is_write=True)
                        run_query(f"DELETE FROM attendance WHERE student_id IN {ids_str}", is_write=True)
                        run_query(f"DELETE FROM students WHERE student_id IN {ids_str}", is_write=True)
                        
                        st.success(f"Removed {len(orphan_ids)} records.")
                        st.rerun()
                    else:
                        st.success("Database is clean.")
                except Exception as e:
                    st.error(f"Cleanup failed: {e}")