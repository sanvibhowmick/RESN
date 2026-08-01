import json
import os
import joblib
import numpy as np
import torch
import torch.nn as nn
from openai import OpenAI


# 1. RESIDUAL MODEL ARCHITECTURE
class RESNModel(nn.Module):
    def __init__(self, input_dim, n_layers, units_per_layer, dropout_rate):
        super().__init__()
        self.blocks = nn.ModuleList()
        self.skips = nn.ModuleList()

        in_f = input_dim
        for out_f, dr in zip(units_per_layer, dropout_rate):
            self.blocks.append(
                nn.Sequential(
                    nn.Linear(in_f, out_f),
                    nn.BatchNorm1d(out_f),
                    nn.ReLU(),
                    nn.Dropout(dr),
                )
            )
            self.skips.append(nn.Linear(in_f, out_f, bias=False))
            in_f = out_f

        self.head = nn.Linear(in_f, 1)

    def forward(self, x):
        for block, skip in zip(self.blocks, self.skips):
            x = block(x) + skip(x)
        return self.head(x)


class RiskAnalyst:
    # Dataset-mean fallbacks, used ONLY if a field is missing from the DB row
    # (e.g. a legacy student created before the schema added these columns).
    # These are NOT used for normal operation anymore now that the schema
    # and Data Entry form actually collect hh_size / hh_children /
    # school_distanceKm / home_language / hh_occupation / location_name.
    DEFAULTS = {
        "grade": 10,
        "age": 15,
        "income": 0,
        "attendance": 85.0,
        "hh_size": 5,
        "school_distanceKm": 2.0,
        "hh_children": 2,
        "gender": "Unknown",
        "mothers_edu": "Unknown",
        "hh_edu": "Unknown",
        "location_name": "Rural",
        "home_language": "Unknown",
        "hh_occupation": "Unknown",
        "meansToSchool": "Unknown",
    }

    def __init__(self):
        """Initializes the Hybrid Risk Analyst using RESN Model and LLM."""
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model_llm = os.getenv("LLM_MODEL", "gpt-4o")

        # Load custom model assets
        model_dir = os.path.join(os.getcwd(), "model")
        self.scaler = joblib.load(os.path.join(model_dir, "scaler.joblib"))
        self.features_list = joblib.load(
            os.path.join(model_dir, "features_list.joblib")
        )

        checkpoint_path = os.path.join(model_dir, "dropout_model.pth")
        config_path = os.path.join(model_dir, "best_params.json")
        if not os.path.exists(config_path):
            config_path = os.path.join(model_dir, "config.json")

        state_dict = torch.load(
            checkpoint_path, map_location=torch.device("cpu")
        )

        # Handle checkpoint saved as dict vs pure state_dict
        if isinstance(state_dict, dict) and "state_dict" in state_dict:
            checkpoint_meta = state_dict
            state_dict = state_dict["state_dict"]
        else:
            checkpoint_meta = {}

        # 1. Try reading dynamic hyperparameters from config file
        units = None
        dropouts = None
        n_layers = None

        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
            n_layers = config.get("n_layers")
            units = config.get("units_per_layer")
            dropouts = config.get("dropout_rate")
        elif "config" in checkpoint_meta:
            config = checkpoint_meta["config"]
            n_layers = config.get("n_layers")
            units = config.get("units_per_layer")
            dropouts = config.get("dropout_rate")

        # 2. Dynamic Fallback: Infer architecture structure directly from
        # saved state_dict shapes. This means retraining with a different
        # architecture doesn't require a code change here.
        if not units:
            layer_keys = [
                k
                for k in state_dict.keys()
                if k.startswith("blocks.") and k.endswith(".0.weight")
            ]
            n_layers = len(layer_keys)
            units = [
                state_dict[f"blocks.{i}.0.weight"].shape[0]
                for i in range(n_layers)
            ]

        if not dropouts:
            dropouts = [0.0] * n_layers

        # Instantiate dynamic model
        self.risk_model = RESNModel(
            input_dim=len(self.features_list),
            n_layers=n_layers,
            units_per_layer=units,
            dropout_rate=dropouts,
        )

        self.risk_model.load_state_dict(state_dict)
        self.risk_model.eval()

    def _get_ml_risk_score(self, student_data):
        """Maps data to features and generates a 0-100 score.

        `profile` here is the full `students` row (get_student_full_context
        does `SELECT * FROM students`), so hh_size / hh_children /
        school_distanceKm / home_language / hh_occupation / location_name
        are now REAL, per-student columns rather than hardcoded constants.
        DEFAULTS is only a safety net for legacy rows or partially-filled
        bulk uploads, not the normal code path.
        """
        profile = student_data.get("profile", {})
        social = student_data.get("social_risk_factors", {})
        attendance = student_data.get("attendance_history", [])

        latest_att = (
            attendance[0].get("attendance_percent", self.DEFAULTS["attendance"])
            if attendance
            else self.DEFAULTS["attendance"]
        )

        def pf(key, default_key=None):
            """Pull a field from the student profile row, falling back to
            DEFAULTS only if the column is missing or NULL."""
            val = profile.get(key)
            if val is None:
                return self.DEFAULTS[default_key or key]
            return val

        raw_vals = {
            "grade": pf("grade"),
            "age": pf("age"),
            "income": pf("annual_income", "income"),
            "attendance": latest_att,
            "hh_size": pf("hh_size"),
            "school_distanceKm": pf("school_distanceKm"),
            "hh_children": pf("hh_children"),
            "migrant_family": 1 if social.get("migrant_family") else 0,
            "seasonal_labor": 1 if social.get("seasonal_labor") else 0,
            "sibling_dropout": 1 if social.get("sibling_dropout") else 0,
            "gender": pf("gender"),
            "mothers_edu": social.get(
                "parent_education_level", self.DEFAULTS["mothers_edu"]
            ),
            "hh_edu": social.get(
                "parent_education_level", self.DEFAULTS["hh_edu"]
            ),
            "location_name": pf("location_name"),
            "home_language": pf("home_language"),
            "hh_occupation": pf("hh_occupation"),
            "meansToSchool": pf("meansToSchool"),
        }

        input_row = []
        for feat in self.features_list:
            if feat in raw_vals and not isinstance(raw_vals.get(feat), str):
                input_row.append(float(raw_vals[feat]))
            elif "_" in feat:
                base_col, category = feat.rsplit("_", 1)
                val = (
                    1.0
                    if str(raw_vals.get(base_col, "")) == category
                    else 0.0
                )
                input_row.append(val)
            else:
                input_row.append(0.0)

        scaled_data = self.scaler.transform([input_row])
        with torch.no_grad():
            logits = self.risk_model(
                torch.tensor(scaled_data, dtype=torch.float32)
            )
            probability = torch.sigmoid(logits).item()

        return int(probability * 100)

    def analyze(self, student_data, past_memories=None):
        """Combines ML score with LLM reasoning for the UI."""
        ml_score = self._get_ml_risk_score(student_data)

        memory_context = "No previous history."
        if past_memories:
            memory_context = "\n".join(
                [f"- {m.get('context_summary')}" for m in past_memories]
            )

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
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            fallback_status = (
                "DANGER"
                if ml_score >= 70
                else ("WATCH" if ml_score >= 40 else "NORMAL")
            )
            return {
                "risk_score": ml_score,
                "status": fallback_status,
                "primary_drivers": [f"Error in LLM analysis: {str(e)}"],
                "summary_for_memory": "Student flagged due to automated system fallback.",
            }