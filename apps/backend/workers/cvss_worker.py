"""SentinelScan CVSS Worker module.

This module provides a stateless worker that validates CVSS v3.1 base metrics
provided by the AI Agent and calculates the official FIRST CVSS v3.1 Base Score.
It returns structured JSON output in accordance with SentinelScan specifications.

The worker does NOT infer vulnerabilities, interpret findings, or assign metrics.
All base metrics are provided externally; this worker only validates and computes.
"""

import json
import math
import sys
from typing import Any, Dict, Optional, Tuple


WORKER_NAME = "cvss"

# ── Official CVSS v3.1 metric value mappings ─────────────────────────────────

VALID_METRICS: Dict[str, Tuple[str, ...]] = {
    "AV": ("N", "A", "L", "P"),
    "AC": ("L", "H"),
    "PR": ("N", "L", "H"),
    "UI": ("N", "R"),
    "S":  ("U", "C"),
    "C":  ("N", "L", "H"),
    "I":  ("N", "L", "H"),
    "A":  ("N", "L", "H"),
}

REQUIRED_METRIC_KEYS = ("AV", "AC", "PR", "UI", "S", "C", "I", "A")

AV_WEIGHTS: Dict[str, float] = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
AC_WEIGHTS: Dict[str, float] = {"L": 0.77, "H": 0.44}
UI_WEIGHTS: Dict[str, float] = {"N": 0.85, "R": 0.62}

# PR weights depend on Scope
PR_WEIGHTS_UNCHANGED: Dict[str, float] = {"N": 0.85, "L": 0.62, "H": 0.27}
PR_WEIGHTS_CHANGED: Dict[str, float] = {"N": 0.85, "L": 0.68, "H": 0.50}

CIA_WEIGHTS: Dict[str, float] = {"N": 0.00, "L": 0.22, "H": 0.56}


def roundup(value: float) -> float:
    """Round up to one decimal place per CVSS v3.1 specification.

    The smallest number, specified to one decimal place, that is equal to
    or higher than its input. E.g. Roundup(4.02) = 4.1; Roundup(4.00) = 4.0.

    Args:
        value (float): Input score value.

    Returns:
        float: Score rounded up to one decimal place.
    """
    return math.ceil(value * 10) / 10.0


def validate_metrics(base_metrics: Dict[str, str]) -> Optional[str]:
    """Validate that all required CVSS v3.1 base metrics are present and valid.

    Args:
        base_metrics (Dict[str, str]): Dictionary of metric abbreviations to values.

    Returns:
        Optional[str]: Error message string if validation fails, None if valid.
    """
    if not isinstance(base_metrics, dict):
        return "base_metrics must be a JSON object."

    for key in REQUIRED_METRIC_KEYS:
        if key not in base_metrics:
            return f"Missing required metric '{key}'."

    for key in REQUIRED_METRIC_KEYS:
        value = base_metrics[key]
        if not isinstance(value, str):
            return f"Metric '{key}' value must be a string, got {type(value).__name__}."
        upper_val = value.upper()
        if upper_val not in VALID_METRICS[key]:
            allowed = ", ".join(VALID_METRICS[key])
            return f"Invalid value '{value}' for metric '{key}'. Allowed: {allowed}."

    return None


def build_vector_string(base_metrics: Dict[str, str]) -> str:
    """Build the official CVSS v3.1 vector string from base metrics.

    Args:
        base_metrics (Dict[str, str]): Validated metric abbreviations to values.

    Returns:
        str: CVSS vector string (e.g. 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H').
    """
    parts = [f"{key}:{base_metrics[key].upper()}" for key in REQUIRED_METRIC_KEYS]
    return "CVSS:3.1/" + "/".join(parts)


