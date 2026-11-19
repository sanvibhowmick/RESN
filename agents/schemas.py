"""agents/schemas.py
Pydantic V2 Schemas for Runtime Validation across all RESN Multi-Agent Systems.

Enforces deterministic types, schema validation, and guardrails on LLM responses,
preventing JSON parsing crashes, missing fields, or hallucinated types.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


# =====================================================================
# 1. RISK ANALYST SCHEMAS
# =====================================================================
class FeatureBreakdownItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    feature: str = Field(..., description="Name of the socio-demographic or academic feature")
    explanation: str = Field(..., description="Intuitive layman explanation of why this factor impacted the child's risk score")


class RiskAnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    risk_score: int = Field(..., ge=0, le=100, description="Final calculated risk score (0-100)")
    status: Literal["NORMAL", "WATCH", "DANGER"] = Field(..., description="Triage status based on ML score and social risks")
    primary_drivers: List[str] = Field(..., min_length=1, description="Primary risk drivers grounded in model weights and context")
    summary_for_memory: str = Field(..., description="1-sentence factual summary for episodic memory storage")
    xai_layman_explanation: str = Field(..., description="Compassionate layman terms explanation for teachers and parents")
    feature_breakdown_layman: List[FeatureBreakdownItem] = Field(default_factory=list, description="Itemized plain-language breakdown per factor")
    recommended_next_agent: Literal["FinancialAdvocate", "Educator", "CommunityMediator", "None"] = Field(
        default="None", description="Recommended next specialist in the triage hierarchy"
    )


# =====================================================================
# 2. FINANCIAL ADVOCATE SCHEMAS
# =====================================================================
class ScholarshipDecisionSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    selected_scheme: str = Field(..., description="Name of the selected government aid scheme")
    justification: str = Field(..., description="Why this scheme is the optimal match for the student's risk drivers")
    urgency: Literal["High", "Medium", "Low"] = Field(default="High", description="Application urgency based on family distress")
    estimated_benefit: Optional[str] = Field(default="Government Financial Aid", description="Brief description of the benefit amount or stipend")


# =====================================================================
# 3. EDUCATOR AGENT SCHEMAS
# =====================================================================
class RemedialActionCardSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subject: str = Field(..., description="Academic subject requiring pedagogical remediation")
    diagnosis_question: str = Field(..., description="1 targeted question for the teacher to locate the conceptual breakdown")
    real_world_analogy: str = Field(..., description="Relatable rural Indian metaphor (farming, village market, harvest) explaining the concept")
    five_minute_fix: str = Field(..., description="Actionable zero-cost 5-minute peer activity to restore student confidence")
    teacher_tips: Optional[str] = Field(default="Encourage student participation without public reprimand.", description="Classroom delivery tip")


# =====================================================================
# 4. COMMUNITY MEDIATOR AGENT SCHEMAS
# =====================================================================
class CounselingScriptSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    language: str = Field(..., description="Target dialect or language of the counseling session")
    talking_points: List[str] = Field(..., min_length=3, max_length=6, description="Direct-speech persuasive talking points for home visit")
    cultural_metaphor: str = Field(..., description="Rural cultural metaphor used to convince parents of the value of education")
    emotional_hook: str = Field(..., description="Emotional resonance point regarding the child's future support for parents")


# =====================================================================
# 5. ASYNC TASK TRACKING SCHEMAS
# =====================================================================
class TaskStatusSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task_id: str
    task_type: Literal["INTERVENTION", "PDF_GENERATION", "EMBEDDING_INDEXING", "BATCH_SCORING"]
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
