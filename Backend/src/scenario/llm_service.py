"""
               **Here is the Logic of Scenario Creation**
1.Get Response from the LLM
2.Create Scenario and Load to Database
3.Parse updated scenario to be used for feedback loop (Vector Database)
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from src.db.models import Scenario, Incident, User
from src.scenario.client_llm import ClientLLM, _detect_sector
from src.scenario.logger import logger
from src.scenario.schemas import UpdateScenarioIncidentRequest


class LLMService:
    def __init__(self, user: User, scenario_name: str, prompt: str) -> None:
        self.user = user
        self.scenario_name = scenario_name
        self.prompt = prompt
        self.initial_llm_response = None
        # Auto-detect sector from scenario name + instructions for RAG filtering
        self.sector = _detect_sector(f"{scenario_name} {prompt}")
        logger.info(f"LLM Service has been created [sector={self.sector}] ...")

    def split_incidents_into_timestamps(self, incident_or_actions: str) -> list[str]:
        return re.split(r"T\+\d+(?:\s*min\s*)?", incident_or_actions)

    def split_actions_into_phases(self, incident_or_actions: str) -> list[str]:
        return re.split(r"Phase\s\d+", incident_or_actions)

    def split_initial_response(self, llm_response: str) -> tuple[list[str], list[str]]:
        # do transformations:
        llm_response = llm_response.replace("*", "")
        incidents_expected_actions = llm_response.split(
            "Expected Actions & Decision Points"
        )
        incidents, expected_actions = (
            incidents_expected_actions[0],
            incidents_expected_actions[1],
        )
        # split into timestamps:
        incidents = self.split_incidents_into_timestamps(incidents)
        # split into phases:
        expected_actions = self.split_actions_into_phases(expected_actions)
        # remove first parts of re.split
        _ = incidents.pop(0)
        expected_actions.pop(0)
        # return:
        return incidents, expected_actions

    # incidents are devide it to:
    # 1.timestamps
    # 2.description
    # 3.inject
    def handle_incidents(self, incidents: list[str]) -> list[dict[str, Any]]:
        timestamps_incidents_injects = []
        for incident in incidents:
            incident_inject = incident.split("Inject:")
            current_description, current_inject = (
                incident_inject[0].strip(),
                incident_inject[1].strip(),
            )
            hour, title, current_description_updated = (
                self.extract_hour_title_description_per_incident(current_description)
            )
            timestamps_incidents_injects.append(
                {
                    "message_timestamp": hour.strip(),
                    "title": title,
                    "description": current_description_updated,
                    "inject": current_inject,
                    "expected_actions": [],
                }
            )
        return timestamps_incidents_injects

    def extract_hour_title_description_per_incident(
        self, incident: str
    ) -> tuple[str, str, str]:
        # Accept en-dash (–), em-dash (—) or plain hyphen (-) as the separator,
        # since the LLM does not always produce the exact same dash character.
        pattern = re.compile(r"\s*\((\d{2}:\d{2})\)\s*[–—-]\s*(.+?)\s*$")
        # split by line:
        hour_title_description = re.split("\n+", incident)
        hour_title, description = (
            hour_title_description[0].strip(),
            hour_title_description[1].strip(),
        )
        match = pattern.match(hour_title)
        if match:
            time, title = match.groups()
        else:
            # Fallback: pull the HH:MM if present anywhere, use the rest of the
            # line (or a generic label) as title, so a single malformed header
            # from the LLM doesn't fail the whole scenario creation.
            logger.warning(
                f"Incident header did not match expected format, using fallback: {hour_title!r}"
            )
            time_match = re.search(r"(\d{2}:\d{2})", hour_title)
            time = time_match.group(1) if time_match else "00:00"
            title = re.sub(r"^\s*T\+\d+\s*", "", hour_title).strip(" :–—-") or "Untitled Incident"
        return time, title.strip(":"), description

    def extract_content_from_expected_actions(self, action: str) -> str:
        title_action = action.split("\n", 1)
        _, action = title_action[0], title_action[1]
        return (
            action.replace("Expected Actions:", "").replace("\n", "").strip().strip("-")
        )

    def handle_expected_actions(
        self,
        expected_actions: list[str],
    ) -> tuple[list[str], str | None, str | None]:
        actions = [
            self.extract_content_from_expected_actions(e) for e in expected_actions
        ]
        last_expected_action = actions.pop()
        filtered_expected_action = re.split(
            r"Optimal", last_expected_action, flags=re.IGNORECASE
        )[0]
        actions.append(filtered_expected_action)
        optimal, sub_optimal = None, None
        return actions, optimal, sub_optimal

    def concat_description_inject_action(
        self, incidents: list[dict[str, Any]], actions: list[str]
    ) -> list[dict[str, Any]]:
        try:
            for index, action in enumerate(actions):
                incident = incidents[index]
                incident["expected_actions"].append(action)
        except IndexError as e:
            logger.debug(f"Not equal sizes for incidents and actions:{e}")
            # return the subset, which is common
            return incidents
        return incidents

    async def concat_and_create_scenario(
        self,
        incidents_list: list[dict[str, Any]],
        optimal_suboptimal: dict[str, str | None],
    ) -> Scenario:
        # create the list of the incidents:
        context = [
            Incident(
                message_timestamp=ins["message_timestamp"],
                title=ins["title"],
                description=ins["description"],
                inject=ins["inject"],
                expected_actions=ins["expected_actions"],
            )
            for ins in incidents_list
        ]
        # create the scenario:
        s = Scenario(
            scenario_name=self.scenario_name,
            instructions=self.prompt,
            user=self.user,  # store link to User document
            context=context,
            initial_llm_response=self.initial_llm_response,
            optimal=optimal_suboptimal["optimal"],
            suboptimal=optimal_suboptimal["suboptimal"],
        )

        # insert the created scenario into db
        await s.insert()
        # return it for response:
        return s

    async def create_scenario(self) -> Scenario:
        self.initial_llm_response = await ClientLLM.get_llm_response(
            self.prompt, sector=self.sector
        )
        incidents, expected_actions = self.split_initial_response(
            self.initial_llm_response
        )

        timestamps_description_inject = self.handle_incidents(incidents)

        expected_actions_list, opt, sub_opt = self.handle_expected_actions(
            expected_actions
        )

        scenario_data = self.concat_description_inject_action(
            deepcopy(timestamps_description_inject), deepcopy(expected_actions_list)
        )

        created_scenario = await self.concat_and_create_scenario(
            incidents_list=scenario_data,
            optimal_suboptimal={"optimal": opt, "suboptimal": sub_opt},
        )

        return created_scenario

    @staticmethod
    async def reconstruct_llm_response_for_feedback(
        update_data: UpdateScenarioIncidentRequest, scenario_id: str
    ) -> str:
        # take the initial_text the LLM has send:
        initial_text = await Scenario.find_one(Scenario.id == ObjectId(scenario_id))
        if not initial_text:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario not found: {scenario_id}",
            )
        # take the incidents_part from the initial_text:
        initial_incident_part = initial_text.initial_llm_response.split(
            "Expected Actions & Decision Points"
        )[0]
        # take the incidents from the service response:
        actions = [
            f"Phase {index+1} - {incident.title}\n"
            + "Expected Actions: "
            + (
                " ".join(incident.expected_actions)
                if incident.expected_actions
                else "N/A"
            )
            + "\n"
            for index, incident in enumerate(update_data.context)
        ]

        reconstructed_actions = "Expected Actions & Decision Points" + "\n"
        for action in actions:
            reconstructed_actions += "\n" + action
        reconstructed = initial_incident_part + "\n" + reconstructed_actions

        # LOG for comparison:
        logger.info(f"initial text: \n {initial_text.initial_llm_response} + \n")
        logger.info(f"reconstructed text: \n {reconstructed} + \n")
        # return:
        return reconstructed
