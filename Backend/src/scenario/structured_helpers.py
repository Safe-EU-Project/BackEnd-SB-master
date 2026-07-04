"""Pure helpers for structured LLM scenario → stored text (no DB imports)."""


def structured_scenario_to_initial_llm_text(scenario_dict: dict) -> str:
    """Build initial_llm_response text from structured scenario for feedback loop."""
    incidents = scenario_dict.get("incidents", [])
    parts = []
    for inc in incidents:
        ts = inc.get("message_timestamp", "")
        title = inc.get("title", "")
        desc = inc.get("description", "")
        inject = inc.get("inject") or ""
        parts.append(f"T+0 ({ts}) – {title}\n{desc}\nInject: {inject}")
    timeline = "\n\n".join(parts)
    actions_lines = []
    for i, inc in enumerate(incidents, 1):
        acts = inc.get("expected_actions", [])
        act_text = acts[0] if acts else ""
        actions_lines.append(f"Phase {i} – {inc.get('title', '')}\nExpected Actions: {act_text}")
    actions_block = "Expected Actions & Decision Points\n\n" + "\n\n".join(actions_lines)
    return timeline + "\n\n" + actions_block
