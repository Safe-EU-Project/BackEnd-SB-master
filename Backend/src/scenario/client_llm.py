from fastapi import HTTPException, status

from src.scenario.config import get_LLM_settings
from src.scenario.logger import logger
import httpx


env_llm = get_LLM_settings()


# ---------------------------------------------------------------------------
# Lightweight sector detection (mirrors LLM service detect_sector logic)
# ---------------------------------------------------------------------------
_SECTOR_KEYWORDS: dict[str, list[str]] = {
    "banking": [
        "bank", "swift", "payment", "financial", "fraud", "atm", "wire transfer",
        "money laundering", "credit card", "fintech", "transaction", "iban",
    ],
    "energy": [
        "energy", "power grid", "electricity", "scada", "ics", "oil", "gas",
        "pipeline", "utilities", "water treatment", "critical infrastructure",
    ],
    "health": [
        "hospital", "healthcare", "medical", "patient", "ehr", "pacs",
        "pharmacy", "clinical", "health record", "diagnostic",
    ],
    "telecom": [
        "telecom", "telco", "5g", "network operator", "isp", "sim", "ss7",
        "roaming", "voip", "mobile network",
    ],
    "lea": [
        "law enforcement", "police", "cert", "csirt", "nca", "interpol",
        "europol", "ministry of interior", "government agency",
    ],
}


def _detect_sector(text: str) -> str:
    """Detect domain sector from scenario name / instructions."""
    t = text.lower()
    scores = {s: sum(1 for kw in kws if kw in t) for s, kws in _SECTOR_KEYWORDS.items()}
    best = max(scores, key=lambda s: scores[s])
    return best if scores[best] > 0 else "general"


# here we add some custom exceptions
class LLMKeywordException(Exception):
    def __init__(self, detail: str, status_code: int):
        self.detail = detail
        self.status_code = status_code
        super().__init__(self.detail)


# client LLM class
class ClientLLM:

    def __init__(self):
        pass

    @staticmethod
    def validate(llm_message, instructions):
        if "Expected Actions & Decision Points" not in llm_message:
            raise LLMKeywordException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="LLM response does not contain the keyword - Expected Actions & Decision Points",
            )

    @staticmethod
    async def get_llm_response(instructions, max_retries=5, sector: str = None):
        initial_instructions = instructions
        resolved_sector = sector or _detect_sector(instructions)
        logger.info(
            f"Scenario Service Sends Request at LLM Service to get a new scenario "
            f"[sector={resolved_sector}] ..."
        )
        BASE_URL = env_llm.LLM_BASE_URL
        QUERY_ENDPOINT = f"{BASE_URL}/api/v1/query"

        async with httpx.AsyncClient(timeout=120.0) as client:
            for attempt in range(max_retries):

                query_data = {
                    "query": instructions,
                    "top_k": 20,
                    "use_reranking": True,
                    "use_hybrid": False,
                    "sector": resolved_sector,
                }

                try:
                    response = await client.post(QUERY_ENDPOINT, json=query_data)

                    if response.status_code == 200:
                        result = response.json()
                        answer = result["answer"]

                        # do the keyword validation
                        ClientLLM.validate(answer, instructions)

                        logger.info(f"Response: {response.status_code} - {answer}\n")
                        logger.info(
                            "---------------------------------------------------------"
                        )
                        return answer
                    else:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries}: HTTP {response.status_code}"
                        )

                # catch the custom exception:
                except LLMKeywordException as e:
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries}: Validation failed - {e.detail}"
                    )

                    # for the last 2 attempts give a hint
                    # to enforce the LLM to add the keyword
                    if attempt >= max_retries - 2:
                        instructions = (
                            initial_instructions
                            + " - comment: dont forget add to your reply the keyword: 'Expected Actions & Decision Points'"
                        )

                    # if it was the last attempt raise an error:
                    if attempt == max_retries - 1:
                        raise

                    continue

                except httpx.RequestError as e:
                    logger.error(
                        f"Attempt {attempt + 1}/{max_retries}: Request failed - {str(e)}"
                    )
                    if attempt == max_retries - 1:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"LLM service unavailable after {max_retries} attempts",
                        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"LLM response validation failed after {max_retries} attempts",
        )

    @staticmethod
    async def get_policy_draft(payload: dict) -> dict:
        """Call the LLM service's /api/v1/policy_draft endpoint."""
        BASE_URL = env_llm.LLM_BASE_URL
        ENDPOINT = f"{BASE_URL}/api/v1/policy_draft"
        logger.info("Scenario Service requests policy draft from LLM service...")

        async with httpx.AsyncClient(timeout=180.0) as client:
            try:
                response = await client.post(ENDPOINT, json=payload)
            except httpx.RequestError as e:
                logger.error(f"Policy draft request failed: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="LLM policy draft service unavailable",
                )

        if response.status_code == 200:
            logger.info("Policy draft received from LLM service")
            return response.json()

        logger.error(
            f"Policy draft LLM error: HTTP {response.status_code} - {response.text[:200]}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM policy_draft returned {response.status_code}",
        )

    @staticmethod
    async def get_exploit_path(scenario_payload: dict) -> dict:
        """
        Call the LLM service /api/v1/exploit_path endpoint.

        Sends the full scenario and returns a structured AttackChain with
        per-incident exploit paths, MITRE ATT&CK techniques, and containment windows.

        Args:
            scenario_payload: Dict with key "scenario" containing the full Scenario dict.

        Returns:
            ExploitPathResponse dict from the LLM service.
        """
        BASE_URL = env_llm.LLM_BASE_URL
        ENDPOINT = f"{BASE_URL}/api/v1/exploit_path"
        logger.info("Scenario Service requests exploit path analysis from LLM service...")

        async with httpx.AsyncClient(timeout=240.0) as client:
            try:
                response = await client.post(ENDPOINT, json=scenario_payload)
            except httpx.RequestError as e:
                logger.error(f"Exploit path request failed: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="LLM exploit path service unavailable",
                )

        if response.status_code == 200:
            logger.info("Exploit path analysis received from LLM service")
            return response.json()

        logger.error(
            f"Exploit path LLM error: HTTP {response.status_code} - {response.text[:200]}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM exploit_path returned {response.status_code}",
        )

    @staticmethod
    async def send_back_scenario_for_feedback_loop(
        fixed_scenario: str, sector: str = None
    ):
        BASE_URL = env_llm.LLM_BASE_URL
        INGEST_ENDPOINT = f"{BASE_URL}/api/v1/ingest_scenario"
        resolved_sector = sector or _detect_sector(fixed_scenario)
        ingest_data = {"content": fixed_scenario, "sector": resolved_sector}

        logger.info("Sending scenario to ingestion endpoint...")
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(INGEST_ENDPOINT, json=ingest_data)
            except httpx.RequestError as e:
                logger.error(f"Ingestion request failed: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="LLM ingestion service unavailable",
                )

        if response.status_code == 200:
            logger.info("Scenario ingestion succeeded")
            return response.json()

        logger.error(f"Ingestion failed: HTTP {response.status_code} - {response.text}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM ingestion service returned {response.status_code}",
        )
