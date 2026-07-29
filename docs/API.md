# REST API Specification

This document details the Flask API endpoints used by the frontend UI to interact with the backend orchestration engine.

| Method | Endpoint | Request Body | Response Body | Description |
|---|---|---|---|---|
| `POST` | `/api/v1/scans` | `{"target": "example.com"}` | `{"scan_id": "uuid", "status": "PENDING"}` | Initiates a new authorized scan against the target domain. Spawns the AI Agent loop in the background. |
| `GET` | `/api/v1/scans/<scan_id>` | None | `{"scan_id": "uuid", "status": "IN_PROGRESS", "current_action": "port_scan", "progress_percent": 45}` | Polls the status of an ongoing scan. Used by the UI dashboard to show real-time progress. |
| `GET` | `/api/v1/scans` | None | `{"scans": [{"scan_id": "uuid", "target": "...", "status": "COMPLETED", "date": "..."}]}` | Lists the historical record of all scans previously executed. |
| `GET` | `/api/v1/reports/<scan_id>/json` | None | `{"findings": [...], "cvss_score": 7.5, "summary": "..."}` | Retrieves the structured JSON report for a completed scan. Returns 404 if not finished. |
| `GET` | `/api/v1/reports/<scan_id>/pdf` | None | Binary PDF Stream (`application/pdf`) | Downloads the generated PDF report for a completed scan. |

## Standard Error Responses
All endpoints adhere to a standard error format:
```json
{
  "error": "Not Found",
  "message": "The requested scan_id does not exist.",
  "code": 404
}
```
