# Graph Report - SentinelScan-Project  (2026-08-30)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1820 nodes · 3344 edges · 121 communities (97 shown, 24 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 69 edges (avg confidence: 0.6)
- Token cost: 93,003 input · 5,523 output

## Graph Freshness
- Built from commit: `8e272f21`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Backend Bootstrap & Firebase Init
- WHOIS Worker
- Logstore Query Tests
- Gemini Client
- Telemetry Sink Pipeline
- SSL/TLS Inspection Worker
- Dev Routes & App Factory
- Frontend Event Validation
- Report Generation Worker
- Auth Decorators & Dev API
- Splash Cursor WebGL Effect
- Report Page Frontend
- React App Entry & UI
- AI Agent Orchestrator
- Sitemap Worker Tests
- Frontend Auth Modal
- Fake Firestore Test Double
- CVSS Worker
- UI Component Registry Config
- Fake Log Seeder Script
- Firestore Sink & Schema
- Sitemap URL/Tag Tests
- Worker Dispatch Layer
- Scan API Routes
- Data Redaction Utilities
- Firestore Sink Tests
- Telemetry Pipeline Wiring
- Port Scan Worker
- Report Bento UI Cards
- Scan Routes Tests
- Telemetry Logging Bridge
- Log Site API Tests
- Sitemap XML Parsing Tests
- Scan History Storage
- Telemetry Context Propagation
- Sitemap Worker
- Log Site Sessions View
- DDoS/CDN Resilience Worker
- Cookie Worker Tests
- Headers Worker Tests
- Robots.txt Worker Tests
- Frontend Package Dependencies
- Log Site Flask App
- Log Site Auth Tests
- Telemetry Rollup Aggregation
- Frontend Telemetry Client
- Uptime Probe Ingest
- Uptime Probe Tests
- Telemetry Flask Hooks
- Scan Dashboard Frontend
- Firestore Presence & Stats
- SSRF Target Validator
- Live Events Dashboard
- Demo Log Reset Script
- Telemetry JS Test Harness
- Rollup Tests
- Telemetry Emit & Queue
- Event Schema & Validation
- Frontend Dev Tooling Config
- Magic Bento UI Component
- Scan Terminal UI
- Reset Demo Logs Tests
- React App Package Config
- Docs Explorer UI
- Fake Firestore Client
- Worker CLI Entry Tests
- Stdout Sink Thread
- Status Page Frontend
- Scan History API Routes
- Domain Ownership Verifier
- Oxlint Config
- Report Crawl Animation UI
- Skiper Nav Links Component
- Log Site Frontend Auth
- Seeded Query Range Tests
- DNS Lookup Worker
- Reverse DNS Worker
- Intro Preloader Animation
- Scan Start Frontend
- Knowledge Vault MCP Config
- Log Site Security Headers Tests
- Worker Error Schema Tests
- Animated Input Component
- Worker Health Dashboard
- Rollup Checkpoint Crash Tests
- Event Schema Compatibility Tests
- JS Path Alias Config
- Circular Text Animation
- Gooey Nav Components
- Log Site API Client
- LLM Usage Chart Frontend
- Headless Auth Test
- MCP Server Config
- Seed Script Tests
- Auth Module Init
- Logstore Module Init
- Scan Database Model
- CVA Styling Dependency
- Geist Font Dependency
- Framer Motion Dependency
- Animation Library (GSAP)
- Icon Library
- Animation Library (Motion)
- UI Component Library
- React Core Library
- React DOM Library
- Tailwind Vite Plugin
- Tailwind Animation Utilities
- Log Site Package

## God Nodes (most connected - your core abstractions)
1. `SplashCursor()` - 43 edges
2. `get_db()` - 41 edges
3. `FirestoreSink` - 36 edges
4. `build_frontend_event()` - 32 edges
5. `TestBuildFrontendEvent` - 26 edges
6. `run_worker()` - 25 edges
7. `run_worker()` - 23 edges
8. `require_auth()` - 22 edges
9. `FakeFirestoreClient` - 21 edges
10. `react` - 21 edges

## Surprising Connections (you probably didn't know these)
- `_reseed()` --uses--> `FirestoreSink`  [INFERRED]
  scripts/reset_demo_logs.py → apps/backend/logstore/firestore_sink.py
