"""Append backward-compat aliases to scenario/schemas.py on the server."""
path = "/home/intrasoft/Documents/gandalf/BackEnd-SB/Backend/src/scenario/schemas.py"

with open(path) as f:
    content = f.read()

aliases = """

# ── Backward-compat aliases (routes.py still uses old names) ──────────────────
class UpdateScenarioModel(BaseModel):
    scenario_name: str

CreateScenarioModel = CreateScenarioRequest
UpdateScenarioIncidentsModel = UpdateScenarioIncidentRequest
"""

if "CreateScenarioModel" not in content:
    with open(path, "a") as f:
        f.write(aliases)
    print("Aliases added.")
else:
    print("Aliases already present.")
