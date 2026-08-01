import os
import json
import asyncio
from agents.risk_analyst import RiskAnalyst
from agents.financial_adv import FinancialAdvocate
from agents.educator import Educator
from agents.community_mediator import CommunityMediator
from memory.pg_vector import PGVectorMemory
from tools.db_tools import get_student_full_context

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
        
        # Save the Analyst's current conclusion to long-term memory
        self.memory.add_memory(
            student_id=student_id, 
            context_summary=risk_report.get('summary_for_memory', 'No summary provided.'),
            metadata={"status": risk_report.get('status'), "score": risk_report.get('risk_score')}
        )

        # Cross-student lookup: find OTHER students whose past summaries are
        # semantically similar to THIS student's current situation, using
        # this run's own summary as the query so it reflects the live case
        # rather than a fixed generic phrase.
        similar_cases = self.memory.find_similar_cases(
            query_text=risk_report.get('summary_for_memory', ''),
            exclude_student_id=student_id,
            limit=3
        )

        # ✅ CRITICAL FIX: Sanitize the string so "Watch", "WATCH ", and "watch" are all treated equally
        raw_status = risk_report.get('status', 'NORMAL')
        status = str(raw_status).strip().upper() 

        results = {
            "analysis": risk_report,
            "similar_cases": similar_cases,
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