- `main()` --uses--> `FirestoreSink`  [INFERRED]
  scripts/seed_fake_logs.py → apps/backend/logstore/firestore_sink.py
- `_seed_day()` --uses--> `FirestoreSink`  [INFERRED]
  scripts/seed_fake_logs.py → apps/backend/logstore/firestore_sink.py
- `_write_events()` --uses--> `FirestoreSink`  [INFERRED]
  scripts/seed_fake_logs.py → apps/backend/logstore/firestore_sink.py
- `TestPipeline` --uses--> `FirestoreSink`  [INFERRED]
  tests/test_logstore_pipeline.py → apps/backend/logstore/firestore_sink.py

## Import Cycles
- None detected.

## Communities (121 total, 24 thin omitted)

### Community 0 - "Backend Bootstrap & Firebase Init"
Cohesion: 0.05
Nodes (73): Flask entrypoint for the SentinelScan backend., Auth verification utilities. Provides a Flask decorator that verifies a…, get_db(), Firebase Admin SDK initialization. Loads the service account credentials once…, Returns the initialized Firestore client., _ceil_hour(), count_active_users(), _empty_events_result() (+65 more)

### Community 1 - "WHOIS Worker"
Cohesion: 0.05
Nodes (48): extract_whois_fields(), format_error_response(), format_success_response(), main(), perform_whois_lookup(), Any, SentinelScan WHOIS Worker module. This module provides a stateless worker that…, Execute WHOIS lookup for a given target domain. Args: target (str): Target… (+40 more)

### Community 2 - "Logstore Query Tests"
Cohesion: 0.06
Nodes (19): make_event(), patch, QueryTestCase, Tests for apps.backend.logstore.query -- the 10 frozen-signature read functions…, An event timestamp inside the default query window, for tests that exercise it., Marks rollup.py as having processed up to `created_at`. query.get_llm_usage…, Base class: patches get_db to a fresh FakeFirestoreClient, and resets the…, recent_ts() (+11 more)

### Community 3 - "Gemini Client"
Cohesion: 0.05
Nodes (40): _build_tools(), _cache_key_for(), _extract_normalized_response(), GeminiClient, _get_cached(), _init_cache_db(), Any, Gemini Client Wrapper. Handles the actual calls to Google's Gemini API for the… (+32 more)

### Community 4 - "Telemetry Sink Pipeline"
Cohesion: 0.06
Nodes (31): _handle_sigterm(), Any, Background pipeline that drains a bounded queue and batches events into a sink…, Starts the module-level sink thread and installs a graceful-drain SIGTERM…, Stops the module-level sink thread, if one is running., Drains the sink, then hands SIGTERM back to whoever owned it before us.…, A pluggable destination for batched events (e.g. Firestore, stdout)., Persists one batch of events. May raise; the sink thread retries with backoff. (+23 more)

### Community 5 - "SSL/TLS Inspection Worker"
Cohesion: 0.07
Nodes (43): build_certificate_data(), check_hostname_from_certificate(), classify_verification_failure(), decode_der_certificate(), format_dn(), format_error_response(), format_success_response(), main() (+35 more)

### Community 6 - "Dev Routes & App Factory"
Cohesion: 0.07
Nodes (15): create_app(), Flask, Application factory -- builds and configures the Flask app., is_enabled(), True when SENTINELSCAN_TELEMETRY_ENABLED is one of 1/true/yes/on. Read per call…, patch, Offline tests for dev_routes.py (team secrets bootstrap endpoint). Mocks…, Builds a fake Firestore client covering developers/{uid} and config/secrets… (+7 more)

### Community 7 - "Frontend Event Validation"
Cohesion: 0.09
Nodes (20): build_frontend_event(), _cap_data_size(), _clean_id(), Any, Validates and builds events for the untrusted browser ingest path. Originally…, Returns `value` if it is a usable correlation id, else None. Nulling a…, Drops `data` entirely (replacing it with {}) if it exceeds MAX_DATA_BYTES…, Builds a schema-conformant event from one client-submitted event dict. Returns… (+12 more)

