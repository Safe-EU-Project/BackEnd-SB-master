from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from src.assignment.schemas import (
    AssignmentForSubmissionRequest,
    AssignmentUpdateScoreRequest,
    CreateAssignmentRequest,
    FinishedAssignmentsInfoResponse,
    GetSpecificAssignmentRequest,
    ThreatAnalyticsResponse,
    ThreatDimensionStats,
)
from src.db.models import Assignment
from src.db.models import Scenario
from src.user.utils import user_retrieve_method

# from Backend.src.assignment.utils import evaluate_answer
from src.assignment.logger import logger
from functools import reduce
from beanie import UpdateResponse
from .utils import (
    evaluate_answer,
    grade_with_llm,
    get_assignment_trainer_id,
)


class AssignmentService:

    def __init__(self):
        pass

    async def create_assignment(
        self, create_assignment_data: CreateAssignmentRequest, user_identifier: str
    ) -> Assignment:
        user = await user_retrieve_method(user_identifier)
        exercise_incidents = []
        base_scenario = await Scenario.get(ObjectId(create_assignment_data.scenario_id))
        if base_scenario and user:
            # for every incident inside context:
            for incident in base_scenario.model_dump()["context"]:
                # for every expected action of a specific incident:
                for index, _ in enumerate(incident["expected_actions"]):
                    incident["expected_actions"][index] = "add your solution here ..."
                # add the incident to the exercise incidents:
                exercise_incidents.append(incident)
            # create assignment:
            current_assignment = Assignment(
                scenario=base_scenario,
                trainee=user,
                context_solution=exercise_incidents,
            )
            # insert the created scenario into db
            await current_assignment.insert()
            # return in order to be depicted at exersice panel
            # in order the trainee to start solve:
            return current_assignment

        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User or Scenario Not Found",
            )

    # we need this to be ***atomic operation***
    # handles lost update problem - difficult to occur
    # due to one trainer changes grades but ok.
    async def update_assignment_score(
        self, assignment_data: AssignmentUpdateScoreRequest, user_identifier: str
    ) -> Assignment:
        user = await user_retrieve_method(user_identifier)
        assignment_trainer_id = await get_assignment_trainer_id(
            assignment_id=assignment_data.id
        )
        if assignment_trainer_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Assignment Trainer Not Match the Trainer Performs the Request",
            )

        # do atomic read-write
        assignment = await Assignment.find_one(
            Assignment.id == assignment_data.id
        ).update(
            {
                "$set": {
                    "grade": assignment_data.grade,
                    "grade_per_incident": assignment_data.grade_per_incident,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            response_type=UpdateResponse.NEW_DOCUMENT,
        )
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment Not Found")
        return assignment

    # this is for a patch request:
    # the trainee at step 1, creates the exercise (look above)
    # -> then solves the exercise at the frontend and presses submit
    async def solve_assignment(
        self,
        assignment_data: AssignmentForSubmissionRequest,
        user_identifier: str,
    ) -> FinishedAssignmentsInfoResponse:
        scores = []
        # find the user:
        user = await user_retrieve_method(user_identifier)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # take the assignment of the student and check if is with status: assigned
        current_assignment = await Assignment.find_one(
            Assignment.id == ObjectId(assignment_data.id),
            Assignment.status == "assigned",
            fetch_links=True,
        )
        if not current_assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"There is no assignment with id: {assignment_data.id}",
            )

        if current_assignment.trainee.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to submit this assignment",
            )

        # update the in-memory object assignment:
        current_assignment.context_solution = assignment_data.context_solution
        # evaluate the assignment:
        scenario_title = current_assignment.scenario.scenario_name
        for index, incident in enumerate(current_assignment.context_solution):
            logger.debug(f"Grading incident: {incident.title}")
            original_incident = current_assignment.scenario.context[index]
            expected_actions = original_incident.expected_actions
            trainee_answer = incident.expected_actions[0] if incident.expected_actions else ""
            grade_result = await grade_with_llm(
                scenario_title=scenario_title,
                incident_title=incident.title,
                expected_actions=expected_actions,
                trainee_answer=trainee_answer,
            )
            scores.append({incident.title: grade_result})
        if not scores:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assignment has no incidents to grade",
            )
        # set it as completed:
        current_assignment.status = "completed"
        # calculate the total grade from LLM scores (each value is now a dict with "score" key):
        sum_score = sum(list(entry.values())[0]["score"] for entry in scores)
        current_assignment.grade = sum_score / len(scores)
        # add scores:
        current_assignment.grade_per_incident = scores
        # persist into the database:
        await current_assignment.save()
        # return:
        return FinishedAssignmentsInfoResponse(
            id=current_assignment.id,
            context_solution=current_assignment.context_solution,
            grade=current_assignment.grade,
            grade_per_incident=scores,
            scenario_name=current_assignment.scenario.scenario_name,
        )

    # trainee fetches all assignments
    # (it is for the my assignments table in react)
    async def fetch_trainee_assignments(
        self, user_identifier: str
    ) -> list[FinishedAssignmentsInfoResponse]:

        user = await user_retrieve_method(user_identifier)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        pipeline = [
            {"$match": {"trainee.$id": user.id, "status": "completed"}},
            {
                "$lookup": {
                    "from": "scenarios",
                    "localField": "scenario.$id",
                    "foreignField": "_id",
                    "as": "scenario_data",
                }
            },
            {"$unwind": "$scenario_data"},
            # {"$unwind": {"path": "$scenario_data", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "_id": 1,
                    "grade": 1,
                    "grade_per_incident": 1,
                    "context_solution": 1,
                    "scenario_name": "$scenario_data.scenario_name",
                }
            },
        ]

        assignments = await Assignment.aggregate(pipeline).to_list()

        return [
            FinishedAssignmentsInfoResponse(
                id=assignment["_id"],
                context_solution=assignment["context_solution"],
                grade=assignment["grade"],
                grade_per_incident=assignment["grade_per_incident"],
                scenario_name=assignment["scenario_name"],
            )
            for assignment in assignments
        ]

    """
    # here some analytics services will be added 
    # for the overall progess of the USER.
    """

    # analytics for all assignments
    async def calculate_average_analytics_per_user(
        self, user_identifier: str
    ) -> list[dict[str, Any]]:
        # find the current user
        user = await user_retrieve_method(user_identifier)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        # define a pipeline for aggregations:
        pipeline = [
            {
                "$match": {
                    "status": "completed",
                    "grade": {"$ne": None},
                }
            },
            {
                "$group": {
                    "_id": "$trainee.$id",
                    "average_grade": {"$avg": "$grade"},
                    "assignments_count": {"$sum": 1},
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "user",
                }
            },
            {"$unwind": "$user"},
            {
                "$project": {
                    "email": "$user.email",
                    "average_grade": 1,
                    "assignments_count": 1,
                    "_id": 1,
                }
            },
        ]

        results = await Assignment.aggregate(pipeline).to_list()
        for record in results:
            if record["_id"] == user.id:
                record.update({"me": True})
        return results

    async def calculate_analytics_for_specific_assignment(
        self,
        assignment_data: GetSpecificAssignmentRequest,
        user_identifier: str,
    ) -> list[dict[str, Any]]:
        user = await user_retrieve_method(user_identifier)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        current_assignment = await Assignment.get(
            ObjectId(assignment_data.assignment_id), fetch_links=True
        )
        if not current_assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No assignment with id {assignment_data.assignment_id}",
            )

        # Get Scenario of the assignment
        scenario_id = current_assignment.scenario.id  # ObjectId

        # in match, initially takes, all the assignments of the other users.
        # so not equal to user.id. Then will take the specific assignment and
        # add it to the list.
        pipeline = [
            {
                "$match": {
                    "status": "completed",
                    "grade": {"$ne": None},
                    "scenario.$id": scenario_id,
                    "trainee.$id": {"$ne": user.id},
                    # "trainee.$id": not equal user.id,
                }
            },
            # JOIN scenarios
            {
                "$lookup": {
                    "from": "scenarios",
                    "localField": "scenario.$id",
                    "foreignField": "_id",
                    "as": "scenario",
                }
            },
            {"$unwind": "$scenario"},
            # GROUP
            {
                "$group": {
                    "_id": "$trainee.$id",
                    "average_grade": {"$avg": "$grade"},
                    "assignments_count": {"$sum": 1},
                    "scenario_name": {"$first": "$scenario.scenario_name"},
                }
            },
            # JOIN users
            {
                "$lookup": {
                    "from": "users",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "user",
                }
            },
            {"$unwind": "$user"},
            # FINAL attributes
            {
                "$project": {
                    "_id": 0,
                    "email": "$user.email",
                    "scenario_name": 1,
                    "average_grade": 1,
                    # "assignments_count": 1,
                }
            },
        ]

        results = await Assignment.aggregate(pipeline).to_list()
        # add the current user analytics for this assignment:
        # this dont takes into account the other assignments
        # FOR THIS USER + THIS SCENARIO
        results.append(
            {
                "assignment_id": assignment_data.assignment_id,
                "scenario_name": current_assignment.scenario.scenario_name,
                "grade_of_this_attempt": current_assignment.grade,
                "email": user.email,
                "grade_per_incident": current_assignment.grade_per_incident,
                "me": True,
            }
        )
        return results

    # This service method fetches all assignments of a specific trainer
    # from his entire scenarios collections has created inside the DB.
    async def fetch_all_assignments_of_trainer(
        self, user_identifier: str
    ) -> list[dict[str, Any]]:

        user = await user_retrieve_method(user_identifier)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        pipeline = [
            {"$match": {"status": "completed"}},
            {
                "$lookup": {
                    "from": "scenarios",
                    "localField": "scenario.$id",
                    "foreignField": "_id",
                    "as": "scenario_data",
                }
            },
            {"$unwind": "$scenario_data"},
            {"$match": {"scenario_data.user.$id": user.id}},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "trainee.$id",
                    "foreignField": "_id",
                    "as": "trainee_data",
                }
            },
            {"$unwind": "$trainee_data"},
            {
                "$project": {
                    "_id": 1,
                    "status": 1,
                    "grade": 1,
                    "grade_per_incident": 1,
                    "context_solution": 1,
                    "scenario_name": "$scenario_data.scenario_name",
                    "trainee_email": "$trainee_data.email",
                }
            },
        ]

        results = await Assignment.aggregate(pipeline).to_list()
        return results

    async def analyze_threat_performance(self) -> ThreatAnalyticsResponse:
        """
        Aggregate grading results across all completed assignments grouped by the
        predictive-analysis metadata fields added in TASK 1:
        attack_technique, target_asset, vulnerability_class, estimated_impact.

        Handles both old (int score) and new (dict with score/level/...) grade formats.
        Returns empty dimension lists if no metadata is available yet (old scenarios).
        """
        assignments = await Assignment.find(
            Assignment.status == "completed",
            fetch_links=True,
        ).to_list()

        def _extract_score(grade_value) -> int | None:
            if isinstance(grade_value, dict):
                return grade_value.get("score")
            if isinstance(grade_value, (int, float)):
                return int(grade_value)
            return None

        def _extract_missed(grade_value) -> list[str]:
            if isinstance(grade_value, dict):
                return grade_value.get("missed_actions", [])
            return []

        def _extract_grading_method(grade_value) -> str:
            if isinstance(grade_value, dict):
                return grade_value.get("graded_by", "unknown")
            return "cosine_fallback"

        def _threat_likelihood(avg: float) -> str:
            if avg < 40:
                return "HIGH"
            if avg < 70:
                return "MEDIUM"
            return "LOW"

        # Accumulators: dim_name → value → [scores]
        dims: dict[str, dict[str, list[int]]] = {
            "attack_technique": defaultdict(list),
            "target_asset": defaultdict(list),
            "vulnerability_class": defaultdict(list),
            "estimated_impact": defaultdict(list),
        }
        missed_counter: dict[str, int] = defaultdict(int)
        grading_method_counter: dict[str, int] = defaultdict(int)
        total_incidents = 0
        metadata_populated = 0

        for assignment in assignments:
            if not assignment.grade_per_incident:
                continue
            scenario_context = getattr(assignment.scenario, "context", [])

            for idx, grade_entry in enumerate(assignment.grade_per_incident):
                if not isinstance(grade_entry, dict):
                    continue
                # grade_entry = {"incident_title": score_or_dict}
                incident_title, grade_value = next(iter(grade_entry.items()))
                score = _extract_score(grade_value)
                if score is None:
                    continue
                total_incidents += 1
                grading_method_counter[_extract_grading_method(grade_value)] += 1
                for action in _extract_missed(grade_value):
                    missed_counter[action.strip()] += 1

                # Match to scenario context by index
                if idx < len(scenario_context):
                    orig = scenario_context[idx]
                    for dim in dims:
                        val = getattr(orig, dim, None)
                        if val:
                            dims[dim][val].append(score)
                            metadata_populated += 1

        def _build_stats(dim_data: dict[str, list[int]]) -> list[ThreatDimensionStats]:
            result = []
            for val, scores in sorted(dim_data.items(), key=lambda x: sum(x[1]) / len(x[1])):
                avg = round(sum(scores) / len(scores), 1)
                result.append(ThreatDimensionStats(
                    value=val,
                    avg_score=avg,
                    incident_count=len(scores),
                    threat_likelihood=_threat_likelihood(avg),
                ))
            return result

        top_missed = sorted(missed_counter, key=missed_counter.get, reverse=True)[:10]

        note = None
        if total_incidents > 0 and metadata_populated == 0:
            note = (
                "No metadata available yet — analytics by threat type will populate "
                "once new scenarios (generated after TASK 1 upgrade) are used in assignments."
            )

        return ThreatAnalyticsResponse(
            total_assignments_analyzed=len(assignments),
            total_incidents_analyzed=total_incidents,
            by_attack_technique=_build_stats(dims["attack_technique"]),
            by_target_asset=_build_stats(dims["target_asset"]),
            by_vulnerability_class=_build_stats(dims["vulnerability_class"]),
            by_estimated_impact=_build_stats(dims["estimated_impact"]),
            top_missed_actions=top_missed,
            grading_method_breakdown=dict(grading_method_counter),
            note=note,
        )

    async def count_distinct_scenarios_for_trainee(
        self, user_identifier: str
    ) -> dict[str, int]:
        response = {}
        user = await user_retrieve_method(user_identifier)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        pipeline = [
            {
                "$match": {
                    "trainee.$id": user.id,
                    "status": "completed",
                }
            },
            {"$group": {"_id": "$scenario.$id"}},
            {"$count": "distinct_scenarios"},
        ]

        result = await Assignment.aggregate(pipeline).to_list()

        if not result:
            response.update({"solved_by_current_user": 0})
        else:
            response.update({"solved_by_current_user": result[0]["distinct_scenarios"]})

        total_scenarios = await Scenario.count()
        response.update({"total_scenarios": total_scenarios})

        return response
