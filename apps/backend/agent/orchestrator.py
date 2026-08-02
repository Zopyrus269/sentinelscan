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

from typing import Any, Dict

from google.genai import types

from apps.backend.agent.gemini_client import GeminiClient
from apps.backend.agent.worker_dispatch import dispatch_tool
from apps.backend.workers.report_worker import generate_report


CRITICAL_TOOLS = {"dns_lookup"}
DEFAULT_MAX_ITERATIONS = 20


def run_scan(target: str, max_iterations: int = DEFAULT_MAX_ITERATIONS) -> Dict[str, Any]:
    """
    Runs a full autonomous SentinelScan assessment against target.

    Args:
        target: The domain/IP to assess (must be authorized -- this
            function performs no authorization checks itself, that is
            the caller's responsibility).
        max_iterations: Safety cap on how many Gemini decision rounds
            to allow before giving up, in case generate_report is
            never called.

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

    for iteration in range(1, max_iterations + 1):
        response = client.generate(history)

        # Always append the model's own turn back into history verbatim
        # (per Google's guidance -- do not reconstruct it manually).
        if response.get("model_content") is not None:
            history.append(response["model_content"])

        if response["type"] == "tool_call":
            tool_name = response["tool_name"]
            tool_args = response["tool_args"]

            if tool_name == "generate_report":
                result = generate_report(
                    target=tool_args.get("target", target),
                    findings=tool_args.get("findings", []),
                    cvss_scores=tool_args.get("cvss_scores", []),
                )
                return {
                    "status": "complete",
                    "report": result,
                    "iterations": iteration,
                    "reason": "generate_report called",
                }

            result = dispatch_tool(tool_name, tool_args)
            is_failure = isinstance(result, dict) and "error" in result

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
