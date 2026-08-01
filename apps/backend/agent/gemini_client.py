"""
Gemini Client Wrapper.

Handles the actual calls to Google's Gemini API for the SentinelScan
orchestration agent, using the current google.genai SDK, including:
  - Exponential backoff retry on rate-limit errors (429 / RESOURCE_EXHAUSTED)
  - Local SQLite caching of identical requests, to avoid redundant
    calls against the free tier's strict RPM limits
  - Minimum delay pacing between consecutive API calls
  - Normalizing Gemini's response into a simple, agent-loop-friendly
    shape: either a tool call or a plain text message

This module does NOT contain the orchestration loop itself (deciding
what to do with each response) -- that lives in a separate module.
This module's only job is: given conversation history, get Gemini's
next response, reliably and efficiently.
"""

import hashlib
import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from apps.backend.agent.tool_schemas import TOOL_SCHEMAS


SYSTEM_PROMPT = """You are the SentinelScan Orchestrator, an autonomous AI agent designed for AUTHORIZED security reconnaissance.
Your goal is to assess the security posture of the provided target domain using a specific set of tools.
You must act iteratively: evaluate current findings, determine the next best tool to gather more context or verify vulnerabilities, and execute that tool.

RULES:
1. Do not repeat a tool unnecessarily unless checking a newly discovered sub-target or port.
2. If a port scan reveals HTTP (80) or HTTPS (443), follow up with web-specific tools (ssl_check, http_headers, cookie_analysis, robots_txt_parse, sitemap_parse) as relevant.
3. If a worker result contains an "error" key, do not treat it as a finding -- decide whether to retry once, skip it, or continue without that data, per your worker-failure-handling guidance.
4. Once you have exhausted all relevant reconnaissance based on the discovered attack surface, call generate_report with all findings and cvss_scores gathered so far, and stop.
5. Never call generate_report until you have gathered at least some real findings.
"""

DEFAULT_MODEL_NAME = "gemini-2.5-flash"
MIN_SECONDS_BETWEEN_CALLS = 2.0
MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 2.0

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CACHE_DB_PATH = os.path.join(_PROJECT_ROOT, "apps", "backend", "agent", "gemini_cache.sqlite3")


def _init_cache_db(db_path: str = CACHE_DB_PATH) -> None:
    """Creates the local response cache table if it doesn't already exist."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gemini_cache (
                cache_key TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _cache_key_for(history: List[Dict[str, Any]]) -> str:
    """Builds a stable hash key from conversation history, for cache lookups."""
    serialized = json.dumps(history, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _get_cached(cache_key: str, db_path: str = CACHE_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "SELECT response_json FROM gemini_cache WHERE cache_key = ?", (cache_key,)
        )
        row = cur.fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()


def _set_cached(cache_key: str, response: Dict[str, Any], db_path: str = CACHE_DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO gemini_cache (cache_key, response_json, created_at) VALUES (?, ?, ?)",
            (cache_key, json.dumps(response), time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def _build_tools() -> List[Any]:
    """Converts our SDK-agnostic TOOL_SCHEMAS into google.genai Tool objects."""
    declarations = [
        types.FunctionDeclaration(
            name=schema["name"],
            description=schema["description"],
            parameters_json_schema=schema["parameters"],
        )
        for schema in TOOL_SCHEMAS
    ]
    return [types.Tool(function_declarations=declarations)]


def _extract_normalized_response(response: Any) -> Dict[str, Any]:
    """
    Converts a google.genai GenerateContentResponse into a simple dict:
        {"type": "tool_call", "tool_name": str, "tool_args": dict}
    or
        {"type": "text", "text": str}
    """
    function_calls = getattr(response, "function_calls", None)
    if function_calls:
        first_call = function_calls[0]
        args = dict(first_call.args) if first_call.args else {}
        return {"type": "tool_call", "tool_name": first_call.name, "tool_args": args}

    text = getattr(response, "text", None)
    return {"type": "text", "text": text or ""}


class GeminiClient:
    """
    Thin, resilient wrapper around the Gemini API for the SentinelScan agent.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL_NAME,
        system_prompt: str = SYSTEM_PROMPT,
        cache_db_path: str = CACHE_DB_PATH,
    ) -> None:
        resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            raise ValueError(
                "No Gemini API key provided. Set GEMINI_API_KEY in your .env file "
                "or pass api_key explicitly."
            )

        self._client = genai.Client(api_key=resolved_key)
        self._model_name = model_name
        self._config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=_build_tools(),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        self._cache_db_path = cache_db_path
        _init_cache_db(self._cache_db_path)
        self._last_call_time: float = 0.0

    def _respect_rate_limit(self) -> None:
        """Sleeps just long enough to keep at least MIN_SECONDS_BETWEEN_CALLS
        between consecutive real API calls."""
        elapsed = time.time() - self._last_call_time
        remaining = MIN_SECONDS_BETWEEN_CALLS - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _call_with_backoff(self, history: List[Dict[str, Any]]) -> Any:
        """Calls the Gemini API with exponential backoff retry on rate-limit errors."""
        backoff = INITIAL_BACKOFF_SECONDS
        last_exception: Optional[Exception] = None

        for attempt in range(MAX_RETRIES):
            self._respect_rate_limit()
            try:
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=history,
                    config=self._config,
                )
                self._last_call_time = time.time()
                return response
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                is_rate_limit = (
                    "429" in error_str
                    or "quota" in error_str
                    or "resource_exhausted" in error_str
                )
                if not is_rate_limit or attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2

        raise last_exception  # pragma: no cover - unreachable safeguard

    def generate(self, history: List[Dict[str, Any]], use_cache: bool = True) -> Dict[str, Any]:
        """
        Gets Gemini's next response given the current conversation history.

        Args:
            history: The full conversation so far, as a list of
                {"role": ..., "parts": [...]} dicts.
            use_cache: If True (default), identical history is served
                from the local SQLite cache instead of hitting the API.

        Returns:
            A normalized dict, either:
                {"type": "tool_call", "tool_name": str, "tool_args": dict}
            or:
                {"type": "text", "text": str}
        """
        cache_key = _cache_key_for(history)

        if use_cache:
            cached = _get_cached(cache_key, self._cache_db_path)
            if cached is not None:
                return cached

        raw_response = self._call_with_backoff(history)
        normalized = _extract_normalized_response(raw_response)

        if use_cache:
            _set_cached(cache_key, normalized, self._cache_db_path)

        return normalized
