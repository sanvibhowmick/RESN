import os
import json
import logging
from pathlib import Path
from fpdf import FPDF
from openai import OpenAI
from db_connector import run_query

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DropoutInterventionSystem:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = self._get_ai_client()
        self.output_dir = Path("generated_forms")
        self.output_dir.mkdir(exist_ok=True)

    def _get_ai_client(self):
        if not self.api_key:
            logging.warning("No API Key found. AI features will be disabled.")
            return None
        # FIX: Ensure the URL ends exactly like this
        return OpenAI(api_key=self.api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

    # --- MODULE A: DATA FETCHING ---
    def get_demographics(self, student_id):
        # 🔧 FIX: Corrected table name to 'students' and column to 'grade'
        sql = "SELECT grade, annual_income, caste_category, gender FROM students WHERE student_id = %s"
        df = run_query(sql, params=(student_id,))
        if df.empty:
            return {}
        # Normalize keys for the rest of the app
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
        
        academic_data = {"weakest_subject": "General Studies", "current_score": 0, "previous_score": 0, "decline_duration": 0}

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
            if row['seasonal_labor']: risks.append("Seasonal Harvest Labor")
            if row['sibling_dropout']: risks.append("History of Sibling Dropout")
            if row['migrant_family']: risks.append("Migrant Family")
            if row['parent_education_level'] in ['None', 'Primary']: literacy = "Low"
        
        return {
            "attendance": attendance,
            "academic": academic_data,
            "social_risks": risks,
            "literacy": literacy
        }

    def get_student_name(self, student_id):
        df = run_query("SELECT name FROM students WHERE student_id = %s", (student_id,))
        return df.iloc[0]['name'] if not df.empty else "Unknown"

    # --- MODULE B: ACTION GENERATORS ---
    
    def match_scholarship(self, metrics, demographics):
        if not demographics: return None
        # 🔧 FIX: Matches 'schemes' table columns correctly
        sql = """
        SELECT scheme_name FROM schemes 
        WHERE min_grade <= %s AND max_grade >= %s
        AND income_limit >= %s AND (caste_category = %s OR caste_category = 'Any')
        LIMIT 1;
        """
        params = (demographics['grade_level'], demographics['grade_level'], demographics['family_income'], demographics['caste'])
        df = run_query(sql, params)
        return df.iloc[0]['scheme_name'] if not df.empty else None

    def generate_pdf(self, student_name, scheme_name):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, txt="SCHOLARSHIP APPLICATION", ln=1, align='C')
        pdf.set_font("Arial", size=12)
        pdf.ln(10)
        pdf.cell(0, 10, txt=f"Name: {student_name}", ln=1)
        pdf.cell(0, 10, txt=f"Scheme: {scheme_name}", ln=1)
        pdf.cell(0, 10, txt="Status: URGENT INTERVENTION REQUIRED", ln=1)
        
        filename = self.output_dir / f"{student_name.replace(' ', '_')}.pdf"
        pdf.output(str(filename))
        return str(filename)

    def generate_ai_script(self, student_name, risk_list, literacy, language="Hindi"):
        if not self.client: return "AI Client not configured."
        
        strategy = "Use farming analogies." if literacy == "Low" else "Focus on career stability."
        prompt = f"""
        Act as a social worker. Goal: Persuade parents to keep {student_name} in school.
        Risks: {', '.join(risk_list)}. Literacy: {literacy} (Strategy: {strategy}).
        Write a 3-4 sentence script in {language}.
        """
        try:
            response = self.client.chat.completions.create(
                model="gemini-1.5-flash", 
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"AI Script Error: {e}")
            return "Error generating script."

    def generate_remedial_plan(self, student_name, subject, current_score, previous_score, decline_duration):
        if not self.client: return "AI Client not configured."

        trend_msg = "Steady Struggle"
        if previous_score - current_score > 15:
            trend_msg = "SUDDEN CRASH (Check for recent trauma/events)"
        elif decline_duration > 0:
            trend_msg = "Chronic Decline (Foundational Gaps)"

        prompt = f"""
        Act as a Senior Headmaster mentoring a teacher.
        Student: {student_name}. Subject: {subject}.
        Status: Score {current_score} (Prev: {previous_score}). Trend: {trend_msg}.
        
        Task: Provide a structured 3-point Remedial Plan.
        1. INVESTIGATION: Specific question the teacher should ask.
        2. ANALOGY: Explain a difficult concept in {subject} using a rural/farming metaphor.
        3. ACTIVITY: A zero-cost peer learning activity.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gemini-1.5-flash", 
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"AI Plan Error: {e}")
            return f"Error generating plan: {e}"

    # --- 🧠 ORCHESTRATOR ---
    def process_intervention(self, student_id, target_language="Hindi"):
        name = self.get_student_name(student_id)
        metrics = self.get_student_metrics(student_id)
        demographics = self.get_demographics(student_id)
        
        acad = metrics['academic']
        risks = metrics['social_risks']
        att = metrics['attendance']

        is_high_risk = False
        risk_reasons = risks.copy()

        if att < 75:
            is_high_risk = True
            risk_reasons.append(f"Critical Attendance ({att}%)")
        
        if (acad['previous_score'] - acad['current_score']) > 20:
            is_high_risk = True
            risk_reasons.append(f"Academic Crash in {acad['weakest_subject']}")

        result = {
            "student_id": student_id,
            "student_name": name,
            "status": "NORMAL",
            "actions": []
        }

        if is_high_risk:
            result['status'] = "HIGH RISK 🚨"
            script = self.generate_ai_script(name, risk_reasons, metrics['literacy'], language=target_language)
            result['actions'].append({"type": "script", "content": script})

            scheme = self.match_scholarship(metrics, demographics)
            if scheme:
                pdf_path = self.generate_pdf(name, scheme)
                result['actions'].append({"type": "file", "path": pdf_path, "description": "Scholarship Form"})

        elif acad['current_score'] < 50:
            result['status'] = "ACADEMIC WATCH ⚠️"
            plan = self.generate_remedial_plan(
                student_name=name,
                subject=acad['weakest_subject'],
                current_score=acad['current_score'],
                previous_score=acad['previous_score'],
                decline_duration=acad['decline_duration']
            )
            result['actions'].append({"type": "teacher_plan", "content": plan})
            
        return result