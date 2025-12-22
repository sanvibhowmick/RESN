import os
import logging
import google.generativeai as genai
from pathlib import Path
from fpdf import FPDF
from db_connector import run_query

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DropoutInterventionSystem:
    def __init__(self):
        # Load API Key
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.output_dir = Path("generated_forms")
        self.output_dir.mkdir(exist_ok=True)
        self._configure_ai()

    def _configure_ai(self):
        if not self.api_key:
            logging.warning("No API Key found. AI features will be disabled.")
            return
        
        try:
            genai.configure(api_key=self.api_key)
            # Using Gemini 2.5 Flash for optimized performance
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        except Exception as e:
            logging.error(f"Error configuring AI: {e}")

    # --- MODULE A: DATA FETCHING ---
    def get_demographics(self, student_id):
        sql = "SELECT grade, annual_income, caste_category, gender FROM students WHERE student_id = %s"
        df = run_query(sql, params=(student_id,))
        if df.empty:
            return {}
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
        sql = """
        SELECT scheme_name FROM schemes 
        WHERE min_grade <= %s AND max_grade >= %s
        AND income_limit >= %s AND (caste_category = %s OR caste_category = 'Any')
        LIMIT 1;
        """
        params = (demographics['grade_level'], demographics['grade_level'], demographics['family_income'], demographics['caste'])
        df = run_query(sql, params)
        return df.iloc[0]['scheme_name'] if not df.empty else None

    def generate_pdf(self, student_name, scheme_name, demographics, metrics):
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
        # Row 1
        pdf.cell(95, 10, f"Name: {student_name}", border=1)
        pdf.cell(95, 10, f"Gender: {demographics.get('gender', 'N/A')}", border=1, ln=1)
        # Row 2
        pdf.cell(95, 10, f"Grade: {demographics.get('grade_level', 'N/A')}", border=1)
        pdf.cell(95, 10, f"Caste Category: {demographics.get('caste', 'N/A')}", border=1, ln=1)
        # Row 3
        pdf.cell(190, 10, f"Annual Family Income: INR {demographics.get('family_income', 0)}", border=1, ln=1)
        
        pdf.ln(5)

        # --- SECTION 2: ACADEMIC & RISK STATUS ---
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "2. PERFORMANCE & RISK ASSESSMENT", ln=1, fill=True)
        
        pdf.set_font("Arial", size=11)
        # Metrics
        att_status = "CRITICAL" if metrics['attendance'] < 75 else "Stable"
        pdf.cell(95, 10, f"Attendance: {metrics['attendance']}% ({att_status})", border=1)
        pdf.cell(95, 10, f"Literacy Background: {metrics['literacy']}", border=1, ln=1)
        
        # Risk Factors List
        pdf.cell(0, 10, "Identified Risk Factors:", border="L R", ln=1)
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
        pdf.multi_cell(0, 10, f"Based on the analysis of the student's socioeconomic background and academic trajectory, we strongly recommend enrollment in the following government scheme to prevent dropout:\n\n>> {scheme_name.upper()}")
        pdf.ln(5)

        # --- SECTION 4: DECLARATION & SIGNATURES ---
        pdf.ln(20)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 5, "I hereby certify that the information provided above is true to the best of my knowledge. The student requires immediate financial or counseling intervention to continue their education.")
        
        pdf.ln(30)
        
        # Signatures
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(63, 10, "_______________________", align='C')
        pdf.cell(63, 10, "_______________________", align='C')
        pdf.cell(63, 10, "_______________________", align='C', ln=1)
        
        pdf.cell(63, 5, "School Principal", align='C')
        pdf.cell(63, 5, "Nodal Officer", align='C')
        pdf.cell(63, 5, "Parent/Guardian", align='C', ln=1)

        # Output
        filename = self.output_dir / f"{student_name.replace(' ', '_')}_Profile.pdf"
        pdf.output(str(filename))
        return str(filename)

    def generate_ai_script(self, student_name, risk_list, literacy, scheme_name=None, language="Hindi"):
        if not getattr(self, 'model', None): return "AI Client not configured."
        
        strategy = "Use simple words, focus on how education helps in the long run." if literacy == "Low" else "Focus on career stability and dignity."
        
        # Include Scholarship Logic
        scholarship_instruction = ""
        if scheme_name:
            scholarship_instruction = f"CRITICAL: You must explicitly mention that we have prepared the application for the '{scheme_name}' scholarship. Explain to them that this government scheme will provide money to support the family, so they don't have to worry about costs."

        prompt = f"""
        Act as a compassionate social worker in rural India. 
        Goal: Persuade parents to keep {student_name} in school.
        
        Context:
        - The family is considering making the child drop out.
        - Risks identified: {', '.join(risk_list)}.
        - Parent Literacy: {literacy} (Strategy: {strategy}).
        
        {scholarship_instruction}
        
        Task: Write a convincing, emotional, yet respectful 3-4 sentence script in {language} to say to the parents.
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logging.error(f"AI Script Error: {e}")
            return "Error generating script."

    def generate_remedial_plan(self, student_name, subject, current_score, previous_score, decline_duration):
        if not getattr(self, 'model', None): return "AI Client not configured."

        trend_msg = "Steady Struggle"
        if previous_score - current_score > 15:
            trend_msg = "SUDDEN CRASH (Check for recent trauma/events)"
        elif decline_duration > 0:
            trend_msg = "Chronic Decline (Foundational Gaps)"

        prompt = f"""
        Act as a teacher's guide. You see a fall in the student's grade. Depending on the fall and the subject, suggest measures for the teacher.
        Do not mention you are a teacher's guide or even reference the teacher in second person. Only talk about {student_name}.
        Student: {student_name}. Subject: {subject}.
        Status: Score {current_score} (Prev: {previous_score}). Trend: {trend_msg}.
        
        Task: Provide a structured 3-point Remedial Plan.
        1. Questions: Specific questions the teacher should ask.
        2. ANALOGY: Explain a difficult concept in {subject} using a rural/farming metaphor.
        3. ACTIVITY: A zero-cost peer learning activity.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logging.error(f"AI Plan Error: {e}")
            return f"Error generating plan: {e}"

    # --- 🧠 ORCHESTRATOR ---
    def process_intervention(self, student_id, target_language="Hindi"):
        name = self.get_student_name(student_id)
        if name == "Unknown":
            return {"status": "ERROR", "message": "Student ID not found in DB"}

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
            
            scheme = self.match_scholarship(metrics, demographics)
            
            script = self.generate_ai_script(
                student_name=name, 
                risk_list=risk_reasons, 
                literacy=metrics['literacy'], 
                scheme_name=scheme,
                language=target_language
            )
            result['actions'].append({"type": "script", "content": script})

            if scheme:
                pdf_path = self.generate_pdf(name, scheme, demographics, metrics)
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