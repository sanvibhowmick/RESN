import os
import json
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
        # Every student goes through the Analyst first
        risk_report = self.analyst.analyze(student_data, past_memories)
        
        # Save the Analyst's current conclusion to long-term memory
        self.memory.add_memory(
            student_id=student_id, 
            context_summary=risk_report['summary_for_memory'],
            metadata={"status": risk_report['status'], "score": risk_report['risk_score']}
        )

        status = risk_report.get('status', 'NORMAL')
        results = {
            "analysis": risk_report,
            "actions": []
        }

        # 3. Level 2: Conditional Intervention Triage
        # --- PATH A: HIGH RISK (Counseling + Scholarship + Remedial) ---
        if status == "HIGH_RISK":
            # Financial Support
            finance_result = self.finance.provide_support(student_id, student_data, risk_report)
            results['actions'].append({"type": "finance", "data": finance_result})

            # Community Counseling Script
            mediator_result = self.mediator.generate_counseling_script(
                student_id, student_data, risk_report, language=counseling_lang
            )
            results['actions'].append({"type": "counseling", "data": mediator_result})

            # Academic Remedial Plan
            edu_result = self.educator.create_remedial_plan(student_id, student_data, risk_report)
            results['actions'].append({"type": "academic", "data": edu_result})

        # --- PATH B: WATCH STATUS (Remedial Only) ---
        elif status == "WATCH":
            edu_result = self.educator.create_remedial_plan(student_id, student_data, risk_report)
            results['actions'].append({"type": "academic", "data": edu_result})

        # --- PATH C: NORMAL (Monitor Only) ---
        else:
            results['message'] = "Student is currently on track. No immediate intervention required."

        return results