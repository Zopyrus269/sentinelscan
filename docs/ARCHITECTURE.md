# Technical Architecture

## Overview
SentinelScan is built on a distributed logic model where a central AI Agent (powered by Google Gemini) orchestrates a suite of single-purpose Python Workers. A lightweight Flask application serves as the frontend UI and API gateway.

## System Diagram

```text
+-------------------+       +-----------------------+
|   User Browser    | ----> |  Flask Website (UI)   |
| (React/HTML/JS)   | <---- | (Dumb Presentation)   |
+-------------------+       +-----------+-----------+
                                        |
                                  REST API calls
                                        |
+---------------------------------------+---------------------------------------+
|                            Backend (Python)                                   |
|                                                                               |
|  +--------------------+       +---------------------------------------------+ |
|  |     Database       |       |                 AI Agent                    | |
|  | (SQLite/Postgres)  | <---> | (The "Brain" - Gemini API Integration)      | |
|  +--------------------+       +-------------------+-------------------------+ |
|                                                   |                           |
|                                           Dynamic Handoff                     |
|                                                   |                           |
|  +------------------------------------------------+-------------------------+ |
|  |                        Python Workers                                    | |
|  |                                                                          | |
|  | +-------+ +------+ +----------+ +-------------+ +-----+ +--------------+ | |
|  | | WHOIS | | DNS  | | Rev DNS  | | Port (Nmap) | | SSL | | HTTP Headers | | |
|  | +-------+ +------+ +----------+ +-------------+ +-----+ +--------------+ | |
|  | +---------+ +------------+ +-------------+ +------+ +------------------+ | |
|  | | Cookies | | robots.txt | | sitemap.xml | | CVSS | | Report Generator | | |
|  | +---------+ +------------+ +-------------+ +------+ +------------------+ | |
|  +--------------------------------------------------------------------------+ |
+-------------------------------------------------------------------------------+
```

## Component Responsibilities
- **Flask Website**: Acts as a "dumb" UI. Displays forms, triggers API endpoints, polls for progress, and renders reports. It contains no scanning logic.
- **AI Agent**: The orchestrator. Sends current state and context to Gemini, receives a decision on which tool to call next, parses tool outputs, and maintains the context window for the scan session.
- **Python Workers**: Highly specialized, single-purpose modules. They accept standard inputs, perform their network or parsing task, and return structured JSON. They contain zero business or orchestration logic.
- **Database**: Stores scan history, active scan states, and findings. Currently SQLite, designed to be swapped to PostgreSQL later.
- **Report Generator**: A specialized worker invoked at the end of the scan to compile findings into PDF (via reportlab) and JSON formats.

## End-to-End Data Flow
1. **User Request**: User submits `target.com` via the web UI.
2. **API Intake**: Flask receives the request, creates a new scan record in the DB (Status: `IN_PROGRESS`), and spawns a background thread/process for the AI Agent.
3. **Agent Initialization**: AI Agent initializes context for `target.com` and queries Gemini.
4. **Orchestration Loop**:
   - Gemini responds with `call_tool(whois, target=target.com)`.
   - Agent executes WHOIS worker.
   - WHOIS worker returns JSON to the Agent.
   - Agent updates context and queries Gemini with the new data.
   - Gemini decides the next tool (e.g., `call_tool(dns_lookup)`).
5. **Termination**: Gemini evaluates the context and determines recon is complete. It outputs a `done` command.
6. **Reporting**: Agent triggers the Report Generator worker, passing all gathered findings and CVSS scores.
7. **Finalization**: Reports are saved, DB status updates to `COMPLETED`, and the UI fetches the results for the user.

## Repository Folder Structure
```text
sentinelscan/
├── apps/
│   ├── backend/
│   │   ├── app.py             # Flask entrypoint
│   │   ├── agent/             # AI Agent logic and Gemini integration
│   │   ├── workers/           # Python worker modules
│   │   ├── models/            # Database models
│   │   └── routes/            # API endpoints
│   └── frontend/              # Frontend assets (templates/static)
├── docs/                      # Documentation
├── tests/                     # Unit and integration tests
├── .env.example
├── requirements.txt
└── README.md
```
