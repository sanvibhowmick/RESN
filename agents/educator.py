import os
from openai import OpenAI
import json
from agents.schemas import RemedialActionCardSchema
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

        Generate a pedagogical Quick-Action Card.
        Output MUST be in valid JSON:
        {{
            "subject": "{subject}",
            "diagnosis_question": "One targeted question to pinpoint exactly where the student's conceptual understanding broke",
            "real_world_analogy": "A relatable rural Indian metaphor (farming, village market, harvest, carpentry) explaining the concept",
            "five_minute_fix": "A quick zero-cost peer activity to rebuild confidence and mastery",
            "teacher_tips": "A practical classroom tip for delivery"
        }}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.4
            )
            
            # Runtime validation with Pydantic
            card = RemedialActionCardSchema.model_validate_json(response.choices[0].message.content)
            
            plan_content = (
                f"1. 🔍 THE DIAGNOSIS QUESTION:\n{card.diagnosis_question}\n\n"
                f"2. 💡 THE REAL-WORLD ANALOGY:\n{card.real_world_analogy}\n\n"
                f"3. ⚡ THE 5-MINUTE FIX:\n{card.five_minute_fix}\n\n"
                f"📌 TEACHER TIP:\n{card.teacher_tips}"
            )

            # 3. Log the intervention in the DB
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
                "action_card": card.model_dump(),
                "decline_observed": decline
            }

        except Exception as e:
            return {"error": f"Educational Planning Failed: {str(e)}"}