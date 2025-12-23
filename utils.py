import os
import logging
import google.generativeai as genai
from pathlib import Path
from fpdf import FPDF
from datetime import datetime

# ---------------------------------------------------------
# DATABASE DEPENDENCY
# Ensure you have a file named 'db_connector.py' with a function 'run_query'
# OR replace this import with your actual database logic.
try:
    from db_connector import run_query
except ImportError:
    # Fallback for testing purposes if db_connector is missing
    logging.warning("db_connector not found. Using Mock Data mode.")
    import pandas as pd
    def run_query(sql, params=None):
        # MOCK DATA FOR TESTING
        return pd.DataFrame() 
# ---------------------------------------------------------

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DropoutInterventionSystem:
    def __init__(self):
        # 1. Configuration
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.output_dir = Path("generated_forms")
        self.output_dir.mkdir(exist_ok=True)
        
        # 2. Risk Model Weights
        self.SOCIAL_RISK_WEIGHTS = {
            "Seasonal Harvest Labor": 30,
            "History of Sibling Dropout": 40,
            "Migrant Family": 25,
            "Burdened with Care Work": 20,
            "Single Parent Household": 15
        }
        self.HIGH_RISK_THRESHOLD = 60 

        # 3. Initialize AI
        self._configure_ai()

    def _configure_ai(self):
        if not self.api_key:
            logging.warning("No Gemini API Key found. AI features (Script/Plan) will be disabled.")
            self.model = None
            return
        
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        except Exception as e:
            logging.error(f"Error configuring AI: {e}")
            self.model = None

    # =========================================================================
    # MODULE A: DATA FETCHING LAYER
    # =========================================================================

    def get_student_name(self, student_id):
        sql = "SELECT name FROM students WHERE student_id = %s"
        df = run_query(sql, (student_id,))
        return df.iloc[0]['name'] if not df.empty else "Unknown Student"

    def get_demographics(self, student_id):
        sql = "SELECT grade, annual_income, caste_category, gender FROM students WHERE student_id = %s"
        df = run_query(sql, params=(student_id,))
        if df.empty:
            # Return default/mock if DB fails
            return {'grade_level': 10, 'family_income': 0, 'caste': 'General', 'gender': 'N/A'}
        
        data = df.iloc[0].to_dict()
        return {
            'grade_level': data['grade'],
            'family_income': data['annual_income'],
            'caste': data['caste_category'],
            'gender': data['gender']
        }

    def get_student_metrics(self, student_id):
        # 1. Attendance
        sql_att = "SELECT attendance_percent FROM attendance WHERE student_id = %s ORDER BY month DESC LIMIT 1"
        df_att = run_query(sql_att, params=(student_id,))
        attendance = df_att.iloc[0]['attendance_percent'] if not df_att.empty else 100

        # 2. Academic (Weakest Subject Logic)
        sql_academic = """
        SELECT subject,
            AVG(score) FILTER (WHERE exam_date >= CURRENT_DATE - INTERVAL '3 months') AS recent,
            AVG(score) FILTER (WHERE exam_date < CURRENT_DATE - INTERVAL '3 months') AS past
        FROM exam_scores WHERE student_id = %s GROUP BY subject ORDER BY recent ASC LIMIT 1;
        """
        df_acad = run_query(sql_academic, params=(student_id,))
        
        academic_data = {"weakest_subject": "General", "current_score": 0, "previous_score": 0, "decline_duration": 0}

        if not df_acad.empty:
            row = df_acad.iloc[0]
            recent = row['recent'] or 0
            past = row['past'] or 0
            academic_data = {
                "weakest_subject": row['subject'],
                "current_score": round(recent, 1),
                "previous_score": round(past, 1),
                "decline_duration": 3 if past > recent else 0
            }

        # 3. Social Risks
        sql_social = "SELECT * FROM social_risk WHERE student_id = %s"
        df_social = run_query(sql_social, params=(student_id,))
        risks = []
        literacy = "High"
        
        if not df_social.empty:
            row = df_social.iloc[0]
            # Map DB boolean columns to Risk Strings
            if row.get('seasonal_labor'): risks.append("Seasonal Harvest Labor")
            if row.get('sibling_dropout'): risks.append("History of Sibling Dropout")
            if row.get('migrant_family'): risks.append("Migrant Family")
            if row.get('parent_education_level') in ['None', 'Primary']: literacy = "Low"
        
        return {
            "attendance": attendance,
            "academic": academic_data,
            "social_risks": risks,
            "literacy": literacy
        }

    # =========================================================================
    # MODULE B: INTELLIGENCE GENERATORS (AI & LOGIC)
    # =========================================================================

    def match_scholarship(self, metrics, demographics):
        """Finds the best government scheme based on eligibility criteria."""
        if not demographics: return None
        sql = """
        SELECT scheme_name FROM schemes 
        WHERE min_grade <= %s AND max_grade >= %s
        AND income_limit >= %s AND (caste_category = %s OR caste_category = 'Any')
        LIMIT 1;
        """
        params = (demographics['grade_level'], demographics['grade_level'], demographics['family_income'], demographics['caste'])
        df = run_query(sql, params)
        return df.iloc[0]['scheme_name'] if not df.empty else None

    def generate_ai_script(self, student_name, risk_list, literacy, scheme_name=None, language="Hindi"):
        """Generates talking points for volunteers using Gemini."""
        if not self.model: return "AI Not Configured."

        # 1. Define Contextual Analogy
        analogy_context = "investment and ROI"
        if literacy == "Low":
            analogy_context = "farming (sowing seeds for future harvest) or building a strong house foundation"

        # 2. Define the Scholarship Variable for the Prompt
        financial_solution = f"the '{scheme_name}' Government Scheme" if scheme_name else "available government support"

        # 3. STRICT PROMPT ENGINEERING
        prompt = f"""
        You are an expert Cultural Mediator creating a 'Cheat Sheet' for a social worker.
        
        Target Audience: Parents of {student_name}.
        Context: 
        - Risk Factors: {', '.join(risk_list)}
        - Parent Literacy Level: {literacy} (Use {analogy_context} analogies)
        - Language: {language}

        TASK:
        Generate 5 distinct, powerful "Talking Points" (Arguments) that the volunteer can glance at and use immediately.

        CONSTRAINTS (CRITICAL):
        1. DO NOT act like a manager. DO NOT write "Tell them that..." or "You should mention...".
        2. DIRECT SPEECH ONLY. Write the arguments exactly as they should be spoken.
        3. KEEP IT BRIEF. One sentence per bullet point.
        4. EMOTIONAL HOOK. Focus on the child's future support for the parents.

        Output Format:
        * [The Financial Solution]: "You do not need to worry about money because we have already matched {student_name} with {financial_solution} which covers the costs."
        * [Social Prestige Angle]: (Write a point about how the village will respect them)
        * [Fear of Missing Out]: (Write a point about how neighbors' kids are getting ahead)
        * [Addressing the Risk]: (Address {', '.join(risk_list)} directly)
        * [Closing Emotional Appeal]: (A final sentence about the parent's old age security)
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logging.error(f"AI Script Error: {e}")
            return "Error generating script."

    def generate_remedial_plan(self, student_name, subject, current_score, previous_score, decline_duration):
        """Generates a pedagogical plan for teachers using Gemini."""
        if not self.model: return "AI Not Configured."

        prompt = f"""
        Act as a Senior Pedagogy Expert. Create a "Quick-Action Card" for a teacher to help a struggling student.
        
        Student: {student_name} | Subject: {subject}
        Current Score: {current_score} (Dropped from {previous_score})
        
        Generate exactly 3 actionable items. Do not use generic advice like "work harder".

        Output Structure:
        1. 🔍 THE DIAGNOSIS QUESTION: One specific technical question the teacher should ask the student to identify exactly where they are stuck in {subject}.
        2. 💡 THE REAL-WORLD ANALOGY: A specific, non-academic metaphor to explain a core concept in {subject} to a rural student.
        3. ⚡ THE 5-MINUTE FIX: A quick peer-activity or exercise that costs $0 and takes 5 minutes to boost confidence.

        Output strictly these 3 points. No intro/outro.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logging.error(f"AI Plan Error: {e}")
            return f"Error generating plan: {e}"

    def generate_pdf(self, student_name, scheme_name, demographics, metrics):
        """Generates a printable PDF form for the intervention."""
        pdf = FPDF()
        pdf.add_page()
        
        # --- HEADER ---
        pdf.set_font("Arial", 'B', 20)
        pdf.cell(0, 15, txt="INTERVENTION & SCHOLARSHIP FORM", ln=1, align='C', border=1)
        pdf.ln(10)

        # --- SECTION 1: STUDENT PROFILE ---
        pdf.set_fill_color(200, 220, 255) # Light Blue
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "1. STUDENT PROFILE", ln=1, fill=True)
        
        pdf.set_font("Arial", size=11)
        pdf.cell(95, 10, f"Name: {student_name}", border=1)
        pdf.cell(95, 10, f"Gender: {demographics.get('gender', 'N/A')}", border=1, ln=1)
        pdf.cell(95, 10, f"Grade: {demographics.get('grade_level', 'N/A')}", border=1)
        pdf.cell(95, 10, f"Caste: {demographics.get('caste', 'N/A')}", border=1, ln=1)
        pdf.cell(190, 10, f"Family Income: INR {demographics.get('family_income', 0)}", border=1, ln=1)
        pdf.ln(5)

        # --- SECTION 2: RISK ASSESSMENT ---
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "2. PERFORMANCE & RISK ASSESSMENT", ln=1, fill=True)
        
        pdf.set_font("Arial", size=11)
        att_status = "CRITICAL" if metrics['attendance'] < 75 else "Stable"
        pdf.cell(95, 10, f"Attendance: {metrics['attendance']}% ({att_status})", border=1)
        pdf.cell(95, 10, f"Literacy Background: {metrics['literacy']}", border=1, ln=1)
        
        pdf.cell(0, 8, "Identified Risk Factors:", border="L R", ln=1)
        pdf.set_font("Arial", 'I', 11)
        if metrics['social_risks']:
            for risk in metrics['social_risks']:
                pdf.cell(0, 8, f"   - {risk}", border="L R", ln=1)
        else:
            pdf.cell(0, 8, "   - No specific social risks identified.", border="L R", ln=1)
        pdf.cell(0, 2, "", border="T", ln=1) # Closing line
        pdf.ln(5)

        # --- SECTION 3: RECOMMENDATION ---
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "3. RECOMMENDED INTERVENTION", ln=1, fill=True)
        
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, f"Based on the analysis, we strongly recommend enrollment in:\n\n>> {scheme_name.upper()}\n\nThis scheme covers education costs and mitigates the financial risk of dropout.")
        pdf.ln(20)
        
        # --- SIGNATURES ---
        pdf.set_font("Arial", size=10)
        pdf.cell(63, 10, "_______________________", align='C')
        pdf.cell(63, 10, "_______________________", align='C')
        pdf.cell(63, 10, "_______________________", align='C', ln=1)
        pdf.cell(63, 5, "Principal", align='C')
        pdf.cell(63, 5, "Nodal Officer", align='C')
        pdf.cell(63, 5, "Parent/Guardian", align='C', ln=1)

        filename = self.output_dir / f"{student_name.replace(' ', '_')}_Profile.pdf"
        pdf.output(str(filename))
        return str(filename)

    # =========================================================================
    # MODULE C: ORCHESTRATOR
    # =========================================================================

    def process_intervention(self, student_id, target_language="Hindi"):
        """
        Advanced Rule-Based Analysis for Student Risk Calculation.
        Considers: Social, Financial, Academic, Attendance, and Demographic factors.
        """
        name = self.get_student_name(student_id)
        if name == "Unknown":
            return {"status": "ERROR", "message": "Student ID not found in DB"}

        metrics = self.get_student_metrics(student_id)
        demographics = self.get_demographics(student_id)
        
        # Unpack Data
        acad = metrics.get('academic', {})
        risks_list = metrics.get('social_risks', [])
        att = metrics.get('attendance', 100)
        literacy = metrics.get('literacy', 'None') # Parent Education
        income = demographics.get('income', 0)

        # --- 1. DEFINE WEIGHTS ---
        # Refined weights based on dropout research
        RISK_WEIGHTS = {
            'sibling_dropout': 30,  # High correlation with dropout
            'seasonal_labor': 25,   # Indicates economic pressure
            'migrant_family': 20,   # Stability issue
            'childcare_responsibility': 15
        }

        current_risk_score = 0
        risk_reasons = []

        # --- 2. CALCULATE SCORE ---

        # A. SOCIAL FACTORS (Existing Risks)
        for risk in risks_list:
            weight = RISK_WEIGHTS.get(risk, 10)
            current_risk_score += weight
        if risks_list:
            risk_reasons.append(f"Social Factors ({len(risks_list)} identified)")

        # B. ECONOMIC FACTOR (New)
        if income < 50000:
            current_risk_score += 25
            risk_reasons.append("Severe Economic Distress (<50k)")
        elif income < 100000:
            current_risk_score += 10

        # C. PARENTAL SUPPORT FACTOR (New)
        if literacy == 'None':
            current_risk_score += 15
            risk_reasons.append("Lack of Parental Academic Support")

        # D. ATTENDANCE (Nuanced)
        if att < 50:
            current_risk_score += 60 # Critical
            risk_reasons.append(f"Critical Attendance ({att}%)")
        elif att < 75:
            current_risk_score += 30 # Warning
            risk_reasons.append(f"Low Attendance ({att}%)")

        # E. ACADEMIC PERFORMANCE (Nuanced)
        current_score = acad.get('current_score', 0)
        prev_score = acad.get('previous_score', 0)
        
        if current_score < 35:
            current_risk_score += 40 # Failing
            risk_reasons.append(f"Failing Grades ({current_score})")
        elif (prev_score - current_score) > 15:
            current_risk_score += 25 # Sharp Drop
            risk_reasons.append("Sharp Academic Decline")

        # Cap score at 100
        current_risk_score = min(current_risk_score, 100)

        # --- 3. DETERMINE STATUS ---
        # Thresholds: Safe (0-30), Watch (31-59), High Risk (60+)
        if current_risk_score >= 60:
            status = "HIGH RISK 🚨"
            is_high_risk = True
        elif current_risk_score >= 30:
            status = "ACADEMIC WATCH ⚠️"
            is_high_risk = False
        else:
            status = "NORMAL ✅"
            is_high_risk = False

        result = {
            "student_id": student_id,
            "student_name": name,
            "risk_score": current_risk_score,
            "status": status,
            "actions": []
        }

        # --- 4. GENERATE INTERVENTIONS ---

        # SCENARIO 1: High Risk (Socio-Economic Focus)
        if is_high_risk:
            # Match Govt Scheme
            scheme = self.match_scholarship(metrics, demographics)
            
            # Action: Talking Points
            script = self.generate_ai_script(
                student_name=name, 
                risk_list=risk_reasons, 
                literacy=literacy, 
                scheme_name=scheme,
                language=target_language
            )
            result['actions'].append({
                "type": "script", # Changed type name to match app.py logic
                "content": script
            })

            # Action: PDF Form
            if scheme:
                pdf_path = self.generate_pdf(name, scheme, demographics, metrics)
                result['actions'].append({
                    "type": "file", 
                    "path": pdf_path, 
                    "description": f"Application for {scheme}"
                })

        # SCENARIO 2: Academic/Attendance Watch (Pedagogy Focus)
        # Trigger this if they are explicitly 'Watch' status OR if they are 'High Risk' but specifically due to grades
        if "WATCH" in status or (current_score < 40): 
            plan = self.generate_remedial_plan(
                student_name=name,
                subject=acad.get('weakest_subject', 'General'),
                current_score=current_score,
                previous_score=prev_score,
                decline_duration="3 months" # Placeholder or calc from DB
            )
            result['actions'].append({
                "type": "teacher_plan", 
                "content": plan
            })
            
        return result