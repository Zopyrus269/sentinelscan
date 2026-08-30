from apps.backend.observability.emit import (
    emit_event, emit, get_queue, get_stats, is_enabled,
)
from apps.backend.observability.context import (
    set_context, get_context, clear_context, snapshot, restore, bound, new_trace_id,
)
from apps.backend.observability.flask_hooks import init_app as init_flask_hooks
from apps.backend.observability.logging_bridge import install as install_logging_bridge

def init_app(app: "Flask") -> None:
    """Installs request hooks and the logging bridge. No-op when disabled."""
    if not is_enabled():
        return
    init_flask_hooks(app)
    install_logging_bridge()

def wrap_progress_callback(callback):
    """Wraps the orchestrator's on_progress callback so agent stages are recorded.
    Returns callback unchanged when telemetry is disabled."""
    if not is_enabled():
        return callback
        
    def wrapped(*args, **kwargs):
        # We need to emit an event
        try:
            # Arguments are tool_name, phase, reasoning, action, summary, status, duration
            # The callback might be called with positional or keyword args, we extract what we can
            data = {}
            keys = ["tool_name", "phase", "reasoning", "action", "summary", "status", "duration"]
            for i, val in enumerate(args):
                if i < len(keys):
                    data[keys[i]] = val
            data.update(kwargs)
            
            tool_name = data.get("tool_name", "unknown")
            phase = data.get("phase", "unknown")
            msg = f"AI selected {tool_name}" if phase == "selected" else f"AI {phase} {tool_name}"
            
            # Use 'emit' directly
            emit(
                level="info",
                source="agent",
                category="agent",
                message=msg,
                data=data
            )
        except Exception:
            pass # Never raise into orchestrator
            
        if callback:
            return callback(*args, **kwargs)
            
    return wrapped
