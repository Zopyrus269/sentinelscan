# Workstream C Integration Instructions

> **Owner:** Danny (Workstream C)  
> **Target Integrator:** Shreyas  

This document details all deployment and integration steps required to deploy the developer-only **SentinelScan Log Site** alongside the main application.

---

## 1. Render Deployment (`render.yaml`)

Add the following second service definition to `render.yaml` alongside the existing `sentinelscan` service:

```yaml
  - type: web
    name: sentinelscan-logs
    env: python
    region: oregon
    plan: free
    branch: main
    autoDeploy: true
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --workers 1 --bind 0.0.0.0:$PORT apps.logsite.app:app
    healthCheckPath: /healthz
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.9
      - key: FLASK_SECRET_KEY
        generateValue: true
      - key: FIREBASE_SERVICE_ACCOUNT_PATH
        sync: false
      - key: LOGSITE_PROBE_TOKEN
        sync: false
      - key: MAIN_SITE_URL
        value: https://sentinelscan-yd2u.onrender.com
```

### Environment Variables Matrix

| Variable | Description | Where to Set |
|---|---|---|
| `FIREBASE_SERVICE_ACCOUNT_PATH` | Path to Firebase Service Account JSON (same as main app) | Render Environment Variables |
| `LOGSITE_PROBE_TOKEN` | Shared secret string for uptime probe authentication | Render Environment Variables & GitHub Secrets |
| `MAIN_SITE_URL` | Base URL of the main SentinelScan deployment | Render Environment Variables |

---

## 2. Firebase Authorized Domains

To permit Google Sign-In on the Log Site:

1. Open the [Firebase Console](https://console.firebase.google.com/).
2. Navigate to **Authentication** > **Settings** > **Authorized Domains**.
3. Click **Add Domain** and enter the final Render hostname for `sentinelscan-logs` (e.g. `sentinelscan-logs.onrender.com`).
4. `localhost` is already present and covers local development on `http://localhost:5000` or `http://localhost:5001`.

---

## 3. Firestore Indexes and TTL Configuration

Workstream C relies on Workstream B's Firestore schema and query layer (`apps.backend.logstore.query`).

Ensure the following Firestore composite indexes and TTL rules configured by Workstream B are applied:
- `logs` collection: Composite index on `(session_id ASC, ts ASC)`.
- `logs` collection: Composite index on `(trace_id ASC, ts ASC)`.
- `logs` collection: Composite index on `(level ASC, ts DESC)`.
- `logs` collection: Composite index on `(category ASC, ts DESC)`.
- `uptime` collection: Index on `(checked_at DESC)`.
- TTL policy: 30-day retention on `logs` collection documents using `ts`.

---

## 4. GitHub Secret for Uptime Probe

1. Open the GitHub repository settings.
2. Navigate to **Secrets and variables** > **Actions**.
3. Create a repository secret named `LOGSITE_PROBE_TOKEN`.
4. Set its value to match the `LOGSITE_PROBE_TOKEN` set in Render for `sentinelscan-logs`.

The scheduled workflow in `.github/workflows/uptime-probe.yml` will automatically pass this secret in the `X-Probe-Token` header when posting uptime probe telemetry to `/api/probe`.

---

## 5. Dependencies

Workstream C adds **zero new dependencies**. All Python requirements (`flask`, `firebase-admin`, etc.) and frontend packages (Tailwind CSS via CDN, Firebase Web SDK via CDN) are already present in the repository.
