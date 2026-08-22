"use strict";

/**
 * SentinelScan browser telemetry client -- the client half of
 * POST /api/v1/telemetry (apps/backend/routes/telemetry_routes.py).
 *
 * Not wired into any page yet (no <script> tag references this file) -- it ships this phase
 * as a self-contained module, ready for a later phase to load. Every public entry point is
 * wrapped so a bug here can never break the page it's loaded into.
 */
(function () {
    const ENDPOINT = "/api/v1/telemetry";
    const SESSION_STORAGE_KEY = "sentinelscan_telemetry_session";
    const FLUSH_INTERVAL_MS = 5000;
    const FLUSH_THRESHOLD = 20;

    let buffer = [];
    let flushTimer = null;

    function safeRandomId() {
        try {
            return crypto.randomUUID();
        } catch {
            // Fallback for environments without crypto.randomUUID (e.g. non-HTTPS contexts).
            return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        }
    }

    function getSessionId() {
        try {
            let sessionId = sessionStorage.getItem(SESSION_STORAGE_KEY);
            if (!sessionId) {
                sessionId = safeRandomId();
                sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
            }
            return sessionId;
        } catch {
            return null;
        }
    }

    function newTraceId() {
        return safeRandomId();
    }

    function capture(category, message, data) {
        try {
            buffer.push({
                level: "info",
                category: category || "ui",
                message: String(message || ""),
                data: data && typeof data === "object" ? data : {},
                trace_id: null,
                session_id: getSessionId(),
                duration_ms: 0,
            });

            if (buffer.length >= FLUSH_THRESHOLD) {
                flush();
            } else {
                scheduleFlush();
            }
        } catch {
            // Telemetry must never throw into caller code.
        }
    }

    function captureError(level, message, data) {
        try {
            buffer.push({
                level,
                category: "error",
                message: String(message || "").slice(0, 2000),
                data: data && typeof data === "object" ? data : {},
                trace_id: null,
                session_id: getSessionId(),
                duration_ms: 0,
            });
            scheduleFlush();
        } catch {
            // Telemetry must never throw into caller code.
        }
    }

    function scheduleFlush() {
        if (flushTimer) return;
        flushTimer = setTimeout(() => {
            flushTimer = null;
            flush();
        }, FLUSH_INTERVAL_MS);
    }

    function flush(useBeacon) {
        try {
            if (buffer.length === 0) return;
            const events = buffer;
            buffer = [];

            const payload = JSON.stringify({ events });

            if (useBeacon && navigator.sendBeacon) {
                navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: "application/json" }));
                return;
            }

            fetch(ENDPOINT, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: payload,
                keepalive: true,
            }).catch(() => {
                // Fire-and-forget: a failed send is dropped, never retried, never blocks the page.
            });
        } catch {
            // Telemetry must never throw into caller code.
        }
    }

    try {
        window.addEventListener("error", (event) => {
            captureError("error", event.message, {
                filename: event.filename,
                lineno: event.lineno,
                stack: event.error && event.error.stack ? String(event.error.stack).slice(0, 2000) : null,
            });
        });

        window.addEventListener("unhandledrejection", (event) => {
            const reason = event.reason;
            captureError("error", reason && reason.message ? reason.message : String(reason), {
                stack: reason && reason.stack ? String(reason.stack).slice(0, 2000) : null,
            });
        });

        window.addEventListener("visibilitychange", () => {
            if (document.visibilityState === "hidden") {
                flush(true);
            }
        });

        window.addEventListener("pagehide", () => {
            flush(true);
        });
    } catch {
        // Telemetry must never throw into caller code.
    }

    window.SentinelTelemetry = {
        getSessionId,
        newTraceId,
        capture,
    };
})();
