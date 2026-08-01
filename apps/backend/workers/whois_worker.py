"""SentinelScan WHOIS Worker module.

This module provides a stateless worker that performs WHOIS domain lookups using
python-whois and returns structured JSON output in accordance with SentinelScan specifications.
"""

from datetime import datetime
import json
import sys
from typing import Any, Dict
import whois


WORKER_NAME = "whois"


def serialize_value(val: Any) -> Any:
    """Convert Python objects into JSON-serializable values."""

    if val is None:
        return None

    if isinstance(val, (str, int, float, bool)):
        return val

    if isinstance(val, datetime):
        return val.isoformat()

    if isinstance(val, (list, tuple, set)):
        return [serialize_value(item) for item in val]

    if isinstance(val, dict):
        return {str(k): serialize_value(v) for k, v in val.items()}

    return str(val)


def extract_whois_fields(whois_entry: Any) -> Dict[str, Any]:
    """Extract specified WHOIS fields from a python-whois entry object.

    Args:
        whois_entry (Any): The WhoisEntry object returned by whois.whois().

    Returns:
        Dict[str, Any]: Extracted and serialized fields dictionary containing:
            - registrar
            - creation_date
            - expiration_date
            - updated_date
            - domain_name
            - name_servers
            - status
    """
    WHOIS_FIELDS = (
    "registrar",
    "creation_date",
    "expiration_date",
    "updated_date",
    "domain_name",
    "name_servers",
    "status",
)

    extracted_data: Dict[str, Any] = {}
    for field in WHOIS_FIELDS:
        raw_val = getattr(whois_entry, field, None)
        if raw_val is None and isinstance(whois_entry, dict):
            raw_val = whois_entry.get(field)
        extracted_data[field] = serialize_value(raw_val)

    return extracted_data


def format_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Format success output dictionary matching SentinelScan schema.

    Args:
        data (Dict[str, Any]): Extracted WHOIS data.

    Returns:
        Dict[str, Any]: Standardized success payload.
    """
    return {
        "worker": WORKER_NAME,
        "status": "success",
        "data": data,
        "error": None,
    }


def format_error_response(error_message: str) -> Dict[str, Any]:
    """Format error output dictionary matching SentinelScan schema.

    Args:
        error_message (str): Detailed error message.

    Returns:
        Dict[str, Any]: Standardized error payload.
    """
    return {
        "worker": WORKER_NAME,
        "status": "error",
        "data": {},
        "error": error_message,
    }


def perform_whois_lookup(target: str) -> Dict[str, Any]:
    """Execute WHOIS lookup for a given target domain.

    Args:
        target (str): Target domain name or IP address.

    Returns:
        Dict[str, Any]: Standardized response dictionary.
    """
    if not target or not isinstance(target, str) or not target.strip():
        return format_error_response("Target domain must be a non-empty string.")

    clean_target = target.strip()

    try:
        whois_entry = whois.whois(clean_target)
        if not whois_entry:
            return format_error_response(f"No WHOIS data returned for target '{clean_target}'.")

        data = extract_whois_fields(whois_entry)
        return format_success_response(data)
    except Exception as exc:
        return format_error_response(f"WHOIS lookup failed: {str(exc)}")


def run_worker(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate input payload schema and execute worker task.

    Args:
        input_payload (Dict[str, Any]): Input dictionary expected to contain 'target'.

    Returns:
        Dict[str, Any]: Standardized JSON-serializable response payload.
    """
    if not isinstance(input_payload, dict):
        return format_error_response("Input payload must be a JSON object.")

    if "target" not in input_payload:
        return format_error_response("Missing required field 'target' in input payload.")

    target = input_payload.get("target")
    if not isinstance(target, str) or not target.strip():
        return format_error_response("Target domain must be a non-empty string.")

    return perform_whois_lookup(target)


def main() -> None:
    """CLI Entry point for executing the WHOIS worker.

    Reads JSON payload from CLI command-line argument or stdin and outputs
    structured JSON to standard output.
    """
    input_str = ""
    if len(sys.argv) > 1:
        input_str = sys.argv[1]
    elif not sys.stdin.isatty():
        input_str = sys.stdin.read()

    if not input_str.strip():
        result = format_error_response("No input provided via CLI argument or stdin.")
        print(json.dumps(result, indent=4))
        return

    try:
        input_payload = json.loads(input_str)
    except json.JSONDecodeError as err:
        result = format_error_response(f"Invalid JSON input: {str(err)}")
        print(json.dumps(result, indent=4))
        return

    result = run_worker(input_payload)
    print(json.dumps(result, indent=4))


if __name__ == "__main__":
    main()
