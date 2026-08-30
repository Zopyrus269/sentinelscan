import logging
import traceback
from apps.backend.observability.emit import is_enabled, emit

class TelemetryHandler(logging.Handler):
    """Routes standard-library log records into the telemetry pipeline."""
    
    def emit(self, record: logging.LogRecord) -> None:
        if not is_enabled():
            return
            
        # Prevent infinite recursion
        if record.name.startswith("apps.backend.observability") or record.name.startswith("apps.backend.logstore"):
            return

        try:
            if record.name.startswith("apps.backend.workers."):
                source = "worker"
                category = "worker"
            elif record.name.startswith("apps.backend.agent."):
                source = "agent"
                category = "agent"
            else:
                source = "backend"
                category = "error" if record.exc_info else "scan"
                
            level_map = {
                logging.DEBUG: "debug",
                logging.INFO: "info",
                logging.WARNING: "warn",
                logging.ERROR: "error",
                logging.CRITICAL: "fatal"
            }
            level = level_map.get(record.levelno, "info")
            
            data = {
                "logger": record.name,
                "func": record.funcName,
                "line": record.lineno
            }
            
            if record.exc_info:
                exc_type, exc_value, exc_tb = record.exc_info
                data["stack"] = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
                
            emit(
                level=level,
                source=source,
                category=category,
                message=record.getMessage(),
                data=data
            )
        except Exception:
            self.handleError(record)

_handler = None

def install(level: int = logging.INFO) -> None:
    global _handler
    if not is_enabled():
        return
        
    if _handler is None:
        _handler = TelemetryHandler()
        _handler.setLevel(level)
        
    logger = logging.getLogger("apps")
    if _handler not in logger.handlers:
        logger.addHandler(_handler)

def uninstall() -> None:
    global _handler
    if _handler is not None:
        logger = logging.getLogger("apps")
        if _handler in logger.handlers:
            logger.removeHandler(_handler)
        _handler = None
