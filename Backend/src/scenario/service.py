from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from src.db.models import Assignment, Scenario, Incident, User
from src.scenario.schemas import (
    CreateScenarioRequest,
    UpdateScenarioIncidentRequest,
)
from src.assignment.schemas import GetAssignmentByStatusRequest
from src.scenario.logger import logger
from src.scenario.client_llm import ClientLLM, _detect_sector
from src.scenario.llm_service import LLMService
from src.user.utils import user_retrieve_method


class ScenarioService:

    def __init__(self):
        logger.info("Scenario Service has been created ...")

    # admin (THIS IS FOR DEBUG NOW - LATER INTO PRODUCTION - ROUTER MUST BE GUARDED WITH ROLE:ADMIN)
    async def get_all_scenario(self) -> list[Scenario]:
        scenario = Scenario.find(fetch_links=True)
        scenarioODB = await scenario.to_list()
        return scenarioODB

    # admin: (THIS IS FOR DEBUG NOW - LATER INTO PRODUCTION - ROUTER MUST BE GUARDED WITH ROLE:ADMIN)
    async def get_scenario(self, scenario_id: str) -> Scenario:
        scenario = await Scenario.find_one(
            Scenario.id == ObjectId(scenario_id), fetch_links=True
        )
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario Not Found",
            )
        return scenario

    # This is for Trainer in order to
    # perform feedback at AI generated incidents
    async def update_scenario_incidents(
        self,
        update_data: UpdateScenarioIncidentRequest,
        scenario_id: str,
        user_identifier: str,
    ) -> dict[str, Any]:
        user = await user_retrieve_method(user_identifier)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        scenario_to_update = await Scenario.find_one(
            Scenario.id == ObjectId(scenario_id)
        )
        if not scenario_to_update:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Scenario Not Found"
            )
        # check if the correct trainer updates:
        if scenario_to_update.user.ref.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to update this scenario",
            )
        # is partial update, not replacement
        # so before update event is not triggered
        # do we add here the "updated at"
        await scenario_to_update.set(
            {
                Scenario.context: update_data.context,
                Scenario.updated_at: datetime.now(timezone.utc),
            }
        )
        # reconstruct the text for LLM:
        ###############################
        reconstructed_text = await LLMService.reconstruct_llm_response_for_feedback(
            update_data=update_data, scenario_id=scenario_id
        )
        # send back to LLM (pass sector detected from the reconstructed text):
        llm_service_feedback_data = (
            await ClientLLM.send_back_scenario_for_feedback_loop(
                reconstructed_text,
                sector=_detect_sector(reconstructed_text),
            )
        )
        # logger.info(llm_service_feedback_data)
        ###############################
        scenario_to_update = scenario_to_update.model_dump()
        scenario_to_update["user"] = str(scenario_to_update["user"].ref.id)
        scenario_to_update["_id"] = scenario_to_update.pop("id")
        return scenario_to_update

    async def delete_scenario(self, scenario_id: str, user_identifier: str) -> None:
        user = await user_retrieve_method(user_identifier)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        scenario_to_delete = await Scenario.find_one(
            Scenario.id == ObjectId(scenario_id)
        )
        if not scenario_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scenario Not Found",
            )
        # just do ref --> no need fetch Link:
        if scenario_to_delete.user.ref.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to delete this scenario",
            )
        await scenario_to_delete.delete()
        return

    # fetches all the scenarios a trainer has created
    async def get_scenario_by_trainer(self, user_identifier: str) -> list[Scenario]:
        user = await user_retrieve_method(user_identifier)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User Not Found",
            )
        # Performs Eager Fetch (N+1 ALERT), if you DO NOT want
        # remove fetch link and change the Response
        # Model from the Route
        return await Scenario.find(
            Scenario.user.id == user.id, fetch_links=True
        ).to_list()

    async def get_scenarios_with_stats(self, user_identifier: str) -> list[dict]:
        """
        Return trainer's scenarios enriched with run/trainee counts.

        Uses a single MongoDB aggregation pipeline instead of N+1 queries:
        - total_runs: completed assignments by trainees OTHER than the creator
        - unique_trainees: distinct trainee IDs in those completed assignments
        """
        user = await user_retrieve_method(user_identifier)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")

        pipeline = [
            # 1. Start from scenarios owned by this trainer
            {"$match": {"user.$id": user.id}},

            # 2. Join completed assignments for each scenario
            {
                "$lookup": {
                    "from": "assignment",
                    "let": {"scenario_id": "$_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$scenario.$id", "$$scenario_id"]},
                                        {"$eq": ["$status", "completed"]},
                                        # Exclude trainer self-runs
                                        {"$ne": ["$trainee.$id", user.id]},
                                    ]
                                }
                            }
                        },
                        {"$project": {"trainee.$id": 1}},
                    ],
                    "as": "trainee_assignments",
                }
            },

            # 3. Compute stats
            {
                "$addFields": {
                    "total_runs": {"$size": "$trainee_assignments"},
                    "unique_trainees": {
                        "$size": {
                            "$setUnion": [
                                {
                                    "$map": {
                                        "input": "$trainee_assignments",
                                        "as": "a",
                                        "in": "$$a.trainee.$id",
                                    }
                                }
                            ]
                        }
                    },
                    "context_length": {"$size": "$context"},
                }
            },

            # 4. Project only what the frontend needs
            {
                "$project": {
                    "_id": 1,
                    "scenario_name": 1,
                    "context_length": 1,
                    "total_runs": 1,
                    "unique_trainees": 1,
                    "created_at": 1,
                }
            },
            {"$sort": {"created_at": -1}},
        ]

        return await Scenario.aggregate(pipeline).to_list()

    # only trainer can create a scenario
    # guard the route with "trainer" role
    async def create_scenario(
        self, create_scenario_data: CreateScenarioRequest, user_identifier: str
    ) -> Scenario:
        logger.info("Create Scenario Request ...")
        user = await user_retrieve_method(user_identifier)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"User Not Found"
            )
        llm_service = LLMService(
            user=user,
            scenario_name=create_scenario_data.scenario_name,
            prompt=create_scenario_data.instructions,
        )
        try:
            created_scenario = await llm_service.create_scenario()
        except Exception as e:
            logger.error(f"Scenario creation failed: {e}")
            raise
        return created_scenario

    async def generate_policy_draft(
        self, scenario_id: str, user_identifier: str
    ) -> dict[str, Any]:
        """
        Aggregate simulation performance data for a scenario, then call the LLM
        service to generate a formal operational policy draft.

        - If completed assignments exist, produces an evidence-based draft using
          real trainee performance gaps.
        - If no assignments have been run yet, produces a threat-based draft from
          the scenario description alone.
        """
        user = await user_retrieve_method(user_identifier)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        scenario = await Scenario.find_one(
            Scenario.id == ObjectId(scenario_id),
            fetch_links=True,
        )
        if not scenario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

        # ── Aggregate assignment performance data ──────────────────────────────
        # Exclude runs by the scenario's creator (trainer self-tests) so only
        # genuine trainee performance shapes the policy draft.
        creator_id = scenario.user.id  # available because fetch_links=True
        assignments = await Assignment.find(
            Assignment.scenario.id == scenario.id,
            Assignment.status == "completed",
            Assignment.trainee.id != creator_id,
        ).to_list()

        simulations_count = len(assignments)
        grades = [a.grade for a in assignments if a.grade is not None]
        average_grade = round(sum(grades) / len(grades), 1) if grades else None

        incident_scores: dict[str, list[float]] = defaultdict(list)
        missed_counter: dict[str, int] = defaultdict(int)

        for assignment in assignments:
            if not assignment.grade_per_incident:
                continue
            for entry in assignment.grade_per_incident:
                if not isinstance(entry, dict):
                    continue
                incident_title, grade_value = next(iter(entry.items()))
                score = (
                    grade_value.get("score")
                    if isinstance(grade_value, dict)
                    else grade_value
                )
                if isinstance(score, (int, float)):
                    incident_scores[incident_title].append(float(score))
                if isinstance(grade_value, dict):
                    for action in grade_value.get("missed_actions", []):
                        missed_counter[action.strip()] += 1

        grade_per_incident = [
            {title: round(sum(scores) / len(scores), 1)}
            for title, scores in incident_scores.items()
        ]
        top_missed = sorted(missed_counter, key=missed_counter.get, reverse=True)[:10]

        # ── Build LLM payload ─────────────────────────────────────────────────
        scenario_payload = {
            "scenario_title": scenario.scenario_name,
            "incidents": [
                {
                    "title": inc.title,
                    "message_timestamp": inc.message_timestamp,
                    "description": inc.description,
                    "expected_actions": inc.expected_actions,
                }
                for inc in scenario.context
            ],
        }

        llm_payload: dict[str, Any] = {"scenario": scenario_payload}

        if simulations_count > 0:
            llm_payload["performance_data"] = {
                "simulations_count": simulations_count,
                "average_grade": average_grade,
                "top_missed_actions": top_missed,
                "grade_per_incident": grade_per_incident,
            }

        logger.info(
            f"Requesting policy draft: scenario={scenario.scenario_name}, "
            f"simulations={simulations_count}, evidence_based={simulations_count > 0}"
        )

        return await ClientLLM.get_policy_draft(llm_payload)

    # here the trainer can fetch all the (completed) assignments
    # of a specific scenario, in order later to
    # grade the assignment.
    async def get_all_assignments_of_a_scenario(
        self, scenario_data: GetAssignmentByStatusRequest, user_identifier: str
    ) -> list[Assignment]:
        logger.info("Get all Assignments of a scenario ...")
        scenario_id, assignment_status = scenario_data.scenario_id, scenario_data.status
        user = await user_retrieve_method(user_identifier)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"User Not Found"
            )

        # get sure that the token corresponds to the correct trainer:
        scenario = await Scenario.find_one(
            Scenario.id == ObjectId(scenario_id),
            Scenario.user.id == user.id,
            fetch_links=True,
        )

        if scenario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario Not Found"
            )

        corresponding_assignments = await Assignment.find(
            Assignment.scenario.id == scenario.id,
            Assignment.status == assignment_status,
        ).to_list()
        return corresponding_assignments
