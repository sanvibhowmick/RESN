import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from db_connector import run_query
from utils import DropoutInterventionSystem

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="RESN | Rural Education Safety Net",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS FOR MODERN LOOK ---
st.markdown("""
    <style>
    /* Main theme colors */
    :root {
        --primary-color: #2E7D32;
        --secondary-color: #FFA726;
        --danger-color: #D32F2F;
        --warning-color: #F57C00;
        --success-color: #388E3C;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Modern card styling */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        color: white;
        margin: 0.5rem 0;
    }
    
    .metric-card-green {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    }
    
    .metric-card-orange {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    }
    
    .metric-card-blue {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    }
    
    /* Header styling */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #2E7D32;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #2E7D32;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.5rem 1.5rem;
        border-radius: 25px;
        font-weight: 600;
        font-size: 1.1rem;
        margin: 1rem 0;
    }
    
    .status-high-risk {
        background-color: #ffebee;
        color: #c62828;
        border: 2px solid #c62828;
    }
    
    .status-watch {
        background-color: #fff3e0;
        color: #e65100;
        border: 2px solid #e65100;
    }
    
    .status-safe {
        background-color: #e8f5e9;
        color: #2e7d32;
        border: 2px solid #2e7d32;
    }
    
    /* Action cards */
    .action-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        margin: 1rem 0;
        border-left: 4px solid #2E7D32;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #f8f9fa;
    }
    
    /* Button styling */
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #2E7D32 0%, #66BB6A 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-size: 1.1rem;
        font-weight: 600;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(46,125,50,0.3);
    }
    
    /* Info boxes */
    .info-box {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1976d2;
        margin: 1rem 0;
    }
    
    /* Download button custom */
    .download-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.75rem 2rem;
        border-radius: 8px;
        text-decoration: none;
        display: inline-block;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .download-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102,126,234,0.4);
    }
    </style>
""", unsafe_allow_html=True)

# Initialize the System Logic
@st.cache_resource
def get_system():
    return DropoutInterventionSystem()

system = get_system()

