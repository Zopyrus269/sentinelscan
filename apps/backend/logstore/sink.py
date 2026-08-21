"""Background pipeline that drains a bounded queue and batches events into a sink backend.

This is what keeps Workstream A's ``emit_event()`` non-blocking: it only ever appends to
an in-process ``queue.Queue`` (see ``apps/backend/observability/emit.py``). Everything that
can be slow -- Firestore writes, retries, backoff -- happens here, on this thread, never on
a request thread.
"""
import logging
import queue
import signal
import threading
import time
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

DEFAULT_FLUSH_COUNT = 100
DEFAULT_FLUSH_INTERVAL_SECONDS = 5.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 1.0
DEFAULT_POLL_TIMEOUT_SECONDS = 1.0


class SinkBackend(Protocol):
    """A pluggable destination for batched events (e.g. Firestore, stdout)."""

    def write_batch(self, events: List[Dict[str, Any]]) -> None:
        """Persists one batch of events. May raise; the sink thread retries with backoff."""
        ...


class SinkThread(threading.Thread):
    """Drains a queue, flushing batches to a backend at a count or time threshold.

    A batch is flushed when either ``flush_count`` events have accumulated or
    ``flush_interval_seconds`` have elapsed since the first event in the current batch,
    whichever comes first. A backend failure is retried with exponential backoff up to
    ``max_retries`` times; if it still fails, the batch is dropped so the thread keeps
    draining rather than growing unbounded memory or wedging on a dead backend. A
    persistent backend outage can therefore never block or crash this thread.
    """

    def __init__(
        self,
        source_queue: "queue.Queue[Dict[str, Any]]",
        backend: SinkBackend,
        flush_count: int = DEFAULT_FLUSH_COUNT,
        flush_interval_seconds: float = DEFAULT_FLUSH_INTERVAL_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
        poll_timeout_seconds: float = DEFAULT_POLL_TIMEOUT_SECONDS,
    ) -> None:
        super().__init__(name="logstore-sink", daemon=True)
        self._queue = source_queue
        self._backend = backend
        self._flush_count = flush_count
        self._flush_interval = flush_interval_seconds
        self._max_retries = max_retries
        self._backoff_base = backoff_base_seconds
        self._poll_timeout = poll_timeout_seconds
        self._stop_event = threading.Event()
        self._buffer: List[Dict[str, Any]] = []
        self._buffer_started_at: Optional[float] = None

    def stop(self, drain: bool = True) -> None:
        """Signals the thread to stop.

        If `drain` is True (default), blocks until it has flushed whatever remains
        buffered and exited -- this is what a SIGTERM handler calls so Render shutting
        the process down doesn't lose the last few seconds of events.
        """
        self._stop_event.set()
        if drain:
            self.join(timeout=self._flush_interval + 5.0)

    def run(self) -> None:
        while not self._stop_event.is_set():
            self._poll_once()
        self._drain_remaining()
        self._flush()

    def _poll_once(self) -> None:
        try:
            event = self._queue.get(timeout=self._poll_timeout)
        except queue.Empty:
            event = None

        if event is not None:
            self._append(event)

        if self._should_flush():
            self._flush()

    def _drain_remaining(self) -> None:
        """Non-blocking sweep of whatever is immediately available, for a final flush."""
        while True:
            try:
                self._append(self._queue.get_nowait())
            except queue.Empty:
                return

    def _append(self, event: Dict[str, Any]) -> None:
        if not self._buffer:
            self._buffer_started_at = time.monotonic()
        self._buffer.append(event)

    def _should_flush(self) -> bool:
        if not self._buffer:
            return False
        if len(self._buffer) >= self._flush_count:
            return True
        elapsed = time.monotonic() - self._buffer_started_at
        return elapsed >= self._flush_interval

    def _flush(self) -> None:
        if not self._buffer:
            return
        batch, self._buffer = self._buffer, []
        self._buffer_started_at = None
        self._write_with_retry(batch)

    def _write_with_retry(self, batch: List[Dict[str, Any]]) -> None:
        attempt = 0
        while True:
            try:
                self._backend.write_batch(batch)
                return
            except Exception:
                attempt += 1
                if attempt > self._max_retries:
                    logger.error(
                        "logstore sink: dropping a batch of %d events after %d failed attempts",
                        len(batch), attempt, exc_info=True,
                    )
                    return
                delay = self._backoff_base * (2 ** (attempt - 1))
                # Interruptible sleep: a stop() mid-backoff doesn't stall shutdown.
                if self._stop_event.wait(timeout=delay):
                    try:
                        self._backend.write_batch(batch)
                    except Exception:
                        logger.error(
                            "logstore sink: dropping a batch of %d events during shutdown",
                            len(batch), exc_info=True,
                        )
                    return


_sink_thread: Optional[SinkThread] = None
_sigterm_installed = False


def start(source_queue: "queue.Queue[Dict[str, Any]]", backend: SinkBackend, **kwargs: Any) -> SinkThread:
    """Starts the module-level sink thread and installs a graceful-drain SIGTERM handler.

    Must be called from the main thread the first time, since signal handler
    registration requires it; a second call replaces the running thread reference
    without re-registering the handler.
    """
    global _sink_thread, _sigterm_installed
    _sink_thread = SinkThread(source_queue, backend, **kwargs)
    _sink_thread.start()

    if not _sigterm_installed:
        try:
            signal.signal(signal.SIGTERM, _handle_sigterm)
            _sigterm_installed = True
        except (ValueError, OSError):
            # Not the main thread, or the platform doesn't support it -- best effort.
            pass
    return _sink_thread


def stop(drain: bool = True) -> None:
    """Stops the module-level sink thread, if one is running."""
    if _sink_thread is not None:
        _sink_thread.stop(drain=drain)


def _handle_sigterm(signum: int, frame: Any) -> None:
    stop(drain=True)
