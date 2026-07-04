"""
Minimal patch for the server's Backend/src files.
Adds:
  1. grade_with_llm() to assignment_utils.py
  2. LLM grading in solve_assignment + analyze_threat_performance() in service.py
  3. ThreatDimensionStats + ThreatAnalyticsResponse to schemas.py
  4. GET /assignment/analytics/threat route to routes.py
  5. 4 predictive fields to scenario/schemas.py Incident model
"""
import os, re

BASE = "/home/intrasoft/Documents/gandalf/BackEnd-SB/Backend/src"

# ─────────────────────────────────────────────────────────────────────────────
# 1. assignment_utils.py — add grade_with_llm
# ─────────────────────────────────────────────────────────────────────────────
utils_path = os.path.join(BASE, "assignment", "assignment_utils.py")
with open(utils_path) as f:
    utils_content = f.read()

if "grade_with_llm" not in utils_content:
    addition = '''

import httpx

async def grade_with_llm(
    scenario_title: str,
    incident_title: str,
    expected_actions: list,
    trainee_answer: str,
) -> dict:
    """LLM semantic grading with cosine-similarity fallback."""
    try:
        from src.scenario.config import get_LLM_settings
        llm_base_url = get_LLM_settings().LLM_BASE_URL
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{llm_base_url}/api/v1/grade_step",
                json={
                    "scenario_title": scenario_title,
                    "incident_title": incident_title,
                    "expected_actions": expected_actions,
                    "user_action": trainee_answer,
                },
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
        fallback = evaluate_answer(trainee_answer, expected_actions[0] if expected_actions else "")
        return {
            "score": fallback,
            "level": "partial" if fallback > 0 else "missing",
            "feedback": "",
            "matched_actions": [],
            "missed_actions": [],
            "graded_by": "cosine_fallback",
        }
'''
    with open(utils_path, "a") as f:
        f.write(addition)
    print("✓ grade_with_llm added to assignment_utils.py")
else:
    print("  grade_with_llm already present")

# ─────────────────────────────────────────────────────────────────────────────
# 2. schemas.py — add ThreatDimensionStats + ThreatAnalyticsResponse
# ─────────────────────────────────────────────────────────────────────────────
schemas_path = os.path.join(BASE, "assignment", "schemas.py")
with open(schemas_path) as f:
    schemas_content = f.read()

if "ThreatAnalyticsResponse" not in schemas_content:
    # Ensure Dict/List/Any are imported
    if "from typing import" in schemas_content:
        schemas_content = re.sub(
            r"from typing import ([^\n]+)",
            lambda m: "from typing import " + ", ".join(sorted(set(
                x.strip() for x in m.group(1).split(",")
            ) | {"Any", "Dict", "List", "Optional"})),
            schemas_content, count=1
        )
    else:
        schemas_content = "from typing import Any, Dict, List, Optional\n" + schemas_content

    schemas_content += '''

class ThreatDimensionStats(BaseModel):
    label: str
    avg_score: float
    incident_count: int
    top_missed_actions: list = []
    grading_method_breakdown: dict = {}


class ThreatAnalyticsResponse(BaseModel):
    by_attack_technique: list = []
    by_target_asset: list = []
    by_vulnerability_class: list = []
    by_estimated_impact: list = []
'''
    with open(schemas_path, "w") as f:
        f.write(schemas_content)
    print("✓ ThreatAnalyticsResponse added to schemas.py")
else:
    print("  ThreatAnalyticsResponse already present")

# ─────────────────────────────────────────────────────────────────────────────
# 3. service.py — add grade_with_llm call + analyze_threat_performance
# ─────────────────────────────────────────────────────────────────────────────
service_path = os.path.join(BASE, "assignment", "service.py")
with open(service_path) as f:
    service_content = f.read()

# 3a. Fix solve_assignment to use grade_with_llm
if "grade_with_llm" not in service_content:
    # Add import
    service_content = service_content.replace(
        "from src.assignment.assignment_utils import evaluate_answer",
        "from src.assignment.assignment_utils import evaluate_answer, grade_with_llm"
    )

    # Replace the evaluate_answer call inside solve_assignment
    old_grade = "scores.append({incident.title: evaluate_answer(trainee_answer, original_answer)})"
    new_grade = """grade_result = await grade_with_llm(
                scenario_title=current_assignment.scenario.scenario_name,
                incident_title=incident.title,
                expected_actions=[original_answer],
                trainee_answer=trainee_answer,
            )
            scores.append({incident.title: grade_result})"""
    service_content = service_content.replace(old_grade, new_grade)

    # Fix score summation to handle dict grades
    old_sum = "sum_score = reduce(lambda acc, x: sum(x.values()) + acc, scores, 0)"
    new_sum = """sum_score = sum(
            (list(e.values())[0]["score"] if isinstance(list(e.values())[0], dict)
             else list(e.values())[0])
            for e in scores
        )"""
    service_content = service_content.replace(old_sum, new_sum)

    # Add collections import if missing
    if "from collections import" not in service_content:
        service_content = "from collections import defaultdict\n" + service_content

    with open(service_path, "w") as f:
        f.write(service_content)
    print("✓ grade_with_llm wired into service.py")
