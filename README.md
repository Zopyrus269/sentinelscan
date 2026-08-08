<div align="center">

#  SENTINELSCAN 

###  The Autonomous Penetration Tester — An AI-Driven Reconnaissance Engine 

*Point it. Authorize it. It thinks for itself.*

---

> *"A checklist scanner runs the same steps every time. A pentester adapts —*
> *sees an open port, pivots to check what's behind it, follows the evidence.*
> *SentinelScan doesn't simulate that instinct. It has Gemini make the call,*
> *live, after every single result."*

---

![Python](https://img.shields.io/badge/PYTHON-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/FLASK-FRONTEND-000000?style=for-the-badge&logo=flask&logoColor=white)
![Gemini](https://img.shields.io/badge/GOOGLE_GEMINI-AGENT-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)
![Nmap](https://img.shields.io/badge/NMAP-PORT_SCAN-D9822B?style=for-the-badge&logo=nmap&logoColor=white)
![Reportlab](https://img.shields.io/badge/REPORTLAB-PDF-CC0000?style=for-the-badge)
![dnspython](https://img.shields.io/badge/DNSPYTHON-DNS-4B8BBE?style=for-the-badge)
![pytest](https://img.shields.io/badge/PYTEST-123_PASSING-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/USE-AUTHORIZED_TARGETS_ONLY-FF3B30?style=for-the-badge)

</div>

---

## 🧬 The Core Concept

Most "automated pentesting" tools are really just **hardcoded scripts wearing a UI**. They run the same fixed sequence of checks regardless of what they find, then dump raw tool output on a human to interpret.

**SentinelScan is built differently, on purpose:**

- The **frontend is deliberately dumb.** No logic lives in the UI — it only displays what the agent decides.
- **Gemini is the only brain in the system.** It doesn't just summarize results at the end; it *decides which tool to run next*, dynamically, after seeing each result — the same way a human analyst would pivot from "port 443 is open" to "let's check the SSL config" mid-assessment.
- **Every worker is a single-purpose, zero-logic tool.** A worker does not decide anything, judge severity, or draw conclusions — it executes one job (a DNS lookup, a port scan, a header check) and returns raw structured data. All reasoning — severity, correlation, recommendations — happens exclusively in Gemini.
- **The Report Generator has zero embedded intelligence either.** It formats what Gemini already concluded into a clean PDF + JSON deliverable. It does not analyze anything itself.

The result: a system where the *agent* — not the developer — decides the shape of every assessment, while every component underneath it stays simple, testable, and auditable in isolation.

> ⚠️ **Scope & Ethics:** SentinelScan is a reconnaissance and assessment aid for **explicitly authorized security testing only**. It performs passive/read-only checks (DNS, headers, SSL config, port state, etc.) — it does not generate or run exploits. Do not point it at any target you do not have written authorization to assess.

---

## 🏛️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    FLASK FRONTEND  (dumb UI)                     │
│  dashboard  ->  live scan progress                               │
│  report     ->  PDF / JSON viewer                                │
└──────────────────────────────────────────────────────────────────┘
                                 │  target + consent
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                GEMINI AI AGENT   (the only brain)                │
│                                                                  │
│  1. Decide which tool to run next                                │
│  2. Call that worker via worker_dispatch                         │
│  3. Read the result, go back to step 1                           │
│     ...repeats until confident...                                │
│                                                                  │
│  4. Scores findings (CVSS)                                       │
│  5. Calls generate_report  ->  loop ends                         │
└──────────────────────────────────────────────────────────────────┘
                                 │  tool calls
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│         11 SINGLE-PURPOSE WORKERS  (zero business logic)         │
│                                                                  │
│  Reverse DNS | DNS | Port Scanner | SSL Check                    │
│  WHOIS | Sitemap | Cookies | HTTP Headers                        │
│  robots.txt | CVSS Scoring | Report Generator                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🧰 The Workers

| Category | Worker | What it does |
|---|---|---|
| **Reconnaissance** | Reverse DNS | PTR lookups via `socket`, handles valid / no-PTR / invalid-IP cases |
| | DNS | A / AAAA / MX / NS / TXT / CNAME lookups via `dnspython`, graceful per-record degradation |
| | WHOIS | Domain registration and ownership lookup |
| | Port Scanner | Nmap SYN scan with automatic TCP-connect fallback on privilege failure |
| **Web Surface** | SSL Check | Certificate validity, expiry, and configuration checks |
| | HTTP Headers | Security header presence/absence analysis |
| | Cookies | Cookie flag and attribute analysis (`Secure`, `HttpOnly`, `SameSite`) |
| | Sitemap | `sitemap.xml` discovery and structure parsing |
| | robots.txt | Crawl directive parsing and disallowed-path discovery |
| | Passive DDoS Resilience | Non-intrusive inspection of public CDN/WAF/edge/rate-limit indicators; no attack traffic |
| **Analysis & Output** | CVSS Scoring | Pure-math severity scoring — no judgment calls, math only |
| | Report Generator | Formats Gemini's findings into a PDF (`reportlab`) + JSON report — zero analysis of its own |

All 12 workers are designed to be independently testable of the agent, so each one's correctness can be verified in isolation before it's ever handed to Gemini.

---

## 🚀 Getting Started

```bash
# 1. Clone the repo
git clone https://github.com/Zopyrus269/sentinelscan.git
cd sentinelscan

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Nmap (system dependency for the Port Scanner worker)
#    https://nmap.org/download.html — ensure it's on your system PATH

# 5. Add your Gemini API key
cp .env.example .env
# then edit .env and set GEMINI_API_KEY=your_key_here

# 6. Run the full test suite (pytest — not unittest — to catch every test file)
pytest tests/

# 7. Run the app
python -m apps.backend.app
```

Then open the frontend, enter an **authorized** target, confirm the consent checkboxes, and watch the agent work.

---

## 🧪 Testing

- **123 tests** across workers, the dispatch layer, the Gemini client, and the orchestrator.
- Run with `pytest tests/` — plain `unittest discover` silently skips the pytest-style test files.
- Every worker is tested independently of the agent; the orchestrator is tested independently of live Gemini calls (mocked), then verified end-to-end against the real API.

---

## 🧭 Project Status
SentinelScan started as a college project and is now a working, end-to-end platform: 11 reconnaissance/analysis workers, a live Gemini-driven agent orchestration layer, and a full Flask frontend — built with a resume-quality engineering standard rather than as a rushed MVP.

---

## 🤝 Contributing

SentinelScan is open to contributions from the community. To keep the codebase consistent and reliable, please follow this process:

1. **Fork the repository** and create a new branch for your change (e.g. `feature/your-feature-name` or `fix/your-fix-name`).
2. **Make your changes** following the existing project conventions:
   - Workers are single-purpose, zero-logic functions — no analysis, judgment, or severity scoring inside a worker.
   - All reasoning and decision-making belongs in the Gemini agent layer, not in the frontend or the workers.
   - Include or update tests for any code you add or change (`pytest tests/`).
3. **Open a Pull Request** against the `main` branch, with a clear description of what the change does and why.
4. **Wait for review.** A maintainer will review your PR, run the test suite, and may request changes.
5. **Once approved and merged**, you'll be recognized as a contributor to the project.

Please do not submit pull requests containing active exploitation code, DDoS tooling, or anything beyond passive/read-only reconnaissance — this project's scope is strictly authorized, non-destructive security assessment.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

*SentinelScan performs passive, read-only assessments only. Always obtain written authorization before scanning any target you do not own.*

</div>
