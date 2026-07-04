"""Mocked HTTP tests for ClientLLM.get_llm_structured_scenario (no real LLM)."""

import asyncio
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# env before importing client_llm
os.environ.setdefault("LLM_BASE_URL", "http://fake-llm:9999")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import HTTPException

from src.scenario.client_llm import ClientLLM


class MockAsyncClientCtx:
    """Minimal async context manager for httpx.AsyncClient."""

    def __init__(self, response: MagicMock):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json=None):
        return self._response


def _ok_response():
    r = MagicMock()
    r.status_code = 200
    r.json = lambda: {
        "query": "q",
        "scenario": {
            "scenario_title": "Phishing drill",
            "incidents": [
                {
                    "title": "Alert",
                    "message_timestamp": "T+0 (09:00)",
                    "description": "SIEM.",
                    "inject": "log",
                    "expected_actions": ["Verify", "Notify"],
                }
            ],
        },
        "context": "",
        "sources": [],
        "metadata": {},
    }
    return r


class TestGetLlmStructuredScenario(unittest.TestCase):
    def test_returns_scenario_dict(self):
        async def run():
            resp = _ok_response()
            mock_ctx = MockAsyncClientCtx(resp)

            with patch("src.scenario.client_llm.httpx.AsyncClient", return_value=mock_ctx):
                out = await ClientLLM.get_llm_structured_scenario("make a scenario")

            self.assertEqual(out["scenario_title"], "Phishing drill")
            self.assertEqual(len(out["incidents"]), 1)
            self.assertEqual(out["incidents"][0]["title"], "Alert")

        asyncio.run(run())

    def test_missing_scenario_raises(self):
        async def run():
            r = MagicMock()
            r.status_code = 200
            r.json = lambda: {"query": "x"}
            mock_ctx = MockAsyncClientCtx(r)

            with patch("src.scenario.client_llm.httpx.AsyncClient", return_value=mock_ctx):
                with self.assertRaises(HTTPException) as ctx:
                    await ClientLLM.get_llm_structured_scenario("x")
            self.assertIn("missing", str(ctx.exception.detail).lower())

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