else:
    print("  grade_with_llm already in service.py")

# 3b. Add analyze_threat_performance method
with open(service_path) as f:
    service_content = f.read()

if "analyze_threat_performance" not in service_content:
    analytics_method = '''
    async def analyze_threat_performance(self):
        """Aggregate grading results grouped by predictive analysis metadata fields."""
        from src.assignment.schemas import ThreatAnalyticsResponse, ThreatDimensionStats
        from src.db.models import Assignment

        assignments = await Assignment.find(
            Assignment.status == "completed", fetch_links=True
        ).to_list()

        def _score(v):
            return v.get("score") if isinstance(v, dict) else (int(v) if isinstance(v, (int, float)) else None)
        def _missed(v):
            return v.get("missed_actions", []) if isinstance(v, dict) else []
        def _method(v):
            return v.get("graded_by", "unknown") if isinstance(v, dict) else "cosine_legacy"

        dims = ["attack_technique", "target_asset", "vulnerability_class", "estimated_impact"]
        buckets = {d: defaultdict(lambda: {"scores": [], "missed": [], "methods": []}) for d in dims}

        for asgn in assignments:
            sc = asgn.scenario
            if not sc:
                continue
            grade_map = {}
            for entry in (asgn.grade_per_incident or []):
                for k, v in entry.items():
                    grade_map[k] = v
            for inc in (sc.context or []):
                gv = grade_map.get(inc.title)
                if gv is None:
                    continue
                s = _score(gv)
                if s is None:
                    continue
                for d in dims:
                    key = getattr(inc, d, None)
                    if key:
                        buckets[d][key]["scores"].append(s)
                        buckets[d][key]["missed"].extend(_missed(gv))
                        buckets[d][key]["methods"].append(_method(gv))

        def build(d):
            out = []
            for label, data in buckets[d].items():
                sc_list = data["scores"]
                if not sc_list:
                    continue
                mc = defaultdict(int)
                for m in data["missed"]:
                    mc[m] += 1
                meth = defaultdict(int)
                for m in data["methods"]:
                    meth[m] += 1
                out.append(ThreatDimensionStats(
                    label=label,
                    avg_score=round(sum(sc_list)/len(sc_list), 1),
                    incident_count=len(sc_list),
                    top_missed_actions=sorted(mc, key=mc.get, reverse=True)[:5],
                    grading_method_breakdown=dict(meth),
                ))
            return sorted(out, key=lambda x: x.avg_score)

        return ThreatAnalyticsResponse(
            by_attack_technique=build("attack_technique"),
            by_target_asset=build("target_asset"),
            by_vulnerability_class=build("vulnerability_class"),
            by_estimated_impact=build("estimated_impact"),
        )
'''
    # Insert before the last line of the class (find last method boundary)
    # Append at end of file
    with open(service_path, "a") as f:
        f.write(analytics_method)
    print("✓ analyze_threat_performance added to service.py")
else:
    print("  analyze_threat_performance already in service.py")

# ─────────────────────────────────────────────────────────────────────────────
# 4. routes.py — add GET /analytics/threat
# ─────────────────────────────────────────────────────────────────────────────
routes_path = os.path.join(BASE, "assignment", "routes.py")
with open(routes_path) as f:
    routes_content = f.read()

if "analytics/threat" not in routes_content:
    route_addition = '''

@assignment_router.get("/analytics/threat")
async def get_threat_analytics(
    user_token=Depends(get_current_user),
    _=Depends(get_user_role("trainer")),
):
    from src.assignment.schemas import ThreatAnalyticsResponse
    result = await assignment_service.analyze_threat_performance()
    return result
'''
    with open(routes_path, "a") as f:
        f.write(route_addition)
    print("✓ /analytics/threat route added to routes.py")
else:
    print("  /analytics/threat already present")

# ─────────────────────────────────────────────────────────────────────────────
# 5. scenario/schemas.py — add predictive fields to Incident
# ─────────────────────────────────────────────────────────────────────────────
sc_schemas = os.path.join(BASE, "scenario", "schemas.py")
with open(sc_schemas) as f:
    sc_content = f.read()

if "attack_technique" not in sc_content:
    sc_content = sc_content.replace(
        "    expected_actions: List[str] = Field(default_factory=list)",
        """    expected_actions: List[str] = Field(default_factory=list)
    # predictive analysis metadata
    attack_technique: Optional[str] = None
    target_asset: Optional[str] = None
    vulnerability_class: Optional[str] = None
    estimated_impact: Optional[str] = None"""
    )
    if "Optional" not in sc_content:
        sc_content = sc_content.replace(
            "from typing import List",
            "from typing import List, Optional"
        )
    with open(sc_schemas, "w") as f:
        f.write(sc_content)
    print("✓ Predictive fields added to scenario/schemas.py")
else:
    print("  Predictive fields already present")

print("\nAll patches applied.")
