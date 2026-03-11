import os
import torch
import torch.nn as nn
import joblib
import numpy as np
import json
from openai import OpenAI

# 1. RESIDUAL MODEL ARCHITECTURE
class RESNModel(nn.Module):
    def __init__(self, input_dim, n_layers, units_per_layer, dropout_rate):
        super().__init__()
        self.blocks = nn.ModuleList()
        self.skips = nn.ModuleList()
        
        in_f = input_dim
        for out_f, dr in zip(units_per_layer, dropout_rate):
            self.blocks.append(nn.Sequential(
                nn.Linear(in_f, out_f),
                nn.BatchNorm1d(out_f),
                nn.ReLU(),
                nn.Dropout(dr)
            ))
            self.skips.append(nn.Linear(in_f, out_f, bias=False))
            in_f = out_f
            
        self.head = nn.Linear(in_f, 1)

    def forward(self, x):
        for block, skip in zip(self.blocks, self.skips):
            x = block(x) + skip(x)
        return self.head(x)

class RiskAnalyst:
    def __init__(self):
        """Initializes the Hybrid Risk Analyst using RESN Model and LLM."""
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model_llm = "gpt-4o"
        
        # Load custom model assets
        model_dir = os.path.join(os.getcwd(), "model")
        self.scaler = joblib.load(os.path.join(model_dir, "scaler.joblib"))
        self.features_list = joblib.load(os.path.join(model_dir, "features_list.joblib"))
        
        # Exact sizes from your training architecture
        best_n_layers = 4 
        best_units = [224, 160, 64, 256] 
        best_dropouts = [0.2, 0.2, 0.2, 0.2]

        self.risk_model = RESNModel(
            input_dim=len(self.features_list),
            n_layers=best_n_layers, 
            units_per_layer=best_units, 
            dropout_rate=best_dropouts
        )
        
        self.risk_model.load_state_dict(
            torch.load(os.path.join(model_dir, "dropout_model.pth"), map_location=torch.device('cpu'))
        )
        self.risk_model.eval()

    def _get_ml_risk_score(self, student_data):
        """Maps data to features and generates a 0-100 score."""
        profile = student_data.get('profile', {})
        social = student_data.get('social_risk_factors', {})
        attendance = student_data.get('attendance_history', [])
        latest_att = attendance[0].get('attendance_percent', 85.0) if attendance else 85.0
        
        raw_vals = {
            'grade': profile.get('grade', 0),
            'gender': profile.get('gender', 'Other'),
            'annual_income': profile.get('annual_income', 0),
            'attendance': latest_att,
            'hh_size': 5,  
            'school_distanceKm': 2.0,  
            'hh_children': 3,  
            'mothers_edu': social.get('parent_education_level', 'None'),
            'hh_edu': social.get('parent_education_level', 'None'),
            'migrant_family': 1 if social.get('migrant_family') else 0,
            'seasonal_labor': 1 if social.get('seasonal_labor') else 0,
            'sibling_dropout': 1 if social.get('sibling_dropout') else 0
        }

        input_row = []
        for feat in self.features_list:
            if feat in raw_vals:
                input_row.append(float(raw_vals[feat]))
            elif "_" in feat:
                base_col, category = feat.rsplit("_", 1)
                val = 1.0 if str(raw_vals.get(base_col)) == category else 0.0
                input_row.append(val)
            else:
                input_row.append(0.0)

        scaled_data = self.scaler.transform([input_row])
        with torch.no_grad():
            logits = self.risk_model(torch.tensor(scaled_data, dtype=torch.float32))
            probability = torch.sigmoid(logits).item()
            
        return int(probability * 100)

    def analyze(self, student_data, past_memories=None):
        """Combines ML score with LLM reasoning for the UI."""
        ml_score = self._get_ml_risk_score(student_data)
        
        memory_context = "No previous history."
        if past_memories:
            memory_context = "\n".join([f"- {m.get('context_summary')}" for m in past_memories])

        # 🚨 UPDATED PROMPT: Forcing the LLM to decide NORMAL, WATCH, or DANGER
        # AND strictly forbidding the mention of the ML score in the output.
        system_instruction = f"""
        You are a Rural Education Intervention Expert. 
        A Neural Network calculated a base dropout risk score of {ml_score}/100.
        
        Your task is to analyze this score alongside the student's Social Factors (attendance, labor, income, sibling dropouts).
        Based on the full context, you MUST categorize the student into exactly one of these three statuses:
        1. "NORMAL" - Student is doing fine, attendance is good, no immediate risks.
        2. "WATCH" - Mild concerns, dropping attendance, or some social risks present.
        3. "DANGER" - High ML score OR severe social risks (e.g., extremely poor attendance, child labor, multiple risk factors). Override the ML score with a high number (75-95) if social risks indicate DANGER but the ML score is low.DO NOT MENTION ML SCORE AS A FACTOR.
        
        CRITICAL INSTRUCTION: In your output JSON, DO NOT use the words "model", "ML score", or "Neural Network". Write your reasoning purely based on the student's real-world social, academic, and attendance facts.
        """

        user_prompt = f"""
        Base ML Risk Score: {ml_score}
        STUDENT DATA: {json.dumps(student_data, indent=2, default=str)}
        HISTORY: {memory_context}

        OUTPUT JSON FORMAT:
        {{
            "risk_score": <INT: Final adjusted risk score (0-100)>,
            "status": "NORMAL" | "WATCH" | "DANGER",
            "primary_drivers": ["Reason 1 based on real-world facts", "Reason 2 based on real-world facts"],
            "summary_for_memory": "A 1-sentence summary focusing exclusively on the student's real-world situation and social risks.",
            "recommended_next_agent": "FinancialAdvocate" | "Educator" | "None"
        }}
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model_llm,
                messages=[
                    {"role": "system", "content": system_instruction}, 
                    {"role": "user", "content": user_prompt}
                ],
                response_format={ "type": "json_object" }, 
                temperature=0.3
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            # Fallback will also use the new statuses
            fallback_status = "DANGER" if ml_score >= 70 else ("WATCH" if ml_score >= 40 else "NORMAL")
            return {
                "risk_score": ml_score, 
                "status": fallback_status, 
                "primary_drivers": [f"Error in LLM analysis: {str(e)}"],
                "summary_for_memory": "Student flagged due to automated system fallback."
            }