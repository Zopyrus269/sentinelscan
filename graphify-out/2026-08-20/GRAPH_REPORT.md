# Graph Report - SentinelScan-Project  (2026-08-20)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1050 nodes · 1747 edges · 86 communities (63 shown, 23 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 34 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b6ad5a16`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- run_worker
- ssl_worker.py
- TestGeminiClientOffline
- SplashCursor
- main.jsx
- report.js
- report_worker.py
- orchestrator.py
- cvss_worker.py
- run_worker
- auth_routes.py
- auth.js
- scan_routes.py
- components.json
- TestHelperFunctions
- TestScanRoutes
- portscan_worker.py
- ReportBento.jsx
- require_auth
- TestParseSitemapXml
- test_sitemap_worker.py
- ddos_resilience_check
- cookie_worker
- headers_worker
- robots_worker
- dependencies
- react
- dashboard.js
- is_safe_target
- bootstrap_env.py
- worker_dispatch.py
- devDependencies
- MagicBento.jsx
- ScanTerminal.jsx
- react-app/package.json
- TestMainCli
- TestDevRoutes
- DomainVerifier
- .oxlintrc.json
- skiper40.jsx
- WarpText.jsx
- dns_lookup
- reverse_dns_lookup
- IntroPreloader.jsx
- skiper106.jsx
- app.js
- TestJsonSchema
- placeholders-and-vanish-input.jsx
- get_db
- compilerOptions
- CircularText.jsx
- GooeyActionNav.jsx
- devDependencies
- FloatingLines.jsx
- button.jsx
- test_headless_authentication
- knowledge-vault
- auth/__init__.py
- scan.py
- _error
- dialkit
- @fontsource-variable/geist
- gsap
- motion
- ogl
- react
- react-dom
- shadcn
- tailwind-merge
- @tailwindcss/vite
- three
- .test_invalid_input_payloads
- @gsap/react