def calculate_impact_subscore(
    conf: str, integ: str, avail: str, scope: str
) -> float:
    """Calculate the CVSS v3.1 Impact sub-score.

    Args:
        conf (str): Confidentiality impact value (N, L, H).
        integ (str): Integrity impact value (N, L, H).
        avail (str): Availability impact value (N, L, H).
        scope (str): Scope value (U or C).

    Returns:
        float: Calculated impact sub-score.
    """
    iss = 1.0 - (
        (1.0 - CIA_WEIGHTS[conf.upper()])
        * (1.0 - CIA_WEIGHTS[integ.upper()])
        * (1.0 - CIA_WEIGHTS[avail.upper()])
    )

    if scope.upper() == "U":
        return 6.42 * iss
    else:
        return 7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15)


def calculate_exploitability_subscore(
    av: str, ac: str, pr: str, ui: str, scope: str
) -> float:
    """Calculate the CVSS v3.1 Exploitability sub-score.

    Args:
        av (str): Attack Vector value.
        ac (str): Attack Complexity value.
        pr (str): Privileges Required value.
        ui (str): User Interaction value.
        scope (str): Scope value (determines PR weight lookup).

    Returns:
        float: Calculated exploitability sub-score.
    """
    pr_weights = PR_WEIGHTS_CHANGED if scope.upper() == "C" else PR_WEIGHTS_UNCHANGED

    return (
        8.22
        * AV_WEIGHTS[av.upper()]
        * AC_WEIGHTS[ac.upper()]
        * pr_weights[pr.upper()]
        * UI_WEIGHTS[ui.upper()]
    )


def calculate_base_score(base_metrics: Dict[str, str]) -> float:
    """Calculate the official CVSS v3.1 Base Score from validated metrics.

    Implements the FIRST CVSS v3.1 specification equations exactly.

    Args:
        base_metrics (Dict[str, str]): Validated metric abbreviations to values.

    Returns:
        float: CVSS v3.1 Base Score rounded per specification (0.0–10.0).
    """
    m = {k: v.upper() for k, v in base_metrics.items()}

    impact = calculate_impact_subscore(m["C"], m["I"], m["A"], m["S"])
    exploitability = calculate_exploitability_subscore(
        m["AV"], m["AC"], m["PR"], m["UI"], m["S"]
    )

    if impact <= 0:
        return 0.0

    if m["S"] == "U":
        score = roundup(min(impact + exploitability, 10.0))
    else:
        score = roundup(min(1.08 * (impact + exploitability), 10.0))

    return score


def determine_severity(score: float) -> str:
    """Map a CVSS v3.1 Base Score to its qualitative severity rating.

    Args:
        score (float): CVSS Base Score (0.0–10.0).

    Returns:
        str: Severity string (NONE, LOW, MEDIUM, HIGH, or CRITICAL).
    """
    if score == 0.0:
        return "NONE"
    if score <= 3.9:
        return "LOW"
    if score <= 6.9:
        return "MEDIUM"
    if score <= 8.9:
        return "HIGH"
    return "CRITICAL"


def format_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Format success output dictionary matching SentinelScan schema.

    Args:
        data (Dict[str, Any]): Calculated CVSS data.

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


def run_worker(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate input payload, compute CVSS v3.1 Base Score, and return result.

    Args:
        input_payload (Dict[str, Any]): Input dictionary containing 'base_metrics'.

    Returns:
        Dict[str, Any]: Standardized JSON-serializable response payload.
    """
    if not isinstance(input_payload, dict):
        return format_error_response("Input payload must be a JSON object.")

    if "base_metrics" not in input_payload:
        return format_error_response(
            "Missing required field 'base_metrics' in input payload."
        )

    base_metrics = input_payload["base_metrics"]
    validation_error = validate_metrics(base_metrics)
    if validation_error:
        return format_error_response(validation_error)

    vector = build_vector_string(base_metrics)
    score = calculate_base_score(base_metrics)
    severity = determine_severity(score)

    data = {
        "vector": vector,
        "base_score": score,
        "severity": severity,
    }

    return format_success_response(data)


def main() -> None:
    """CLI Entry point for executing the CVSS worker.

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
