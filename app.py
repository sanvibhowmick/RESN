import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import date
from db_connector import run_query, run_transaction
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
    .main-header { font-size: 2.5rem; font-weight: 700; color: #FFFFFF; margin-bottom: 0.5rem; }
    .metric-container { background-color: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); border-top: 4px solid #ccc; text-align: center; height: 100%; }
    .metric-value { font-size: 2.2rem; font-weight: 800; color: #1E293B; }
    .metric-label { font-size: 0.9rem; text-transform: uppercase; color: #64748B; font-weight: 600; }
    .card-blue { border-top-color: #3B82F6; }
    .card-red { border-top-color: #EF4444; }
    .card-green { border-top-color: #10B981; }
    .section-title { font-size: 1.5rem; font-weight: 700; color: #FFFFFF; margin-top: 2rem; border-left: 5px solid #1E3A8A; padding-left: 15px; margin-bottom: 1rem; }
    .status-badge { padding: 15px; border-radius: 8px; font-weight: bold; text-align: center; margin-top: 10px; }
    .status-high { background-color: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA; }
    .status-warn { background-color: #FFFBEB; color: #B45309; border: 1px solid #FDE68A; }
    .status-safe { background-color: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; }
    .similar-case-tag { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 700; margin-right: 8px; }
    .tag-danger { background-color: #FEF2F2; color: #B91C1C; }
    .tag-watch { background-color: #FFFBEB; color: #B45309; }
    .tag-normal { background-color: #ECFDF5; color: #047857; }
</style>
""", unsafe_allow_html=True)

# --- ORCHESTRATOR & QUERY CACHING ---
@st.cache_resource
def get_orchestrator():
    """Initializes the multi-agent orchestrator dynamically with resource caching."""
    return RESNOrchestrator()

@st.cache_data(ttl=60)
def get_cached_students():
    """Fetches student list with 60-second caching to improve UI responsiveness."""
    df = run_query("SELECT student_id, name FROM students ORDER BY name", return_dict=False)
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame(columns=['student_id', 'name'])

@st.cache_data(ttl=60)
def get_cached_student_count():
    """Fetches student count with caching to eliminate UI freezes on dropdown clicks."""
    count_res = run_query("SELECT COUNT(*) as count FROM students")
    return count_res[0]['count'] if count_res else 0

orchestrator = get_orchestrator()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🌾 RESN Platform")
    st.caption("Rural Education Safety Net")
    st.divider()
    page = st.radio("Navigation", ["📊 Dashboard", "🚨 Intervention Center", "📝 Data Entry"])
    
    try:
        total_students = get_cached_student_count()
        st.metric("Total Students Enrolled", total_students)
        st.success("🟢 System Online")
        st.caption("⚡ Async Worker Pool: Ready (4 Workers)")
    except Exception:
        st.error("🔴 Connection Error")
        total_students = 0

# =========================================================
# PAGE 1: DASHBOARD
# =========================================================
if page == "📊 Dashboard":
    st.markdown('<div class="main-header">School Performance Analytics</div>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    
    # Calculate Risk Count based on attendance < 75% or scores < 35
    risk_sql = """
        SELECT COUNT(DISTINCT s.student_id) as count
        FROM students s
        LEFT JOIN attendance a ON s.student_id = a.student_id
        LEFT JOIN exam_scores e ON s.student_id = e.student_id
        WHERE a.attendance_percent < 75 OR (e.score IS NOT NULL AND e.score < 35)
    """
    df_risk_count = run_query(risk_sql, return_dict=False)
    at_risk_count = int(df_risk_count.iloc[0]['count']) if not df_risk_count.empty else 0

    with c1: st.markdown(f'<div class="metric-container card-blue"><div class="metric-value">{total_students}</div><div class="metric-label">Total Students</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-container card-red"><div class="metric-value">{at_risk_count}</div><div class="metric-label">Needs Attention</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-container card-green"><div class="metric-value">{max(0, total_students - at_risk_count)}</div><div class="metric-label">On Track</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">📉 Analytics & Trends</div>', unsafe_allow_html=True)
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### Parental Literacy Profile")
        df_risk = run_query(
            "SELECT parent_education_level as factor, COUNT(*) as count FROM social_risk GROUP BY factor",
            return_dict=False,
        )
        if not df_risk.empty:
            st.plotly_chart(
                px.pie(df_risk, values="count", names="factor", hole=0.4),
                use_container_width=True,
            )
        else:
            st.info("No data available")

    with col_r:
        st.markdown("#### Subject Performance Overview")
        df_acad = run_query(
            "SELECT subject, AVG(score) as avg_score FROM exam_scores GROUP BY subject",
            return_dict=False,
        )
        if not df_acad.empty:
            st.plotly_chart(
                px.bar(df_acad, x="subject", y="avg_score", color="subject"),
                use_container_width=True,
            )
        else:
            st.info("No data available")

# =========================================================
# PAGE 2: INTERVENTION CENTER
# =========================================================
elif page == "🚨 Intervention Center":
    st.markdown('<div class="main-header">Student Intervention Center</div>', unsafe_allow_html=True)
    
    students_df = get_cached_students()
    
    if not students_df.empty:
        tab_analysis, tab_improvements = st.tabs([
            "🚀 Real-time Triage & Analysis", 
            "📈 Log Student Improvements"
        ])

        with tab_analysis:
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
                        st.session_state[f"analysis_result_{sid}"] = result
                    except Exception as e:
                        st.error(f"Analysis Failed: {e}")

            result = st.session_state.get(f"analysis_result_{sid}")
            if result:
                analysis = result.get('analysis', {})
                status = analysis.get('status', 'NORMAL')
                score = analysis.get('risk_score', 0)
                trajectory = result.get('trajectory', {})

                col_gauge, col_details = st.columns([1, 2])
                with col_gauge:
                    gauge_color = "#EF4444" if score >= 60 else ("#F59E0B" if score >= 30 else "#10B981")
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number", value=score,
                        title={'text': "Risk Score"},
                        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': gauge_color}}
                    ))
                    st.plotly_chart(fig, use_container_width=True)

                with col_details:
                    badge_class = "status-high" if score >= 60 else ("status-warn" if score >= 30 else "status-safe")
                    st.markdown(f'<div class="status-badge {badge_class}">{status}</div>', unsafe_allow_html=True)
                    st.info(f"**AI Summary:** {analysis.get('summary_for_memory', '')}")

                # --- LONGITUDINAL PROGRESS & TRAJECTORY TRACKING ---
                if trajectory:
                    st.markdown('<div class="section-title">📈 Longitudinal Progress Tracking</div>', unsafe_allow_html=True)
                    if trajectory.get('is_baseline'):
                        st.info(
                            f"ℹ️ **Baseline Diagnostic Run (Run #1):** Initial risk profile calibrated at **{score}% ({status})**. "
                            f"Subsequent analyses will automatically track measurable improvements, grade shifts, attendance gains, or risk regressions."
                        )
                    else:
                        trend = trajectory.get('trend', 'STEADY')
                        if trend == "IMPROVEMENT":
                            st.success(f"### {trajectory.get('title')}")
                        elif trend == "DEPROVEMENT":
                            st.error(f"### {trajectory.get('title')}")
                        else:
                            st.info(f"### {trajectory.get('title')}")

                        m1, m2, m3, m4 = st.columns(4)
                        with m1:
                            st.metric(
                                label="Risk Score",
                                value=f"{trajectory.get('current_score')}%",
                                delta=f"{trajectory.get('delta_score', 0):+d} pts",
                                delta_color="inverse"
                            )
                        with m2:
                            st.metric(
                                label="Attendance Rate",
                                value=f"{trajectory.get('current_attendance', 0.0):.1f}%",
                                delta=f"{trajectory.get('delta_attendance', 0.0):+.1f}%",
                                delta_color="normal"
                            )
                        with m3:
                            st.metric(
                                label="Latest Exam Score",
                                value=f"{trajectory.get('current_exam_score', 0.0):.1f}",
                                delta=f"{trajectory.get('delta_exam_score', 0.0):+.1f} pts",
                                delta_color="normal"
                            )
                        with m4:
                            prev_st = trajectory.get('prev_status', 'N/A')
                            curr_st = trajectory.get('current_status', 'N/A')
                            st.metric(
                                label="Triage Shift",
                                value=curr_st,
                                delta=f"{prev_st} → {curr_st}",
                                delta_color="off"
                            )

                # --- PAST MEASURES TAKEN & IMPROVEMENTS SEEN ---
                st.markdown('<div class="section-title">📋 Past Measures Taken & Improvements Seen</div>', unsafe_allow_html=True)
                student_measures = run_query(
                    """
                    SELECT improvement_id, previous_attendance, new_attendance, subject, 
                           previous_score, new_score, grade, outcome_status, measures_taken, notes, created_at
                    FROM student_improvements
                    WHERE student_id = %s
                    ORDER BY created_at DESC
                    """,
                    (sid,),
                    return_dict=True
                ) or []

                if student_measures:
                    for i, imp in enumerate(student_measures, start=1):
                        p_att = imp.get('previous_attendance')
                        n_att = imp.get('new_attendance')
                        p_sc = imp.get('previous_score')
                        n_sc = imp.get('new_score')
                        subj = imp.get('subject', 'Academics')
                        outcome = imp.get('outcome_status', 'Improved')
                        measures = imp.get('measures_taken', 'N/A')
                        notes = imp.get('notes', '')
                        rec_date = str(imp.get('created_at', ''))[:10]

                        card_header = f"Measure #{i}: {outcome}"
                        if rec_date:
                            card_header += f" · Logged {rec_date}"

                        with st.expander(card_header, expanded=(i == 1)):
                            c_m1, c_m2, c_m3 = st.columns(3)
                            with c_m1:
                                if p_att is not None and n_att is not None:
                                    diff_att = n_att - p_att
                                    st.metric("Attendance Shift", f"{n_att:.1f}%", f"{diff_att:+.1f}%")
                                else:
                                    st.metric("Attendance", "N/A")
                            with c_m2:
                                if p_sc is not None and n_sc is not None:
                                    diff_sc = n_sc - p_sc
                                    st.metric(f"{subj} Score", f"{n_sc:.0f}/100", f"{diff_sc:+.0f} pts")
                                else:
                                    st.metric(f"{subj}", "N/A")
                            with c_m3:
                                st.metric("Academic Grade", f"Grade {imp.get('grade', 'N/A')}")

                            st.markdown(f"**🛠️ Specific Measures Implemented:**\n> {measures if measures else 'No specific measure description logged.'}")
                            if notes:
                                st.info(f"📝 **Caseworker Observation & Feedback:** {notes}")
                else:
                    st.info(f"ℹ️ No past intervention measures recorded yet for **{selected_name}**. Use the **📈 Log Student Improvements** tab to document actions, track attendance gains, and record test score increases.")

                # --- EXPLAINABLE AI (XAI / SHAP) BREAKDOWN ---
                shap_data = analysis.get('shap_explanation')
                if shap_data and (shap_data.get('risk_drivers') or shap_data.get('mitigating_factors')):
                    st.markdown('<div class="section-title">🔍 Explainable AI (XAI): Model Feature Attribution</div>', unsafe_allow_html=True)
                    st.caption(
                        f"Marginal feature contributions from PyTorch neural network weights relative to baseline population risk ({shap_data.get('base_rate', 0.15)*100:.1f}%):"
                    )
                    all_features = []
                    all_impacts = []
                    all_colors = []

                    # Protective buffers (green, negative impact reduces risk)
                    for item in reversed(shap_data.get('mitigating_factors', [])[:4]):
                        all_features.append(item['readable_name'])
                        all_impacts.append(item['impact'] * 100)
                        all_colors.append('#2ecc71')

                    # Risk escalators (red, positive impact increases risk)
                    for item in shap_data.get('risk_drivers', [])[:4]:
                        all_features.append(item['readable_name'])
                        all_impacts.append(item['impact'] * 100)
                        all_colors.append('#e74c3c')

                    if all_features:
                        min_val = min(all_impacts)
                        max_val = max(all_impacts)
                        x_min = min(min_val * 1.3, -8.0) if min_val < 0 else -5.0
                        x_max = max(max_val * 1.3, 8.0) if max_val > 0 else 5.0

                        shap_fig = go.Figure(go.Bar(
                            x=all_impacts,
                            y=all_features,
                            orientation='h',
                            marker=dict(color=all_colors),
                            text=[f"{val:+.1f}%" for val in all_impacts],
                            textposition="outside"
                        ))
                        shap_fig.update_layout(
                            xaxis_title="Contribution to Predicted Dropout Risk (%)",
                            yaxis_title="",
                            height=max(280, len(all_features) * 38),
                            margin=dict(l=10, r=50, t=20, b=20),
                            xaxis=dict(
                                range=[x_min, x_max],
                                zeroline=True,
                                zerolinecolor='gray',
                                zerolinewidth=1.5,
                                ticksuffix="%"
                            )
                        )
                        st.plotly_chart(shap_fig, use_container_width=True)

                        # --- AGENT LAYMAN'S TERMS EXPLANATION ---
                        layman_text = analysis.get('xai_layman_explanation')
                        if layman_text:
                            st.info(f"🗣️ **Risk Analyst Translation (Layman's Terms):** {layman_text}")

                        breakdown = analysis.get('feature_breakdown_layman')
                        if breakdown and isinstance(breakdown, list) and len(breakdown) > 0:
                            with st.expander("💬 View Factor-by-Factor Breakdown", expanded=False):
                                for item in breakdown:
                                    st.markdown(f"- **{item.get('feature', 'Factor')}**: {item.get('explanation', '')}")

                if result.get('actions'):
                    st.markdown('<div class="section-title">📋 Recommended Actions</div>', unsafe_allow_html=True)
                    for action in result['actions']:
                        with st.expander(f"Action: {action['type'].title()}", expanded=True):
                            if action['type'] == 'finance':
                                st.success(f"Matched: {action['data'].get('scheme', 'N/A')}")
                                if action['data'].get('urgency'):
                                    st.caption(f"🚨 Urgency: **{action['data'].get('urgency')}** | Benefit: **{action['data'].get('estimated_benefit', 'Government Financial Aid')}**")
                                st.write(action['data'].get('justification', ''))
                                
                                # Download button for scholarship PDF
                                pdf_path = action['data'].get('pdf_path')
                                if pdf_path and os.path.exists(pdf_path):
                                    with open(pdf_path, "rb") as f:
                                        st.download_button(
                                            label="📥 Download Filled Application (PDF)",
                                            data=f,
                                            file_name=os.path.basename(pdf_path),
                                            mime="application/pdf"
                                        )
                            elif action['type'] == 'counseling':
                                struct = action['data'].get('structured_counseling')
                                if struct:
                                    st.markdown(f"**Dialect/Language:** `{action['data'].get('language', 'Local Dialect')}`")
                                    for i, pt in enumerate(struct.get('talking_points', []), 1):
                                        st.markdown(f"**{i}.** {pt}")
                                    c_m1, c_m2 = st.columns(2)
                                    with c_m1:
                                        st.info(f"🌾 **Cultural Metaphor:** {struct.get('cultural_metaphor', 'N/A')}")
                                    with c_m2:
                                        st.success(f"❤️ **Emotional Hook:** {struct.get('emotional_hook', 'N/A')}")
                                else:
                                    st.code(action['data'].get('script', ''), language='text')

                            elif action['type'] == 'academic':
                                card = action['data'].get('action_card')
                                if card:
                                    st.markdown(f"### 📘 Subject Remediation: **{card.get('subject', 'General')}**")
                                    st.markdown(f"**🔍 The Diagnosis Question:**\n> *\"{card.get('diagnosis_question', '')}\"*")
                                    st.markdown(f"**💡 Rural Metaphor:**\n{card.get('real_world_analogy', '')}")
                                    st.markdown(f"**⚡ 5-Minute Fix Activity:**\n{card.get('five_minute_fix', '')}")
                                    if card.get('teacher_tips'):
                                        st.caption(f"📌 **Teacher Tip:** {card.get('teacher_tips')}")
                                elif 'remedial_plan' in action['data']:
                                    st.markdown(action['data']['remedial_plan'])
                                elif 'message' in action['data']:
                                    st.warning(f"⚠️ {action['data']['message']}")
                                elif 'error' in action['data']:
                                    st.error(f"❌ {action['data']['error']}")
                                else:
                                    st.write(action['data'])

                if 'message' in result:
                    st.success(f"ℹ️ {result['message']}")

                # --- SIMILAR PAST CASES (cross-student semantic memory) ---
                similar_cases = result.get('similar_cases') or []
                st.markdown('<div class="section-title">🔎 Similar Past Cases</div>', unsafe_allow_html=True)
                if similar_cases:
                    st.caption(
                        "Other students whose situations most closely match this case's risk cohort"
                    )
                    tag_map = {
                        "DANGER": ("tag-danger", "🔴"),
                        "WATCH": ("tag-watch", "🟡"),
                        "NORMAL": ("tag-normal", "🟢"),
                    }
                    for i, case in enumerate(similar_cases, start=1):
                        meta = case.get('metadata') or {}
                        case_status = str(meta.get('status', 'N/A')).upper()
                        case_score = meta.get('score', 'N/A')
                        tag_class, tag_emoji = tag_map.get(case_status, ("tag-normal", "⚪"))

                        distance = case.get('distance')
                        match_pct = None
                        if distance is not None:
                            match_pct = max(0, min(100, round((1 - float(distance)) * 100)))

                        created = case.get('created_at')
                        created_str = str(created)[:10] if created else "unknown date"

                        header = f"Case {i} — {tag_emoji} {case_status}"
                        if match_pct is not None:
                            header += f" · {match_pct}% match"

                        with st.expander(header):
                            decay_val = case.get('time_decay_factor')
                            decay_str = f" &nbsp;|&nbsp; Recency weight: {float(decay_val):.2f}" if decay_val is not None else ""
                            st.markdown(
                                f'<span class="similar-case-tag {tag_class}">{case_status}</span>'
                                f'<span style="color:#64748B; font-size:0.85rem;">Risk score: {case_score} &nbsp;|&nbsp; Logged: {created_str}{decay_str}</span>',
                                unsafe_allow_html=True
                            )
                            st.write(case.get('context_summary', 'No summary available.'))

                            # --- PRINT IMPROVEMENTS ALONG WITH SIMILAR CASES ---
                            imp = case.get('improvement')
                            if imp:
                                st.markdown("---")
                                st.markdown("##### 📈 Documented Improvement Post-Measures")
                                p_att = imp.get('previous_attendance')
                                n_att = imp.get('new_attendance')
                                p_sc = imp.get('previous_score')
                                n_sc = imp.get('new_score')
                                subj = imp.get('subject', 'Academics')
                                outcome = imp.get('outcome_status', 'Improved')
                                measures = imp.get('measures_taken', '')
                                notes = imp.get('notes', '')

                                c_imp1, c_imp2, c_imp3 = st.columns(3)
                                with c_imp1:
                                    if p_att is not None and n_att is not None:
                                        diff_att = n_att - p_att
                                        st.metric("Attendance", f"{n_att:.1f}%", f"{diff_att:+.1f}%")
                                with c_imp2:
                                    if p_sc is not None and n_sc is not None:
                                        diff_sc = n_sc - p_sc
                                        st.metric(f"{subj} Score", f"{n_sc:.0f}/100", f"{diff_sc:+.0f} pts")
                                with c_imp3:
                                    st.markdown(f"**Outcome:** `{outcome}`")

                                if measures:
                                    st.caption(f"🛠️ **Measures Implemented:** {measures}")
                                if notes:
                                    st.info(f"📝 **Caseworker Observation:** {notes}")
                            else:
                                st.caption("ℹ️ Baseline historical record (Post-intervention follow-up pending).")
                else:
                    st.info("No comparable past cases yet — this pattern hasn't been logged before.")

        # =========================================================
        # TAB 2: POST-INTERVENTION TRACKING & IMPROVEMENTS
        # =========================================================
        with tab_improvements:
            st.markdown("### 📈 Record Student Progress Post-Intervention")
            st.caption(
                "Track measurable academic and attendance improvements after intervention measures "
                "were implemented, and sync results back into institutional memory."
            )
            
            imp_student = st.selectbox("Select Student to Update", students_df['name'].tolist(), key="imp_student_sel")
            imp_sid = int(students_df[students_df['name'] == imp_student]['student_id'].values[0])
            
            # Fetch latest baseline context (newest records first)
            baseline_att_res = run_query(
                "SELECT attendance_percent FROM attendance WHERE student_id = %s ORDER BY month DESC, record_id DESC LIMIT 1",
                (imp_sid,)
            )
            curr_att = float(baseline_att_res[0]['attendance_percent']) if baseline_att_res else 75.0
            
            baseline_score_res = run_query(
                "SELECT subject, score FROM exam_scores WHERE student_id = %s ORDER BY exam_date DESC, score_id DESC LIMIT 1",
                (imp_sid,)
            )
            curr_subj = baseline_score_res[0]['subject'] if baseline_score_res else "Mathematics"
            curr_score = float(baseline_score_res[0]['score']) if baseline_score_res else 45.0

            with st.form("form_student_improvement", clear_on_submit=True):
                col_i1, col_i2 = st.columns(2)
                
                with col_i1:
                    st.markdown("#### 📅 Attendance Progress")
                    st.caption(f"Baseline Attendance: **{curr_att:.1f}%**")
                    new_attendance = st.slider(
                        "Updated Attendance Rate (%)", 
                        min_value=0.0, max_value=100.0, 
                        value=min(100.0, curr_att + 10.0), step=0.5
                    )
                    
                    st.markdown("#### 🎯 Intervention Measures Taken")
                    measures_taken = st.text_area(
                        "Specific Measures Implemented",
                        placeholder="e.g., Provided bicycle for 4km commute, enrolled in after-school math clinic, secured NSP Pre-Matric scholarship.",
                        help="Detail the actions that led to this student's change."
                    )
                
                with col_i2:
                    st.markdown("#### 📚 Academic Progress")
                    subject = st.selectbox(
                        "Subject Evaluated", 
                        ["Mathematics", "Science", "English", "Hindi", "Social Studies"],
                        index=0
                    )
                    st.caption(f"Baseline Score in {curr_subj}: **{curr_score:.0f}/100**")
                    new_score = st.slider(
                        "Updated Exam Score (0-100)", 
                        min_value=0.0, max_value=100.0, 
                        value=min(100.0, curr_score + 15.0), step=1.0
                    )
                    new_grade = st.selectbox(
                        "Current Academic Grade / Class",
                        [6, 7, 8, 9, 10, 11, 12],
                        index=3,
                        format_func=lambda g: f"Grade {g}"
                    )
                    outcome_status = st.selectbox(
                        "Outcome / Triage Trajectory",
                        ["Significant Improvement", "Moderate Improvement", "Stabilized", "Requires Further Support", "Regressed"],
                        index=0
                    )
                
                notes = st.text_input(
                    "Caseworker Observations & Future Goals", 
                    placeholder="e.g., Kavita now arrives punctually; family agreed to postpone seasonal labor until harvest holidays."
                )
                
                submit_improvement = st.form_submit_button("💾 Save Progress & Update Student Profile", type="primary", use_container_width=True)
                
                if submit_improvement:
                    try:
                        grade_val = int(new_grade) if isinstance(new_grade, int) else int(''.join(filter(str.isdigit, str(new_grade))) or 9)
                        
                        # 1. Insert record into student_improvements table & update student grade
                        insert_imp_sql = """
                            INSERT INTO student_improvements 
                            (student_id, previous_attendance, new_attendance, subject, previous_score, new_score, grade, outcome_status, measures_taken, notes)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        update_student_grade_sql = "UPDATE students SET grade = %s WHERE student_id = %s"
                        run_transaction([
                            (insert_imp_sql, (
                                imp_sid, curr_att, new_attendance, subject, curr_score, new_score, 
                                grade_val, outcome_status, measures_taken, notes
                            )),
                            (update_student_grade_sql, (grade_val, imp_sid))
                        ])
                        
                        # 2. Update real-time student attendance in attendance table
                        insert_att_sql = """
                            INSERT INTO attendance (student_id, month, attendance_percent)
                            VALUES (%s, %s, %s)
                        """
                        run_transaction([(insert_att_sql, (imp_sid, date.today(), new_attendance))])
                        
                        # 3. Update exam score in exam_scores table
                        insert_score_sql = """
                            INSERT INTO exam_scores (student_id, subject, score, exam_date)
                            VALUES (%s, %s, %s, %s)
                        """
                        run_transaction([(insert_score_sql, (imp_sid, subject, new_score, date.today()))])
                        
                        # 4. Add semantic reflection to PGVectorMemory so similar cases reflect this turnaround
                        memory_summary = (
                            f"Post-intervention follow-up for {imp_student}: Attendance improved from {curr_att:.1f}% to {new_attendance:.1f}%. "
                            f"{subject} score improved from {curr_score:.0f} to {new_score:.0f}. "
                            f"Measures: {measures_taken}. Trajectory: {outcome_status}. Notes: {notes}"
                        )
                        orchestrator.memory.add_memory(
                            student_id=imp_sid,
                            context_summary=memory_summary,
                            metadata={
                                "status": "IMPROVED" if outcome_status in ["Significant Improvement", "Moderate Improvement"] else "WATCH",
                                "score": max(0, int(100 - new_attendance)),
                                "type": "improvement",
                                "outcome": outcome_status
                            }
                        )
                        
                        # Invalidate cached analysis to ensure fresh evaluation
                        if f"analysis_result_{imp_sid}" in st.session_state:
                            del st.session_state[f"analysis_result_{imp_sid}"]

                        st.success(f"🎉 Successfully logged improvement for **{imp_student}**! Attendance and academic records updated in real-time.")
                    except Exception as err:
                        st.error(f"Failed to record improvement: {err}")

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
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.subheader("Profile Info")
                name = st.text_input("Full Name")
                age = st.number_input("Age", 5, 20, 14)
                gender = st.selectbox("Gender", ["Male", "Female", "Other"])
                grade = st.number_input("Grade", 1, 12, 9)
            with col2:
                st.subheader("Socio-Economic")
                caste = st.selectbox("Caste", ["General", "OBC", "SC", "ST"])
                income = st.number_input("Annual Income (INR)", 0, 1000000, 45000, step=5000)
                parent_edu = st.selectbox("Parent Literacy", ["None", "Primary", "Secondary", "Graduate"])
            with col3:
                st.subheader("Academics")
                att_pct = st.slider("Attendance Rate (%)", 0.0, 100.0, 80.0)
                score = st.slider("Latest Math Score", 0.0, 100.0, 65.0)
                school_distance_km = st.number_input(
                    "School Distance (km)",
                    min_value=0.1, max_value=50.0, value=2.0, step=0.5,
                    help="Distance in kilometers from home to school"
                )
            with col4:
                st.subheader("Social Flags & Household")
                labor = st.checkbox("Engaged in Seasonal Labor")
                dropout = st.checkbox("Sibling Dropped Out")
                migrant = st.checkbox("Migrant Family")
                hh_size = st.number_input("Household Size", min_value=1, max_value=20, value=5, step=1)
                hh_children = st.number_input("Children in Household", min_value=1, max_value=15, value=2, step=1)
                home_language = st.selectbox("Home Language", ["Hindi", "Bengali", "Marathi", "Tamil", "Telugu", "Kannada", "Other"])
                hh_occupation = st.selectbox("Household Occupation", ["Farming", "Daily Wage Labor", "Small Business", "Salaried", "Other"])
                location_name = st.selectbox("Location Type", ["Rural", "Semi-Urban", "Urban"])

            if st.form_submit_button("Save Student Record", type="primary"):
                if name:
                    queries = [
                        (
                            """INSERT INTO students (name, age, gender, grade, caste_category, annual_income,
                                                   hh_size, hh_children, school_distanceKm, home_language,
                                                   hh_occupation, location_name)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                               RETURNING student_id;""",
                            (name, age, gender, grade, caste, income,
                             hh_size, hh_children, school_distance_km, home_language,
                             hh_occupation, location_name)
                        )
                    ]
                    
                    try:
                        conn = run_query("SELECT 1", return_dict=False)
                        from db_connector import get_db_connection
                        with get_db_connection() as c:
                            with c.cursor() as cur:
                                cur.execute(queries[0][0], queries[0][1])
                                new_id = cur.fetchone()[0]
                                cur.execute("INSERT INTO attendance (student_id, month, attendance_percent) VALUES (%s, %s, %s)",
                                            (new_id, date.today(), att_pct))
                                cur.execute("INSERT INTO exam_scores (student_id, subject, score, exam_date) VALUES (%s, %s, %s, %s)",
                                            (new_id, "Mathematics", score, date.today()))
                                cur.execute("""INSERT INTO social_risk (student_id, parent_education_level, 
                                               seasonal_labor, sibling_dropout, migrant_family) 
                                               VALUES (%s, %s, %s, %s, %s)""",
                                            (new_id, parent_edu, labor, dropout, migrant))
                                c.commit()
                        st.success(f"Enrolled {name} (ID: {new_id}) successfully!")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Error saving student: {e}")
                else:
                    st.warning("Please provide a name.")

    with tab2:
        uploaded_file = st.file_uploader("Upload Student Roster (CSV)", type=["csv"])
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                st.write("Preview of Uploaded Data:")
                st.dataframe(df.head())

                req_cols = [
                    'name', 'age', 'gender', 'grade', 'caste_category',
                    'annual_income', 'attendance_percent', 'math_score',
                    'parent_education_level', 'seasonal_labor',
                    'sibling_dropout', 'migrant_family',
                ]
                missing = [c for c in req_cols if c not in df.columns]

                if missing:
                    st.error(f"Missing required columns in CSV: {missing}")
                else:
                    if st.button("Import Roster", type="primary"):
                        from db_connector import get_db_connection
                        success_count = 0
                        with get_db_connection() as conn:
                            with conn.cursor() as cur:
                                for _, row in df.iterrows():
                                    hh_sz = int(row.get('hh_size', 5))
                                    hh_ch = int(row.get('hh_children', 2))
                                    dist = float(row.get('school_distanceKm', 2.0))
                                    lang_val = str(row.get('home_language', 'Unknown'))
                                    occ_val = str(row.get('hh_occupation', 'Unknown'))
                                    loc_val = str(row.get('location_name', 'Rural'))

                                    cur.execute(
                                        """INSERT INTO students (name, age, gender, grade, caste_category, annual_income,
                                                               hh_size, hh_children, school_distanceKm, home_language,
                                                               hh_occupation, location_name)
                                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                           RETURNING student_id;""",
                                        (row['name'], row['age'], row['gender'], row['grade'],
                                         row['caste_category'], row['annual_income'],
                                         hh_sz, hh_ch, dist, lang_val, occ_val, loc_val)
                                    )
                                    sid = cur.fetchone()[0]
                                    cur.execute("INSERT INTO attendance (student_id, month, attendance_percent) VALUES (%s, %s, %s)",
                                                (sid, date.today(), row['attendance_percent']))
                                    cur.execute("INSERT INTO exam_scores (student_id, subject, score, exam_date) VALUES (%s, %s, %s, %s)",
                                                (sid, "Mathematics", row['math_score'], date.today()))
                                    cur.execute("""INSERT INTO social_risk (student_id, parent_education_level, 
                                                   seasonal_labor, sibling_dropout, migrant_family) 
                                                   VALUES (%s, %s, %s, %s, %s)""",
                                                (sid, row['parent_education_level'],
                                                 bool(row['seasonal_labor']), bool(row['sibling_dropout']), bool(row['migrant_family'])))
                                    success_count += 1
                                conn.commit()
                        st.success(f"Successfully imported {success_count} students!")
                        st.cache_data.clear()
            except Exception as e:
                st.error(f"Error processing CSV: {e}")
