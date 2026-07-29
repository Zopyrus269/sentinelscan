# Worker Modules Specification

Workers are isolated Python scripts. They take inputs (usually a domain or IP), perform a specific action, and return structured JSON. **Workers remain intentionally "dumb" (they execute one task, return structured JSON, never assign severity, never recommend fixes, and never decide what runs next). They contain NO orchestration logic.**

### 1. WHOIS Worker
- **Purpose**: Fetches domain registration details.
- **Input**: `{"target": "string"}`
- **Output JSON**: `{"registrar": "...", "creation_date": "...", "expiration_date": "..."}`
- **Error Handling**: Returns `{"error": "WHOIS lookup failed", "details": "..."}` on timeout.
- **Dependencies**: `python-whois`

### 2. DNS Worker
- **Purpose**: Retrieves A, AAAA, MX, NS, and TXT records.
- **Input**: `{"target": "string"}`
- **Output JSON**: `{"A": [...], "MX": [...], "TXT": [...]}`
- **Error Handling**: Graceful degradation if specific records are missing.
- **Dependencies**: `dnspython`

### 3. Reverse DNS Worker
- **Purpose**: Resolves IPs back to hostnames.
- **Input**: `{"ip": "string"}`
- **Output JSON**: `{"hostnames": ["..."]}`
- **Error Handling**: Returns empty list if no PTR record exists.
- **Dependencies**: `socket` (built-in)

### 4. Port Scanner Worker
- **Purpose**: Discovers open ports and services.
- **Input**: `{"target": "string", "ports": "string (optional)"}`
- **Output JSON**: `{"open_ports": [{"port": 80, "service": "http", "state": "open"}], "host_status": "up"}`
- **Error Handling**: Handles Nmap execution errors and permission drops. Note that SYN scans require elevated/admin privileges; if unavailable, the worker should fall back to a TCP connect scan instead of failing outright.
- **Dependencies**: `python-nmap`

### 5. SSL Worker
- **Purpose**: Validates SSL/TLS certificate configuration and expiration.
- **Input**: `{"target": "string", "port": 443}`
- **Output JSON**: `{"issuer": "...", "valid_from": "...", "valid_to": "...", "is_valid": true}`
- **Error Handling**: Catches SSL context exceptions (e.g., self-signed certs).
- **Dependencies**: `ssl`, `socket` (built-ins)

### 6. HTTP Headers Worker
- **Purpose**: Analyzes response headers for security misconfigurations (e.g., missing CSP, HSTS).
- **Input**: `{"url": "string"}`
- **Output JSON**: `{"headers": {"Strict-Transport-Security": "missing", ...}, "security_score": 5}`
- **Error Handling**: Timeouts and connection resets return partial data.
- **Dependencies**: `requests`

### 7. Cookies Worker
- **Purpose**: Checks cookies for `Secure` and `HttpOnly` flags.
- **Input**: `{"url": "string"}`
- **Output JSON**: `{"cookies": [{"name": "session", "secure": true, "httponly": true}]}`
- **Error Handling**: Returns empty array if no cookies are set.
- **Dependencies**: `requests`

### 8. robots.txt Worker
- **Purpose**: Parses robots.txt for hidden or sensitive paths.
- **Input**: `{"url": "string"}`
- **Output JSON**: `{"disallowed_paths": ["/admin", "/private"]}`
- **Error Handling**: 404 returns empty array.
- **Dependencies**: `requests`

### 9. sitemap.xml Worker
- **Purpose**: Extracts URLs from sitemap for further surface area discovery.
- **Input**: `{"url": "string"}`
- **Output JSON**: `{"urls": [".../page1", ".../page2"]}`
- **Error Handling**: Handles invalid XML parsing gracefully.
- **Dependencies**: `requests`, `BeautifulSoup`

### 10. CVSS Scoring Worker
- **Purpose**: Calculates standard CVSSv3 scores based on vulnerability vectors found by the agent. Note that the AI Agent (Gemini) is responsible for inferring the CVSS base metrics (AV, AC, PR, UI, S, C, I, A) from the raw findings of other workers before calling this tool. The CVSS worker does not perform interpretation; it is strictly for mathematical calculation.
- **Input**: `{"base_metrics": {"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "H"}}`
- **Output JSON**: `{"vector": "CVSS:3.1/...", "base_score": 9.8, "severity": "CRITICAL"}`
- **Error Handling**: Validates metric inputs against CVSS specifications.
- **Dependencies**: Native python math / static lookup tables.

### 11. Report Generator Worker
- **Purpose**: Formats AI-generated report data into PDF and JSON deliverables. It performs ZERO analysis.
- **Input**: Fully prepared JSON from the AI Agent (`{"executive_summary": "...", "findings": [...], "recommendations": [...], "overall_security_score": 85, "cvss_scores": [...], "metadata": {...}}`)
- **Output JSON**: `{"pdf_path": "/reports/scan_1.pdf", "json_path": "/reports/scan_1.json"}`
- **Error Handling**: Catches file IO and disk space errors.
- **Dependencies**: `reportlab`, `json`
