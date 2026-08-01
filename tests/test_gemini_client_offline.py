"""
Offline tests for gemini_client.py.

These tests do NOT make any real network calls or require a real
Gemini API key -- google.genai's Client is fully mocked, so we can
verify caching, rate-limit/backoff logic, and response parsing
entirely offline.

Run directly: python test_gemini_client_offline.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import tempfile
import unittest
from unittest.mock import patch, MagicMock

from apps.backend.agent import gemini_client as gc_module
from apps.backend.agent.gemini_client import GeminiClient


class FakeFunctionCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args


class FakeContent:
    """Placeholder standing in for a real google.genai Content object."""
    def __init__(self, label):
        self.label = label


class FakeCandidate:
    def __init__(self, content):
        self.content = content


class FakeResponse:
    """Mimics google.genai's GenerateContentResponse convenience attributes."""
    def __init__(self, text=None, function_calls=None):
        self.text = text
        self.function_calls = function_calls or []
        self.candidates = [FakeCandidate(FakeContent("mock-model-turn"))]


class TestGeminiClientOffline(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cache_path = os.path.join(self.tmp_dir, "test_cache.sqlite3")

        self.sleep_patcher = patch.object(gc_module.time, "sleep", return_value=None)
        self.sleep_patcher.start()

    def tearDown(self):
        self.sleep_patcher.stop()

    def _make_client_with_mock_generate(self, generate_content_mock):
        with patch.object(gc_module.genai, "Client") as MockClientClass:
            mock_client_instance = MagicMock()
            mock_client_instance.models.generate_content = generate_content_mock
            MockClientClass.return_value = mock_client_instance
            client = GeminiClient(api_key="fake-test-key", cache_db_path=self.cache_path)
        return client

    def test_text_response_parsing(self):
        """A plain text response should normalize to {"type": "text", "text": ...}."""
        mock_generate = MagicMock(return_value=FakeResponse(text="Scan complete."))
        client = self._make_client_with_mock_generate(mock_generate)

        result = client.generate([{"role": "user", "parts": ["hello"]}], use_cache=False)

        self.assertEqual(result["type"], "text")
        self.assertEqual(result["text"], "Scan complete.")
        self.assertEqual(mock_generate.call_count, 1)
        self.assertIsNotNone(result["model_content"])

    def test_tool_call_response_parsing(self):
        """A function-call response should normalize to a tool_call dict."""
        mock_generate = MagicMock(
            return_value=FakeResponse(
                function_calls=[FakeFunctionCall("dns_lookup", {"target": "example.com"})]
            )
        )
        client = self._make_client_with_mock_generate(mock_generate)

        result = client.generate([{"role": "user", "parts": ["scan example.com"]}], use_cache=False)

        self.assertEqual(result["type"], "tool_call")
        self.assertEqual(result["tool_name"], "dns_lookup")
        self.assertEqual(result["tool_args"], {"target": "example.com"})
        self.assertIsNotNone(result["model_content"])

    def test_caching_avoids_duplicate_api_calls(self):
        """Calling generate() twice with identical history should only hit the mock API once."""
        mock_generate = MagicMock(return_value=FakeResponse(text="cached response"))
        client = self._make_client_with_mock_generate(mock_generate)

        history = [{"role": "user", "parts": ["scan example.com"]}]
        result1 = client.generate(history, use_cache=True)
        result2 = client.generate(history, use_cache=True)

        # The meaningful fields must match between the live call and the cache hit.
        self.assertEqual(result1["type"], result2["type"])
        self.assertEqual(result1["text"], result2["text"])
        # model_content will legitimately be a different object on a cache hit
        # (reconstructed via Part.from_text) vs. a live call -- both should
        # simply be present and non-None, not identical objects.
        self.assertIsNotNone(result1["model_content"])
        self.assertIsNotNone(result2["model_content"])

        self.assertEqual(mock_generate.call_count, 1, "Second identical call should be served from cache")

    def test_backoff_retries_on_rate_limit_then_succeeds(self):
        """A 429-style error should trigger a retry, not an immediate failure."""
        mock_generate = MagicMock(
            side_effect=[
                Exception("429 RESOURCE_EXHAUSTED. You exceeded your current quota."),
                FakeResponse(text="succeeded on retry"),
            ]
        )
        client = self._make_client_with_mock_generate(mock_generate)

        result = client.generate([{"role": "user", "parts": ["scan example.com"]}], use_cache=False)

        self.assertEqual(result["type"], "text")
        self.assertEqual(result["text"], "succeeded on retry")
        self.assertEqual(mock_generate.call_count, 2)

    def test_non_rate_limit_error_raises_immediately(self):
        """A non-rate-limit error should NOT be retried -- it should raise right away."""
        mock_generate = MagicMock(side_effect=ValueError("Some unrelated bug"))
        client = self._make_client_with_mock_generate(mock_generate)

        with self.assertRaises(ValueError):
            client.generate([{"role": "user", "parts": ["scan example.com"]}], use_cache=False)

        self.assertEqual(mock_generate.call_count, 1, "Should not retry non-rate-limit errors")

    def test_tool_call_responses_are_never_cached(self):
        """Tool-call responses should always hit the live API, never be served from cache."""
        mock_generate = MagicMock(
            return_value=FakeResponse(
                function_calls=[FakeFunctionCall("dns_lookup", {"target": "example.com"})]
            )
        )
        client = self._make_client_with_mock_generate(mock_generate)

        history = [{"role": "user", "parts": ["scan example.com"]}]
        client.generate(history, use_cache=True)
        client.generate(history, use_cache=True)

        self.assertEqual(
            mock_generate.call_count, 2,
            "Tool-call responses must never be cached -- each call should hit the live API"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
