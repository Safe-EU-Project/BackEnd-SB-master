# Run local tests for structured scenario flow (no Mongo, no real LLM).
# Usage: from Backend folder:  .\scripts\run-structured-tests.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
$env:PYTHONPATH = "."
if (-not $env:LLM_BASE_URL) { $env:LLM_BASE_URL = "http://fake-llm:9999" }

python -m unittest tests.test_structured_helpers tests.test_client_llm_structured -v
