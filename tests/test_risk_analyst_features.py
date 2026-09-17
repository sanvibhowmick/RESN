"""Tests for the feature-vocabulary mapping in RiskAnalyst._get_ml_risk_score.

These tests validate that real production DB values (numeric school_distanceKm,
integer grade, Indian home_language, etc.) are correctly mapped to the trained
model's categorical vocabulary before one-hot encoding.

The test constructs a student_data dict with known values and inspects the
resulting input_row to confirm nonzero entries appear in the expected feature
slots.  It is designed to FAIL against the original code (which has a vocabulary
mismatch) and PASS after the mapping layer is added.
"""

import os
import sys
import unittest

# Ensure project root is on sys.path so imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import joblib


class TestFeatureMapping(unittest.TestCase):
    """Validate the production-value → training-vocabulary mapping."""

    @classmethod
    def setUpClass(cls):
        """Load the feature list once for all tests."""
        model_dir = os.path.join(os.path.dirname(__file__), "..", "model")
        cls.features_list = joblib.load(
            os.path.join(model_dir, "features_list.joblib")
        )

    # ------------------------------------------------------------------
    # Helper: build a student_data dict that looks like what
    # get_student_full_context returns from the production DB.
    # ------------------------------------------------------------------
    @staticmethod
    def _make_student_data(
        grade=10,
        age=15,
        annual_income=50000,
        gender="Male",
        school_distanceKm=2.0,
        home_language="Hindi",
        hh_occupation="Farming",
        hh_size=5,
        hh_children=2,
        location_name="Rural",
        attendance_percent=85.0,
        seasonal_labor=False,
        sibling_dropout=False,
        migrant_family=False,
        parent_education_level="Primary",
    ):
        return {
            "profile": {
                "student_id": 1,
                "name": "Test Student",
                "grade": grade,
                "age": age,
                "annual_income": annual_income,
                "gender": gender,
                "hh_size": hh_size,
                "hh_children": hh_children,
                "school_distanceKm": school_distanceKm,
                "home_language": home_language,
                "hh_occupation": hh_occupation,
                "location_name": location_name,
                "caste_category": "General",
                "meansToSchool": None,  # not collected in production
            },
            "attendance_history": [
                {"month": "2026-01-01", "attendance_percent": attendance_percent}
            ],
            "academic_performance": [
                {"subject": "Math", "score": 75, "exam_date": "2026-01-10"}
            ],
            "social_risk_factors": {
                "seasonal_labor": seasonal_labor,
                "sibling_dropout": sibling_dropout,
                "migrant_family": migrant_family,
                "parent_education_level": parent_education_level,
            },
        }

    def _build_input_row(self, student_data):
        """Call _get_ml_risk_score's feature-building logic and return the
        raw input_row list BEFORE scaling, so we can inspect individual
        feature slots.

        We import the class here to avoid module-level import failures
        (the class constructor loads the full model, which is fine for tests).
        """
        from agents.risk_analyst import RiskAnalyst

        analyst = RiskAnalyst()
        # We need the input_row before scaling.  The cleanest way is to
        # call the internal mapping + encoding logic directly.  We'll
        # monkey-patch the method to capture the row.
        captured = {}
        original_method = analyst._get_ml_risk_score

        def patched(sd):
            # We replicate the method body up to the point where input_row
            # is built, capturing it before scaling.
            profile = sd.get("profile", {})
            social = sd.get("social_risk_factors", {})
            attendance = sd.get("attendance_history", [])

            latest_att = (
                attendance[0].get("attendance_percent", analyst.DEFAULTS["attendance"])
                if attendance
                else analyst.DEFAULTS["attendance"]
            )

            def pf(key, default_key=None):
                val = profile.get(key)
                if val is None:
                    return analyst.DEFAULTS[default_key or key]
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
                    "parent_education_level", analyst.DEFAULTS["mothers_edu"]
                ),
                "hh_edu": social.get(
                    "parent_education_level", analyst.DEFAULTS["hh_edu"]
                ),
                "location_name": pf("location_name"),
                "home_language": pf("home_language"),
                "hh_occupation": pf("hh_occupation"),
                "meansToSchool": pf("meansToSchool"),
            }

            # Apply mapping if it exists (post-fix only)
            if hasattr(analyst, "_map_production_values_to_training_vocab"):
                raw_vals = analyst._map_production_values_to_training_vocab(raw_vals)

            input_row = []
            for feat in analyst.features_list:
                if feat in raw_vals and not isinstance(raw_vals.get(feat), str):
                    input_row.append(float(raw_vals[feat]))
                elif "_" in feat:
                    # Use the same parsing the production code uses
                    parts = feat.split("_", 1)
                    if len(parts) == 2:
                        base_col = parts[0]
                        category = parts[1]
                        # Try all possible base column splits for multi-word bases
                        matched = False
                        for key in raw_vals:
                            if feat.startswith(key + "_"):
                                category = feat[len(key) + 1:]
                                val = (
                                    1.0
                                    if str(raw_vals.get(key, "")) == category
                                    else 0.0
                                )
                                input_row.append(val)
                                matched = True
                                break
                        if not matched:
                            val = (
                                1.0
                                if str(raw_vals.get(base_col, "")) == category
                                else 0.0
                            )
                            input_row.append(val)
                    else:
                        input_row.append(0.0)
                else:
                    input_row.append(0.0)

            captured["input_row"] = input_row
            captured["raw_vals"] = raw_vals
            return original_method(sd)

        patched(student_data)
        return captured["input_row"], captured["raw_vals"]

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_school_distance_2km_maps_to_correct_bucket(self):
        """school_distanceKm=2.0 should activate 'school_distanceKm_2-3 km'."""
        student_data = self._make_student_data(school_distanceKm=2.0)
        input_row, _ = self._build_input_row(student_data)

        idx = self.features_list.index("school_distanceKm_2-3 km")
        self.assertEqual(
            input_row[idx],
            1.0,
            f"Feature 'school_distanceKm_2-3 km' (index {idx}) should be 1.0 "
            f"for school_distanceKm=2.0, but got {input_row[idx]}",
        )

    def test_grade_10_maps_to_form_one(self):
        """grade=10 (Indian system) should activate 'grade_Form One'."""
        student_data = self._make_student_data(grade=10)
        input_row, _ = self._build_input_row(student_data)

        idx = self.features_list.index("grade_Form One")
        self.assertEqual(
            input_row[idx],
            1.0,
            f"Feature 'grade_Form One' (index {idx}) should be 1.0 "
            f"for grade=10, but got {input_row[idx]}",
        )

    def test_hindi_language_maps_to_native_language(self):
        """home_language='Hindi' should activate 'home_language_Native language'."""
        student_data = self._make_student_data(home_language="Hindi")
        input_row, _ = self._build_input_row(student_data)

        idx = self.features_list.index("home_language_Native language")
        self.assertEqual(
            input_row[idx],
            1.0,
            f"Feature 'home_language_Native language' (index {idx}) should be 1.0 "
            f"for home_language='Hindi', but got {input_row[idx]}",
        )

    def test_male_gender_maps_correctly(self):
        """gender='Male' should activate 'gender_Male'."""
        student_data = self._make_student_data(gender="Male")
        input_row, _ = self._build_input_row(student_data)

        idx = self.features_list.index("gender_Male")
        self.assertEqual(
            input_row[idx],
            1.0,
            f"Feature 'gender_Male' (index {idx}) should be 1.0 "
            f"for gender='Male', but got {input_row[idx]}",
        )

    def test_farming_occupation_maps_to_self_employed(self):
        """hh_occupation='Farming' should activate 'hh_occupation_Self-employed'."""
        student_data = self._make_student_data(hh_occupation="Farming")
        input_row, _ = self._build_input_row(student_data)

        idx = self.features_list.index("hh_occupation_Self-employed")
        self.assertEqual(
            input_row[idx],
            1.0,
            f"Feature 'hh_occupation_Self-employed' (index {idx}) should be 1.0 "
            f"for hh_occupation='Farming', but got {input_row[idx]}",
        )

    def test_walk_default_for_missing_means_to_school(self):
        """meansToSchool=None should default to 'Walk', activating 'meansToSchool_Walk'."""
        student_data = self._make_student_data()
        input_row, _ = self._build_input_row(student_data)

        idx = self.features_list.index("meansToSchool_Walk")
        self.assertEqual(
            input_row[idx],
            1.0,
            f"Feature 'meansToSchool_Walk' (index {idx}) should be 1.0 "
            f"for meansToSchool=None (default 'Walk'), but got {input_row[idx]}",
        )

    def test_multiple_nonzero_features(self):
        """A realistic student should have MANY nonzero one-hot features, not just
        the 7 numeric ones."""
        student_data = self._make_student_data(
            grade=10,
            school_distanceKm=5.0,
            home_language="Bengali",
            hh_occupation="Daily Wage Labor",
            gender="Male",
            hh_size=5,
            hh_children=3,
            parent_education_level="Primary",
        )
        input_row, _ = self._build_input_row(student_data)

        # Count nonzero entries
        nonzero_count = sum(1 for v in input_row if v != 0.0)
        # We expect at least 12 nonzero entries:
        #   7 numeric (age, attendance, income, seasonal_labor, sibling_dropout,
        #              migrant_family, and either hh_size or school_distanceKm
        #              depending on mapping)
        # + at least 5 one-hot features that should match
        self.assertGreaterEqual(
            nonzero_count,
            12,
            f"Expected at least 12 nonzero features for a realistic student, "
            f"but got {nonzero_count}. Most one-hot features are failing to match.",
        )


if __name__ == "__main__":
    unittest.main()
