# Product Requirements Document (PRD)

## Problem Statement
Many vulnerability scanners and penetration testing tools lack intelligent orchestration, relying on static scripts that run sequentially regardless of intermediate findings. SentinelScan aims to solve this by providing an AI-orchestrated autonomous penetration testing platform for **authorized** security assessments. The platform acts dynamically, deciding its next actions based on live findings.

## Target Users
- **Security Professionals & Ethical Hackers**: Users conducting authorized assessments who need an intelligent assistant to streamline reconnaissance and basic vulnerability scanning.
- **System Administrators**: IT staff seeking automated tools to assess the security posture of their own infrastructure.
- **Cybersecurity Students**: Individuals learning about autonomous defensive and offensive security concepts through safe, recon-based tools.

## Goals
- Build a genuinely working, resume-quality project with real agent-driven reasoning.
- Provide dynamic, non-deterministic scanning where the AI agent chooses the optimal sequence of specialized Python workers based on current context.
- Output comprehensive, easily digestible PDF and JSON reports with actionable findings and CVSS scoring.
- Implement a clear separation of concerns between orchestration (AI Agent), data gathering (Workers), and presentation (Website).

## Non-Goals & Out of Scope
- **Active Exploitation**: The platform will explicitly NOT write, generate, or execute actual exploit code. It is for reconnaissance, assessment, and reporting only.
- **Complex Authentication**: Multi-tenant user management, SSO, and advanced RBAC are out of scope for this college project.
- **Real-Time Interactive Shells**: No remote code execution or reverse shell capabilities will be integrated.

## User Flow
1. **Initiate Scan**: User accesses the Flask-based web UI and enters a target domain for an authorized scan.
2. **Orchestration**: The request is passed to the AI Agent (the "brain").
3. **Execution Loop**: The AI Agent dynamically calls specific Python Workers (e.g., WHOIS, Nmap, DNS) based on its findings, parsing results and planning the next steps iteratively.
4. **Completion**: Once the agent determines no further beneficial reconnaissance can be performed, it concludes the execution loop. The AI Agent analyzes the collected findings, prioritizes issues, determines severity, and prepares the final assessment report. Where applicable, CVSS scores are calculated using the dedicated CVSS Worker. It then triggers the Report Generator worker.
5. **Report Delivery**: The user is presented with downloadable PDF and JSON reports summarizing the findings and calculated CVSS scores.

## Success Criteria
- **Functional Completeness**: All 11 specialized workers are implemented and can be successfully invoked by the AI agent.
- **Agent Intelligence**: The Gemini agent demonstrates logical, dynamic decision-making rather than executing a hardcoded sequence.
- **Reporting Quality**: The system generates professional, well-formatted PDF and structured JSON reports containing accurate findings.
- **Reliability**: The system gracefully handles errors, timeouts, and Gemini free-tier rate limits without crashing.
