# Workstream C Integration Instructions

**Owner:** Workstream C  
**Target:** SentinelScan integrator

## Render service

Add a second Render web service after integration (Workstream C does not edit `render.yaml`):

```yaml
name: sentinelscan-logs
branch: main
autoDeploy: true
buildCommand: pip install -r requirements.txt
startCommand: gunicorn --workers 1 --bind 0.0.0.0:$PORT apps.logsite.app:app
healthCheckPath: /healthz
```

Required environment variables:

- `FIREBASE_SERVICE_ACCOUNT_PATH` — same Firebase Admin project used by the main application.
- `LOGSITE_PROBE_TOKEN` — strong shared secret used only by the scheduled uptime probe.
- `MAIN_SITE_URL` — deployed main SentinelScan URL.

## Firebase

Add the final Log Site Render hostname to **Firebase Authentication → Authorized Domains**. The Log Site reuses SentinelScan's existing Firebase project and Google sign-in flow.

## Firestore — use Workstream B as the authority

Workstream C does not define or duplicate Firestore schema/index configuration. Deploy Workstream B's `apps/backend/logstore/firestore.indexes.json`.

Its current composite indexes on the batched `logs` collection are:

- `session_ids` (`array-contains`) + `created_at` ascending
- `trace_ids` (`array-contains`) + `created_at` ascending
- `scan_ids` (`array-contains`) + `created_at` ascending

Raw log documents are batched documents. Configure Firestore TTL using Workstream B's `expires_at` field. Do **not** create C-side indexes on event-level `session_id`, `trace_id`, `level`, `category`, or `ts`; those are not the persisted top-level batch query contract.

## GitHub Actions probe secret

Create repository Actions secret `LOGSITE_PROBE_TOKEN` with the exact same value as the Render environment variable. `.github/workflows/uptime-probe.yml` sends it in `X-Probe-Token` when posting probe results.

## Query-contract limitations intentionally reflected in the UI

The current Workstream B contract does not expose per-scan Gemini cost/ranking, LLM retry rate, or frequent-error fingerprint aggregation. Workstream C displays these as unavailable rather than fabricating values. Extend B only through a separately agreed contract change.

## Dependencies

Workstream C adds **zero new dependencies** and must not change `requirements.txt`.