### Community 8 - "Report Generation Worker"
Cohesion: 0.09
Nodes (42): _generate_pdf(), generate_report(), informational_posture_score(), _normalize_text(), Any, SentinelScan report generator. The report worker formats retained evidence and…, Produces one internally consistent findings/CVSS view. Rules: - Informational-…, Generates SentinelScan JSON and PDF reports. (+34 more)

### Community 9 - "Auth Decorators & Dev API"
Cohesion: 0.11
Nodes (42): Decorator for Flask routes that require a logged-in user. Expects an…, Decorator for Flask routes restricted to allowlisted project developers. Must…, require_auth(), require_developer(), bootstrap_secrets(), limit, route, GET /api/v1/dev/bootstrap-secrets -- returns the shared dev secrets doc. (+34 more)

### Community 10 - "Splash Cursor WebGL Effect"
Cohesion: 0.09
Nodes (37): SplashCursor(), addKeywords(), applyInputs(), calcDeltaTime(), compileShader(), correctDeltaX(), correctDeltaY(), correctRadius() (+29 more)

### Community 11 - "Report Page Frontend"
Cohesion: 0.11
Nodes (34): buildCvssParagraph(), buildFindingsParagraph(), buildRecommendations(), buildRecommendationsParagraph(), buildWorkerParagraph(), calculateSecurityScore(), clearError(), configureDownloadButtons() (+26 more)

### Community 12 - "React App Entry & UI"
Cohesion: 0.06
Nodes (30): SplitText(), StaggeredMenu(), bgMountPoint, brandMountPoint, dashboardNoticeMountPoint, docsExplorerMountPoint, FOOTER_LINKS, footerBrandMountPoint (+22 more)

### Community 13 - "AI Agent Orchestrator"
Cohesion: 0.10
Nodes (30): _coverage_entry(), _cvss_items(), _derive_findings(), _emit_progress(), _finding_key(), _host(), _looks_like_session_cookie(), _normalize_result() (+22 more)

### Community 14 - "Sitemap Worker Tests"
Cohesion: 0.11
Nodes (21): Validate input payload schema and execute worker task. Args: input_payload…, run_worker(), _mock_response(), parametrize, patch, Tests for run_worker covering HTTP mocking and input validation., Valid sitemap.xml returns success with URL list., Sitemap index XML returns success with child sitemap list. (+13 more)

### Community 15 - "Frontend Auth Modal"
Cohesion: 0.08
Nodes (27): accountModal, accountModalBackdrop, accountModalCloseButton, accountPanelHistory, accountPanelSettings, accountTabHistory, accountTabSettings, app (+19 more)

### Community 16 - "Fake Firestore Test Double"
Cohesion: 0.13
Nodes (10): _FakeCollection, _FakeDocumentRef, _FakeQuery, _FakeSnapshot, _get_field(), _matches(), Any, In-memory fake Firestore client for logstore read-layer tests. query.py and… (+2 more)

### Community 17 - "CVSS Worker"
Cohesion: 0.12
Nodes (24): build_vector_string(), calculate_base_score(), calculate_exploitability_subscore(), calculate_impact_subscore(), determine_severity(), format_error_response(), format_success_response(), main() (+16 more)

### Community 18 - "UI Component Registry Config"
Cohesion: 0.08
Nodes (24): aliases, components, hooks, lib, ui, utils, iconLibrary, menuAccent (+16 more)

### Community 19 - "Fake Log Seeder Script"
Cohesion: 0.18
Nodes (23): date, Random, _backdated_batches(), _fake_uid(), _finalize(), _fingerprint(), _generate_scan_action(), _generate_session() (+15 more)

### Community 20 - "Firestore Sink & Schema"
Cohesion: 0.16
Nodes (14): Firestore-backed sink backend. Writes each batch to ``logs/{batch_id}``,…, build_batch_document(), Any, datetime, Firestore collection layout and document shapes for the observability pipeline.…, Doc id for one hourly rollup bucket, e.g. "2026-08-22T14" (UTC, hour-truncated)., Builds the document Workstream B writes to ``logs/{batch_id}``. Denormalizes…, Returns the sorted, non-null, de-duplicated values of `key` across `events`. (+6 more)

