from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from src.scenario.schemas import Incident
from beanie import PydanticObjectId

""" here we will put the pydantic models - DTOs"""
###################################################


class CreateAssignmentRequest(BaseModel):
    scenario_id: str


class GetAssignmentByStatusRequest(BaseModel):
    scenario_id: str
    status: str


class GetSpecificAssignmentRequest(BaseModel):
    assignment_id: str


class AnalyticsPerUserResponse(BaseModel):
    email: str
    average_grade: float
    assignments_count: float
    me: bool = False


# ---------------------------------------------------------------


# ''' parent class '''
class AssignmentModel(BaseModel):
    id: PydanticObjectId
    context_solution: List[Incident]


# ''' children '''
class AssignmentForSolutionRequest(AssignmentModel):
    pass


class AssignmentForSolutionResponse(AssignmentModel):
    pass


class AssignmentForSubmissionRequest(AssignmentModel):
    pass


class AssignmentsByStatusResponse(AssignmentModel):
    pass


class FinishedAssignmentsInfoResponse(AssignmentModel):
    grade: float
    grade_per_incident: List[dict]
    scenario_name: str | None = None


# ----------------------------------------------------------------


# ''' parent class '''
class AssignmentForTrainer(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    # trainer_id: PydanticObjectId | None = None
    trainee_email: str | None = None
    scenario_name: str | None = None
    grade: float | None = None
    grade_per_incident: List[dict] = Field(default_factory=list)
    context_solution: List[Incident] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


# ''' children '''
class AssignmentOfTrainerResponse(AssignmentForTrainer):
    pass


# ----------------------------------------------------------------


# ''' parent class '''
class AssignmentForScoring(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    grade: float
    grade_per_incident: List[dict] = Field(default_factory=list)

    # some configs:
    model_config = ConfigDict(populate_by_name=True)


# ''' children '''
class AssignmentUpdateScoreRequest(AssignmentForScoring):
    """VALIDATORS"""

    @field_validator("grade")
    @classmethod
    def validate_grade(cls, v):
        if (v is not None) and (not (0 <= v <= 100)):
            raise ValueError("Grade must be between 0 and 100")
        return v

    @field_validator("grade_per_incident")
    @classmethod
    def validate_grade_per_incident(cls, incidents):
        for incident in incidents:
            ((incident_name, score),) = incident.items()
            if score is None or score == "":
                raise ValueError("score must be not None or empty string")
            if not (0 <= score <= 100):
                raise ValueError(
                    f"{incident_name} has no valid score - must be between 0 and 100"
                )
        return incidents

    @model_validator(mode="after")
    def validate_grade_matches_average(self):
        if not self.grade_per_incident or self.grade is None:
            return self
        scores = [list(inc.values())[0] for inc in self.grade_per_incident]
        average = sum(scores) / len(scores)
        if round(self.grade, 8) != round(average, 8):
            raise ValueError("Overall grade differs from the average of incidents")
        return self


class AssignmentUpdateScoreResponse(AssignmentForScoring):
    pass


# ---- Threat Analytics -------------------------------------------------------

class ThreatDimensionStats(BaseModel):
    """Performance statistics for one value of a metadata dimension."""
    value: str = Field(..., description="e.g. 'phishing', 'database server'")
    avg_score: float = Field(..., description="Average score 0-100 across all incidents with this value")
    incident_count: int = Field(..., description="Number of graded incidents with this value")
    threat_likelihood: str = Field(
        ..., description="HIGH (<40), MEDIUM (40-70), LOW (>70) — inverse of avg performance"
    )


class ThreatAnalyticsResponse(BaseModel):
    """Comprehensive threat-performance analytics across all completed assignments."""
    total_assignments_analyzed: int
    total_incidents_analyzed: int
    by_attack_technique: List[ThreatDimensionStats] = Field(default_factory=list)
    by_target_asset: List[ThreatDimensionStats] = Field(default_factory=list)
    by_vulnerability_class: List[ThreatDimensionStats] = Field(default_factory=list)
    by_estimated_impact: List[ThreatDimensionStats] = Field(default_factory=list)
    top_missed_actions: List[str] = Field(
        default_factory=list,
        description="Most frequently missed expected actions across all graded incidents",
    )
    grading_method_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of incidents graded by 'llm' vs 'cosine_fallback'",
    )
    note: Optional[str] = Field(
        None,
        description="Warning if metadata is sparse (e.g. old scenarios without attack_technique)",
    )
