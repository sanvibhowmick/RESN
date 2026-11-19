import os
from openai import OpenAI
import json
from agents.schemas import CounselingScriptSchema
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

        

        system_instruction = f"""
        You are a Cultural Mediator. Generate a 'Cheat Sheet' for a volunteer visiting parents in rural India.You will be addresing the parents in {language}.
        Your goal is to convince them to support their child's education using relatable metaphors.
        Context:
        - Language: {language}
        - Parent Literacy Level: {literacy}
        - Risk Factors: {drivers_str}
        
        CONSTRAINTS:
        1. DIRECT SPEECH ONLY. No "Tell them that..."
        2. One sentence per bullet point.
        3. Use emotional hooks regarding the child's future support for parents.
        Output MUST be in valid JSON.
        """

        student_name = profile.get('name', 'your child')
        user_prompt = f"""
        Student: {student_name}.
        Generate the structured counseling cheat sheet for a home visit in {language}.
        Output JSON:
        {{
            "language": "{language}",
            "talking_points": [
                "Direct speech sentence 1 in {language}",
                "Direct speech sentence 2 in {language}",
                "Direct speech sentence 3 in {language}",
                "Direct speech sentence 4 in {language}",
                "Direct speech sentence 5 in {language}"
            ],
            "cultural_metaphor": "Brief explanation of the agricultural/cultural metaphor used",
            "emotional_hook": "Core emotional message regarding the child's future and family pride"
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
                temperature=0.5
            )
            
            # Runtime validation with Pydantic
            counseling_data = CounselingScriptSchema.model_validate_json(response.choices[0].message.content)
            
            # Bulleted formatted text for UI backwards-compatibility
            bullets = "\n".join([f"• {pt}" for pt in counseling_data.talking_points])
            formatted_script = (
                f"{bullets}\n\n"
                f"🌾 Cultural Metaphor: {counseling_data.cultural_metaphor}\n"
                f"❤️ Emotional Hook: {counseling_data.emotional_hook}"
            )

            # Log intervention
            record_intervention(
                student_id=student_id, 
                agent_type="CommunityMediator", 
                action_taken=f"Counseling Script ({language})", 
                content=formatted_script
            )

            return {
                "action_status": "SUCCESS",
                "language": language,
                "script": formatted_script,
                "structured_counseling": counseling_data.model_dump()
            }
            
        except Exception as e:
            return {"error": f"Community Mediation Failed: {str(e)}"}