## God Nodes (most connected - your core abstractions)
1. `SplashCursor()` - 43 edges
2. `run_worker()` - 25 edges
3. `run_worker()` - 23 edges
4. `react` - 23 edges
5. `get_db()` - 19 edges
6. `TestSSLWorker` - 16 edges
7. `run_worker()` - 16 edges
8. `generate_report()` - 16 edges
9. `run_scan()` - 15 edges
10. `ddos_resilience_check()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `run_test()` --calls--> `port_scan()`  [INFERRED]
  tests/test_portscan_worker.py → apps/backend/workers/portscan_worker.py
- `test_dns_worker()` --calls--> `dns_lookup()`  [INFERRED]
  tests/test_dns_worker.py → apps/backend/workers/dns_worker.py
- `run_tests()` --calls--> `reverse_dns_lookup()`  [INFERRED]
  tests/test_reverse_dns_worker.py → apps/backend/workers/reverse_dns_worker.py
- `run_tests()` --calls--> `generate_report()`  [INFERRED]
  tests/test_report_worker.py → apps/backend/workers/report_worker.py
- `TestGeminiClientOffline` --uses--> `GeminiClient`  [INFERRED]
  tests/test_gemini_client_offline.py → apps/backend/agent/gemini_client.py

## Import Cycles
- None detected.

## Communities (86 total, 23 thin omitted)

### Community 0 - "run_worker"
Cohesion: 0.05
Nodes (49): extract_whois_fields(), format_error_response(), format_success_response(), main(), perform_whois_lookup(), Any, SentinelScan WHOIS Worker module. This module provides a stateless worker that…, Execute WHOIS lookup for a given target domain. Args: target (str): Target… (+41 more)

### Community 1 - "ssl_worker.py"
Cohesion: 0.07
Nodes (42): build_certificate_data(), check_hostname_from_certificate(), classify_verification_failure(), decode_der_certificate(), format_dn(), format_error_response(), format_success_response(), main() (+34 more)

### Community 2 - "TestGeminiClientOffline"
Cohesion: 0.06
Nodes (35): _build_tools(), _cache_key_for(), _extract_normalized_response(), GeminiClient, _get_cached(), _init_cache_db(), Any, Gemini Client Wrapper. Handles the actual calls to Google's Gemini API for the… (+27 more)

### Community 3 - "SplashCursor"
Cohesion: 0.09
Nodes (37): SplashCursor(), addKeywords(), applyInputs(), calcDeltaTime(), compileShader(), correctDeltaX(), correctDeltaY(), correctRadius() (+29 more)

### Community 4 - "main.jsx"
Cohesion: 0.06
Nodes (31): ShinyText(), SplitText(), StaggeredMenu(), bgMountPoint, brandMountPoint, dashboardNoticeMountPoint, docsExplorerMountPoint, FOOTER_LINKS (+23 more)

### Community 5 - "report.js"
Cohesion: 0.11
Nodes (34): buildCvssParagraph(), buildFindingsParagraph(), buildRecommendations(), buildRecommendationsParagraph(), buildWorkerParagraph(), calculateSecurityScore(), clearError(), configureDownloadButtons() (+26 more)

### Community 6 - "report_worker.py"
Cohesion: 0.13
Nodes (34): get_report_pdf(), GET /api/v1/reports/<scan_id>/pdf -- downloads the completed scan's PDF report., _generate_pdf(), generate_report(), informational_posture_score(), _normalize_text(), Any, SentinelScan report generator. The report worker formats retained evidence and… (+26 more)

### Community 7 - "orchestrator.py"
Cohesion: 0.10
Nodes (30): _coverage_entry(), _cvss_items(), _derive_findings(), _emit_progress(), _finding_key(), _host(), _looks_like_session_cookie(), _normalize_result() (+22 more)

### Community 8 - "cvss_worker.py"
Cohesion: 0.08
Nodes (35): _call_cvss_worker(), _call_sitemap_worker(), _call_ssl_worker(), _call_whois_worker(), Any, Normalizes the {worker, status, data, error} envelope shape returned by some…, Adapts ssl_check(target, port) -> ssl_worker.run_worker({...})., Adapts sitemap_parse(url) -> sitemap_worker.run_worker({...}). (+27 more)

### Community 9 - "run_worker"
Cohesion: 0.12
Nodes (19): Validate input payload schema and execute worker task. Args: input_payload…, run_worker(), _mock_response(), patch, Tests for run_worker covering HTTP mocking and input validation., Valid sitemap.xml returns success with URL list., Sitemap index XML returns success with child sitemap list., Empty urlset returns success with zero URLs. (+11 more)

### Community 10 - "auth_routes.py"
Cohesion: 0.14
Nodes (15): create_app(), Flask entrypoint for the SentinelScan backend., Application factory -- builds and configures the Flask app., Auth verification utilities. Provides a Flask decorator that verifies a…, Decorator for Flask routes restricted to allowlisted project developers. Must…, require_developer(), Auth routes -- session verification and user profile management. The frontend…, bootstrap_secrets() (+7 more)

### Community 11 - "auth.js"
Cohesion: 0.08
Nodes (27): accountModal, accountModalBackdrop, accountModalCloseButton, accountPanelHistory, accountPanelSettings, accountTabHistory, accountTabSettings, app (+19 more)

### Community 12 - "scan_routes.py"
Cohesion: 0.13
Nodes (24): get_user_scan_history(), Any, Firestore storage module for completed scans. Provides reusable functions to…, save_completed_scan(), scan_exists(), add_scan_event(), create_scan(), get_scan() (+16 more)

### Community 13 - "components.json"
Cohesion: 0.08
Nodes (24): aliases, components, hooks, lib, ui, utils, iconLibrary, menuAccent (+16 more)

### Community 14 - "TestHelperFunctions"
Cohesion: 0.09
Nodes (14): get_clean_tag(), Extract XML tag name without namespace prefix. Args: elem (ET.Element): XML…, Element, Tags without namespace are returned as-is., Success response has correct schema., Error response has correct schema., Tests for URL normalization, tag cleaning, and response formatting., Bare domain gets https scheme and /sitemap.xml path. (+6 more)

### Community 16 - "portscan_worker.py"
Cohesion: 0.17
Nodes (17): _normalize_target(), _parse_ports(), port_scan(), _probe_port(), Any, SentinelScan - Bounded Port Scan Worker Performs a small authorized TCP port…, # IMPORTANT:, Accepts: example.com www.example.com https://example.com… (+9 more)

### Community 17 - "ReportBento.jsx"
Cohesion: 0.12
Nodes (9): CountUp(), ReportMetaBento(), ReportNoScanNotice(), ReportRiskBento(), ReportSummaryBento(), RISK_KEYS, useRiskSummary(), SpecularButton() (+1 more)

### Community 18 - "require_auth"
Cohesion: 0.15
Nodes (17): Decorator for Flask routes that require a logged-in user. Expects an…, require_auth(), get_scan(), create_session(), get_current_user(), limit, route, Verifies the caller's Firebase ID token (via @require_auth) and ensures a… (+9 more)

### Community 19 - "TestParseSitemapXml"
Cohesion: 0.11
Nodes (10): Tests for parse_sitemap_xml covering standard, index, edge-case XML., Standard sitemap with namespace yields correct URLs., Sitemap index XML yields child sitemap URLs., Sitemap without XML namespace is parsed correctly., Empty urlset returns no URLs., Relative <loc> values are resolved against the base URL., Malformed XML raises ET.ParseError., Empty string input raises ET.ParseError. (+2 more)

### Community 20 - "test_sitemap_worker.py"
Cohesion: 0.21
Nodes (15): format_error_response(), format_success_response(), main(), normalize_sitemap_url(), parse_sitemap_xml(), perform_sitemap_fetch(), Any, SentinelScan Sitemap Worker module. This module provides a stateless worker… (+7 more)

### Community 21 - "ddos_resilience_check"
Cohesion: 0.24
Nodes (14): _challenge_observed(), _collect_dns(), ddos_resilience_check(), _detect_providers(), _normalize_url(), Any, Response, Passive DDoS/CDN/WAF resilience indicator worker. This worker is deliberately… (+6 more)

### Community 22 - "cookie_worker"
Cohesion: 0.17
Nodes (10): cookie_worker(), Any, Fetches target and inspects its cookies for Secure/HttpOnly flags. Args:…, patch, Unit tests for cookie_worker., Automated unit test suite for cookie_worker using mock HTTP responses., Test identification of a cookie missing Secure and HttpOnly flags., Test fallback parsing when inspecting raw Set-Cookie response headers. (+2 more)

### Community 23 - "headers_worker"
Cohesion: 0.17
Nodes (10): headers_worker(), Any, Fetches target and checks its response headers against a critical list. Args:…, patch, Unit tests for headers_worker., Automated unit test suite for headers_worker using mock HTTP responses., Test detection of missing critical security headers., Test when all critical security headers are present. (+2 more)

### Community 24 - "robots_worker"
Cohesion: 0.17
Nodes (10): Any, Fetches target's /robots.txt and parses out all Disallow: paths. Args: target:…, robots_worker(), patch, Unit tests for robots_worker., Automated unit test suite for robots_worker using mock HTTP responses., Test fetching and parsing Disallow: directives from robots.txt., Test response when robots.txt does not exist (HTTP 404). (+2 more)

### Community 25 - "dependencies"
Cohesion: 0.13
Nodes (15): dependencies, @base-ui/react, class-variance-authority, clsx, framer-motion, lucide-react, tailwindcss, tw-animate-css (+7 more)

### Community 26 - "react"
Cohesion: 0.19
Nodes (8): DocsExplorer(), SECTIONS, ENTRANCE_END, readLatchedCrawlData(), ReportCrawl(), TEXT_KEYS, ScrollReveal(), react

### Community 27 - "dashboard.js"
Cohesion: 0.27
Nodes (10): bindNavigation(), clearError(), dispatchDashboardNotice(), fetchScan(), loadScan(), openReport(), renderScan(), showError() (+2 more)

### Community 28 - "is_safe_target"
Cohesion: 0.36
Nodes (10): is_safe_target(), Validates if a given target URL or IP resolves to a safe, non-internal IP., _addr_info(), test_any_unsafe_resolved_ip_rejects_multi_a_record_target(), test_dns_failure_is_rejected(), test_link_local_is_rejected(), test_loopback_is_rejected(), test_malformed_target_is_rejected() (+2 more)

### Community 29 - "bootstrap_env.py"
Cohesion: 0.26
Nodes (11): Path, exchange_for_firebase_token(), fetch_secrets(), get_google_id_token(), main(), Teammate-facing script: fetches the shared dev secrets and writes them into a…, Merges the given key/value pairs into the .env file, preserving any existing…, Runs the installed-app OAuth flow, opening a browser once, and returns the… (+3 more)

### Community 30 - "worker_dispatch.py"
Cohesion: 0.27
Nodes (6): Worker Dispatch Layer. Maps a Gemini tool-call name (e.g. "dns_lookup") to the…, fetch_with_browser(), Fetches the given URL using a headless Chromium browser via Playwright. Returns…, Cookies Security Worker. Inspects a target URL's HTTP response cookies (and raw…, HTTP Headers Security Worker. Analyzes a target URL's HTTP response headers for…, robots.txt Security Worker. Fetches and parses a target's robots.txt to extract…

### Community 31 - "devDependencies"
Cohesion: 0.18
Nodes (11): devDependencies, oxlint, @types/react, @types/react-dom, vite, @vitejs/plugin-react, oxlint, @types/react (+3 more)

### Community 32 - "MagicBento.jsx"
Cohesion: 0.25
Nodes (9): calculateSpotlightValues(), cardData, createParticleElement(), GlobalSpotlight(), MagicBento(), ParticleCard(), updateCardGlowProperties(), useMobileDetection() (+1 more)

### Community 33 - "ScanTerminal.jsx"
Cohesion: 0.27
Nodes (9): ASCII_BANNER, formatDuration(), friendlyName(), renderOutput(), ScanTerminal(), STAGE_LABELS, statusClassName(), WORD_REVEAL_SPRING (+1 more)

### Community 34 - "react-app/package.json"
Cohesion: 0.20
Nodes (9): name, private, scripts, build, dev, lint, preview, type (+1 more)

### Community 35 - "TestMainCli"
Cohesion: 0.20
Nodes (6): Tests for the CLI entry point main()., main() reads JSON from sys.argv and invokes run_worker., main() reads JSON from stdin when no CLI argument is provided., main() prints error when no input is provided., main() prints error for invalid JSON input., TestMainCli

### Community 36 - "TestDevRoutes"
Cohesion: 0.36
Nodes (3): patch, Builds a fake Firestore client covering developers/{uid} and config/secrets…, TestDevRoutes

### Community 37 - "DomainVerifier"
Cohesion: 0.25
Nodes (5): DomainVerifier, Domain ownership verification utility for SentinelScan. Ensures that targets…, Utility class to verify domain ownership via DNS TXT records or HTML meta tags., Verify ownership by checking the TXT records of a domain for the expected…, Verify ownership by checking for a specific meta tag on the target URL. Looks…

### Community 38 - ".oxlintrc.json"
Cohesion: 0.25
Nodes (7): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema, oxc, warn

### Community 40 - "WarpText.jsx"
Cohesion: 0.57
Nodes (6): buildTextCanvas(), drawLine(), getFontValue(), measureLine(), syncUniforms(), WarpText()

### Community 41 - "dns_lookup"
Cohesion: 0.40
Nodes (4): dns_lookup(), Any, Retrieves DNS records for a target domain. Queries A, AAAA, MX, NS, TXT, and…, test_dns_worker()

### Community 42 - "reverse_dns_lookup"
Cohesion: 0.40
Nodes (4): Any, Resolves an IP address back to its hostname(s) via PTR DNS record lookup. Args:…, reverse_dns_lookup(), run_tests()

### Community 43 - "IntroPreloader.jsx"
Cohesion: 0.33
Nodes (4): columns, EXPO_OUT, IntroPreloader(), TIMING

### Community 45 - "app.js"
Cohesion: 0.60
Nodes (5): clearError(), normalizeTarget(), readJsonResponse(), showError(), startScan()

### Community 46 - "TestJsonSchema"
Cohesion: 0.33
Nodes (4): Verify output schema and JSON serializability., Error response contains exactly the expected top-level keys., Error response round-trips through json.dumps/loads., TestJsonSchema

### Community 47 - "placeholders-and-vanish-input.jsx"
Cohesion: 0.50
Nodes (4): CARET_SPRING, CARET_SPRING_REDUCED_MOTION, PlaceholdersAndVanishInput(), useSmoothCaret()

### Community 48 - "get_db"
Cohesion: 0.24
Nodes (9): get_db(), Firebase Admin SDK initialization. Loads the service account credentials once…, Returns the initialized Firestore client., main(), Admin-only script: allowlists a teammate for the secrets bootstrap system.…, collect_secrets(), main(), Admin-only, one-off script: seeds the shared dev secrets into Firestore. Copies… (+1 more)

### Community 49 - "compilerOptions"
Cohesion: 0.50
Nodes (3): compilerOptions, baseUrl, paths

### Community 50 - "CircularText.jsx"
Cohesion: 0.83
Nodes (3): CircularText(), getRotationTransition(), getTransition()

### Community 52 - "devDependencies"
Cohesion: 0.50
Nodes (3): @modelcontextprotocol/server-filesystem, devDependencies, @modelcontextprotocol/server-filesystem

### Community 59 - "_error"
Cohesion: 0.17
Nodes (13): _error(), get_report_json(), get_scan_status(), list_all_scans(), Response, route, GET /api/v1/scans/<scan_id> -- polls the status/progress of a scan., GET /api/v1/scans -- lists all scans ever run (historical record). (+5 more)

## Knowledge Gaps
- **116 isolated node(s):** `accountModal`, `accountModalBackdrop`, `accountModalCloseButton`, `accountPanelHistory`, `accountPanelSettings` (+111 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GeminiClient` connect `TestGeminiClientOffline` to `orchestrator.py`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `parse_sitemap_xml()` connect `test_sitemap_worker.py` to `TestParseSitemapXml`, `TestHelperFunctions`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Why does `run_worker()` connect `run_worker` to `cvss_worker.py`, `test_sitemap_worker.py`, `TestJsonSchema`, `.test_invalid_input_payloads`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `SplashCursor()` (e.g. with `handleMouseMove()` and `handleTouchEnd()`) actually correct?**
  _`SplashCursor()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `accountModal`, `accountModalBackdrop`, `accountModalCloseButton` to the rest of the system?**
  _116 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `run_worker` be split into smaller, more focused modules?**
  _Cohesion score 0.053555750658472345 - nodes in this community are weakly interconnected._
- **Should `ssl_worker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06896551724137931 - nodes in this community are weakly interconnected._