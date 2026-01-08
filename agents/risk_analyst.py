import os
from openai import OpenAI
import json

class RiskAnalyst:
    def __init__(self):
        """Initializes the Risk Analyst with OpenAI credentials."""
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o"  # High reasoning capability for socio-economic analysis

    def analyze(self, student_data, past_memories=None):
        """
        Performs a deep diagnostic analysis of a student's dropout risk.
        """
        # 1. Prepare the Memory Context
        memory_context = "No previous intervention history available."
        if past_memories:
            # Added default=str here as a precaution if created_at is a datetime object
            memory_context = "\n".join([
                f"- {m.get('created_at', 'N/A')}: {m.get('context_summary', '')}" 
                for m in past_memories
            ])

        # 2. System Prompt: Defining the Persona
        system_instruction = """
        You are a Senior Social Intervention Expert specializing in rural Indian education. 
        Your goal is to identify students at risk of dropping out by analyzing:
        1. Academic Trends (declines are more dangerous than consistent low scores).
        2. Attendance patterns (missing school frequently suggests labor or family issues).
        3. Social Risk Factors (Migrant status, sibling dropouts, or seasonal labor).

        You must output your analysis in STRICT JSON format so the Orchestrator can read it.
        """

        # 3. User Prompt: The Data
        # CRITICAL FIX: Added default=str to handle date objects in student_data
        user_prompt = f"""
        Analyze the following student profile and history:
        
        STUDENT DATA:
        {json.dumps(student_data, indent=2, default=str)}

        PAST INTERVENTION MEMORY:
        {memory_context}

        OUTPUT FORMAT (JSON):
        {{
            "risk_score": (int 0-100),
            "status": "NORMAL" | "WATCH" | "HIGH_RISK",
            "primary_drivers": ["reason 1", "reason 2"],
            "summary_for_memory": "A 1-sentence summary of the current situation",
            "recommended_next_agent": "FinancialAdvocate" | "Educator" | "None"
        }}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={ "type": "json_object" }, 
                temperature=0.2
            )
            
            return json.loads(response.choices[0].message.content)
        
        except Exception as e:
            return {
                "error": f"Risk Analysis Failed: {str(e)}",
                "risk_score": 50,
                "status": "WATCH"
            }