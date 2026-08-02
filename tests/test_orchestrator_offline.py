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

    @patch("apps.backend.agent.orchestrator.generate_report")
    @patch("apps.backend.agent.orchestrator.dispatch_tool")
    @patch("apps.backend.agent.orchestrator.GeminiClient")
    def test_happy_path_single_tool_then_report(
        self, MockGeminiClient, mock_dispatch_tool, mock_generate_report
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
        self.assertEqual(result["iterations"], 2)
        mock_dispatch_tool.assert_called_once_with("dns_lookup", {"target": "example.com"})
        mock_generate_report.assert_called_once()

    @patch("apps.backend.agent.orchestrator.generate_report")
    @patch("apps.backend.agent.orchestrator.dispatch_tool")
    @patch("apps.backend.agent.orchestrator.GeminiClient")
    def test_critical_tool_failure_triggers_stop_nudge(
        self, MockGeminiClient, mock_dispatch_tool, mock_generate_report
    ):
        """dns_lookup (a CRITICAL tool) failing twice should append a nudge telling Gemini to stop and report."""
        mock_client_instance = MagicMock()
        mock_client_instance.generate.side_effect = [
            {"type": "tool_call", "tool_name": "dns_lookup", "tool_args": {"target": "bad.com"}, "model_content": fake_model_content()},
            {"type": "tool_call", "tool_name": "dns_lookup", "tool_args": {"target": "bad.com"}, "model_content": fake_model_content()},
            {
                "type": "tool_call",
                "tool_name": "generate_report",
                "tool_args": {"target": "bad.com", "findings": [], "cvss_scores": []},
                "model_content": fake_model_content(),
            },
        ]
        MockGeminiClient.return_value = mock_client_instance
        mock_dispatch_tool.return_value = {"error": "DNS lookup failed", "details": "timeout"}
        mock_generate_report.return_value = {"pdf_path": "x.pdf", "json_path": "x.json"}

        result = orch_module.run_scan("bad.com")

        self.assertEqual(result["status"], "complete")
        self.assertEqual(mock_dispatch_tool.call_count, 2)

        final_call_history = mock_client_instance.generate.call_args_list[-1][0][0]
        nudge_texts = [
            part.text
            for content in final_call_history
            if hasattr(content, "role") and content.role == "user"
            for part in content.parts
            if hasattr(part, "text") and part.text is not None
        ]
        self.assertTrue(
            any("Critical tool 'dns_lookup'" in t for t in nudge_texts),
            f"Expected a critical-tool stop nudge in history, got: {nudge_texts}",
        )

    @patch("apps.backend.agent.orchestrator.generate_report")
    @patch("apps.backend.agent.orchestrator.dispatch_tool")
    @patch("apps.backend.agent.orchestrator.GeminiClient")
    def test_non_critical_tool_failure_triggers_skip_nudge(
        self, MockGeminiClient, mock_dispatch_tool, mock_generate_report
    ):
        """A non-critical tool (e.g. whois_lookup) failing twice should nudge Gemini to skip it, not stop entirely."""
        mock_client_instance = MagicMock()
        mock_client_instance.generate.side_effect = [
            {"type": "tool_call", "tool_name": "whois_lookup", "tool_args": {"target": "example.com"}, "model_content": fake_model_content()},
            {"type": "tool_call", "tool_name": "whois_lookup", "tool_args": {"target": "example.com"}, "model_content": fake_model_content()},
            {
                "type": "tool_call",
                "tool_name": "generate_report",
                "tool_args": {"target": "example.com", "findings": [], "cvss_scores": []},
                "model_content": fake_model_content(),
            },
        ]
        MockGeminiClient.return_value = mock_client_instance
        mock_dispatch_tool.return_value = {"error": "WHOIS lookup failed", "details": "rate limited"}
        mock_generate_report.return_value = {"pdf_path": "x.pdf", "json_path": "x.json"}

        result = orch_module.run_scan("example.com")

        self.assertEqual(result["status"], "complete")

        final_call_history = mock_client_instance.generate.call_args_list[-1][0][0]
        nudge_texts = [
            part.text
            for content in final_call_history
            if hasattr(content, "role") and content.role == "user"
            for part in content.parts
            if hasattr(part, "text") and part.text is not None
        ]
        self.assertTrue(
            any("Tool 'whois_lookup' has now failed" in t for t in nudge_texts),
            f"Expected a skip nudge in history, got: {nudge_texts}",
        )
        self.assertFalse(any("Critical tool" in t for t in nudge_texts))

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
