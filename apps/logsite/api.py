"""Developer-only HTTP API for the SentinelScan Log Site.

Routes validate inputs and delegate reads to Workstream B's frozen query layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
import importlib
import logging
from typing import Any, Callable, Optional

from flask import Blueprint, jsonify, request

from apps.logsite.auth import require_auth, require_developer


api_bp = Blueprint("logsite_api", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


STATE_OPERATIONAL = "operational"
STATE_DEGRADED = "degraded"
STATE_DOWN = "down"

ERROR_RATE_DEGRADED = 0.05
ERROR_RATE_DOWN = 0.25

LLM_FAILURE_DEGRADED = 0.05
LLM_FAILURE_DOWN = 0.30

WORKER_DEGRADED = 0.80
WORKER_DOWN = 0.50

VALID_LEVELS = {
    "debug",
    "info",
    "warn",
    "error",
    "fatal",
}

VALID_SOURCES = {
    "frontend",
    "backend",
    "agent",
    "worker",
}

VALID_CATEGORIES = {
    "http",
    "auth",
    "scan",
    "agent",
    "worker",
    "llm",
    "ui",
    "error",
    "health",
}

VALID_GROUP_BY = {
    "day",
    "hour",
}


def _error(
    message: str,
    code: int = 400,
    error_type: str = "Bad Request",
):
    """Return the project's standard JSON error shape."""

    return (
        jsonify(
            {
                "error": error_type,
                "message": message,
                "code": code,
            }
        ),
        code,
    )


def _query_function(
    name: str,
) -> Callable[..., Any]:
    """Resolve a required Workstream B query function.

    Import the fully qualified query module directly.

    This keeps production behaviour strict while allowing isolated
    Workstream C unit tests to substitute
    ``apps.backend.logstore.query`` in ``sys.modules`` even when
    Workstream B is not physically checked out on the C branch.
    """

    try:
        logstore_query = importlib.import_module(
            "apps.backend.logstore.query"
        )

    except (
        ImportError,
        ModuleNotFoundError,
    ) as exc:

        raise RuntimeError(
            "Workstream B logstore query layer is unavailable."
        ) from exc

    fn = getattr(
        logstore_query,
        name,
        None,
    )

    if not callable(fn):
        raise RuntimeError(
            f"Required logstore query function is unavailable: {name}"
        )

    return fn


def _call_query(
    name: str,
    **kwargs: Any,
) -> tuple[Any, Any]:
    """Call one B query function and safely surface integration failures."""

    try:
        result = _query_function(name)(
            **kwargs
        )

        return result, None

    except Exception:
        logger.exception(
            "Log Site query failed: %s",
            name,
        )

        return (
            None,
            _error(
                "Telemetry service is temporarily unavailable.",
                503,
                "Service Unavailable",
            ),
        )


def _parse_iso_date(
    value: Optional[str],
    param_name: str,
) -> Optional[str]:
    """Validate an ISO-8601 datetime parameter."""

    if not value:
        return None

    try:
        datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

    except (
        ValueError,
        AttributeError,
    ) as exc:

        raise ValueError(
            f"Invalid ISO datetime for '{param_name}'."
        ) from exc

    return value


def _state(
    rate: float,
    degraded: float,
    down: float,
) -> str:
    """Map a failure/error rate to a status-board state."""

    if rate > down:
        return STATE_DOWN

    if rate > degraded:
        return STATE_DEGRADED

    return STATE_OPERATIONAL


