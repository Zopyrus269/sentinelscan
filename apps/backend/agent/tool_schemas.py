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
                "reasoning": {
                    "type": "string",
                    "description": (
                        "A short (1-2 sentence), plain-English explanation of why "
                        "you are calling this tool right now. If this is your first "
                        "tool call, explain why it's a sensible starting point. "
                        "Otherwise, base it specifically on what you learned from "
                        "the previous tool's result."
                    ),
                },
            },
            "required": ["target", "reasoning"],
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
                "reasoning": {
                    "type": "string",
                    "description": (
                        "A short (1-2 sentence), plain-English explanation of why "
                        "you are calling this tool right now. If this is your first "
                        "tool call, explain why it's a sensible starting point. "
                        "Otherwise, base it specifically on what you learned from "
                        "the previous tool's result."
                    ),
                },
            },
            "required": ["ip", "reasoning"],
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
                "reasoning": {
                    "type": "string",
                    "description": (
                        "A short (1-2 sentence), plain-English explanation of why "
                        "you are calling this tool right now. If this is your first "
                        "tool call, explain why it's a sensible starting point. "
                        "Otherwise, base it specifically on what you learned from "
                        "the previous tool's result."
                    ),
                },
            },
            "required": ["target", "reasoning"],
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
                "reasoning": {
                    "type": "string",
                    "description": (
                        "A short (1-2 sentence), plain-English explanation of why "
                        "you are calling this tool right now. If this is your first "
                        "tool call, explain why it's a sensible starting point. "
                        "Otherwise, base it specifically on what you learned from "
                        "the previous tool's result."
                    ),
                },
            },
            "required": ["target", "reasoning"],
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
                "reasoning": {
                    "type": "string",
                    "description": (
                        "A short (1-2 sentence), plain-English explanation of why "
                        "you are calling this tool right now. If this is your first "
                        "tool call, explain why it's a sensible starting point. "
                        "Otherwise, base it specifically on what you learned from "
                        "the previous tool's result."
                    ),
                },
            },
            "required": ["target", "reasoning"],
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
                "reasoning": {
                    "type": "string",
                    "description": (
                        "A short (1-2 sentence), plain-English explanation of why "
                        "you are calling this tool right now. If this is your first "
                        "tool call, explain why it's a sensible starting point. "
                        "Otherwise, base it specifically on what you learned from "
                        "the previous tool's result."
                    ),
                },
            },
            "required": ["target", "reasoning"],
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
                "reasoning": {
                    "type": "string",
                    "description": (
                        "A short (1-2 sentence), plain-English explanation of why "
                        "you are calling this tool right now. If this is your first "
                        "tool call, explain why it's a sensible starting point. "
                        "Otherwise, base it specifically on what you learned from "
                        "the previous tool's result."
                    ),
                },
            },
            "required": ["target", "reasoning"],
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
                "reasoning": {
                    "type": "string",
                    "description": (
                        "A short (1-2 sentence), plain-English explanation of why "
                        "you are calling this tool right now. If this is your first "
                        "tool call, explain why it's a sensible starting point. "
                        "Otherwise, base it specifically on what you learned from "
                        "the previous tool's result."
                    ),
                },
            },
            "required": ["url", "reasoning"],
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
                "reasoning": {
                    "type": "string",
                    "description": (
                        "A short (1-2 sentence), plain-English explanation of why "
                        "you are calling this tool right now. If this is your first "
                        "tool call, explain why it's a sensible starting point. "
                        "Otherwise, base it specifically on what you learned from "
                        "the previous tool's result."
                    ),
                },
            },
            "required": ["target", "reasoning"],
        },
    },
    {
        "name": "ddos_resilience_check",
        "description": (
            "Performs a strictly passive DDoS/CDN/WAF resilience-indicator check. "
            "It inspects public DNS, reverse-DNS and HTTP metadata for observable "
            "CDN, WAF, edge-proxy, rate-limit, or challenge indicators. It does NOT "
            "generate attack traffic, load test, flood, or prove whether DDoS "
            "protection is present or absent. Treat its result as informational only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The authorized domain or URL to inspect passively.",
                },
                "reasoning": {
                    "type": "string",
                    "description": (
                        "A short plain-English explanation of why passive edge/CDN/WAF "
                        "indicators are useful at this point in the assessment."
                    ),
                },
            },
            "required": ["target", "reasoning"],
        },
    },
    {
        "name": "calculate_cvss",
        "description": (
            "Signals the single CVSS v3.1 scoring phase after all evidence workers "
            "have been accounted for. The orchestrator supplies the retained, "
            "evidence-backed actionable findings to the CVSS worker; do not invent "
            "metrics or call this more than once."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": (
                        "A short plain-English explanation of why evidence gathering "
                        "is complete and the one CVSS scoring phase should run now."
                    ),
                },
            },
            "required": ["reasoning"],
        },
    },
    {
        "name": "generate_report",
        "description": (
            "Signals terminal report generation after all evidence categories are "
            "accounted for and the single CVSS phase has completed. The orchestrator "
            "uses its authoritative retained state; do not construct findings yourself."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The authorized domain/IP that was assessed.",
                },
                "reasoning": {
                    "type": "string",
                    "description": (
                        "A short plain-English explanation that evidence and CVSS are "
                        "complete and the final report can now be generated."
                    ),
                },
            },
            "required": ["target", "reasoning"],
        },
    },
]


def get_tool_names() -> List[str]:
    """Returns the list of all tool names defined above, for validation/logging."""
    return [tool["name"] for tool in TOOL_SCHEMAS]
