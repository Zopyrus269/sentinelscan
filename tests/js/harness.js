"use strict";

/**
 * Loads apps/frontend/static/js/telemetry.js into a fresh, fully-faked browser environment.
 *
 * telemetry.js is a browser IIFE with module-level state (the event buffer, the current
 * trace, the cached ID token) and it registers window listeners on load. Requiring it once
 * and sharing it between tests would leak all of that across cases, so each call here builds
 * a new `vm` context and evaluates the file into it -- every test gets its own module.
 *
 * Nothing here is a mock of telemetry.js itself: the real file runs unmodified. Only the
 * browser surface underneath it is faked, and only the parts the file actually touches.
 */
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const TELEMETRY_SRC = path.join(
    __dirname, "..", "..", "apps", "frontend", "static", "js", "telemetry.js",
);

/** Lets the background ID-token refresh (a promise chain) settle before asserting. */
function settle() {
    return new Promise((resolve) => setImmediate(resolve));
}

/**
 * @param {object} [options]
 * @param {string|null} [options.idToken]        What getCurrentUserIdToken() resolves to.
 * @param {boolean} [options.hasIdTokenProvider] False simulates a page without auth.js loaded.
 * @param {boolean} [options.idTokenRejects]     True simulates the token lookup failing.
 * @param {boolean} [options.storageThrows]      True simulates sessionStorage being blocked.
 * @param {boolean} [options.fetchThrows]        True simulates fetch() throwing synchronously.
 * @param {boolean} [options.withBeacon]         Whether navigator.sendBeacon exists.
 */
function loadTelemetry(options = {}) {
    const {
        idToken = null,
        hasIdTokenProvider = true,
        idTokenRejects = false,
        storageThrows = false,
        fetchThrows = false,
        withBeacon = false,
    } = options;

    const requests = [];
    const beacons = [];
    const listeners = {};
    const timers = [];
    let idCounter = 0;

    const storage = new Map();
    const sessionStorage = {
        getItem(key) {
            if (storageThrows) throw new Error("sessionStorage is blocked");
            return storage.has(key) ? storage.get(key) : null;
        },
        setItem(key, value) {
            if (storageThrows) throw new Error("sessionStorage is blocked");
            storage.set(key, String(value));
        },
    };

    const navigator = {};
    if (withBeacon) {
        navigator.sendBeacon = (url, blob) => {
            beacons.push({ url, blob });
            return true;
        };
    }

    const sandbox = {
        // Deterministic ids, so tests can assert on identity rather than shape alone.
        crypto: { randomUUID: () => `id-${++idCounter}` },
        sessionStorage,
        navigator,
        document: { visibilityState: "visible" },  // tests mutate this via `handle.document`
        // Node's Blob, needed by the sendBeacon path; not an ECMAScript intrinsic, so the vm
        // context does not get one for free.
        Blob,
        console,
        fetch: (url, init) => {
            if (fetchThrows) throw new Error("network is down");
            requests.push({ url, headers: init.headers, body: JSON.parse(init.body) });
            return Promise.resolve();
        },
        setTimeout: (fn) => {
            timers.push(fn);
            return timers.length;
        },
        clearTimeout: () => {},
    };

    sandbox.window = {
        addEventListener: (name, fn) => { listeners[name] = fn; },
    };
    if (hasIdTokenProvider) {
        sandbox.window.getCurrentUserIdToken = async () => {
            if (idTokenRejects) throw new Error("token lookup failed");
            return idToken;
        };
    }

    const context = vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync(TELEMETRY_SRC, "utf8"), context, {
        filename: TELEMETRY_SRC,
    });

    return {
        telemetry: sandbox.window.SentinelTelemetry,
        window: sandbox.window,
        document: sandbox.document,
        requests,
        beacons,
        listeners,
        storage,
        /** Fires every pending flush timer, as the browser would after FLUSH_INTERVAL_MS. */
        runTimers() {
            const pending = timers.splice(0, timers.length);
            pending.forEach((fn) => fn());
        },
        /** Every event across every request made so far, in send order. */
        sentEvents() {
            return requests.flatMap((request) => request.body.events);
        },
    };
}

module.exports = { loadTelemetry, settle, TELEMETRY_SRC };