@api_bp.route(
    "/status",
    methods=["GET"],
)
@require_auth
@require_developer
def get_status():
    """Return component state from exactly one B health query."""

    health, error = _call_query(
        "get_health_snapshot"
    )

    if error:
        return error

    if not isinstance(
        health,
        dict,
    ):
        return _error(
            "Telemetry service returned an invalid health snapshot.",
            503,
            "Service Unavailable",
        )

    try:
        error_rate = float(
            health.get(
                "error_rate"
            )
            or 0.0
        )

    except (
        TypeError,
        ValueError,
    ):
        error_rate = 0.0

    try:
        llm_rate = float(
            health.get(
                "llm_failure_rate"
            )
            or 0.0
        )

    except (
        TypeError,
        ValueError,
    ):
        llm_rate = 0.0

    workers = (
        health.get("workers")
        if isinstance(
            health.get("workers"),
            list,
        )
        else []
    )

    scan_state = _state(
        error_rate,
        ERROR_RATE_DEGRADED,
        ERROR_RATE_DOWN,
    )

    gemini_state = _state(
        llm_rate,
        LLM_FAILURE_DEGRADED,
        LLM_FAILURE_DOWN,
    )

    degraded_workers = []

    for worker in workers:

        if not isinstance(
            worker,
            dict,
        ):
            continue

        try:
            success_rate = float(
                worker.get(
                    "success_rate"
                )
                or 0.0
            )

        except (
            TypeError,
            ValueError,
        ):
            success_rate = 0.0

        if success_rate < WORKER_DEGRADED:
            degraded_workers.append(
                worker
            )

    if not workers:

        worker_state = STATE_OPERATIONAL

        worker_detail = (
            "No worker telemetry in the current window"
        )

    else:

        ratio = (
            len(degraded_workers)
            / len(workers)
        )

        if ratio > WORKER_DOWN:
            worker_state = STATE_DOWN

        elif degraded_workers:
            worker_state = STATE_DEGRADED

        else:
            worker_state = STATE_OPERATIONAL

        if degraded_workers:

            worker_detail = (
                f"{len(degraded_workers)}/{len(workers)} "
                f"workers below {WORKER_DEGRADED:.0%} success"
            )

        else:

            worker_detail = (
                f"{len(workers)} workers reporting normally"
            )

    components = [
        {
            "name": "Web",
            "state": STATE_OPERATIONAL,
            "detail": (
                "Uptime is reported separately "
                "by the external probe"
            ),
        },
        {
            "name": "Scan API",
            "state": scan_state,
            "detail": (
                f"Observed error rate "
                f"{error_rate:.1%}"
            ),
        },
        {
            "name": "Gemini",
            "state": gemini_state,
            "detail": (
                f"Observed failure rate "
                f"{llm_rate:.1%}"
            ),
        },
        {
            "name": "Firestore",
            "state": STATE_OPERATIONAL,
            "detail": (
                "Telemetry query completed"
            ),
        },
        {
            "name": "Workers",
            "state": worker_state,
            "detail": worker_detail,
        },
    ]

    states = {
        component["state"]
        for component
        in components
    }

    if STATE_DOWN in states:
        overall = STATE_DOWN

    elif STATE_DEGRADED in states:
        overall = STATE_DEGRADED

    else:
        overall = STATE_OPERATIONAL

    return jsonify(
        {
            "overall": overall,
            "checked_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "components": components,
        }
    )


@api_bp.route(
    "/uptime",
    methods=["GET"],
)
@require_auth
@require_developer
def get_uptime():
    """Return Workstream B's daily uptime history."""

    raw_days = request.args.get(
        "days",
        "90",
    )

    try:
        days = int(
            raw_days
        )

    except (
        TypeError,
        ValueError,
    ):
        return _error(
            "Parameter 'days' must be an integer from 1 to 366."
        )

    if not 1 <= days <= 366:
        return _error(
            "Parameter 'days' must be an integer from 1 to 366."
        )

    result, error = _call_query(
        "get_uptime_history",
        days=days,
    )

    if error:
        return error

    if not isinstance(
        result,
        list,
    ):
        return _error(
            "Telemetry service returned invalid uptime data.",
            503,
            "Service Unavailable",
        )

    return jsonify(
        result
    )


@api_bp.route(
    "/active-users",
    methods=["GET"],
)
@require_auth
@require_developer
def get_active_users():
    """Return active sessions for a validated time window."""

    raw_window = request.args.get(
        "window",
        "5",
    )

    try:
        window = int(
            raw_window
        )

    except (
        TypeError,
        ValueError,
    ):
        return _error(
            "Parameter 'window' must be an integer from 1 to 1440."
        )

    if not 1 <= window <= 1440:
        return _error(
            "Parameter 'window' must be an integer from 1 to 1440."
        )

    result, error = _call_query(
        "count_active_users",
        window_minutes=window,
    )

    if error:
        return error

    if not isinstance(
        result,
        dict,
    ):
        return _error(
            "Telemetry service returned invalid active-user data.",
            503,
            "Service Unavailable",
        )

    return jsonify(
        result
    )


@api_bp.route(
    "/events",
    methods=["GET"],
)
@require_auth
@require_developer
def get_events():
    """Query events with validated filters and cursor pagination."""

    raw_limit = request.args.get(
        "limit",
        "200",
    )

    try:
        limit = int(
            raw_limit
        )

    except (
        TypeError,
        ValueError,
    ):
        return _error(
            "Parameter 'limit' must be an integer from 1 to 500."
        )

    if limit <= 0:
        return _error(
            "Parameter 'limit' must be an integer from 1 to 500."
        )

    if limit > 500:
        return _error(
            "Limit cannot exceed 500."
        )

    level = request.args.get(
        "level"
    )

    source = request.args.get(
        "source"
    )

    category = request.args.get(
        "category"
    )

    if (
        level
        and level
        not in VALID_LEVELS
    ):
        return _error(
            f"Invalid level '{level}'."
        )

    if (
        source
        and source
        not in VALID_SOURCES
    ):
        return _error(
            f"Invalid source '{source}'."
        )

    if (
        category
        and category
        not in VALID_CATEGORIES
    ):
        return _error(
            f"Invalid category '{category}'."
        )

    try:
        since = _parse_iso_date(
            request.args.get(
                "since"
            ),
            "since",
        )

        until = _parse_iso_date(
            request.args.get(
                "until"
            ),
            "until",
        )

    except ValueError as exc:
        return _error(
            str(exc)
        )

    result, error = _call_query(
        "query_events",
        since=since,
        until=until,
        level=level,
        source=source,
        category=category,
        session_id=request.args.get(
            "session_id"
        ),
        uid=request.args.get(
            "uid"
        ),
        trace_id=request.args.get(
            "trace_id"
        ),
        scan_id=request.args.get(
            "scan_id"
        ),
        cursor=request.args.get(
            "cursor"
        ),
        limit=limit,
    )

    if error:
        return error

    if not isinstance(
        result,
        dict,
    ):
        return _error(
            "Telemetry service returned invalid event data.",
            503,
            "Service Unavailable",
        )

    return jsonify(
        result
    )


