import os
from openai import OpenAI
import json
from tools.db_tools import find_eligible_scholarships, record_intervention
from tools.report_tools import generate_intervention_pdf

class FinancialAdvocate:
    def __init__(self):
        """Initializes the Financial Advocate with OpenAI."""
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Using gpt-4o-mini here to save costs while maintaining high accuracy
        self.model = "gpt-4o-mini" 

    def provide_support(self, student_id, student_data, risk_report):
        """
        Matches scholarships and generates the intervention PDF.
        """
        # 1. Use the Tool to find all eligible schemes from the DB
        eligible_schemes = find_eligible_scholarships(student_id)
        
        if not eligible_schemes:
            return {
                "action_status": "NO_SCHEME_FOUND",
                "message": "No matching government schemes found for current demographics."
            }

        # 2. Ask the Agent to pick the BEST scheme and explain why
        system_instruction = """
        You are a Government Policy Expert for Indian Education. 
        Your task is to select the most impactful scholarship from a list of eligible options.
        Consider the student's specific risk drivers (e.g., if income is very low, pick the highest-paying scheme).
        """

        # CRITICAL FIX: Added default=str for both risk_report and eligible_schemes
        user_prompt = f"""
        Student Risk Profile: {json.dumps(risk_report, default=str)}
        Eligible Schemes: {json.dumps(eligible_schemes, default=str)}

        Identify the single best scheme and provide a brief justification.
        Output in JSON:
        {{
            "selected_scheme": "Scheme Name",
            "justification": "Why this is the best fit",
            "urgency": "High/Medium"
        }}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={ "type": "json_object" }
            )
            
            decision = json.loads(response.choices[0].message.content)
            scheme_name = decision['selected_scheme']

            # 3. Use the Report Tool to generate the PDF
            # NOTE: If generate_intervention_pdf also uses json internally, 
            # ensure it is updated to handle date objects.
            pdf_path = generate_intervention_pdf(
                student_data=student_data, 
                scheme_name=scheme_name, 
                risk_analysis=risk_report.get('summary_for_memory', 'High Risk Student')
            )

            # 4. Log the intervention
            record_intervention(
                student_id=student_id,
                agent_type="FinancialAdvocate",
                action_taken=f"Matched to {scheme_name}",
                content=decision['justification']
            )

            return {
                "action_status": "SUCCESS",
                "scheme": scheme_name,
                "pdf_path": pdf_path,
                "justification": decision['justification']
            }
        
        except Exception as e:
            return {"error": f"Financial Support Planning Failed: {str(e)}"}