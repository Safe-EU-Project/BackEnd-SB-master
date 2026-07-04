from typing import List
from bson import ObjectId
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from src.user.utils import PAYLOAD_KEY
from src.scenario.logger import logger

from src.db.models import Scenario
from src.scenario.schemas import (
    ExploitPathProxyRequest,
    PolicyDraftResponse,
    ScenarioResponse,
    ScenarioWithStatsResponse,
    CreateScenarioRequest,
    UpdateScenarioIncidentRequest,
)
from src.user.dependencies import get_current_user, get_user_role
from .service import ScenarioService
from .client_llm import ClientLLM


scenario_router = APIRouter()
scenario_service = ScenarioService()


# TODO **must be guarded** with role admin - now free for DEV
@scenario_router.get("", response_model=List[ScenarioResponse])
async def get_all_scenario():
    all_scenarios = await scenario_service.get_all_scenario()
    return all_scenarios


# (order)
@scenario_router.get("/trainer", response_model=List[ScenarioResponse])
async def get_all_trainer_scenario(
    user_token=Depends(get_current_user), _=Depends(get_user_role("trainer"))
):
    # get all scenarios, trainer has created:
    all_scenario = await scenario_service.get_scenario_by_trainer(
        user_identifier=user_token[PAYLOAD_KEY]
    )
    return all_scenario


@scenario_router.get("/trainer/stats", response_model=List[ScenarioWithStatsResponse])
async def get_trainer_scenarios_with_stats(
    user_token=Depends(get_current_user),
):
    """
    Return all scenarios created by the authenticated user, enriched with
    total completed runs and unique trainee counts (excluding creator self-runs).
    No role guard — any authenticated user who created scenarios can view their stats.
    """
    return await scenario_service.get_scenarios_with_stats(
        user_identifier=user_token[PAYLOAD_KEY]
    )


# TODO **must be guarded** with role admin - now free for DEV
@scenario_router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(scenario_id: str):
    scenario = await scenario_service.get_scenario(scenario_id=scenario_id)
    return scenario


@scenario_router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(
    scenario_id: str,
    user_token=Depends(get_current_user),
    _=Depends(get_user_role("trainer")),
):
    await scenario_service.delete_scenario(
        scenario_id=scenario_id, user_identifier=user_token[PAYLOAD_KEY]
    )
    return None


@scenario_router.post("", response_model=ScenarioResponse)
async def trainer_create_scenario(
    create_scenario_data: CreateScenarioRequest,
    user_token=Depends(get_current_user),
    _=Depends(get_user_role("trainer")),
):
    # create a new scenario:
    scenario = await scenario_service.create_scenario(
        create_scenario_data, user_token[PAYLOAD_KEY]
    )
    return scenario


"""
**********************************************************
The bellow end point is used for the trainer to update the 
expected actions in case that an expected actions produced  
by the LLM is not so "appropriate" - **HUMAN IN THE LOOP**
***********************************************************
"""


@scenario_router.post("/{scenario_id}/policy_draft", response_model=PolicyDraftResponse)
async def generate_policy_draft(
    scenario_id: str,
    user_token=Depends(get_current_user),
):
    """
    Generate a formal operational policy document for a scenario.

    Aggregates all completed assignment performance data for the given scenario
    and sends it to the LLM service to produce an evidence-based (or threat-based
    if no assignments exist) policy draft for LEA review.
    """
    return await scenario_service.generate_policy_draft(
        scenario_id=scenario_id,
        user_identifier=user_token[PAYLOAD_KEY],
    )


@scenario_router.post("/{scenario_id}/exploit_path")
async def get_exploit_path(
    scenario_id: str,
    request: ExploitPathProxyRequest,
    user_token=Depends(get_current_user),
):
    """
    Analyze the full attack chain for a scenario.

    Forwards the structured scenario to the LLM service /exploit_path endpoint,
    which returns an AttackChain with per-incident exploit paths, MITRE ATT&CK
    techniques, containment windows, and detection indicators.

    Designed to feed the SAFE dashboard attack chain visualization.
    """
    return await ClientLLM.get_exploit_path(
        scenario_payload={"scenario": request.scenario, "use_rag": request.use_rag}
    )


@scenario_router.patch("/incidents/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario_incidents(
    scenario_id: str,
    update_data: UpdateScenarioIncidentRequest,
    user_token=Depends(get_current_user),
    _=Depends(get_user_role("trainer")),
):

    updated_scenario = await scenario_service.update_scenario_incidents(
        update_data, scenario_id, user_token[PAYLOAD_KEY]
    )
    return updated_scenario
