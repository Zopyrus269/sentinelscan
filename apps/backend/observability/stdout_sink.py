import threading
import queue
import json
from apps.backend.observability.emit import get_queue, is_enabled

class StdoutSinkThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="TelemetryStdoutSink")
        self._stop_event = threading.Event()
        
    def run(self):
        q = get_queue()
        while not self._stop_event.is_set():
            try:
                # Wait for up to 1 second for an item
                event = q.get(timeout=1.0)
                try:
                    print(json.dumps(event))
                except Exception:
                    pass
                q.task_done()
            except queue.Empty:
                continue
            except Exception:
                pass
                
    def stop(self):
        self._stop_event.set()

_sink_thread = None

def start_sink():
    """Starts the stdout draining thread if telemetry is enabled."""
    global _sink_thread
    if not is_enabled():
        return
        
    if _sink_thread is None or not _sink_thread.is_alive():
        _sink_thread = StdoutSinkThread()
        _sink_thread.start()

def stop_sink():
    """Stops the stdout draining thread."""
    global _sink_thread
    if _sink_thread is not None:
        _sink_thread.stop()
        _sink_thread = None
