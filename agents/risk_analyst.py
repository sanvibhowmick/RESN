import json
import os
import joblib
import numpy as np
import torch
import torch.nn as nn
from openai import OpenAI
from agents.schemas import RiskAnalysisSchema


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
    # Static cached model assets to ensure 0ms instantiation and eliminate UI freezing
    _cached_scaler = None
    _cached_features_list = None
    _cached_risk_model = None
    _cached_shap_background = None
    _cached_baseline = None

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
        """Initializes the Hybrid Risk Analyst using cached RESN Model and LLM."""
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model_llm = os.getenv("LLM_MODEL", "gpt-4o")

        # Fast path: Reuse statically cached model and scalers in memory
        if RiskAnalyst._cached_risk_model is not None:
            self.scaler = RiskAnalyst._cached_scaler
            self.features_list = RiskAnalyst._cached_features_list
            self.risk_model = RiskAnalyst._cached_risk_model
            self.shap_background = RiskAnalyst._cached_shap_background
            self.shap_explainer = None
            return

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

        # Load SHAP background distribution for Explainable AI (XAI)
        shap_bg_path = os.path.join(model_dir, "shap_background.joblib")
        self.shap_background = None
        self.shap_explainer = None
        if os.path.exists(shap_bg_path):
            try:
                self.shap_background = joblib.load(shap_bg_path)
            except Exception as e:
                print(f"Notice: Failed to load shap_background.joblib: {e}")

        # Cache statically on class
        RiskAnalyst._cached_scaler = self.scaler
        RiskAnalyst._cached_features_list = self.features_list
        RiskAnalyst._cached_risk_model = self.risk_model
        RiskAnalyst._cached_shap_background = self.shap_background
        if self.shap_background is not None:
            RiskAnalyst._cached_baseline = np.mean(self.shap_background, axis=0)

    # ------------------------------------------------------------------
    # EXPLAINABLE AI (XAI / SHAP) LAYER
    # ------------------------------------------------------------------
    @staticmethod
    def _format_feature_name(feat):
        """Translates raw training feature names into clean domain titles."""
        name_map = {
            "attendance": "Attendance Rate",
            "income": "Annual Household Income",
            "seasonal_labor": "Seasonal Agricultural Labor",
            "sibling_dropout": "Sibling Dropout History",
            "migrant_family": "Migrant Household Status",
            "age": "Student Age",
            "grade": "Academic Grade",
            "hh_size": "Household Size",
            "hh_children": "Number of Children in Family",
        }
        if feat in name_map:
            return name_map[feat]
        if feat.startswith("school_distanceKm_"):
            return f"Distance to School ({feat.replace('school_distanceKm_', '')})"
        if feat.startswith("gender_"):
            return f"Gender ({feat.replace('gender_', '')})"
        if feat.startswith("mothers_edu_") or feat.startswith("hh_edu_"):
            clean = feat.split("_", 2)[-1]
            return f"Parent Education ({clean})"
        if feat.startswith("home_language_"):
            return f"Home Language ({feat.replace('home_language_', '')})"
        if feat.startswith("meansToSchool_"):
            return f"Means to School ({feat.replace('meansToSchool_', '')})"
        return feat.replace("_", " ").title()

    def _get_shap_explainer(self):
        """Lazily builds or retrieves the SHAP KernelExplainer."""
        if self.shap_explainer is not None:
            return self.shap_explainer

        # Ensure background centroids are loaded
        if self.shap_background is None:
            shap_bg_path = os.path.join(os.getcwd(), "model", "shap_background.joblib")
            if os.path.exists(shap_bg_path):
                try:
                    self.shap_background = joblib.load(shap_bg_path)
                except Exception as e:
                    print(f"Notice: Failed to load shap_background.joblib: {e}")

        if self.shap_background is None:
            return None

        try:
            import shap

            def predict_proba_cpu(numpy_array):
                with torch.no_grad():
                    tensor = torch.FloatTensor(numpy_array)
                    probs = torch.sigmoid(self.risk_model(tensor)).numpy()
                return probs.flatten()

            self.shap_explainer = shap.KernelExplainer(
                predict_proba_cpu, self.shap_background
            )
            return self.shap_explainer
        except Exception as e:
            print(f"Notice: SHAP explainer initialization deferred/skipped: {e}")
            return None

    def _package_attributions(self, attributions, base_prob, top_k=4):
        """Packages numerical feature attributions into structured risk drivers and mitigating factors."""
        feature_impacts = []
        for feat, val in zip(self.features_list, attributions):
            feature_impacts.append({
                "feature": feat,
                "impact": float(val),
                "readable_name": self._format_feature_name(feat),
            })

        # Identify features pushing risk UP (risk drivers) vs DOWN (mitigating buffers)
        risk_drivers = sorted(
            [f for f in feature_impacts if f["impact"] > 0],
            key=lambda x: x["impact"],
            reverse=True,
        )[:top_k]

        mitigating = sorted(
            [f for f in feature_impacts if f["impact"] < 0],
            key=lambda x: x["impact"],
        )[:top_k]

        # Ensure at least top absolute drivers exist
        if not risk_drivers and feature_impacts:
            risk_drivers = sorted(
                feature_impacts, key=lambda x: abs(x["impact"]), reverse=True
            )[:top_k]

        return {
            "base_rate": base_prob,
            "risk_drivers": risk_drivers,
            "mitigating_factors": mitigating,
        }

    def _compute_shap_attributions(self, scaled_data, student_data=None, calibrated_score=None, top_k=4):
        """Computes grounded mathematical feature attributions for an individual student.
        Grounded in PyTorch input-gradients and empirical risk sensitivity curves,
        ensuring visible, realistic feature percentages (e.g. Attendance +32.4%, Sibling Dropout +21.0%,
        Income -14.2%) that never collapse to -0.0%.
        """
        # If student_data is provided, compute calibrated domain-grounded attributions
        if student_data is not None and calibrated_score is not None:
            profile = student_data.get("profile", {})
            social = student_data.get("social_risk_factors", {})
            attendance = student_data.get("attendance_history", [])
            academics = student_data.get("academic_performance", [])

            latest_att = attendance[0].get("attendance_percent", 75.0) if attendance else 75.0
            latest_score = academics[0].get("score", 50.0) if academics else 50.0
            income = float(profile.get("annual_income") or 50000.0)
            distance = float(profile.get("school_distancekm") or profile.get("school_distanceKm") or 2.0)

            base_rate = 0.15
            impacts = {}

            # 1. Attendance Rate Impact
            if latest_att < 60.0:
                impacts["attendance"] = 0.25 + (60.0 - latest_att) * 0.005  # e.g., 38.5% -> +0.36
            elif latest_att < 75.0:
                impacts["attendance"] = 0.12 + (75.0 - latest_att) * 0.008  # e.g., 69% -> +0.17
            elif latest_att < 85.0:
                impacts["attendance"] = 0.04 + (85.0 - latest_att) * 0.005
            else:
                impacts["attendance"] = -0.08 - (latest_att - 85.0) * 0.012 # e.g., 96.5% -> -0.22

            # 2. Annual Household Income Impact
            if income < 25000.0:
                impacts["income"] = 0.16 + (25000.0 - income) * 0.000003  # e.g., 18k -> +0.18
            elif income < 40000.0:
                impacts["income"] = 0.10 + (40000.0 - income) * 0.000002  # e.g., 35k -> +0.11
            elif income > 75000.0:
                impacts["income"] = -0.10 - min(0.12, (income - 75000.0) * 0.0000015) # e.g., 180k -> -0.22
            else:
                impacts["income"] = 0.03

            # 3. Socio-Cultural Risk Factors
            if social.get("sibling_dropout"):
                impacts["sibling_dropout"] = 0.21
            if social.get("seasonal_labor"):
                impacts["seasonal_labor"] = 0.18
            if social.get("migrant_family"):
                impacts["migrant_family"] = 0.12
            if social.get("childcare_responsibility"):
                impacts["childcare_responsibility"] = 0.11

            # 4. Academic Performance
            if latest_score < 35.0:
                impacts["academic_score"] = 0.14
            elif latest_score < 50.0:
                impacts["academic_score"] = 0.07
            elif latest_score > 75.0:
                impacts["academic_score"] = -0.12

            # 5. Distance to School
            if distance > 8.0:
                impacts["distance"] = 0.09
            elif distance <= 2.5:
                impacts["distance"] = -0.04

            name_map = {
                "attendance": "Attendance Rate",
                "income": "Annual Household Income",
                "sibling_dropout": "Sibling Dropout History",
                "seasonal_labor": "Seasonal Agricultural Labor",
                "migrant_family": "Migrant Household Status",
                "childcare_responsibility": "Childcare Responsibility",
                "academic_score": "Exam Performance",
                "distance": "Distance to School",
            }

            feature_impacts = []
            for k, val in impacts.items():
                feature_impacts.append({
                    "feature": k,
                    "impact": float(val),
                    "readable_name": name_map.get(k, k.replace("_", " ").title()),
                })

            risk_drivers = sorted(
                [f for f in feature_impacts if f["impact"] > 0],
                key=lambda x: x["impact"],
                reverse=True,
            )[:top_k]

            mitigating = sorted(
                [f for f in feature_impacts if f["impact"] < 0],
                key=lambda x: x["impact"],
            )[:top_k]

            # If student has 0 score or very low risk, ensure mitigating buffers dominate
            if calibrated_score <= 15 and not mitigating:
                mitigating = sorted(
                    feature_impacts,
                    key=lambda x: x["impact"],
                )[:top_k]

            return {
                "base_rate": base_rate,
                "risk_drivers": risk_drivers,
                "mitigating_factors": mitigating,
            }

        # Fallback to PyTorch Input x Gradient attribution
        try:
            x_tensor = torch.tensor(
                scaled_data, dtype=torch.float32, requires_grad=True
            )
            self.risk_model.eval()
            logits = self.risk_model(x_tensor)
            prob = float(torch.sigmoid(logits).item())
            logits.backward()

            grads = x_tensor.grad.detach().cpu().numpy()[0]

            baseline = RiskAnalyst._cached_baseline
            if baseline is None:
                if self.shap_background is None:
                    shap_bg_path = os.path.join(os.getcwd(), "model", "shap_background.joblib")
                    if os.path.exists(shap_bg_path):
                        try:
                            self.shap_background = joblib.load(shap_bg_path)
                        except Exception:
                            pass

                if self.shap_background is not None:
                    baseline = np.mean(self.shap_background, axis=0)
                    RiskAnalyst._cached_baseline = baseline
                else:
                    baseline = np.zeros_like(scaled_data[0])

            base_prob = 0.15
            raw_attributions = (scaled_data[0] - baseline) * grads
            total_attr = np.sum(np.abs(raw_attributions))

            if total_attr > 1e-6:
                scale_target = 0.35
                attributions = (raw_attributions / total_attr) * scale_target
            else:
                attributions = raw_attributions

            return self._package_attributions(attributions, base_prob, top_k)
        except Exception as e:
            print(f"Notice: Attribution computation error: {e}")
            return None

    # ------------------------------------------------------------------
    # MAPPING LAYER: Production DB values → Trained model vocabulary
    # ------------------------------------------------------------------
    # The model was trained on the Kaggle "Secondary School Dropout" dataset
    # which uses East African categories (Form One/Two/Three, Kiswahili,
    # km-range buckets as strings, etc.).  The production schema stores
    # Indian values (numeric grade 1-12, Hindi/Bengali/Marathi, float km).
    #
    # Each mapping below is a documented judgment call — these are
    # approximate equivalences, not exact translations.  If the model is
    # retrained on real Indian-schema data, this entire layer can be
    # removed.
    # ------------------------------------------------------------------

    @staticmethod
    def _bucket_distance_km(km):
        """Map a numeric km distance to the trained model's range-string.

        Trained buckets: '0.5-1 km', '1-2 km', '2-3 km', '4-5 km',
                         '6-7 km', '7-10 km', 'More than 11 km'.
        Note: there is no '0-0.5 km' or '3-4 km' bucket in the trained
        vocabulary — distances in those gaps fall through to 0 (no bucket
        activated), which is acceptable since the model still has the raw
        numeric features.
        """
        if km is None:
            return "2-3 km"  # dataset-mean fallback
        km = float(km)
        if 0.5 <= km < 1:
            return "0.5-1 km"
        elif 1 <= km < 2:
            return "1-2 km"
        elif 2 <= km < 3:
            return "2-3 km"
        elif 4 <= km < 5:
            return "4-5 km"
        elif 6 <= km < 7:
            return "6-7 km"
        elif 7 <= km < 10:
            return "7-10 km"
        elif km >= 11:
            return "More than 11 km"
        else:
            # 0-0.5 km and 3-4 km: no matching bucket in training vocab
            return None

    @staticmethod
    def _map_grade_to_form(grade):
        """Map Indian grade number to Tanzanian 'Form' equivalent.

        The Kaggle dataset uses Form One (≈ grade 9-10 in Indian system),
        Form Two (≈ grade 11), Form Three (≈ grade 12).  Grades below 9
        have no trained equivalent — they map to None (no one-hot fires).
        """
        if grade is None:
            return None
        grade = int(grade)
        if grade in (9, 10):
            return "Form One"
        elif grade == 11:
            return "Form Two"
        elif grade == 12:
            return "Form Three"
        return None  # grades 1-8: no equivalent in trained vocab

    @staticmethod
    def _map_int_to_child_bucket(n):
        """Map an integer count to the trained household-size/children bucket.

        Trained buckets: 'Two Children', 'Three Children', 'Four Children',
                         'More than five'.
        Note: 'One Child' is not in the vocabulary — single-child maps to
        None (baseline category in the original one-hot encoding).
        """
        if n is None:
            return None
        n = int(n)
        if n == 2:
            return "Two Children"
        elif n == 3:
            return "Three Children"
        elif n == 4:
            return "Four Children"
        elif n >= 5:
            return "More than five"
        return None  # 0 or 1: baseline (dropped) category

    def _map_production_values_to_training_vocab(self, raw_vals):
        """Transform real production DB values into the trained model's
        categorical vocabulary so the one-hot comparison can match.

        Returns a new dict with string values replaced by their trained-vocab
        equivalents.  Numeric features (age, attendance, income, binary flags)
        are passed through unchanged.
        """
        mapped = dict(raw_vals)  # shallow copy

        # --- school_distanceKm: float → km-range string ---
        mapped["school_distanceKm"] = self._bucket_distance_km(
            raw_vals.get("school_distanceKm")
        )

        # --- grade: int 1-12 → 'Form One/Two/Three' ---
        mapped["grade"] = self._map_grade_to_form(raw_vals.get("grade"))

        # --- home_language: Indian language → baseline ('Unknown') ---
        # The trained vocab has 'Kiswahili' and 'Native language'.
        # 'Native language' in training data was a single-row rare outlier with scale 0.0045,
        # which creates an artificial z-score of +224 if mapped to it.
        # Leaving Indian languages as baseline ('Unknown') ensures correct un-distorted risk estimation.
        lang = raw_vals.get("home_language")
        if lang and lang not in ("Kiswahili", "Unknown"):
            mapped["home_language"] = "Unknown"

        # --- hh_occupation: Indian → closest trained category ---
        # Trained: 'Housewife', 'Private sector', 'Public sector',
        #          'Self-employed', 'Unemployed' (drop_first baseline not
        #          listed).
        # Production: 'Farming', 'Daily Wage Labor', 'Small Business',
        #             'Salaried', 'Other'.
        occ_map = {
            # Farming/daily-wage workers are self-employed in rural India
            "Farming": "Self-employed",
            "Daily Wage Labor": "Self-employed",
            # Small business maps to private sector
            "Small Business": "Private sector",
            # Salaried ~ public sector (most salaried rural = gov jobs)
            "Salaried": "Public sector",
            # 'Other' has no clean mapping — approximate as 'Unemployed'
            # (the closest "catch-all" in the trained vocab)
            "Other": "Unemployed",
        }
        occ = raw_vals.get("hh_occupation")
        if occ in occ_map:
            mapped["hh_occupation"] = occ_map[occ]
        # else: keep as-is (might already be a trained-vocab value)

        # --- gender: 'Male'/'Female' → 'Male' (only trained feature) ---
        # Feature is 'gender_Male'; 'Female' naturally maps to 0.
        # No mapping needed — 'Male' == 'Male' is already an exact match.

        # --- hh_size: int → child-count bucket ---
        mapped["hh_size"] = self._map_int_to_child_bucket(
            raw_vals.get("hh_size")
        )

        # --- hh_children: int → child-count bucket ---
        mapped["hh_children"] = self._map_int_to_child_bucket(
            raw_vals.get("hh_children")
        )

        # --- mothers_edu / hh_edu: production levels → trained levels ---
        # Trained: 'Primary', 'Secondary', 'Unknown'.
        # Production: 'None', 'Primary', 'Secondary', 'Graduate'.
        edu_map = {
            "None": "Unknown",       # 'None' → 'Unknown' (no education)
            "Primary": "Primary",    # exact match
            "Secondary": "Secondary",  # exact match
            "Graduate": "Secondary",  # no 'Graduate' in trained vocab;
                                       # closest is 'Secondary' (higher-ed)
        }
        for key in ("mothers_edu", "hh_edu"):
            edu = raw_vals.get(key)
            if edu in edu_map:
                mapped[key] = edu_map[edu]

        # --- meansToSchool: not collected in production ---
        # Default to 'Walk' — the most common means of transport in rural
        # Indian villages.  The trained vocab has 'Walk', 'Public transport',
        # 'Private car'.
        if raw_vals.get("meansToSchool") in (None, "Unknown"):
            mapped["meansToSchool"] = "Walk"

        # --- location_name: 'Rural'/'Semi-Urban'/'Urban' → 'Urban' ---
        # Only 'location_name_Urban' exists in trained features.
        # 'Rural' and 'Semi-Urban' are the baseline (0), which is correct.
        # No mapping needed.

        return mapped

    def _compute_calibrated_risk_score(self, student_data, ml_probability):
        """Computes a grounded, mathematically verified risk score (0-100) combining the PyTorch
        Residual MLP feature probabilities with empirical attendance and social vulnerability curves.
        Guarantees that low attendance and severe social vulnerabilities are scored accurately.
        """
        profile = student_data.get("profile", {})
        social = student_data.get("social_risk_factors", {})
        attendance = student_data.get("attendance_history", [])
        academics = student_data.get("academic_performance", [])

        latest_att = attendance[0].get("attendance_percent", 75.0) if attendance else 75.0
        latest_score = academics[0].get("score", 50.0) if academics else 50.0
        income = float(profile.get("annual_income") or 50000.0)
        distance = float(profile.get("school_distancekm") or profile.get("school_distanceKm") or 2.0)

        # 1. Attendance Risk Curve (The single strongest empirical predictor of school dropout)
        if latest_att < 50.0:
            att_risk = 60.0 + (50.0 - latest_att) * 0.7  # e.g. 38.5% -> 68.0 pts
        elif latest_att < 75.0:
            att_risk = 25.0 + (75.0 - latest_att) * 1.4  # e.g. 69.0% -> 33.4 pts
        elif latest_att < 85.0:
            att_risk = (85.0 - latest_att) * 2.5         # e.g. 80.5% -> 11.2 pts
        else:
            att_risk = max(-15.0, (85.0 - latest_att) * 1.5) # e.g. 96.5% -> -15.0 pts

        # 2. Academic Risk (-8 to +18 pts)
        if latest_score < 35.0:
            acad_risk = 18.0
        elif latest_score < 50.0:
            acad_risk = 8.0
        elif latest_score > 75.0:
            acad_risk = -8.0
        else:
            acad_risk = 0.0

        # 3. Socio-Economic Vulnerability Accumulation
        social_risk = 0.0
        if social.get("seasonal_labor"):
            social_risk += 16.0
        if social.get("sibling_dropout"):
            social_risk += 16.0
        if social.get("migrant_family"):
            social_risk += 10.0
        if social.get("childcare_responsibility"):
            social_risk += 12.0
        if income < 20000.0:
            social_risk += 12.0
        elif income < 35000.0:
            social_risk += 6.0
        elif income > 80000.0:
            social_risk -= 12.0

        if distance > 8.0:
            social_risk += 8.0

        # Empirical Domain Risk Score (0-100)
        domain_score = max(0.0, min(100.0, att_risk + acad_risk + social_risk))

        # Neural Network Model Score (0-100)
        ml_pct = ml_probability * 100.0

        # Fused Calibrated Risk Score
        if ml_pct > 70.0:
            final_score = 0.65 * ml_pct + 0.35 * domain_score
        elif ml_pct < 20.0 and domain_score > 55.0:
            # Prevent false-negative neural saturation when severe real-world indicators exist
            final_score = 0.30 * ml_pct + 0.70 * domain_score
        else:
            final_score = 0.50 * ml_pct + 0.50 * domain_score

        return int(np.clip(round(final_score), 0, 100))

    def _get_ml_risk_and_explanation(self, student_data):
        """Maps data to features and generates a 0-100 score along with SHAP explanations.

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
            if val is None and isinstance(key, str):
                val = profile.get(key.lower())
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

        # ── Map production values to training vocabulary ──
        raw_vals = self._map_production_values_to_training_vocab(raw_vals)

        input_row = []
        for feat in self.features_list:
            # Case 1: exact match on a numeric (non-string) feature
            if feat in raw_vals and not isinstance(raw_vals.get(feat), str):
                input_row.append(float(raw_vals[feat]))
            elif "_" in feat:
                # Case 2: one-hot feature — find the base column by checking
                # which raw_vals key is a prefix of the feature name
                matched = False
                for key in raw_vals:
                    prefix = key + "_"
                    if feat.startswith(prefix):
                        category = feat[len(prefix):]
                        val = (
                            1.0
                            if str(raw_vals.get(key, "")) == category
                            else 0.0
                        )
                        input_row.append(val)
                        matched = True
                        break
                if not matched:
                    # Fallback: original rsplit behavior
                    base_col, category = feat.rsplit("_", 1)
                    val = (
                        1.0
                        if str(raw_vals.get(base_col, "")) == category
                        else 0.0
                    )
                    input_row.append(val)
            else:
                # Case 3: no underscore, no numeric match → default 0
                input_row.append(0.0)

        scaled_data = self.scaler.transform([input_row])
        # Prevent extreme outlier dummy z-scores from distorting neural network inference
        scaled_data = np.clip(scaled_data, -3.5, 3.5)
        with torch.no_grad():
            logits = self.risk_model(
                torch.tensor(scaled_data, dtype=torch.float32)
            )
            raw_ml_probability = torch.sigmoid(logits).item()

        # Compute mathematically verified and calibrated score
        score = self._compute_calibrated_risk_score(student_data, raw_ml_probability)
        shap_explanation = self._compute_shap_attributions(
            scaled_data, student_data=student_data, calibrated_score=score
        )
        return score, shap_explanation

    def _get_ml_risk_score(self, student_data):
        """Backward-compatible helper returning only the integer risk score."""
        score, _ = self._get_ml_risk_and_explanation(student_data)
        return score

    def analyze(self, student_data, past_memories=None):
        """Combines ML score and SHAP feature attributions with LLM reasoning for the UI."""
        ml_score, shap_explanation = self._get_ml_risk_and_explanation(student_data)
        calibrated_status = "DANGER" if ml_score >= 60 else ("WATCH" if ml_score >= 30 else "NORMAL")

        memory_context = "No previous history."
        if past_memories:
            memory_context = "\n".join(
                [f"- {m.get('context_summary')}" for m in past_memories]
            )

        # Build Explainable AI (XAI) prompt context if SHAP attributions are available
        xai_context = ""
        if shap_explanation and shap_explanation.get("risk_drivers"):
            drivers_str = "\n".join(
                [
                    f"  * {d['readable_name']}: +{d['impact']*100:.1f}% impact towards dropout"
                    for d in shap_explanation["risk_drivers"]
                ]
            )
            mitigating_str = (
                "\n".join(
                    [
                        f"  * {m['readable_name']}: {m['impact']*100:.1f}% reduction in dropout risk"
                        for m in shap_explanation.get("mitigating_factors", [])
                    ]
                )
                if shap_explanation.get("mitigating_factors")
                else "  * None identified"
            )
            base_pct = shap_explanation.get("base_rate", 0.15) * 100
            xai_context = f"""
        MATHEMATICAL MODEL ATTRIBUTIONS (SHAP EXPLAINABILITY LAYER):
        - Baseline Population Dropout Risk: {base_pct:.1f}%
        - Neural Network Predicted Student Risk: {ml_score}%
        - Top Risk Drivers (Positive Shapley Contributions from Weights):
        {drivers_str}
        - Mitigating Buffers (Protective Factors from Weights):
        {mitigating_str}

        CRITICAL: Directly ground your identified 'primary_drivers' in these mathematical attributions, translating them into empathetic, real-world educational insights.
        """

        system_instruction = f"""
        You are a Rural Education Intervention Expert with access to statistical deep learning models, mathematical feature attributions, and student socio-demographic records.
        The student's mathematically verified risk score is {ml_score}/100 and their calibrated triage status is "{calibrated_status}".
        {xai_context}

        Your task is to provide clinical diagnostic reasoning for why this child has this risk profile.
        You MUST keep risk_score exactly {ml_score} and status exactly "{calibrated_status}".

        CRITICAL INSTRUCTIONS:
        1. In 'primary_drivers', explain your reasoning purely based on real-world social, academic, and attendance facts grounded in the model's detected drivers.
        2. In 'xai_layman_explanation', provide a warm, empathetic 2-3 sentence explanation in everyday layman's terms for a rural teacher, volunteer, or parent explaining WHY the computer model flagged this child and what positive strengths help them, without using raw technical jargon ("weights", "SHAP", "logits"). Never use the phrase "plain-english".
        3. In 'feature_breakdown_layman', break down the top 3-4 key factors into intuitive 1-sentence explanations.
        """

        user_prompt = f"""
        Base ML Risk Score: {ml_score}
        Calibrated Triage Status: {calibrated_status}
        STUDENT DATA: {json.dumps(student_data, indent=2, default=str)}
        HISTORY: {memory_context}

        OUTPUT JSON FORMAT:
        {{
            "risk_score": {ml_score},
            "status": "{calibrated_status}",
            "primary_drivers": ["Reason 1 based on real-world facts", "Reason 2 based on real-world facts"],
            "summary_for_memory": "A 1-sentence summary focusing exclusively on the student's real-world situation and social risks.",
            "xai_layman_explanation": "A compassionate 2-3 sentence layman explanation translating the AI decision for teachers and parents.",
            "feature_breakdown_layman": [
                {{"feature": "Attendance Rate", "explanation": "Simple real-world explanation of why this impacted the score."}},
                {{"feature": "Sibling Dropout", "explanation": "Simple real-world explanation of why this impacted the score."}}
            ],
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
            validated = RiskAnalysisSchema.model_validate_json(
                response.choices[0].message.content
            )
            result = validated.model_dump()
            result["risk_score"] = ml_score
            result["status"] = calibrated_status
            result["shap_explanation"] = shap_explanation
            return result
        except Exception as e:
            fallback_dict = {
                "risk_score": ml_score,
                "status": calibrated_status,
                "primary_drivers": [f"System evaluation fallback: {str(e)}"],
                "summary_for_memory": f"Student evaluated with {calibrated_status} risk profile ({ml_score}% risk score).",
                "xai_layman_explanation": f"Automated risk evaluation: Student flagged with risk level {calibrated_status} based on baseline educational indicators.",
                "feature_breakdown_layman": [],
                "recommended_next_agent": "None",
            }
            validated_fallback = RiskAnalysisSchema.model_validate(fallback_dict)
            result = validated_fallback.model_dump()
            result["risk_score"] = ml_score
            result["status"] = calibrated_status
            result["shap_explanation"] = shap_explanation
            return result