### Community 21 - "Sitemap URL/Tag Tests"
Cohesion: 0.09
Nodes (14): get_clean_tag(), Extract XML tag name without namespace prefix. Args: elem (ET.Element): XML…, Element, Tags without namespace are returned as-is., Success response has correct schema., Error response has correct schema., Tests for URL normalization, tag cleaning, and response formatting., Bare domain gets https scheme and /sitemap.xml path. (+6 more)

### Community 22 - "Worker Dispatch Layer"
Cohesion: 0.14
Nodes (17): _call_cvss_worker(), _call_sitemap_worker(), _call_ssl_worker(), _call_whois_worker(), Any, Worker Dispatch Layer. Maps a Gemini tool-call name (e.g. "dns_lookup") to the…, Normalizes the {worker, status, data, error} envelope shape returned by some…, Adapts ssl_check(target, port) -> ssl_worker.run_worker({...}). (+9 more)

### Community 23 - "Scan API Routes"
Cohesion: 0.14
Nodes (21): _error(), get_report_json(), get_report_pdf(), get_scan_status(), is_domain_blocked(), list_all_scans(), limit, Response (+13 more)

### Community 24 - "Data Redaction Utilities"
Cohesion: 0.17
Nodes (19): hash_ip(), Any, query_keys(), Recursive redaction plus truncation. Depth-limited to 6., Removes secret-shaped substrings from free text (messages, stack traces)., Salted SHA-256, first 16 hex characters. Never store a raw IP., Returns parameter NAMES only. Values are never recorded., Redacts sensitive headers. (+11 more)

### Community 25 - "Firestore Sink Tests"
Cohesion: 0.30
Nodes (8): FirestoreSink, Sink backend that persists batched events to Firestore., make_event(), _mock_db(), patch, Tests for apps.backend.logstore.firestore_sink -- the Firestore write path.…, Builds a fake Firestore client with one distinct child mock per top-level…, TestFirestoreSink

### Community 26 - "Telemetry Pipeline Wiring"
Cohesion: 0.15
Nodes (12): ensure_started(), Wires the sink thread (Phase 1) up to a real queue for a producer to feed.…, Starts the sink thread against `get_queue()`, if it isn't already running.…, Any, Local-development sink backend. Prints each event as one line of JSON instead…, Sink backend that prints each event as one line of JSON to stdout., Prints each event in `events` as its own JSON line., StdoutSink (+4 more)

### Community 27 - "Port Scan Worker"
Cohesion: 0.17
Nodes (17): _normalize_target(), _parse_ports(), port_scan(), _probe_port(), Any, SentinelScan - Bounded Port Scan Worker Performs a small authorized TCP port…, # IMPORTANT:, Accepts: example.com www.example.com https://example.com… (+9 more)

### Community 28 - "Report Bento UI Cards"
Cohesion: 0.12
Nodes (9): CountUp(), ReportMetaBento(), ReportNoScanNotice(), ReportRiskBento(), ReportSummaryBento(), RISK_KEYS, useRiskSummary(), SpecularButton() (+1 more)

### Community 29 - "Scan Routes Tests"
Cohesion: 0.13
Nodes (7): create_scan(), Creates a new scan record in PENDING state and returns its scan_id., Updates one or more fields on an existing scan record., update_scan(), patch, Offline tests for scan_routes.py. Uses Flask's test client. Mocks…, TestScanRoutes

### Community 30 - "Telemetry Logging Bridge"
Cohesion: 0.16
Nodes (15): drain_for_test(), is_enabled(), True when SENTINELSCAN_TELEMETRY_ENABLED is one of 1/true/yes/on., Test helper. Empties the shared queue and returns its contents., init_app(), Installs request hooks and the logging bridge. No-op when disabled., Wraps the orchestrator's on_progress callback so agent stages are recorded.…, wrap_progress_callback() (+7 more)

### Community 31 - "Log Site API Tests"
Cohesion: 0.20
Nodes (11): patch, Invalid level, source, and category values must return HTTP 400., Invalid ISO date filters must return HTTP 400., GET /api/status must return the documented C status shape., Tests for Workstream C's developer Log Site API., GET /api/stats/<date> rejects invalid YYYY-MM-DD values., API calls delegate through C's Workstream B query boundary., Return a fake Firebase bearer token header. (+3 more)

