"""Authenticated uptime-probe ingest for the SentinelScan Log Site."""

from __future__ import annotations

from datetime import datetime
import hmac
import importlib
import logging
import os
from typing import Any, Callable

from flask import Blueprint, jsonify, request


probe_bp = Blueprint(
    "probe_routes",
    __name__,
    url_prefix="/api",
)

logger = logging.getLogger(
    __name__
)

ALLOWED_COMPONENTS = {
    "web",
}


def _get_query_fn(
    name: str,
) -> Callable[..., Any]:
    """Resolve one required Workstream B query function.

    This intentionally provides a small unit-test seam so
    Workstream C can be tested independently before B is merged.
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


def _query_function(
    name: str,
) -> Callable[..., Any]:
    """Backward-compatible alias for Workstream B query resolution."""

    return _get_query_fn(
        name
    )


def _error(
    message: str,
    code: int,
    kind: str,
):
    """Return the standard Log Site JSON error response."""

    return (
        jsonify(
            {
                "error": kind,
                "message": message,
                "code": code,
            }
        ),
        code,
    )


def _valid_timestamp(
    value: Any,
) -> bool:
    """Return True only for a timezone-aware ISO-8601 timestamp."""

    if not isinstance(
        value,
        str,
    ):
        return False

    try:
        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        return (
            parsed.tzinfo
            is not None
        )

    except ValueError:
        return False


@probe_bp.route(
    "/probe",
    methods=["POST"],
)
def record_probe():
    """Validate and persist one scheduled external uptime probe."""

    supplied = request.headers.get(
        "X-Probe-Token",
        "",
    )

    expected = os.environ.get(
        "LOGSITE_PROBE_TOKEN",
        "",
    )

    if (
        not supplied
        or not expected
        or not hmac.compare_digest(
            supplied.encode(),
            expected.encode(),
        )
    ):
        return _error(
            "Invalid or missing probe token.",
            401,
            "Unauthorized",
        )

    data = request.get_json(
        silent=True
    )

    if not isinstance(
        data,
        dict,
    ):
        return _error(
            "Payload must be a JSON object.",
            400,
            "Bad Request",
        )

    required = {
        "component",
        "ok",
        "status",
        "latency_ms",
        "checked_at",
    }

    if set(data) != required:
        return _error(
            "Probe payload must contain exactly the required fields.",
            400,
            "Bad Request",
        )

    if (
        data["component"]
        not in ALLOWED_COMPONENTS
    ):
        return _error(
            "Unsupported probe component.",
            400,
            "Bad Request",
        )

    if type(
        data["ok"]
    ) is not bool:
        return _error(
            "'ok' must be boolean.",
            400,
            "Bad Request",
        )

    if (
        type(
            data["status"]
        )
        is not int
        or not 0
        <= data["status"]
        <= 599
    ):
        return _error(
            "'status' must be an integer from 0 to 599.",
            400,
            "Bad Request",
        )

    latency = data[
        "latency_ms"
    ]

    if (
        isinstance(
            latency,
            bool,
        )
        or not isinstance(
            latency,
            (int, float),
        )
        or latency < 0
    ):
        return _error(
            "'latency_ms' must be a non-negative number.",
            400,
            "Bad Request",
        )

    if not _valid_timestamp(
        data["checked_at"]
    ):
        return _error(
            "'checked_at' must be a timezone-aware ISO timestamp.",
            400,
            "Bad Request",
        )

    try:
        record_fn = _get_query_fn(
            "record_uptime_probe"
        )

        record_fn(
            data
        )

    except Exception:
        logger.exception(
            "Unable to record uptime probe"
        )

        return _error(
            "Telemetry service is temporarily unavailable.",
            503,
            "Service Unavailable",
        )

    return "", 204