"""
Offline tests for orchestrator.py.

Fully mocks GeminiClient, dispatch_tool, and generate_report, so these
tests verify the orchestration LOGIC (decision loop, failure handling,
termination) without any real network calls or API key.

Run directly: python test_orchestrator_offline.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import patch, MagicMock

from apps.backend.agent import orchestrator as orch_module


def fake_model_content():
    """A lightweight stand-in for a real google.genai Content object --
    orchestrator only ever appends this to a list, never inspects it,
    so any placeholder object is fine for these tests."""
    return object()


class TestOrchestratorOffline(unittest.TestCase):

    @patch("os.path.exists", return_value=True)
    @patch("apps.backend.agent.orchestrator.EVIDENCE_TOOLS", set())
    @patch("apps.backend.agent.orchestrator.generate_report")
    @patch("apps.backend.agent.orchestrator.dispatch_tool")
    @patch("apps.backend.agent.orchestrator.GeminiClient")
    def test_happy_path_single_tool_then_report(
        self, MockGeminiClient, mock_dispatch_tool, mock_generate_report, mock_exists
    ):
        """One successful tool call, then Gemini calls generate_report -- should complete cleanly."""
        mock_client_instance = MagicMock()
        mock_client_instance.generate.side_effect = [
            {
                "type": "tool_call",
                "tool_name": "dns_lookup",
                "tool_args": {"target": "example.com"},
                "model_content": fake_model_content(),
            },
            {
                "type": "tool_call",
                "tool_name": "calculate_cvss",
                "tool_args": {"findings": []},
                "model_content": fake_model_content(),
            },
            {
                "type": "tool_call",
                "tool_name": "generate_report",
                "tool_args": {
                    "target": "example.com",
                    "findings": [{"worker": "dns_lookup", "summary": "Found A record"}],
                    "cvss_scores": [],
                },
                "model_content": fake_model_content(),
            },
        ]
        MockGeminiClient.return_value = mock_client_instance
        mock_dispatch_tool.return_value = {"A": ["1.2.3.4"]}
        mock_generate_report.return_value = {"pdf_path": "reports/x.pdf", "json_path": "reports/x.json"}

        result = orch_module.run_scan("example.com")

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["report"], {"pdf_path": "reports/x.pdf", "json_path": "reports/x.json"})
        self.assertEqual(result["iterations"], 3)
        self.assertEqual(mock_dispatch_tool.call_count, 2)
        mock_generate_report.assert_called_once()

    @patch("os.path.exists", return_value=True)
    @patch("apps.backend.agent.orchestrator.EVIDENCE_TOOLS", set())
    @patch("apps.backend.agent.orchestrator.generate_report")
    @patch("apps.backend.agent.orchestrator.dispatch_tool")
    @patch("apps.backend.agent.orchestrator.GeminiClient")
    def test_critical_tool_failure_triggers_stop_nudge(
        self, MockGeminiClient, mock_dispatch_tool, mock_generate_report, mock_exists
    ):
        """dns_lookup (a CRITICAL tool) failing twice should append a nudge telling Gemini to stop and report."""
        mock_client_instance = MagicMock()
        mock_client_instance.generate.side_effect = [
            {"type": "tool_call", "tool_name": "dns_lookup", "tool_args": {"target": "bad.com"}, "model_content": fake_model_content()},
            {"type": "tool_call", "tool_name": "dns_lookup", "tool_args": {"target": "bad.com"}, "model_content": fake_model_content()},
            {
                "type": "tool_call",
                "tool_name": "calculate_cvss",
                "tool_args": {"findings": []},
                "model_content": fake_model_content(),
            },
            {
                "type": "tool_call",
                "tool_name": "generate_report",
                "tool_args": {"target": "bad.com", "findings": [], "cvss_scores": []},
                "model_content": fake_model_content(),
            },
        ]
        MockGeminiClient.return_value = mock_client_instance
        mock_dispatch_tool.side_effect = lambda tool, args: {"error": "DNS lookup failed", "details": "timeout"} if tool != "calculate_cvss" else {}
        mock_generate_report.return_value = {"pdf_path": "x.pdf", "json_path": "x.json"}

        result = orch_module.run_scan("bad.com")

        self.assertEqual(result["status"], "complete")
        self.assertEqual(mock_dispatch_tool.call_count, 3)

        final_call_history = mock_client_instance.generate.call_args_list[-1][0][0]
        self.assertTrue(
            "had a transient failure" in str(final_call_history),
            f"Expected a transient failure nudge in history, got: {final_call_history}",
        )

    @patch("os.path.exists", return_value=True)
    @patch("apps.backend.agent.orchestrator.EVIDENCE_TOOLS", set())
    @patch("apps.backend.agent.orchestrator.generate_report")
    @patch("apps.backend.agent.orchestrator.dispatch_tool")
    @patch("apps.backend.agent.orchestrator.GeminiClient")
    def test_non_critical_tool_failure_triggers_skip_nudge(
        self, MockGeminiClient, mock_dispatch_tool, mock_generate_report, mock_exists
    ):
        """A non-critical tool (e.g. whois_lookup) failing twice should nudge Gemini to skip it, not stop entirely."""
        mock_client_instance = MagicMock()
        mock_client_instance.generate.side_effect = [
            {"type": "tool_call", "tool_name": "whois_lookup", "tool_args": {"target": "example.com"}, "model_content": fake_model_content()},
            {"type": "tool_call", "tool_name": "whois_lookup", "tool_args": {"target": "example.com"}, "model_content": fake_model_content()},
            {
                "type": "tool_call",
                "tool_name": "calculate_cvss",
                "tool_args": {"findings": []},
                "model_content": fake_model_content(),
            },
            {
                "type": "tool_call",
                "tool_name": "generate_report",
                "tool_args": {"target": "example.com", "findings": [], "cvss_scores": []},
                "model_content": fake_model_content(),
            },
        ]
        MockGeminiClient.return_value = mock_client_instance
        mock_dispatch_tool.side_effect = lambda tool, args: {"error": "WHOIS lookup failed", "details": "rate limited"} if tool != "calculate_cvss" else {}
        mock_generate_report.return_value = {"pdf_path": "x.pdf", "json_path": "x.json"}

        result = orch_module.run_scan("example.com")

        self.assertEqual(result["status"], "complete")

        final_call_history = mock_client_instance.generate.call_args_list[-1][0][0]
        self.assertTrue(
            "Select the next missing evidence worker" in str(final_call_history) or "All ten evidence categories are now accounted for" in str(final_call_history),
            f"Expected a skip nudge in history, got: {final_call_history}",
        )

    @patch("apps.backend.agent.orchestrator.EVIDENCE_TOOLS", set())
    @patch("apps.backend.agent.orchestrator.generate_report")
    @patch("apps.backend.agent.orchestrator.dispatch_tool")
    @patch("apps.backend.agent.orchestrator.GeminiClient")
    def test_max_iterations_safety_net(
        self, MockGeminiClient, mock_dispatch_tool, mock_generate_report
    ):
        """If Gemini never calls generate_report, the loop must stop at max_iterations, not run forever."""
        mock_client_instance = MagicMock()
        mock_client_instance.generate.return_value = {
            "type": "text",
            "text": "Still thinking...",
            "model_content": fake_model_content(),
        }
        MockGeminiClient.return_value = mock_client_instance

        result = orch_module.run_scan("example.com", max_iterations=3)

        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["iterations"], 3)
        self.assertEqual(mock_client_instance.generate.call_count, 3)
        mock_generate_report.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
