from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator, validator


class Incident(BaseModel):
    # incident title:
    title: str
    # hour of the incident
    # is not timestamp
    # is hour of the day, as LLM generates response (e.g 8:05)
    message_timestamp: str
    description: str
    inject: str | None = None
    # expected actions:
    expected_actions: List[str] = Field(default_factory=list)
    # predictive analysis metadata — populated by LLM during scenario generation
    attack_technique: Optional[str] = None
    target_asset: Optional[str] = None
    vulnerability_class: Optional[str] = None
    estimated_impact: Optional[str] = None


class ExploitPathProxyRequest(BaseModel):
    """
    Proxy request sent to the backend /scenario/{id}/exploit_path endpoint.
    The backend forwards this to the LLM service /api/v1/exploit_path.
    """
    scenario: dict = Field(..., description="Full structured Scenario dict (from /query_structured)")
    use_rag: bool = Field(True, description="Calibrate against RAG knowledge base")


class CreateScenarioRequest(BaseModel):
    scenario_name: str
    instructions: str


class UpdateScenarioIncidentRequest(BaseModel):
    context: List[Incident]


class PolicyDraftResponse(BaseModel):
    """Response schema for the policy draft generation endpoint — mirrors the full LLM service output."""

    document_title: str
    classification: str
    generated_at: str
    scenario_name: str
    draft_type: str
    simulations_used: int = 0
    # Sections 1-3
    management_commitment: str = ""
    purpose_and_scope: str = ""
    incident_classification: str = ""
    # Section 4 — Threat Assessment
    executive_summary: str = ""
    identified_risks: List[dict] = Field(default_factory=list)
    # Section 5 — Response Procedures
    detection_procedures: List[str] = Field(default_factory=list)
    containment_procedures: List[str] = Field(default_factory=list)
    evidence_preservation_steps: List[str] = Field(default_factory=list)
    escalation_chain: List[dict] = Field(default_factory=list)
    external_reporting_obligations: List[dict] = Field(default_factory=list)
    # Section 6 — Controls
    preventive_controls: List[str] = Field(default_factory=list)
    administrative_controls: List[str] = Field(default_factory=list)
    # Section 7 — Roles
    roles_and_responsibilities: List[dict] = Field(default_factory=list)
    # Policy Recommendations + Section 8 + Section 9
    policy_recommendations: List[dict] = Field(default_factory=list)
    resource_requirements: List[str] = Field(default_factory=list)
    review_cycle: List[str] = Field(default_factory=list)
    # Metadata
    used_fallback: bool = False
    validation_warnings: List[str] = Field(default_factory=list)


class ScenarioWithStatsResponse(BaseModel):
    """Scenario with aggregated run/trainee counts — used by the trainer dashboard."""

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: str = Field(alias="_id")
    scenario_name: str
    context_length: int = Field(0, description="Number of incidents in this scenario")
    total_runs: int = Field(0, description="Total completed runs by trainees (excluding creator)")
    unique_trainees: int = Field(0, description="Number of distinct trainees who completed this scenario")
    created_at: datetime | None = None

    @field_validator("id", mode="before")
    @classmethod
    def cast_objectid(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: str = Field(alias="_id")
    user: str = Field(alias="user_object_id")
    scenario_name: str
    instructions: str
    context: List[Incident]
    initial_llm_response: str | None = None
    # add timestamps:
    created_at: datetime | None = None
    updated_at: datetime | None = None

    """
    some validations:
    """

    @field_validator("id", mode="before")
    @classmethod
    def cast_objectid(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v

    @field_validator("user", mode="before")
    @classmethod
    def cast_user_id(cls, v):
        from src.db.models import User

        if isinstance(v, User):
            return str(v.id)
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, dict):
            return str(v["_id"])
        return v
