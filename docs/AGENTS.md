# Agent Instructions (Antigravity)

As the Antigravity coding agent working on the SentinelScan repository, you must adhere strictly to the following guidelines in all future sessions:

## Documentation Prerequisites
Before making any architectural, structural, or significant feature changes, you **MUST** read and understand:
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/AI_AGENT.md`
- `docs/API.md`
- `docs/WORKERS.md`

## Safety and Scope Constraints
- **AUTHORIZED USE ONLY**: SentinelScan is an assessment tool. You must assume all operations are authorized.
- **NO EXPLOIT CODE**: You are strictly prohibited from writing, generating, or suggesting active exploit code (e.g., payloads, reverse shells, memory corruption scripts). Confine your implementation to reconnaissance, vulnerability assessment, and reporting.

## Architectural Principles
- **Dumb Workers**: Python workers must NEVER contain business logic, orchestration logic, or state. They execute exactly what they are told and return structured JSON. The AI Agent holds all the intelligence and state.
- **Dynamic Orchestration**: Ensure the AI Agent (Gemini) maintains control of the loop. Do not hardcode sequential scans.

## Coding Conventions
- **Language Standards**: Write Python compliant with PEP8 guidelines.
- **Typing**: Use standard Python type hints (`typing` module) for all function signatures and complex variables to ensure maintainability.
- **Modularity**: Keep functions small and modular.
- **Documentation**: Provide clear, concise docstrings for all classes and functions.

## Version Control
- **Commits**: Structure your commits logically. They should be small, descriptive, and atomic (e.g., "feat(worker): implement WHOIS parsing logic").

Failure to adhere to these rules violates the core design principles of the SentinelScan college project.
