"""
Gemini Tool Schemas.

Defines the function-calling schema for every worker, exposed to Gemini
as "tools" it can choose to invoke during the agent's decision loop.
These schemas describe WHAT each tool does and WHAT parameters it takes
so Gemini can select and call them correctly. They intentionally say
nothing about HOW a worker is implemented (that's worker_dispatch.py's
job) -- this keeps Gemini's view of the system clean and consistent even
though the underlying workers have two different calling conventions.

Format follows Gemini's function declaration schema (OpenAPI-style).
"""

from typing import List, Dict, Any


TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "dns_lookup",
        "description": (
            "Retrieves DNS records (A, AAAA, MX, NS, TXT, CNAME) for a "
            "target domain. Use this early in a scan to understand what "
            "IP addresses and mail/name infrastructure the target uses."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The domain name to look up, e.g. 'example.com'.",
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "reverse_dns_lookup",
        "description": (
            "Resolves an IP address back to its hostname(s) via PTR "
            "record lookup. Useful after discovering an IP (e.g. from "
            "dns_lookup or port_scan) to identify what host it belongs to."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ip": {
                    "type": "string",
                    "description": "The IPv4 or IPv6 address to reverse-resolve.",
                },
            },
            "required": ["ip"],
        },
    },
    {
        "name": "port_scan",
        "description": (
            "Scans a target host for open ports and identifies running "
            "services (e.g. HTTP, HTTPS, SSH). Use this to discover the "
            "attack surface before running web-specific tools like "
            "ssl_check or http_headers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The domain or IP address to scan.",
                },
                "ports": {
                    "type": "string",
                    "description": (
                        "Optional port specification, e.g. '80,443' or "
                        "'1-1000'. If omitted, a default set of common "
                        "ports is scanned."
                    ),
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "ssl_check",
        "description": (
            "Validates the SSL/TLS certificate on a target host: issuer, "
            "expiration, validity, and whether it's self-signed. Only "
            "useful if port 443 (or another HTTPS port) was found open."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The domain to check the SSL certificate for.",
                },
                "port": {
                    "type": "integer",
                    "description": "The HTTPS port to connect to. Defaults to 443 if omitted.",
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "http_headers",
        "description": (
            "Fetches a target URL and checks its HTTP response headers "
            "for missing security-critical headers (HSTS, CSP, "
            "X-Frame-Options, etc.). Only useful if the target serves HTTP/HTTPS."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The URL to inspect, e.g. 'https://example.com'.",
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "cookie_analysis",
        "description": (
            "Fetches a target URL and inspects any cookies it sets for "
            "missing Secure and HttpOnly flags. Only useful if the "
            "target serves HTTP/HTTPS and is expected to set cookies."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The URL to inspect, e.g. 'https://example.com'.",
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "robots_txt_parse",
        "description": (
            "Fetches and parses a target's robots.txt file to discover "
            "disallowed paths, which can reveal hidden or sensitive site "
            "areas worth further investigation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The URL to check, e.g. 'https://example.com'.",
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "sitemap_parse",
        "description": (
            "Fetches and parses a target's sitemap.xml to discover "
            "additional URLs and endpoints for further surface area "
            "assessment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch the sitemap for, e.g. 'https://example.com'.",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "whois_lookup",
        "description": (
            "Fetches WHOIS registration details for a domain: registrar, "
            "creation/expiration dates, and name servers. Good early "
            "reconnaissance step to understand who owns and manages the target."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The domain or IP address to look up.",
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "calculate_cvss",
        "description": (
            "Calculates a standard CVSS v3.1 base score and severity "
            "rating from a set of base metric values. You (the agent) "
            "must determine the base_metrics yourself by interpreting "
            "findings from other tools -- this tool only performs the "
            "mathematical scoring calculation, it does not interpret "
            "findings itself."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "base_metrics": {
                    "type": "object",
                    "description": (
                        "CVSS v3.1 base metric values, e.g. "
                        '{"AV": "N", "AC": "L", "PR": "N", "UI": "N", '
                        '"S": "U", "C": "H", "I": "H", "A": "H"}. '
                        "AV=Attack Vector, AC=Attack Complexity, "
                        "PR=Privileges Required, UI=User Interaction, "
                        "S=Scope, C=Confidentiality, I=Integrity, A=Availability."
                    ),
                },
            },
            "required": ["base_metrics"],
        },
    },
    {
        "name": "generate_report",
        "description": (
            "Compiles all findings and CVSS scores gathered so far into "
            "final PDF and JSON report deliverables. Call this ONLY once "
            "you have finished all relevant reconnaissance and analysis "
            "-- this ends the scan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The domain/IP that was assessed.",
                },
                "findings": {
                    "type": "array",
                    "description": (
                        "List of findings gathered during the scan. Each "
                        "item should be an object with 'worker' (which "
                        "tool produced it), 'severity' (CRITICAL, HIGH, MEDIUM, LOW, or INFORMATIONAL), "
                        "'summary' (a plain-English summary you write), "
                        "'what_it_means' (a simple explanation of the technical finding), "
                        "'recommendation' (actionable remediation advice), "
                        "and 'raw_data' (the tool's raw output)."
                    ),
                    "items": {"type": "object"},
                },
                "cvss_scores": {
                    "type": "array",
                    "description": (
                        "List of CVSS-scored findings, each as returned "
                        "by calculate_cvss, with an added 'finding' field "
                        "describing what was scored."
                    ),
                    "items": {"type": "object"},
                },
            },
            "required": ["target", "findings", "cvss_scores"],
        },
    },
]


def get_tool_names() -> List[str]:
    """Returns the list of all tool names defined above, for validation/logging."""
    return [tool["name"] for tool in TOOL_SCHEMAS]