### Community 32 - "Sitemap XML Parsing Tests"
Cohesion: 0.11
Nodes (10): Tests for parse_sitemap_xml covering standard, index, edge-case XML., Standard sitemap with namespace yields correct URLs., Sitemap index XML yields child sitemap URLs., Sitemap without XML namespace is parsed correctly., Empty urlset returns no URLs., Relative <loc> values are resolved against the base URL., Malformed XML raises ET.ParseError., Empty string input raises ET.ParseError. (+2 more)

### Community 33 - "Scan History Storage"
Cohesion: 0.19
Nodes (15): get_user_scan_history(), Any, Firestore storage module for completed scans. Provides reusable functions to…, save_completed_scan(), scan_exists(), add_scan_event(), get_scan(), list_scans() (+7 more)

### Community 34 - "Telemetry Context Propagation"
Cohesion: 0.31
Nodes (14): bound(), clear_context(), get_context(), Set the current context values if provided., Get the current context values as a dictionary., Clear all context variables., Captures the current context as a plain dict, for handing to a new thread., Re-binds a snapshot inside a new thread. (+6 more)

### Community 35 - "Sitemap Worker"
Cohesion: 0.21
Nodes (15): format_error_response(), format_success_response(), main(), normalize_sitemap_url(), parse_sitemap_xml(), perform_sitemap_fetch(), Any, SentinelScan Sitemap Worker module. This module provides a stateless worker… (+7 more)

### Community 36 - "Log Site Sessions View"
Cohesion: 0.31
Nodes (16): calcDuration(), calcTraceDuration(), esc(), fmtTime(), getTraceLabel(), init(), loadSessions(), renderEmptyTimeline() (+8 more)

### Community 37 - "DDoS/CDN Resilience Worker"
Cohesion: 0.24
Nodes (14): _challenge_observed(), _collect_dns(), ddos_resilience_check(), _detect_providers(), _normalize_url(), Any, Response, Passive DDoS/CDN/WAF resilience indicator worker. This worker is deliberately… (+6 more)

### Community 38 - "Cookie Worker Tests"
Cohesion: 0.17
Nodes (10): cookie_worker(), Any, Fetches target and inspects its cookies for Secure/HttpOnly flags. Args:…, patch, Unit tests for cookie_worker., Automated unit test suite for cookie_worker using mock HTTP responses., Test identification of a cookie missing Secure and HttpOnly flags., Test fallback parsing when inspecting raw Set-Cookie response headers. (+2 more)

### Community 39 - "Headers Worker Tests"
Cohesion: 0.17
Nodes (10): headers_worker(), Any, Fetches target and checks its response headers against a critical list. Args:…, patch, Unit tests for headers_worker., Automated unit test suite for headers_worker using mock HTTP responses., Test detection of missing critical security headers., Test when all critical security headers are present. (+2 more)

### Community 40 - "Robots.txt Worker Tests"
Cohesion: 0.17
Nodes (10): Any, Fetches target's /robots.txt and parses out all Disallow: paths. Args: target:…, robots_worker(), patch, Unit tests for robots_worker., Automated unit test suite for robots_worker using mock HTTP responses., Test fetching and parsing Disallow: directives from robots.txt., Test response when robots.txt does not exist (HTTP 404). (+2 more)

### Community 41 - "Frontend Package Dependencies"
Cohesion: 0.13
Nodes (15): dependencies, @base-ui/react, clsx, @gsap/react, ogl, tailwind-merge, tailwindcss, three (+7 more)

### Community 42 - "Log Site Flask App"
Cohesion: 0.18
Nodes (9): create_app(), Flask, Flask entrypoint for the SentinelScan Log Site service. Serves the developer-…, Builds and configures the developer-only log site Flask app., Tests for SentinelScan Log Site API parameter validation, error shapes, status…, Create a fresh Flask test client for every test., Tests for Firebase authentication and developer allowlist gating on the…, Tests for security headers on the SentinelScan Log Site. (+1 more)

