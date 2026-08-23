"use strict";

/**
 * SentinelScan browser telemetry client -- the client half of
 * POST /api/v1/telemetry (apps/backend/routes/telemetry_routes.py).
 *
 * Not wired into any page yet (no <script> tag references this file) -- it ships this phase
 * as a self-contained module, ready for a later phase to load. Every public entry point is
 * wrapped so a bug here can never break the page it's loaded into.
 *
 * Everything the server will reject is enforced here too: at most MAX_EVENTS_PER_REQUEST
 * events and roughly REQUEST_BYTE_BUDGET bytes per request. An oversized request isn't
 * partially accepted -- the server 400s it and the whole payload is lost -- so a burst of
 * events is split across several requests rather than sent as one it will refuse.
 */
(function () {
    const ENDPOINT = "/api/v1/telemetry";
    const SESSION_STORAGE_KEY = "sentinelscan_telemetry_session";
    const FLUSH_INTERVAL_MS = 5000;
    const FLUSH_THRESHOLD = 20;
    const MAX_MESSAGE_CHARS = 2000;

    // Mirrors MAX_EVENTS_PER_BATCH in apps/backend/logstore/event_validation.py.
    const MAX_EVENTS_PER_REQUEST = 100;
    // Kept under that module's MAX_REQUEST_BYTES (64 KB) with headroom, since this counts
    // UTF-16 characters rather than encoded bytes and a multi-byte message would otherwise
    // measure short.
    const REQUEST_BYTE_BUDGET = 56 * 1024;
    // Hard ceiling on unsent events. A JS error inside an animation frame or a retry loop
    // can produce thousands in the few seconds before a flush; past this the oldest are
    // dropped rather than buffered without limit.
    const MAX_BUFFER = 500;

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

    /**
     * The one place an event is buffered. Errors and ordinary events differ only in level
     * and category -- crucially they now share the same count threshold, so an error storm
     * flushes as it grows instead of waiting out the 5s timer and arriving as one batch far
     * larger than the server accepts.
     */
    function push(level, category, message, data) {
        try {
            buffer.push({
                level,
                category,
                message: String(message || "").slice(0, MAX_MESSAGE_CHARS),
                data: data && typeof data === "object" ? data : {},
                trace_id: null,
                session_id: getSessionId(),
                duration_ms: 0,
            });

            if (buffer.length > MAX_BUFFER) {
                buffer.splice(0, buffer.length - MAX_BUFFER);
            }

            if (buffer.length >= FLUSH_THRESHOLD) {
                flush();
            } else {
                scheduleFlush();
            }
        } catch {
            // Telemetry must never throw into caller code.
        }
    }

    function capture(category, message, data) {
        push("info", category || "ui", message, data);
    }

    function captureError(level, message, data) {
        push(level, "error", message, data);
    }

    function scheduleFlush() {
        if (flushTimer) return;
        flushTimer = setTimeout(() => {
            flushTimer = null;
            flush();
        }, FLUSH_INTERVAL_MS);
    }

    /** Splits `events` into request-sized groups, by both event count and payload size. */
    function chunkEvents(events) {
        const chunks = [];
        let current = [];
        let currentSize = 0;

        for (const event of events) {
            const size = JSON.stringify(event).length + 1;
            const full = current.length >= MAX_EVENTS_PER_REQUEST
                || (current.length > 0 && currentSize + size > REQUEST_BYTE_BUDGET);
            if (full) {
                chunks.push(current);
                current = [];
                currentSize = 0;
            }
            current.push(event);
            currentSize += size;
        }

        if (current.length > 0) {
            chunks.push(current);
        }
        return chunks;
    }

    function send(events, useBeacon) {
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
    }

    function flush(useBeacon) {
        try {
            if (buffer.length === 0) return;
            const pending = buffer;
            buffer = [];

            for (const chunk of chunkEvents(pending)) {
                send(chunk, useBeacon);
            }
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
