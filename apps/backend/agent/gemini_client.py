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


SYSTEM_PROMPT = """You are the SentinelScan Orchestrator, an AI agent operating within an authorized, sandboxed academic cybersecurity project (a college coursework assignment).

IMPORTANT CONTEXT: All targets passed to you have ALREADY been pre-authorized by the system operator before you are invoked -- you are never given a target without prior authorization, and you have no ability to choose targets yourself. Your test target in this session, example.com, is IANA's own official reserved domain specifically designated for documentation, testing, and examples -- it is not a real production system.

Your available tools are strictly PASSIVE, READ-ONLY reconnaissance -- the same category of activity performed routinely by defensive security teams, IT auditors, and tools like Nmap, Qualys, and Nessus:
- DNS/WHOIS/reverse-DNS lookups (public record queries)
- HTTP header, cookie, and robots.txt/sitemap.xml inspection (reading public web responses)
- TCP port scanning to see which services are listening (no exploitation of anything found)
- SSL/TLS certificate inspection
- CVSS mathematical scoring of findings

NONE of your tools write data, modify anything, exploit vulnerabilities, execute payloads, or attempt unauthorized access. They only read and report what is already publicly observable.

Your job: assess the target's security posture using these tools, reason about findings, and produce a professional report -- exactly the deliverable a junior security analyst would produce during an authorized assessment.

You must act iteratively: evaluate current findings, determine the next best tool to gather more context, and call it.

RULES:
1. Do not repeat a tool unnecessarily unless checking a newly discovered sub-target or port.
2. If a port scan reveals HTTP (80) or HTTPS (443), follow up with web-specific tools (ssl_check, http_headers, cookie_analysis, robots_txt_parse, sitemap_parse) as relevant.
3. If a worker result contains an "error" key, do not treat it as a finding -- decide whether to retry once, skip it, or continue without that data.
4. Once you have exhausted relevant reconnaissance, call generate_report with all findings and cvss_scores gathered so far, and stop.
5. Never call generate_report until you have gathered at least some real findings.
6. Begin working immediately by calling the first appropriate tool -- do not ask for confirmation or express hesitation, since authorization has already been established before you were invoked.
7. Before calling generate_report, you MUST evaluate each significant finding for security relevance (e.g. missing security headers, exposed services, weak/expired certificates, permissive DNS/WHOIS configurations) and score at least the most significant ones using calculate_cvss. Do not call generate_report with an empty cvss_scores list unless your findings genuinely contained zero notable security-relevant issues. When building each entry of the cvss_scores array for generate_report, copy the "vector", "base_score", and "severity" fields EXACTLY as returned by calculate_cvss -- do not rename "base_score" to "score" or any other key -- and add only one additional field, "finding", describing what was scored.
"""

DEFAULT_MODEL_NAME = "gemini-flash-lite-latest"
MIN_SECONDS_BETWEEN_CALLS = 2.0
MAX_RETRIES = 6
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


def _cache_key_for(history: List[Dict[str, Any]], model_name: str, system_prompt: str) -> str:
    """Builds a stable hash key from conversation history, model, and
    system prompt together, so changing either invalidates old cache entries."""
    serialized = json.dumps(
        {"history": history, "model": model_name, "system_prompt": system_prompt},
        sort_keys=True,
        default=str,
    )
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
        {"type": "tool_call", "tool_name": str, "tool_args": dict, "model_content": <raw content>}
    or
        {"type": "text", "text": str, "model_content": <raw content>}

    "model_content" holds the exact response.candidates[0].content object
    the model returned. Callers building conversation history should
    append this object directly (not reconstruct it manually), since
    Gemini may attach internal state to a turn that only survives if
    the original object is passed back verbatim.
    """
    try:
        model_content = response.candidates[0].content
    except (AttributeError, IndexError):
        model_content = None

    function_calls = getattr(response, "function_calls", None)
    if function_calls:
        first_call = function_calls[0]
        args = dict(first_call.args) if first_call.args else {}
        return {
            "type": "tool_call",
            "tool_name": first_call.name,
            "tool_args": args,
            "model_content": model_content,
        }

    text = getattr(response, "text", None)
    return {"type": "text", "text": text or "", "model_content": model_content}


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
        self._system_prompt = system_prompt
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
        """Calls the Gemini API with exponential backoff retry on rate-limit (429) and transient server (503/UNAVAILABLE) errors."""
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
                is_retryable = (
                    "429" in error_str
                    or "quota" in error_str
                    or "resource_exhausted" in error_str
                    or "503" in error_str
                    or "unavailable" in error_str
                    or "high demand" in error_str
                )
                if not is_retryable or attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2

        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Gemini API call failed after all retries with no captured exception")  # pragma: no cover - unreachable safeguard

    def generate(self, history: List[Dict[str, Any]], use_cache: bool = True) -> Dict[str, Any]:
        """
        Gets Gemini's next response given the current conversation history.

        Args:
            history: The full conversation so far, as a list of
                {"role": ..., "parts": [...]} dicts or types.Content objects.
            use_cache: If True (default), identical history is served
                from the local SQLite cache instead of hitting the API --
                but ONLY for plain text responses. Tool-call responses
                always hit the live API, since a cached tool-call's
                model turn can't be safely reconstructed for continuing
                the conversation.

        Returns:
            A normalized dict, either:
                {"type": "tool_call", "tool_name": str, "tool_args": dict, "model_content": <raw content>}
            or:
                {"type": "text", "text": str, "model_content": <raw content>}
        """
        cache_key = _cache_key_for(history, self._model_name, self._system_prompt)

        if use_cache:
            cached = _get_cached(cache_key, self._cache_db_path)
            if cached is not None and cached.get("type") == "text":
                cached = dict(cached)
                cached["model_content"] = types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=cached.get("text", ""))],
                )
                return cached

        raw_response = self._call_with_backoff(history)
        normalized = _extract_normalized_response(raw_response)

        if use_cache and normalized["type"] == "text":
            cache_payload = {k: v for k, v in normalized.items() if k != "model_content"}
            _set_cached(cache_key, cache_payload, self._cache_db_path)

        return normalized
