"use strict";

/**
 * Tests for apps/frontend/static/js/telemetry.js -- the browser half of
 * POST /api/v1/telemetry.
 *
 * Run with:  npm run test:js      (or: node --test "tests/js/*.test.js")
 * Needs Node 20+ for the built-in test runner. No test framework is installed for this --
 * `node:test` and `node:assert` ship with Node itself.
 *
 * Pass the glob, not the directory: `node --test tests/js` resolves the path as a module
 * and fails with MODULE_NOT_FOUND rather than walking it.
 *
 * This is the only JavaScript in the repo carrying real logic: request chunking, trace
 * state, and a cached ID token. The Python suite cannot reach any of it, and the two bugs
 * these cases pin down (a burst building a request the server always rejects, and the two
 * correlation ids never being populated) both survived code review once already.
 */
const test = require("node:test");
const assert = require("node:assert");

const { loadTelemetry, settle } = require("./harness");

// Mirrors the constants in telemetry.js, which mirror event_validation.py's server caps.
const MAX_EVENTS_PER_REQUEST = 100;
const MAX_REQUEST_BYTES = 65536;
const FLUSH_THRESHOLD = 20;

function bigStack() {
    return "x".repeat(1800);
}

test("bursts of events never build a request the server would reject", async (t) => {
    await t.test("errors flush on the count threshold, not only on the timer", () => {
        const h = loadTelemetry();

        for (let i = 0; i < FLUSH_THRESHOLD; i++) {
            h.listeners.error({ message: `boom ${i}`, filename: "app.js", lineno: i });
        }

        // No timer has fired. Before the fix, captureError only ever scheduled one, so a
        // burst sat in the buffer growing until the 5s flush sent it all as one request.
        assert.equal(h.requests.length, 1);
        assert.equal(h.sentEvents().length, FLUSH_THRESHOLD);
    });

    // Note on what these two actually pin down. With FLUSH_THRESHOLD at 20, a flush can
    // never hold more than 20 events, so the 100-event cap is defence-in-depth rather than
    // a limit reached in normal operation -- verified by mutation testing, where removing
    // chunkEvents() entirely leaves the count assertions passing and only the byte-size
    // assertion fails. The count assertion still earns its place: it is what would catch a
    // future change that raises the threshold past the server's cap or drops the threshold
    // altogether, which is exactly the regression finding A7 described.
    await t.test("a 5,000-error storm splits into per-request-capped batches", () => {
        const h = loadTelemetry();

        for (let i = 0; i < 5000; i++) {
            h.listeners.error({
                message: `boom ${i}`,
                filename: "app.js",
                lineno: i,
                error: { stack: bigStack() },
            });
        }
        h.runTimers();

        assert.equal(h.sentEvents().length, 5000, "no events may be dropped");
        for (const request of h.requests) {
            assert.ok(
                request.body.events.length <= MAX_EVENTS_PER_REQUEST,
                `request carried ${request.body.events.length} events, over the server cap`,
            );
            assert.ok(
                Buffer.byteLength(JSON.stringify(request.body), "utf8") <= MAX_REQUEST_BYTES,
                "request exceeded the server's byte cap",
            );
        }
    });

    await t.test("oversized events still split by payload size, not just count", () => {
        const h = loadTelemetry();

        // Ten events of ~8 KB each would blow the 64 KB request cap long before the
        // 100-event cap is reached.
        for (let i = 0; i < 40; i++) {
            h.telemetry.capture("ui", `event ${i}`, { blob: "y".repeat(8000) });
        }
        h.runTimers();

        assert.ok(h.requests.length > 1, "a size-bound burst must span several requests");
        for (const request of h.requests) {
            assert.ok(
                Buffer.byteLength(JSON.stringify(request.body), "utf8") <= MAX_REQUEST_BYTES,
            );
        }
    });
});

test("correlation ids", async (t) => {
    await t.test("events carry no trace until an action starts one", () => {
        const h = loadTelemetry();

        h.telemetry.capture("ui", "page loaded", {});
        h.runTimers();

        assert.equal(h.sentEvents()[0].trace_id, null);
    });

    await t.test("newTraceId starts a trace that later events inherit", () => {
        const h = loadTelemetry();

        const traceId = h.telemetry.newTraceId();
        h.telemetry.capture("ui", "clicked start scan", {});
        h.telemetry.capture("scan", "scan requested", {});
        h.runTimers();

        // The bug this pins: newTraceId used to return a fresh id and forget it, while
        // capture() hardcoded trace_id: null. app.js puts the returned id straight into the
        // X-SentinelScan-Trace header, so the header and the events could never match and
        // the click-to-backend correlation silently produced nothing.
        const traces = h.sentEvents().map((e) => e.trace_id);
        assert.deepEqual(traces, [traceId, traceId]);
        assert.equal(h.telemetry.getTraceId(), traceId);
    });

    await t.test("each action gets its own trace", () => {
        const h = loadTelemetry();

        const first = h.telemetry.newTraceId();
        h.telemetry.capture("ui", "first action", {});
        const second = h.telemetry.newTraceId();
        h.telemetry.capture("ui", "second action", {});
        h.runTimers();

        assert.notEqual(first, second);
        assert.deepEqual(h.sentEvents().map((e) => e.trace_id), [first, second]);
    });

    await t.test("correlationHeaders matches what the events carry", () => {
        const h = loadTelemetry();

        const traceId = h.telemetry.newTraceId();
        h.telemetry.capture("ui", "clicked start scan", {});
        h.runTimers();

        const headers = h.telemetry.correlationHeaders();
        const event = h.sentEvents()[0];
        assert.equal(headers["X-SentinelScan-Trace"], traceId);
        assert.equal(headers["X-SentinelScan-Session"], event.session_id);
    });

    await t.test("the session id is stable and persisted", () => {
        const h = loadTelemetry();

        const sessionId = h.telemetry.getSessionId();
        h.telemetry.capture("ui", "one", {});
        h.telemetry.capture("ui", "two", {});
        h.runTimers();

        assert.ok(sessionId);
        assert.equal(h.telemetry.getSessionId(), sessionId, "must not rotate per call");
        for (const event of h.sentEvents()) {
            assert.equal(event.session_id, sessionId);
        }
        assert.equal(h.storage.get("sentinelscan_telemetry_session"), sessionId);
    });
});

