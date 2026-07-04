from typing import List
from src.user.utils import PAYLOAD_KEY
from src.assignment.logger import logger
from src.assignment.schemas import (
    AssignmentForSolutionResponse,
    AssignmentUpdateScoreRequest,
    AssignmentOfTrainerResponse,
    AssignmentUpdateScoreResponse,
    AssignmentsByStatusResponse,
    CreateAssignmentRequest,
    GetAssignmentByStatusRequest,
    FinishedAssignmentsInfoResponse,
    AnalyticsPerUserResponse,
    GetSpecificAssignmentRequest,
    AssignmentForSubmissionRequest,
    ThreatAnalyticsResponse,
)
from src.assignment.service import AssignmentService
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from src.scenario.service import ScenarioService
from src.user.dependencies import get_current_user, get_user_role


# create assignment router:
assignment_router = APIRouter()

# inject services:
assignment_service = AssignmentService()
scenario_service = ScenarioService()


# trainee enters at frontend the scenatio id
# completes the excercise and enters the submit button
@assignment_router.post(
    "/trainee/create_assignment", response_model=AssignmentForSolutionResponse
)
async def trainee_create_assignment(
    create_assignment_data: CreateAssignmentRequest,
    user_token=Depends(get_current_user),
    _=Depends(get_user_role("trainee")),
):
    new_assignment = await assignment_service.create_assignment(
        create_assignment_data=create_assignment_data,
        user_identifier=user_token[PAYLOAD_KEY],
    )
    return new_assignment


# when the trainee solves the excercise
# will proceed to sumbition of the exercise using this route.
@assignment_router.post(
    "/trainee/solve", response_model=FinishedAssignmentsInfoResponse
)
async def trainee_solve_assignment(
    solution_data: AssignmentForSubmissionRequest,
    user_token=Depends(get_current_user),
    _=Depends(get_user_role("trainee")),
):
    assignment = await assignment_service.solve_assignment(
        assignment_data=solution_data, user_identifier=user_token[PAYLOAD_KEY]
    )
    return assignment


# trainer here takes all the sumbited or not (GIVEN AT PAYLOAD)
# sumbited assignments  of a specific scenario.
@assignment_router.post(
    "/trainer/scenario", response_model=List[AssignmentsByStatusResponse]
)
async def trainer_get_assignments_of_a_scenario(
    scenario_data: GetAssignmentByStatusRequest,
    user_token=Depends(get_current_user),
    _=Depends(get_user_role("trainer")),
):

    assignments = await scenario_service.get_all_assignments_of_a_scenario(
        scenario_data=scenario_data, user_identifier=user_token[PAYLOAD_KEY]
    )
    return assignments


# count distinct scenarios the trainee has solved vs total available
@assignment_router.get("/trainee/scenario/solved")
async def trainee_get_solved_scenario_number(
    user_token=Depends(get_current_user), _=Depends(get_user_role("trainee"))
):
    return await assignment_service.count_distinct_scenarios_for_trainee(
        user_identifier=user_token[PAYLOAD_KEY]
    )


# the trainee takes all the
# completed assignments has solved
@assignment_router.get(
    "/trainee/assignments", response_model=List[FinishedAssignmentsInfoResponse]
)
async def trainee_get_assignments(
    user_token=Depends(get_current_user), _=Depends(get_user_role("trainee"))
):

    trainee_assignments = await assignment_service.fetch_trainee_assignments(
        user_identifier=user_token[PAYLOAD_KEY]
    )
    return trainee_assignments


# overall scores of all users + current user
# "me" keyword at json response gives the current user.
@assignment_router.get(
    "/trainee/assignments/analytics", response_model=List[AnalyticsPerUserResponse]
)
async def trainee_get_assignments_analytics(
    user_token=Depends(get_current_user), _=Depends(get_user_role("trainee"))
):

    overall_analytics = await assignment_service.calculate_average_analytics_per_user(
        user_identifier=user_token[PAYLOAD_KEY]
    )
    return overall_analytics


# take analytics for a specific assignment
# for all users + current user
@assignment_router.post("/trainee/assignments/specific")
async def trainee_get_specific_assignment_analytics(
    assignment_data: GetSpecificAssignmentRequest,
    user_token=Depends(get_current_user),
    _=Depends(get_user_role("trainee")),
):

    specific_assignment_analytics = (
        await assignment_service.calculate_analytics_for_specific_assignment(
            assignment_data=assignment_data, user_identifier=user_token[PAYLOAD_KEY]
        )
    )
    return specific_assignment_analytics


@assignment_router.get(
    "/trainer/scenarios",
    response_model=List[AssignmentOfTrainerResponse],
)
async def get_assignments_of_trainer_scenarios(
    user_token=Depends(get_current_user), _=Depends(get_user_role("trainer"))
):
    overall_assignments = await assignment_service.fetch_all_assignments_of_trainer(
        user_identifier=user_token[PAYLOAD_KEY]
    )
    return overall_assignments


@assignment_router.get(
    "/analytics/threat",
    response_model=ThreatAnalyticsResponse,
)
async def get_threat_analytics(
    user_token=Depends(get_current_user),
):
    """
    Aggregate threat-performance analytics across all completed assignments.

    Groups grading results by:
    - attack_technique  (e.g. phishing, lateral movement)
    - target_asset      (e.g. email server, database)
    - vulnerability_class (e.g. misconfiguration, weak credentials)
    - estimated_impact  (e.g. data exfiltration, service disruption)

    Also returns top missed actions and grading method breakdown (LLM vs cosine fallback).
    threat_likelihood per dimension: HIGH (<40 avg), MEDIUM (40-70), LOW (>70).
    """
    return await assignment_service.analyze_threat_performance()


@assignment_router.put(
    "/trainer/rescore",
    response_model=AssignmentUpdateScoreResponse,
    # response_model_by_alias=False,
)
async def trainer_update_assignment_score(
    assignment_data: AssignmentUpdateScoreRequest,
    user_token=Depends(get_current_user),
    _=Depends(get_user_role("trainer")),
):
    updated_assignment = await assignment_service.update_assignment_score(
        assignment_data=assignment_data, user_identifier=user_token[PAYLOAD_KEY]
    )
    return updated_assignment
