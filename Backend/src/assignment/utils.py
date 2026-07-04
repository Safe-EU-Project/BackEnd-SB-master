import httpx
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from bson import ObjectId
from src.db.models import Assignment
from src.scenario.config import get_LLM_settings


def grade_from_similarity(similarity: float) -> int:
    MIN_SIM = 0.50  # below this = 0 points
    MAX_SIM = 0.85  # full credit
    score = (similarity - MIN_SIM) / (MAX_SIM - MIN_SIM)
    score = max(0.0, min(1.0, score))
    return round(score * 100)


def evaluate_answer(trainee_answer, original_answer):
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode([trainee_answer, original_answer])
    similarity_score = cosine_similarity([embeddings[0]], [embeddings[1]])
    return grade_from_similarity(similarity=similarity_score[0][0])


async def grade_with_llm(
    scenario_title: str,
    incident_title: str,
    expected_actions: list[str],
    trainee_answer: str,
) -> dict:
    """
    Call the LLM grade_step endpoint for semantic grading.
    Returns a dict with: score (0-100 int), level, feedback, matched_actions, missed_actions.
    Falls back to evaluate_answer() (cosine similarity) if the LLM service is unavailable.
    """
    try:
        llm_base_url = get_LLM_settings().LLM_BASE_URL
        payload = {
            "scenario_title": scenario_title,
            "incident_title": incident_title,
            "expected_actions": expected_actions,
            "user_action": trainee_answer,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{llm_base_url}/api/v1/grade_step",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "score": round(data["score"] * 100),
                "level": data.get("level", "partial"),
                "feedback": data.get("feedback", ""),
                "matched_actions": data.get("matched_actions", []),
                "missed_actions": data.get("missed_actions", []),
                "graded_by": "llm",
            }
    except Exception:
        fallback_score = evaluate_answer(trainee_answer, expected_actions[0] if expected_actions else "")
        return {
            "score": fallback_score,
            "level": "partial" if fallback_score > 0 else "missing",
            "feedback": "",
            "matched_actions": [],
            "missed_actions": [],
            "graded_by": "cosine_fallback",
        }


async def get_assignment_trainer_id(assignment_id: str):
    pipeline = [
        {
            "$match": {
                "status": "completed",
                "_id": ObjectId(f"{assignment_id}"),
            }
        },
        {
            "$lookup": {
                "from": "scenarios",
                "localField": "scenario.$id",
                "foreignField": "_id",
                "as": "scenario_data",
            }
        },
        {"$unwind": "$scenario_data"},
        {
            "$lookup": {
                "from": "users",
                "localField": "scenario_data.user.$id",
                "foreignField": "_id",
                "as": "trainee_data",
            }
        },
        {"$unwind": "$trainee_data"},
        {
            "$project": {
                "trainer_email": "$trainee_data.email",
                "trainer_id": "$trainee_data._id",
            }
        },
    ]
    assignment = await Assignment.aggregate(pipeline).to_list()
    return assignment[0].get("trainer_id", "") if assignment else ""


if __name__ == "__main__":
    print(evaluate_answer("i will buy a car", "a car will be purchased by me"))
