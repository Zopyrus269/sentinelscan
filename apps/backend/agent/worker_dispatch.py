"""
Worker Dispatch Layer.

Maps a Gemini tool-call name (e.g. "dns_lookup") to the actual Python
worker function that implements it, and normalizes the call so the
agent loop can invoke ANY tool the same way:

    result = dispatch_tool(tool_name, tool_args)

This matters because our 11 workers were built by 3 different people
and ended up with two different calling conventions:

  - 7 workers (Reverse DNS, DNS, Port Scanner, Report Generator,
    Cookies, HTTP Headers, robots.txt) are plain functions taking
    named string arguments directly, e.g. dns_lookup(target: str).

  - 4 workers (SSL, sitemap.xml, CVSS, WHOIS) all share a single
    generic entry point run_worker(input_payload: dict), where the
    payload's expected keys differ per worker.

Rather than rewriting anyone's working, tested code, this module
adapts the second group to look identical to the first from the
agent's point of view. If a worker's internal convention changes
later, only this file needs to change -- not the agent loop, not
the tool schemas.
"""

from typing import Dict, Any, Callable

from apps.backend.workers.dns_worker import dns_lookup
from apps.backend.workers.reverse_dns_worker import reverse_dns_lookup
from apps.backend.workers.portscan_worker import port_scan
from apps.backend.workers.report_worker import generate_report
from apps.backend.workers.cookie_worker import cookie_worker
from apps.backend.workers.headers_worker import headers_worker
from apps.backend.workers.robots_worker import robots_worker

import apps.backend.workers.ssl_worker as ssl_worker
import apps.backend.workers.sitemap_worker as sitemap_worker
import apps.backend.workers.cvss_worker as cvss_worker
import apps.backend.workers.whois_worker as whois_worker


def _unwrap_worker_envelope(result):
    """
    Normalizes the {worker, status, data, error} envelope shape returned by some workers
    to a flat dict, matching the convention every other worker uses.
    """
    if isinstance(result, dict) and "status" in result and "data" in result:
        if result.get("status") == "success":
            return result.get("data", {})
        else:
            return {
                "error": f"{result.get('worker', 'worker')} failed",
                "details": result.get("error", "Unknown error"),
            }
    return result


def _call_ssl_worker(args: Dict[str, Any]) -> Dict[str, Any]:
    """Adapts ssl_check(target, port) -> ssl_worker.run_worker({...})."""
    payload: Dict[str, Any] = {"target": args["target"]}
    if "port" in args and args["port"] is not None:
        payload["port"] = args["port"]
    return _unwrap_worker_envelope(ssl_worker.run_worker(payload))


def _call_sitemap_worker(args: Dict[str, Any]) -> Dict[str, Any]:
    """Adapts sitemap_parse(url) -> sitemap_worker.run_worker({...})."""
    payload: Dict[str, Any] = {"url": args["url"]}
    return _unwrap_worker_envelope(sitemap_worker.run_worker(payload))


def _call_cvss_worker(args: Dict[str, Any]) -> Dict[str, Any]:
    """Adapts calculate_cvss(base_metrics) -> cvss_worker.run_worker({...})."""
    payload: Dict[str, Any] = {"base_metrics": args["base_metrics"]}
    return _unwrap_worker_envelope(cvss_worker.run_worker(payload))


def _call_whois_worker(args: Dict[str, Any]) -> Dict[str, Any]:
    """Adapts whois_lookup(target) -> whois_worker.run_worker({...})."""
    payload: Dict[str, Any] = {"target": args["target"]}
    return _unwrap_worker_envelope(whois_worker.run_worker(payload))


# Maps each Gemini-facing tool name to a callable that accepts the
# tool's argument dict directly and returns the worker's result dict.
# "generate_report" is deliberately excluded here -- the agent loop
# handles it as a special termination signal, not a normal tool call.
TOOL_DISPATCH: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "dns_lookup": lambda args: dns_lookup(args["target"]),
    "reverse_dns_lookup": lambda args: reverse_dns_lookup(args["ip"]),
    "port_scan": lambda args: port_scan(args["target"], args.get("ports")),
    "http_headers": lambda args: headers_worker(args["target"]),
    "cookie_analysis": lambda args: cookie_worker(args["target"]),
    "robots_txt_parse": lambda args: robots_worker(args["target"]),
    "ssl_check": _call_ssl_worker,
    "sitemap_parse": _call_sitemap_worker,
    "calculate_cvss": _call_cvss_worker,
    "whois_lookup": _call_whois_worker,
}


def dispatch_tool(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the worker corresponding to a Gemini tool call.

    Args:
        tool_name: The tool name Gemini selected (must match a key in
            TOOL_DISPATCH -- "generate_report" is handled separately
            by the agent loop, not through this function).
        tool_args: The arguments Gemini provided for that tool call.

    Returns:
        The worker's result dict (whatever shape that worker defines
        in docs/WORKERS.md), OR, if the tool_name is unrecognized or
        the worker raises an unexpected exception, an error dict:
        {"error": "...", "details": "..."}.
    """
    handler = TOOL_DISPATCH.get(tool_name)
    if handler is None:
        return {
            "error": "Unknown tool",
            "details": f"No worker registered for tool name '{tool_name}'",
        }

    try:
        return handler(tool_args)
    except KeyError as e:
        return {
            "error": "Missing required argument",
            "details": f"Tool '{tool_name}' call was missing argument {e}",
        }
    except Exception as e:
        return {
            "error": "Worker execution failed",
            "details": str(e),
        }