### Community 43 - "Log Site Auth Tests"
Cohesion: 0.16
Nodes (9): patch, Authenticated users absent from developers/{uid} must get 403., An authenticated allowlisted developer must pass C's auth gate., Authentication and developer-authorization tests for Workstream C., Create a fresh Flask test client for every test., Build a fake Firestore client for developers/{uid} lookups., GET /healthz must remain public for Render health checks., Every developer API route must reject unauthenticated callers. (+1 more)

### Community 44 - "Telemetry Rollup Aggregation"
Cohesion: 0.30
Nodes (13): _aggregate(), _empty_summary(), _new_bucket(), Any, datetime, Collapses raw events older than RAW_RETENTION_DAYS into hourly summary…, Groups every event across `batches` into per-hour aggregate buckets., Merges `bucket`'s counts into `logs_hourly/{hour_key}` via Increment. Increment… (+5 more)

### Community 45 - "Frontend Telemetry Client"
Cohesion: 0.29
Nodes (12): capture(), captureError(), chunkEvents(), correlationHeaders(), flush(), getSessionId(), newTraceId(), push() (+4 more)

### Community 46 - "Uptime Probe Ingest"
Cohesion: 0.21
Nodes (13): _error(), _get_query_fn(), Any, route, _query_function(), Authenticated uptime-probe ingest for the SentinelScan Log Site., Validate and persist one scheduled external uptime probe., Resolve one required Workstream B query function. This intentionally provides a… (+5 more)

### Community 47 - "Uptime Probe Tests"
Cohesion: 0.15
Nodes (7): patch, Missing X-Probe-Token header returns 401 Unauthorized., Wrong X-Probe-Token header returns 401 Unauthorized., Missing required fields in payload returns 400 Bad Request., Valid probe post delegates to record_uptime_probe and returns 204 No Content., Verify hmac.compare_digest is used for token verification., TestLogsiteProbe

### Community 48 - "Telemetry Flask Hooks"
Cohesion: 0.26
Nodes (12): new_trace_id(), Generate a new UUIDv4 trace ID., emit(), Convenience: build_event(...) then emit_event(...)., _after_request(), _before_request(), init_app(), _is_valid_uuid() (+4 more)

### Community 49 - "Scan Dashboard Frontend"
Cohesion: 0.27
Nodes (10): bindNavigation(), clearError(), dispatchDashboardNotice(), fetchScan(), loadScan(), openReport(), renderScan(), showError() (+2 more)

### Community 50 - "Firestore Presence & Stats"
Cohesion: 0.20
Nodes (7): Any, datetime, How many of `session_ids` this instance has not already counted for `date`.…, Keeps only the most recent `_MAX_TRACKED_DATES` dates' session sets in memory., Upserts one presence document per session, keeping only its latest event.…, Writes one batch document and updates its derived stats/presence records. A no-…, Increments additive daily counters, grouped by each event's UTC date. Also…

### Community 51 - "SSRF Target Validator"
Cohesion: 0.36
Nodes (10): is_safe_target(), Validates if a given target URL or IP resolves to a safe, non-internal IP., _addr_info(), test_any_unsafe_resolved_ip_rejects_multi_a_record_target(), test_dns_failure_is_rejected(), test_link_local_is_rejected(), test_loopback_is_rejected(), test_malformed_target_is_rejected() (+2 more)

### Community 52 - "Live Events Dashboard"
Cohesion: 0.38
Nodes (11): esc(), fmtTime(), init(), loadActiveUsers(), poll(), renderEmptyEvents(), renderEvents(), resetAndPoll() (+3 more)

### Community 53 - "Demo Log Reset Script"
Cohesion: 0.30
Nodes (10): _count_collection(), _delete_collection(), _delete_stats_range(), main(), Any, Deletes demo observability data from Firestore and reseeds it fresh, in one…, Deletes stats/{date} only for the dates about to be reseeded. Unlike the…, Mirrors seed_fake_logs.py's own main() loop, calling its seeding helpers… (+2 more)

### Community 54 - "Telemetry JS Test Harness"
Cohesion: 0.20
Nodes (9): fs, loadTelemetry(), path, settle(), TELEMETRY_SRC, vm, assert, { loadTelemetry, settle } (+1 more)

### Community 55 - "Rollup Tests"
Cohesion: 0.35
Nodes (4): make_event(), Tests for apps.backend.logstore.rollup -- collapsing raw batches older than…, seed_batch(), TestRunRollup

