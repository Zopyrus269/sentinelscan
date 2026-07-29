# AI Agent Specification

## Overview
The AI Agent is the core orchestration engine of SentinelScan, leveraging the Google Gemini API. Instead of a hardcoded procedural script, the agent evaluates the target dynamically, choosing which worker to execute based on previous findings.

## System Prompt Draft
```text
You are the SentinelScan Orchestrator, an autonomous AI agent designed for AUTHORIZED security reconnaissance.
Your goal is to assess the security posture of the provided target domain using a specific set of tools.
You must act iteratively: evaluate current findings, determine the next best tool to gather more context or verify vulnerabilities, and execute that tool.

AVAILABLE TOOLS:
- whois_lookup
- dns_recon
- reverse_dns
- port_scan
- ssl_check
- http_headers
- cookie_analysis
- robots_txt_parse
- sitemap_parse
- calculate_cvss
- generate_report

RULES:
1. Do not repeat tools unnecessarily unless checking a newly discovered sub-target or port.
2. If a port scan reveals HTTP(80) or HTTPS(443), you should follow up with web-specific tools (ssl_check, http_headers, etc.).
3. Once you have exhausted all relevant reconnaissance tools based on the attack surface, invoke `generate_report` and finish.
4. Your responses must be strictly formatted as a tool call or a completion message.
```

## Tool Definitions (Callable Functions)
Workers are exposed to Gemini via Gemini's Function Calling API. Each tool requires a JSON schema defining its parameters.
Example for `port_scan`:
```json
{
  "name": "port_scan",
  "description": "Performs an Nmap port scan on a target to discover open ports and services.",
  "parameters": {
    "type": "object",
    "properties": {
      "target": { "type": "string", "description": "The domain or IP to scan" },
      "ports": { "type": "string", "description": "Specific ports to scan (e.g., '80,443' or 'top-100')" }
    },
    "required": ["target"]
  }
}
```

## Decision Loop Pseudocode
```python
def run_agent_loop(target_domain):
    context = []
    agent = GeminiClient(system_prompt)
    
    # Initial prompt
    context.append({"role": "user", "content": f"Begin authorized scan for {target_domain}"})
    
    while True:
        # Enforce rate limits before calling Gemini
        rate_limiter.wait_if_needed()
        
        response = agent.generate_content(context, tools=AVAILABLE_TOOLS)
        
        if response.is_tool_call:
            tool_name = response.tool_call.name
            tool_args = response.tool_call.args
            
            # Execute the python worker
            worker_result = execute_worker(tool_name, tool_args)
            
            # Append result to context
            context.append({"role": "model", "content": response.tool_call})
            context.append({"role": "tool", "name": tool_name, "content": worker_result})
            
            # Special case for termination
            if tool_name == "generate_report":
                break
        else:
            # If the model explicitly says it's done without generating a report, force it.
            if "complete" in response.text.lower():
                execute_worker("generate_report", {"findings": extract_findings(context)})
                break
            
            context.append({"role": "model", "content": response.text})
            
    return "Scan Complete"
```

## Worker Failure Handling
- When a worker returns an error (e.g. `{"error": "..."}`), that error result is still appended to the context and sent back to Gemini like a normal tool result.
- Gemini then decides what to do next: retry the same tool once, skip it and move to a different tool, or proceed without that data if it's not critical.
- The agent should never retry a failed tool more than once automatically — to avoid infinite loops or wasting rate-limited API calls.
- If a critical worker fails repeatedly (e.g. DNS worker fails, meaning we can't resolve the target at all), the agent should stop the scan gracefully and generate a partial report explaining what failed.

## Completion and Handoff
The agent decides the scan is complete when its context indicates all accessible surfaces have been analyzed. It then calls the `generate_report` tool, passing all aggregated findings and identified vulnerabilities. The Report Generator worker takes this structured data and formats it into PDF and JSON outputs.

## Rate-Limit Handling (Gemini Free Tier)
The Gemini free tier has strict RPM (Requests Per Minute) limits. To mitigate this:
1. **Context Condensation**: Before sending the context array, large worker outputs (like massive Nmap XMLs) are condensed into summaries to save tokens.
2. **Exponential Backoff**: API calls are wrapped in a retry mechanism with exponential backoff for `429 Too Many Requests`.
3. **Local Caching**: Identical prompts within a timeframe (e.g., scanning the exact same target back-to-back) hit a local SQLite cache instead of the API.
4. **Token Pacing**: A token bucket algorithm enforces a slight delay (e.g., `time.sleep(2)`) between requests to stay well below the threshold.
