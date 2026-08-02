# AI Agent Specification

## Overview
The AI Agent is the core orchestration engine of SentinelScan, leveraging the Google Gemini API. Instead of a hardcoded procedural script, the agent evaluates the target dynamically, choosing which worker to execute based on previous findings.

**The AI Agent is the sole reasoning component and single source of intelligence in the SentinelScan system.**

## Responsibilities
- Dynamic worker orchestration
- Context management
- Finding correlation
- Severity determination
- Recommendation generation
- Overall Security Score generation (project-defined score)
- Executive Summary generation
- Complete report preparation


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

## Implementation Notes & Lessons Learned

These notes reflect real issues discovered while building and live-testing the agent, which the original design didn't anticipate. Future changes to this system should account for them.

### Model selection
Do not pin to a specific dated model name (e.g. "gemini-2.5-flash") -- Google retires specific model versions with little notice, and a pinned name can suddenly 404 with "no longer available to new users." Use a `-latest` alias instead (e.g. `gemini-flash-lite-latest`), which automatically tracks Google's current recommended model in that tier. If you must verify what's available/working for a given API key, query `client.models.list()` directly rather than trusting third-party documentation, which is frequently outdated for this fast-moving API.

### System prompt must be explicit about authorization, not just assert it
An early version of the system prompt simply stated the work was "authorized" -- this was not sufficient, and the model repeatedly refused to call tools, responding with canned safety-refusal text instead. The fix required a much more explicit prompt: stating that targets are pre-authorized before the agent ever sees them, explicitly describing every tool as passive/read-only reconnaissance (no exploitation), explicitly comparing the toolset to standard industry tools (Nmap, Qualys, Nessus), and explicitly instructing the model not to hesitate or ask for confirmation. See the current SYSTEM_PROMPT in gemini_client.py for the working version.

### Function-response role
When feeding a tool's result back to Gemini in conversation history, use `role="user"` on the Content object, NOT `role="tool"`. Some official Google documentation examples show `role="tool"`, but the live Gemini Developer API (as opposed to Vertex AI, which may differ) rejects it with `400 INVALID_ARGUMENT`, and its own error message explicitly recommends `role="user"`. Trust the live API's error message over documentation examples if they conflict.

### Cache keys must include everything that affects the response
Our local response cache initially hashed only conversation history. After changing the system prompt to fix the refusal issue above, stale cached refusal responses kept being served instead of hitting the API with the new prompt, because the cache key didn't change. The cache key must include model name and system prompt, not just history, or any prompt/model iteration will silently appear not to work.

### Retry logic must cover more than rate limits
429 (rate limit) is not the only transient, retry-worthy error. 503 (UNAVAILABLE, "high demand") occurs during normal Google-side load spikes and should also trigger backoff-and-retry, not an immediate crash.

### CVSS scoring must be explicitly mandated, not left to model judgment
Without an explicit rule, the agent sometimes completed a scan with real findings (e.g. multiple missing security headers) but chose not to call calculate_cvss before generating the report, leaving cvss_scores empty. Adding an explicit system prompt rule requiring the agent to evaluate and score security-relevant findings before calling generate_report fixed this reliably.