### Community 56 - "Telemetry Emit & Queue"
Cohesion: 0.40
Nodes (8): get_queue(), The bounded queue the sink thread drains. Created lazily, sized once., emit_event(), get_stats(), Enqueues one event. Never blocks. Never raises. Never retries., {'emitted': int, 'dropped': int, 'queued': int, 'errors': int}, test_emit_never_blocks_or_raises(), test_simulated_total_outage()

### Community 57 - "Event Schema & Validation"
Cohesion: 0.33
Nodes (9): build_event(), fingerprint(), Builds a schema-conformant event., Returns (True, "") or (False, reason)., First 8 hex characters of sha256 over the exception type and frame id., validate_event(), test_event_schema_conformance(), test_fingerprint_stability() (+1 more)

### Community 58 - "Frontend Dev Tooling Config"
Cohesion: 0.18
Nodes (11): devDependencies, oxlint, @types/react, @types/react-dom, vite, @vitejs/plugin-react, oxlint, @types/react (+3 more)

### Community 59 - "Magic Bento UI Component"
Cohesion: 0.25
Nodes (9): calculateSpotlightValues(), cardData, createParticleElement(), GlobalSpotlight(), MagicBento(), ParticleCard(), updateCardGlowProperties(), useMobileDetection() (+1 more)

### Community 60 - "Scan Terminal UI"
Cohesion: 0.27
Nodes (9): ASCII_BANNER, formatDuration(), friendlyName(), renderOutput(), ScanTerminal(), STAGE_LABELS, statusClassName(), WORD_REVEAL_SPRING (+1 more)

### Community 62 - "React App Package Config"
Cohesion: 0.20
Nodes (9): name, private, scripts, build, dev, lint, preview, type (+1 more)

### Community 63 - "Docs Explorer UI"
Cohesion: 0.22
Nodes (6): DocsExplorer(), SECTIONS, FloatingLines(), hexToVec3(), ShinyText(), react

### Community 64 - "Fake Firestore Client"
Cohesion: 0.24
Nodes (5): FakeFirestoreClient, Fakes `db.collection(name)`; each named collection is independent and…, Batched multi-document read, as query.py's _read_documents uses. Real Firestore…, Test convenience: pre-populates a document directly, bypassing set()'s merge…, RollupTestCase

### Community 65 - "Worker CLI Entry Tests"
Cohesion: 0.20
Nodes (6): Tests for the CLI entry point main()., main() reads JSON from sys.argv and invokes run_worker., main() reads JSON from stdin when no CLI argument is provided., main() prints error when no input is provided., main() prints error for invalid JSON input., TestMainCli

### Community 66 - "Stdout Sink Thread"
Cohesion: 0.25
Nodes (5): Starts the stdout draining thread if telemetry is enabled., Stops the stdout draining thread., start_sink(), StdoutSinkThread, stop_sink()

### Community 67 - "Status Page Frontend"
Cohesion: 0.44
Nodes (8): loadStatus(), overallPct(), renderKPIs(), renderOverall(), renderServices(), renderUptime(), schedule(), validUptime()

### Community 68 - "Scan History API Routes"
Cohesion: 0.32
Nodes (7): get_scan(), get_history_scan(), list_history(), route, REST API routes for completed scan history. Exposes historical scans fetched…, GET /api/v1/history -- retrieves all completed scans for the authenticated user., GET /api/v1/history/<scan_id> -- retrieves a specific completed scan document.

### Community 69 - "Domain Ownership Verifier"
Cohesion: 0.25
Nodes (5): DomainVerifier, Domain ownership verification utility for SentinelScan. Ensures that targets…, Utility class to verify domain ownership via DNS TXT records or HTML meta tags., Verify ownership by checking the TXT records of a domain for the expected…, Verify ownership by checking for a specific meta tag on the target URL. Looks…

### Community 70 - "Oxlint Config"
Cohesion: 0.25
Nodes (7): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema, oxc, warn

### Community 71 - "Report Crawl Animation UI"
Cohesion: 0.32
Nodes (5): ENTRANCE_END, readLatchedCrawlData(), ReportCrawl(), TEXT_KEYS, ScrollReveal()

