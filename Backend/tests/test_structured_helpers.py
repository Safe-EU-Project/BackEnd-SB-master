"""Tests for structured scenario → feedback text (no async / no HTTP)."""

import unittest

from src.scenario.structured_helpers import structured_scenario_to_initial_llm_text


class TestStructuredScenarioToInitialLlmText(unittest.TestCase):
    def test_contains_feedback_keyword_and_phases(self):
        scenario_dict = {
            "scenario_title": "T",
            "incidents": [
                {
                    "title": "Step one",
                    "message_timestamp": "09:00",
                    "description": "Desc",
                    "inject": "Inj",
                    "expected_actions": ["Do A", "Do B"],
                }
            ],
        }
        text = structured_scenario_to_initial_llm_text(scenario_dict)
        self.assertIn("Expected Actions & Decision Points", text)
        self.assertIn("Phase 1", text)
        self.assertIn("Do A", text)
        self.assertIn("Inject: Inj", text)


if __name__ == "__main__":
    unittest.main()
