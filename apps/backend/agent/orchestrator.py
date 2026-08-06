"""
Agent Orchestration Loop.

Ties together gemini_client.py (talks to Gemini), tool_schemas.py
(what tools exist), and worker_dispatch.py (executes tools) into the
actual scan behavior described in docs/AI_AGENT.md:

    call Gemini -> Gemini decides next tool -> execute it ->
    feed result back to Gemini -> repeat -> Gemini calls
    generate_report -> done.

Worker failure handling (per docs/AI_AGENT.md):
  - A failed tool's error result is still fed back to Gemini like any
    other result -- Gemini decides whether to retry, skip, or continue.
  - We never force more than one automatic retry of the same tool --
    after 2 total failures we tell Gemini explicitly not to call that
    tool again.
  - If a CRITICAL tool (currently just dns_lookup, since nothing else
    can proceed without resolving the target) fails twice, we instruct
    Gemini to stop reconnaissance and generate a partial report
    explaining what couldn't be completed.

A hard iteration cap is a safety net against infinite loops if Gemini
never calls generate_report.
"""

from typing import Any, Callable, Dict, Optional
import logging
import time

logger = logging.getLogger(__name__)

from google.genai import types

from apps.backend.agent.gemini_client import GeminiClient
from apps.backend.agent.worker_dispatch import dispatch_tool
from apps.backend.workers.report_worker import generate_report


CRITICAL_TOOLS = {"dns_lookup"}
DEFAULT_MAX_ITERATIONS = 20


def run_scan(
    target: str,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    on_progress: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    """
    Runs a full autonomous SentinelScan assessment against target.

    Args:
        target: The domain/IP to assess (must be authorized -- this
            function performs no authorization checks itself, that is
            the caller's responsibility).
        max_iterations: Safety cap on how many Gemini decision rounds
            to allow before giving up, in case generate_report is
            never called.
        on_progress: Optional callback invoked as
            on_progress(iteration=int, max_iterations=int, tool_name=str)
            right before each tool is executed, so a caller (e.g. an
            API layer) can report live progress. Safe to leave as None.

    Returns:
        On successful completion:
            {"status": "complete", "report": {...pdf_path, json_path...},
             "iterations": int, "reason": "generate_report called"}
        If the iteration cap is hit without a report being generated:
            {"status": "incomplete", "error": "...", "iterations": int}
    """
    client = GeminiClient()
    history = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(
                text=f"Begin an authorized security assessment for target: {target}"
            )],
        )
    ]
    failure_counts: Dict[str, int] = {}
    
    scan_start_time = time.time()
    worker_coverage: List[Dict[str, Any]] = []

    for iteration in range(1, max_iterations + 1):
        try:
            response = client.generate(history)
        except Exception as e:
            logger.warning(f"AI API unavailable or failed: {e}")
            scan_duration = time.time() - scan_start_time
            result = generate_report(
                target=target,
                findings=[{
                    "worker": "orchestrator",
                    "severity": "INFORMATIONAL",
                    "summary": f"Scan aborted due to AI API error: {e}",
                    "what_it_means": "The scan could not complete because the AI orchestration service was unavailable or returned an error.",
                    "recommendation": "Retry the scan. If the issue persists, check the Gemini API key and service status.",
                    "raw_data": str(e)
                }],
                cvss_scores=[],
                worker_coverage=worker_coverage,
                scan_duration=scan_duration
            )
            return {
                "status": "complete",
                "report": result,
                "iterations": iteration,
                "reason": "generate_report called due to API exception",
            }

        # Always append the model's own turn back into history verbatim
        # (per Google's guidance -- do not reconstruct it manually).
        if response.get("model_content") is not None:
            history.append(response["model_content"])

        if response["type"] == "tool_call":
            tool_name = response["tool_name"]
            tool_args = dict(response["tool_args"])
            reasoning = tool_args.pop("reasoning", "").strip()

            if on_progress is not None:
                on_progress(
                    iteration=iteration,
                    max_iterations=max_iterations,
                    tool_name=tool_name,
                    reasoning=reasoning,
                )

            if tool_name == "generate_report":
                scan_duration = time.time() - scan_start_time
                result = generate_report(
                    target=tool_args.get("target", target),
                    findings=tool_args.get("findings", []),
                    cvss_scores=tool_args.get("cvss_scores", []),
                    worker_coverage=worker_coverage,
                    scan_duration=scan_duration
                )
                return {
                    "status": "complete",
                    "report": result,
                    "iterations": iteration,
                    "reason": "generate_report called",
                }

            tool_start_time = time.time()
            result = dispatch_tool(tool_name, tool_args)
            tool_duration = time.time() - tool_start_time
            
            is_failure = isinstance(result, dict) and result.get("error") is not None
            
            # Record coverage
            worker_coverage.append({
                "worker": tool_name.replace("_", " ").title(),
                "status": "Completed",
                "duration": tool_duration,
                "result": "Completed with structured evidence." if not is_failure else f"Failed: {result.get('error', 'Unknown')}",
                "reasoning": reasoning,
            })

            if is_failure:
                failure_counts[tool_name] = failure_counts.get(tool_name, 0) + 1
            else:
                failure_counts[tool_name] = 0

            # Feed the tool's result (success or error) back to Gemini
            # as a normal function-response turn.
            history.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(name=tool_name, response=result)],
                )
            )

            if is_failure and failure_counts[tool_name] >= 2:
                if tool_name in CRITICAL_TOOLS:
                    nudge_text = (
                        f"Critical tool '{tool_name}' has failed {failure_counts[tool_name]} "
                        "times in a row. Since this data is essential and unavailable, stop "
                        "further reconnaissance now and call generate_report with whatever "
                        "findings and cvss_scores you have gathered so far, noting in your "
                        "findings that this critical step could not be completed."
                    )
                else:
                    nudge_text = (
                        f"Tool '{tool_name}' has now failed {failure_counts[tool_name]} times. "
                        "Do not call it again. Proceed with other relevant tools, or call "
                        "generate_report if you have enough information without this data."
                    )
                history.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=nudge_text)])
                )

        else:
            # Plain text turn -- nudge Gemini to either continue or wrap up.
            history.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=(
                        "If you are finished with reconnaissance and analysis, call the "
                        "generate_report tool now with your findings and cvss_scores. "
                        "Otherwise continue with the next appropriate tool."
                    ))],
                )
            )

    return {
        "status": "incomplete",
        "error": "Reached maximum iterations without generate_report being called",
        "iterations": max_iterations,
    }