# --- MODERN SIDEBAR ---
with st.sidebar:
    st.markdown("### 🌾 RESN Control Panel")
    st.markdown("---")
    
    page = st.radio(
        "Navigation",
        ["📊 Dashboard", "🚨 Intervention Center"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### 📈 Quick Stats")
    
    # Mini stats in sidebar
    total_students = run_query("SELECT COUNT(*) as count FROM students").iloc[0]['count']
    st.metric("Total Students", total_students, delta=None)
    
    st.markdown("---")
    st.markdown("### 🔔 System Status")
    st.success("✓ Database Connected")
    st.success("✓ AI Engine Active")
    
    st.markdown("---")
    st.caption("Rural Education Safety Net v2.0")

# =========================================================
# PAGE 1: MODERN DASHBOARD
# =========================================================
if page == "📊 Dashboard":
    # Header
    st.markdown('<h1 class="main-header">📊 School Performance Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Real-time insights into student risk factors and academic performance</p>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- KEY METRICS ROW ---
    total_students = run_query("SELECT COUNT(*) as count FROM students").iloc[0]['count']
    
    risk_sql = """
    SELECT COUNT(DISTINCT s.student_id) as count
    FROM students s
    LEFT JOIN attendance a ON s.student_id = a.student_id
    LEFT JOIN exam_scores e ON s.student_id = e.student_id
    WHERE a.attendance_percent < 75 OR e.score < 35
    """
    at_risk_count = run_query(risk_sql).iloc[0]['count']
    risk_percentage = round((at_risk_count / total_students * 100), 1) if total_students > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card metric-card-blue">
            <h3 style="margin:0; font-size:2.5rem;">{total_students}</h3>
            <p style="margin:0.5rem 0 0 0; opacity:0.9;">Total Students</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card metric-card-orange">
            <h3 style="margin:0; font-size:2.5rem;">{at_risk_count}</h3>
            <p style="margin:0.5rem 0 0 0; opacity:0.9;">At Risk ({risk_percentage}%)</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card metric-card-green">
            <h3 style="margin:0; font-size:2.5rem;">₹12,000</h3>
            <p style="margin:0.5rem 0 0 0; opacity:0.9;">Scholarships Disbursed</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        safe_count = total_students - at_risk_count
        st.markdown(f"""
        <div class="metric-card">
            <h3 style="margin:0; font-size:2.5rem;">{safe_count}</h3>
            <p style="margin:0.5rem 0 0 0; opacity:0.9;">Students on Track</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # --- VISUALIZATIONS ---
    st.markdown('<h2 class="section-header">📈 Analytics & Insights</h2>', unsafe_allow_html=True)
    
    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        st.markdown("#### 📉 Attendance vs Academic Performance")
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
                df_corr, 
                x="attendance_percent", 
                y="avg_score", 
                color="caste_category",
                size="avg_score",
                hover_data=["name"],
                labels={
                    "attendance_percent": "Attendance %",
                    "avg_score": "Average Score",
                    "caste_category": "Category"
                },
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_corr.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12),
                height=400
            )
            st.plotly_chart(fig_corr, use_container_width=True)
        else:
            st.info("📊 Insufficient data for correlation analysis")

    with col_right:
        st.markdown("#### ⚠️ Primary Risk Factors")
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
            fig_bar = px.bar(
                df_melted, 
                x="Risk Factor", 
                y="Count", 
                color="Risk Factor",
                color_discrete_sequence=['#F57C00', '#D32F2F', '#7B1FA2']
            )
            fig_bar.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                showlegend=False,
                font=dict(size=12),
                height=400
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("📊 No risk factor data available")

# =========================================================
# PAGE 2: MODERN INTERVENTION CENTER
# =========================================================
elif page == "🚨 Intervention Center":
    st.markdown('<h1 class="main-header">🚨 Student Intervention System</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">AI-powered risk assessment and personalized intervention planning</p>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- STUDENT SELECTION ---
    st.markdown('<h2 class="section-header">🔍 Select Student</h2>', unsafe_allow_html=True)
    
    students_df = run_query("SELECT student_id, name FROM students ORDER BY name")
    student_map = dict(zip(students_df['name'], students_df['student_id']))
    
    col_sel1, col_sel2, col_sel3 = st.columns([3, 2, 1])
    
    with col_sel1:
        selected_name = st.selectbox(
            "Student Name",
            students_df['name'],
            help="Search and select a student to analyze"
        )
    
    with col_sel2:
        language = st.selectbox(
            "Communication Language",
            ["Hindi", "English", "Tamil", "Marathi", "Bengali"],
            help="Language for parent communication scripts"
        )
    
    with col_sel3:
        st.markdown("<br>", unsafe_allow_html=True)
        analyze_button = st.button("🚀 Analyze", use_container_width=True)

    # --- ANALYSIS SECTION ---
    if analyze_button:
        student_id = student_map[selected_name]
        
        with st.spinner(f"🔄 Running AI analysis for {selected_name}..."):
            report = system.process_intervention(student_id, target_language=language)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- STATUS DISPLAY ---
        status = report['status']
        
        if "HIGH RISK" in status:
            st.markdown(f'<div class="status-badge status-high-risk">🚨 {status}</div>', unsafe_allow_html=True)
            st.error("⚠️ **Action Required:** Immediate home visit and financial aid assessment needed")
        elif "ACADEMIC WATCH" in status:
            st.markdown(f'<div class="status-badge status-watch">⚠️ {status}</div>', unsafe_allow_html=True)
            st.warning("📋 **Teacher Attention Needed:** Academic support recommended")
        else:
            st.markdown(f'<div class="status-badge status-safe">✅ {status}</div>', unsafe_allow_html=True)
            st.success("🎉 Student is performing well and on track")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- INTERVENTIONS DISPLAY ---
        if report['actions']:
            st.markdown('<h2 class="section-header">📋 Generated Interventions</h2>', unsafe_allow_html=True)
            
            for i, action in enumerate(report['actions'], 1):
                with st.container():
                    if action['type'] == 'script':
                        with st.expander(f"🗣️ Home Visit Communication Script ({language})", expanded=True):
                            st.markdown("##### Script for Parent Meeting")
                            st.info("👥 **Instructions:** Read this script during the home visit. It's tailored to the parent's literacy level and specific risk factors.")
                            st.code(action['content'], language=None)
                            st.caption("🤖 AI-generated based on student profile and cultural context")

                    elif action['type'] == 'file':
                        with st.expander(f"📄 Government Scholarship Application", expanded=True):
                            st.markdown("##### Matched Financial Aid Program")
                            st.success(f"**Scheme:** {action['description']}")
                            st.markdown("---")
                            
                            col_download1, col_download2 = st.columns([1, 3])
                            with col_download1:
                                with open(action['path'], "rb") as pdf_file:
                                    st.download_button(
                                        label="📥 Download PDF",
                                        data=pdf_file,
                                        file_name=os.path.basename(action['path']),
                                        mime="application/pdf",
                                        use_container_width=True
                                    )
                            with col_download2:
                                st.caption("🔒 Pre-filled form with student details. Assist family with submission process.")

                    elif action['type'] == 'teacher_plan':
                        with st.expander(f"👨‍🏫 Remedial Teaching Plan", expanded=True):
                            st.markdown("##### Personalized Academic Support Strategy")
                            st.markdown(action['content'])
                            st.caption("📚 Implement this plan over the next 4-6 weeks with regular progress monitoring")
                
                st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.balloons()
            st.success("### 🎉 No Intervention Required")
            st.info("This student is performing well academically and shows no significant risk factors. Continue regular monitoring.")