@api_bp.route(
    "/sessions",
    methods=["GET"],
)
@require_auth
@require_developer
def get_sessions():
    """List recent sessions using B's summary query."""

    raw_limit = request.args.get(
        "limit",
        "50",
    )

    try:
        limit = int(
            raw_limit
        )

    except (
        TypeError,
        ValueError,
    ):
        return _error(
            "Parameter 'limit' must be an integer from 1 to 500."
        )

    if not 1 <= limit <= 500:
        return _error(
            "Parameter 'limit' must be an integer from 1 to 500."
        )

    try:
        since = _parse_iso_date(
            request.args.get(
                "since"
            ),
            "since",
        )

    except ValueError as exc:
        return _error(
            str(exc)
        )

    result, error = _call_query(
        "list_sessions",
        since=since,
        limit=limit,
    )

    if error:
        return error

    if not isinstance(
        result,
        list,
    ):
        return _error(
            "Telemetry service returned invalid session data.",
            503,
            "Service Unavailable",
        )

    return jsonify(
        result
    )


@api_bp.route(
    "/sessions/<session_id>",
    methods=["GET"],
)
@require_auth
@require_developer
def get_session(
    session_id: str,
):
    """Return one complete session timeline."""

    if not session_id.strip():
        return _error(
            "Missing or invalid session_id."
        )

    result, error = _call_query(
        "get_session_timeline",
        session_id=session_id,
    )

    if error:
        return error

    if not isinstance(
        result,
        dict,
    ):
        return _error(
            "Telemetry service returned invalid timeline data.",
            503,
            "Service Unavailable",
        )

    return jsonify(
        result
    )


@api_bp.route(
    "/traces/<trace_id>",
    methods=["GET"],
)
@require_auth
@require_developer
def get_trace_events(
    trace_id: str,
):
    """Return every event belonging to one trace."""

    if not trace_id.strip():
        return _error(
            "Missing or invalid trace_id."
        )

    result, error = _call_query(
        "get_trace",
        trace_id=trace_id,
    )

    if error:
        return error

    if not isinstance(
        result,
        dict,
    ):
        return _error(
            "Telemetry service returned invalid trace data.",
            503,
            "Service Unavailable",
        )

    return jsonify(
        result
    )


@api_bp.route(
    "/llm-usage",
    methods=["GET"],
)
@require_auth
@require_developer
def get_llm():
    """Return Gemini token and call metrics exposed by B."""

    group_by = request.args.get(
        "group_by",
        "day",
    )

    if group_by not in VALID_GROUP_BY:
        return _error(
            f"Invalid group_by '{group_by}'."
        )

    try:
        since = _parse_iso_date(
            request.args.get(
                "since"
            ),
            "since",
        )

        until = _parse_iso_date(
            request.args.get(
                "until"
            ),
            "until",
        )

    except ValueError as exc:
        return _error(
            str(exc)
        )

    result, error = _call_query(
        "get_llm_usage",
        since=since,
        until=until,
        group_by=group_by,
    )

    if error:
        return error

    if not isinstance(
        result,
        dict,
    ):
        return _error(
            "Telemetry service returned invalid LLM data.",
            503,
            "Service Unavailable",
        )

    return jsonify(
        result
    )


@api_bp.route(
    "/health",
    methods=["GET"],
)
@require_auth
@require_developer
def get_health():
    """Return B's health snapshot."""

    result, error = _call_query(
        "get_health_snapshot"
    )

    if error:
        return error

    if not isinstance(
        result,
        dict,
    ):
        return _error(
            "Telemetry service returned invalid health data.",
            503,
            "Service Unavailable",
        )

    return jsonify(
        result
    )


@api_bp.route(
    "/stats/<date>",
    methods=["GET"],
)
@require_auth
@require_developer
def get_stats_for_date(
    date: str,
):
    """Return B's daily statistics for one YYYY-MM-DD date."""

    try:
        datetime.strptime(
            date,
            "%Y-%m-%d",
        )

    except ValueError:
        return _error(
            "Date must be in YYYY-MM-DD format."
        )

    result, error = _call_query(
        "get_daily_stats",
        date=date,
    )

    if error:
        return error

    if not isinstance(
        result,
        dict,
    ):
        return _error(
            "Telemetry service returned invalid daily statistics.",
            503,
            "Service Unavailable",
        )

    return jsonify(
        result
    )