### Community 73 - "Log Site Frontend Auth"
Cohesion: 0.29
Nodes (7): app, auth, authListeners, escapeHtml(), firebaseConfig, provider, updateAuthUI()

### Community 75 - "DNS Lookup Worker"
Cohesion: 0.40
Nodes (4): dns_lookup(), Any, Retrieves DNS records for a target domain. Queries A, AAAA, MX, NS, TXT, and…, test_dns_worker()

### Community 76 - "Reverse DNS Worker"
Cohesion: 0.40
Nodes (4): Any, Resolves an IP address back to its hostname(s) via PTR DNS record lookup. Args:…, reverse_dns_lookup(), run_tests()

### Community 77 - "Intro Preloader Animation"
Cohesion: 0.33
Nodes (4): columns, EXPO_OUT, IntroPreloader(), TIMING

### Community 78 - "Scan Start Frontend"
Cohesion: 0.60
Nodes (5): clearError(), normalizeTarget(), readJsonResponse(), showError(), startScan()

### Community 79 - "Knowledge Vault MCP Config"
Cohesion: 0.33
Nodes (5): @modelcontextprotocol/server-filesystem, devDependencies, @modelcontextprotocol/server-filesystem, scripts, test:js

### Community 80 - "Log Site Security Headers Tests"
Cohesion: 0.33
Nodes (3): GET /healthz receives all required security headers., API endpoints include security headers even on 401 unauthenticated responses., TestLogsiteHeaders

### Community 81 - "Worker Error Schema Tests"
Cohesion: 0.33
Nodes (4): Verify output schema and JSON serializability., Error response contains exactly the expected top-level keys., Error response round-trips through json.dumps/loads., TestJsonSchema

### Community 82 - "Animated Input Component"
Cohesion: 0.50
Nodes (4): CARET_SPRING, CARET_SPRING_REDUCED_MOTION, PlaceholdersAndVanishInput(), useSmoothCaret()

### Community 83 - "Worker Health Dashboard"
Cohesion: 0.70
Nodes (4): load(), renderKPIs(), renderUnsupported(), renderWorkers()

### Community 85 - "Event Schema Compatibility Tests"
Cohesion: 0.40
Nodes (3): patch, Confirms observability.events.build_event's real output -- not a hand-shaped…, TestBackendEventSchemaCompatibility

### Community 86 - "JS Path Alias Config"
Cohesion: 0.50
Nodes (3): compilerOptions, baseUrl, paths

### Community 87 - "Circular Text Animation"
Cohesion: 0.83
Nodes (3): CircularText(), getRotationTransition(), getTransition()

### Community 90 - "LLM Usage Chart Frontend"
Cohesion: 0.83
Nodes (3): load(), renderChart(), renderUnsupported()

## Knowledge Gaps
- **126 isolated node(s):** `gsap`, `lucide-react`, `motion`, `ogl`, `react` (+121 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_db()` connect `Backend Bootstrap & Firebase Init` to `Scan History Storage`, `Scan History API Routes`, `Auth Decorators & Dev API`, `Telemetry Rollup Aggregation`, `Firestore Presence & Stats`, `Fake Log Seeder Script`, `Firestore Sink & Schema`, `Demo Log Reset Script`, `Telemetry Pipeline Wiring`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Why does `emit()` connect `Telemetry Flask Hooks` to `Telemetry Context Propagation`, `Gemini Client`, `Firestore Sink & Schema`, `Telemetry Emit & Queue`, `Event Schema & Validation`, `Telemetry Logging Bridge`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `wrap_progress_callback()` connect `Telemetry Logging Bridge` to `Telemetry Flask Hooks`, `Telemetry Context Propagation`, `AI Agent Orchestrator`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `SplashCursor()` (e.g. with `handleMouseMove()` and `handleTouchEnd()`) actually correct?**
  _`SplashCursor()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `FirestoreSink` (e.g. with `ensure_started()` and `_reseed()`) actually correct?**
  _`FirestoreSink` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `gsap`, `lucide-react`, `motion` to the rest of the system?**
  _126 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Backend Bootstrap & Firebase Init` be split into smaller, more focused modules?**
  _Cohesion score 0.05201292976785189 - nodes in this community are weakly interconnected._