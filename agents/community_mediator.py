import os
from openai import OpenAI
import json
from tools.db_tools import record_intervention

class CommunityMediator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"

    def generate_counseling_script(self, student_id, student_data, risk_report, language="Bengali"):
        """
        Generates 5 powerful, direct-speech talking points for a home visit.
        """
        # SAFE EXTRACTION: Avoiding crashes if keys are missing
        profile = student_data.get('profile', {})
        social_factors = student_data.get('social_risk_factors', {})
        literacy = social_factors.get('parent_education_level', 'None')
        
        # Risk factors handling (handling potential date objects or non-list data)
        drivers_list = risk_report.get('primary_drivers', [])
        drivers_str = ", ".join([str(d) for d in drivers_list]) if isinstance(drivers_list, list) else str(drivers_list)

        # Select analogy based on literacy
        analogy = "farming and seeds" if literacy in ['None', 'Primary'] else "long-term investment"

        system_instruction = f"""
        You are a Cultural Mediator. Generate a 'Cheat Sheet' for a volunteer visiting parents in rural India.You will be addresing the parents in {language}.
        Your goal is to convince them to support their child's education using relatable metaphors.
        Context:
        - Language: {language}
        - Analogy Style: {analogy}
        - Risk Factors: {drivers_str}
        
        CONSTRAINTS:
        1. DIRECT SPEECH ONLY. No "Tell them that..."
        2. One sentence per bullet point.
        3. Use emotional hooks regarding the child's future support for parents.
        """

        # Using .get() for the name to prevent KeyError
        student_name = profile.get('name', 'your child')
        user_prompt = f"Student: {student_name}. Generate 5 talking points in {language}."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7 # Higher temperature for more natural, persuasive speech
            )
            
            script_content = response.choices[0].message.content

            # Log intervention
            record_intervention(
                student_id=student_id, 
                agent_type="CommunityMediator", 
                action_taken=f"Counseling Script ({language})", 
                content=script_content
            )

            return {
                "action_status": "SUCCESS",
                "language": language,
                "script": script_content
            }
            
        except Exception as e:
            return {"error": f"Community Mediation Failed: {str(e)}"}