test("identity is sent, never asserted", async (t) => {
    await t.test("a signed-in user's token is attached", async () => {
        const h = loadTelemetry({ idToken: "fake-id-token" });
        await settle();

        h.telemetry.capture("ui", "clicked start scan", {});
        h.runTimers();

        // Without this the server's _derive_uid() always resolved None and every event was
        // recorded anonymous, even for a signed-in user.
        assert.equal(h.requests[0].headers.Authorization, "Bearer fake-id-token");
    });

    await t.test("no token means no Authorization header, not a broken one", async () => {
        const h = loadTelemetry({ idToken: null });
        await settle();

        h.telemetry.capture("ui", "anonymous visit", {});
        h.runTimers();

        assert.ok(!("Authorization" in h.requests[0].headers));
    });

    await t.test("a page without the auth helper still sends events", async () => {
        const h = loadTelemetry({ hasIdTokenProvider: false });
        await settle();

        h.telemetry.capture("ui", "anonymous visit", {});
        h.runTimers();

        assert.equal(h.requests.length, 1);
        assert.ok(!("Authorization" in h.requests[0].headers));
    });

    await t.test("a failing token lookup does not stop telemetry", async () => {
        const h = loadTelemetry({ idTokenRejects: true });
        await settle();

        h.telemetry.capture("ui", "clicked start scan", {});
        h.runTimers();

        assert.equal(h.requests.length, 1);
        assert.ok(!("Authorization" in h.requests[0].headers));
    });

    await t.test("the client never claims a uid of its own", () => {
        const h = loadTelemetry();

        h.telemetry.capture("ui", "clicked start scan", {});
        h.runTimers();

        // uid is derived server-side from the token; the client must not send a field the
        // server would have to know to ignore.
        assert.ok(!("uid" in h.sentEvents()[0]));
    });
});

test("page unload still delivers", async (t) => {
    await t.test("pagehide sends buffered events via beacon", () => {
        const h = loadTelemetry({ withBeacon: true });

        h.telemetry.capture("ui", "about to leave", {});
        h.listeners.pagehide();

        assert.equal(h.beacons.length, 1);
        assert.equal(h.requests.length, 0, "must not use fetch on unload when a beacon exists");
    });

    await t.test("hiding the tab flushes, staying visible does not", () => {
        const h = loadTelemetry({ withBeacon: true });

        h.telemetry.capture("ui", "switching tabs", {});
        h.listeners.visibilitychange();
        assert.equal(h.beacons.length, 0, "still visible: nothing to flush yet");

        h.document.visibilityState = "hidden";
        h.listeners.visibilitychange();
        assert.equal(h.beacons.length, 1, "hidden tab must flush before it can be discarded");
    });

    await t.test("without sendBeacon it falls back to fetch rather than losing events", () => {
        const h = loadTelemetry({ withBeacon: false });

        h.telemetry.capture("ui", "about to leave", {});
        h.listeners.pagehide();

        assert.equal(h.sentEvents().length, 1);
    });
});

test("telemetry never throws into caller code", async (t) => {
    await t.test("a blocked sessionStorage does not break capture", () => {
        const h = loadTelemetry({ storageThrows: true });

        assert.doesNotThrow(() => h.telemetry.capture("ui", "clicked start scan", {}));
        assert.equal(h.telemetry.getSessionId(), null);
    });

    await t.test("a failing network does not break capture", () => {
        const h = loadTelemetry({ fetchThrows: true });

        assert.doesNotThrow(() => {
            for (let i = 0; i < FLUSH_THRESHOLD + 5; i++) {
                h.telemetry.capture("ui", `event ${i}`, {});
            }
            h.runTimers();
        });
    });

    await t.test("a non-object data payload is normalised, not forwarded", () => {
        const h = loadTelemetry();

        h.telemetry.capture("ui", "clicked", "not-an-object");
        h.runTimers();

        assert.deepEqual(h.sentEvents()[0].data, {});
    });

    await t.test("unhandled rejections are captured as error events", () => {
        const h = loadTelemetry();

        h.listeners.unhandledrejection({ reason: new Error("promise blew up") });
        h.runTimers();

        const event = h.sentEvents()[0];
        assert.equal(event.level, "error");
        assert.equal(event.category, "error");
        assert.match(event.message, /promise blew up/);
    });
});
