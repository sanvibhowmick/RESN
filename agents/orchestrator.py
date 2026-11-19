import os
import json
import asyncio
from agents.risk_analyst import RiskAnalyst
from agents.financial_adv import FinancialAdvocate
from agents.educator import Educator
from agents.community_mediator import CommunityMediator
from memory.pg_vector import PGVectorMemory
from tools.db_tools import get_student_full_context
from db_connector import run_query

class RESNOrchestrator:
    def __init__(self):
        """Initializes the Brain of the system and its specialized agents."""
        self.memory = PGVectorMemory()
        self.analyst = RiskAnalyst()
        self.finance = FinancialAdvocate()
        self.educator = Educator()
        self.mediator = CommunityMediator()

    async def _run_danger_path_parallel(self, student_id, student_data, risk_report, counseling_lang):
        """
        Runs the three DANGER-path specialists concurrently instead of
        sequentially. FinancialAdvocate / CommunityMediator / Educator each
        only depend on `risk_report` (already computed), not on each
        other's output, so there's no ordering requirement between them --
        they were only running one-after-another before because the code
        called them in sequence, not because they needed to be.

        The OpenAI client used inside each agent is synchronous, so each
        call is dispatched to its own thread via asyncio.to_thread and
        awaited together with asyncio.gather, rather than rewriting all
        three agents onto AsyncOpenAI.
        """
        finance_task = asyncio.to_thread(
            self.finance.provide_support, student_id, student_data, risk_report
        )
        mediator_task = asyncio.to_thread(
            self.mediator.generate_counseling_script,
            student_id, student_data, risk_report, counseling_lang
        )
        educator_task = asyncio.to_thread(
            self.educator.create_remedial_plan, student_id, student_data, risk_report
        )

        finance_result, mediator_result, edu_result = await asyncio.gather(
            finance_task, mediator_task, educator_task
        )
        return finance_result, mediator_result, edu_result

    def run_intervention_pipeline(self, student_id, counseling_lang="Hindi"):
        """
        Executes the targeted intervention logic based on real-time risk assessment.
        """
        # 1. Gather Context (Data + Memory)
        student_data = get_student_full_context(student_id)
        if "error" in student_data:
            return student_data

        # Fetch semantic history to inform the Risk Analyst
        past_memories = self.memory.search_memory(student_id, "previous risk factors and interventions")

        # 2. Level 1: Risk Analysis (The Foundation)
        risk_report = self.analyst.analyze(student_data, past_memories)
        
        # Sanitize status string ('NORMAL', 'WATCH', 'DANGER') and score
        raw_status = risk_report.get('status', 'NORMAL')
        status = str(raw_status).strip().upper()
        current_risk_score = int(risk_report.get('risk_score', 0))

        attendance_hist = student_data.get('attendance_history', [])
        current_att = float(attendance_hist[0].get('attendance_percent', 75.0)) if attendance_hist else 75.0
        academic_hist = student_data.get('academic_performance', [])
        current_score_exam = float(academic_hist[0].get('score', 50.0)) if academic_hist else 50.0

        # Query historical analysis runs to track longitudinal trajectory (improvement / deprovement)
        past_runs = run_query(
            """
            SELECT memory_id, context_summary, metadata, created_at
            FROM agent_memory
            WHERE student_id = %s AND (metadata->>'type' IS NULL OR metadata->>'type' != 'improvement')
            ORDER BY created_at DESC
            """,
            (student_id,),
            return_dict=True
        ) or []

        run_number = len(past_runs) + 1

        if run_number == 1:
            trajectory = {
                "run_number": 1,
                "is_baseline": True,
                "current_score": current_risk_score,
                "current_status": status,
                "current_attendance": current_att,
                "current_exam_score": current_score_exam,
                "message": "Baseline diagnostic run. Future runs will track longitudinal progress, improvements, and risk escalations."
            }
        else:
            prev_run = past_runs[0]
            prev_meta = prev_run.get('metadata', {}) or {}
            prev_score = int(prev_meta.get('score', current_risk_score))
            prev_status = str(prev_meta.get('status', status)).strip().upper()
            prev_att = float(prev_meta.get('attendance', current_att))
            prev_exam = float(prev_meta.get('exam_score', current_score_exam))

            delta_score = current_risk_score - prev_score
            delta_att = current_att - prev_att
            delta_exam = current_score_exam - prev_exam

            if delta_score <= -4 or (delta_score <= 0 and delta_att >= 3.0):
                trend = "IMPROVEMENT"
                title = f"🟢 Measurable Improvement Detected (Run #{run_number})"
            elif delta_score >= 4 or (delta_score >= 0 and delta_att <= -3.0):
                trend = "DEPROVEMENT"
                title = f"🔴 Risk Escalation / Deprovement Alert (Run #{run_number})"
            else:
                trend = "STEADY"
                title = f"⚪ Stable Risk Profile (Run #{run_number})"

            # Fetch documented interventions logged
            recent_measures = run_query(
                """
                SELECT improvement_id, previous_attendance, new_attendance, subject, 
                       previous_score, new_score, grade, outcome_status, measures_taken, notes, created_at
                FROM student_improvements
                WHERE student_id = %s
                ORDER BY created_at DESC
                LIMIT 3
                """,
                (student_id,),
                return_dict=True
            ) or []

            trajectory = {
                "run_number": run_number,
                "is_baseline": False,
                "trend": trend,
                "title": title,
                "prev_score": prev_score,
                "current_score": current_risk_score,
                "delta_score": delta_score,
                "prev_status": prev_status,
                "current_status": status,
                "prev_attendance": prev_att,
                "current_attendance": current_att,
                "delta_attendance": delta_att,
                "prev_exam_score": prev_exam,
                "current_exam_score": current_score_exam,
                "delta_exam_score": delta_exam,
                "recent_measures": recent_measures,
                "prev_run_time": str(prev_run.get('created_at'))
            }

        # Save the Analyst's current conclusion to long-term memory with cohort metadata
        profile = student_data.get('profile', {})
        self.memory.add_memory(
            student_id=student_id, 
            context_summary=risk_report.get('summary_for_memory', 'No summary provided.'),
            metadata={
                "status": status,
                "score": current_risk_score,
                "attendance": current_att,
                "exam_score": current_score_exam,
                "type": "analysis",
                "run_number": run_number,
                "grade": profile.get('grade'),
                "gender": profile.get('gender'),
                "location": profile.get('location_name', 'Rural')
            }
        )

        # Cross-student lookup: find OTHER students whose past summaries are
        # semantically similar to THIS student's current situation and aligned with their
        # risk cohort (preventing DANGER cases from matching NORMAL/WATCH students).
        similar_cases = self.memory.find_similar_cases(
            query_text=risk_report.get('summary_for_memory', ''),
            exclude_student_id=student_id,
            status=status,
            limit=3
        )

        results = {
            "analysis": risk_report,
            "similar_cases": similar_cases,
            "trajectory": trajectory,
            "actions": []
        }

        # 3. Level 2: Conditional Intervention Triage
        
        # --- PATH A: DANGER (Counseling + Scholarship + Remedial, IN PARALLEL) ---
        if status == "DANGER":
            finance_result, mediator_result, edu_result = asyncio.run(
                self._run_danger_path_parallel(student_id, student_data, risk_report, counseling_lang)
            )

            # Preserve the original ordering (finance, counseling, academic)
            # in the returned actions list even though the calls themselves
            # ran concurrently, so app.py's rendering doesn't need to change.
            results['actions'].append({"type": "finance", "data": finance_result})
            results['actions'].append({"type": "counseling", "data": mediator_result})
            results['actions'].append({"type": "academic", "data": edu_result})

        # --- PATH B: WATCH STATUS (Remedial Only) ---
        elif status == "WATCH":
            edu_result = self.educator.create_remedial_plan(student_id, student_data, risk_report)
            results['actions'].append({"type": "academic", "data": edu_result})

        # --- PATH C: NORMAL (Monitor Only) ---
        else:
            results['message'] = "Student is currently on track. No immediate intervention required."

        return results