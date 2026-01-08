import os
from openai import OpenAI
import json
from tools.db_tools import record_intervention

class Educator:
    def __init__(self):
        """Initializes the Educator agent with OpenAI."""
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Using gpt-4o-mini: Perfect for creative instructional writing at low cost
        self.model = "gpt-4o-mini" 

    def create_remedial_plan(self, student_id, student_data, risk_report):
        """
        Generates a pedagogical 'Quick-Action Card' for teachers to help 
        struggling students in specific subjects.
        """
        # 1. Extract Academic Context from the Tool data
        academic_history = student_data.get('academic_performance', [])
        
        if not academic_history:
            return {"action_status": "SKIPPED", "message": "No academic data available for remedial planning."}
        
        latest_exam = academic_history[0]
        subject = latest_exam.get('subject', 'General')
        current_score = latest_exam.get('score', 0)
        
        # Try to find a previous score to calculate the "Decline"
        prev_score = academic_history[1].get('score', current_score) if len(academic_history) > 1 else current_score
        decline = prev_score - current_score

        # 2. System Persona: Senior Pedagogy Expert
        system_instruction = """
        You are a Senior Pedagogy Expert for Rural Schools. 
        Your task is to create a 3-point action card for a teacher to help a student 
        whose grades are falling. 
        
        CONSTRAINTS:
        - Use rural Indian metaphors (farming, harvest, village markets).
        - Keep advice actionable and zero-cost.
        - Be encouraging but technically precise.
        """

        # SAFETY CHECK: Extract name safely. 
        # If student_data contains dates, f-string interpolation is usually fine, 
        # but if you ever dump the whole dict to a log, use default=str.
        student_name = student_data.get('profile', {}).get('name', 'Student')
        drivers = ", ".join(risk_report.get('primary_drivers', []))

        user_prompt = f"""
        Student: {student_name}
        Subject: {subject}
        Current Score: {current_score} (Dropped from {prev_score})
        Risk Context: {drivers}

        Generate a "Quick-Action Card" with exactly these 3 points:
        1. 🔍 THE DIAGNOSIS QUESTION: One question to find where the concept broke.
        2. 💡 THE REAL-WORLD ANALOGY: A rural-context metaphor to explain {subject}.
        3. ⚡ THE 5-MINUTE FIX: A quick peer-activity to rebuild confidence.
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5 
            )
            
            plan_content = response.choices[0].message.content

            # 3. Log the intervention in the DB
            # Ensure any content passed here is serialized safely if it's stored as JSON in DB
            record_intervention(
                student_id=student_id,
                agent_type="Educator",
                action_taken=f"Remedial Plan: {subject}",
                content=plan_content
            )

            return {
                "action_status": "SUCCESS",
                "subject": subject,
                "remedial_plan": plan_content,
                "decline_observed": decline
            }

        except Exception as e:
            return {"error": f"Educational Planning Failed: {str(e)}"}