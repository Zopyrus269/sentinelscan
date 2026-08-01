"""SentinelScan SSL Worker module.

This module provides a stateless worker that inspects SSL/TLS certificates and
negotiated TLS parameters for a target host, returning structured JSON output
in accordance with SentinelScan specifications.
"""

from datetime import datetime, timezone
import json
import os
import socket
import ssl
import sys
import tempfile
from typing import Any, Dict, Optional, Tuple


WORKER_NAME = "ssl"
DEFAULT_PORT = 443
DEFAULT_TIMEOUT = 10.0


def format_dn(dn_sequence: Any) -> str:
    """Format a Distinguished Name (DN) tuple sequence into a readable string.

    Args:
        dn_sequence (Any): Sequence of RDN tuples returned by ssl.getpeercert().

    Returns:
        str: Comma-separated string representation (e.g. 'CN=example.com, O=Org').
    """
    if not dn_sequence:
        return ""
    parts = []
    if isinstance(dn_sequence, (tuple, list)):
        for rdn in dn_sequence:
            if isinstance(rdn, (tuple, list)):
                for item in rdn:
                    if isinstance(item, (tuple, list)) and len(item) == 2:
                        key, val = item
                        parts.append(f"{key}={val}")
    return ", ".join(parts)


def parse_cert_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse SSL certificate date string into a UTC datetime object.

    Args:
        date_str (Optional[str]): GMT date string (e.g. 'May 15 00:00:00 2025 GMT').

    Returns:
        Optional[datetime]: Timezone-aware UTC datetime object, or None if invalid.
    """
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        dt = datetime.strptime(date_str, "%b %d %H:%M:%S %Y GMT")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def decode_unverified_cert(der_bytes: bytes) -> Dict[str, Any]:
    """Decode binary DER certificate into a dictionary format.

    Args:
        der_bytes (bytes): Raw binary DER-encoded certificate.

    Returns:
        Dict[str, Any]: Decoded peer certificate dictionary.
    """
    try:
        pem_str = ssl.DER_cert_to_PEM_cert(der_bytes)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
        try:
            tmp_file.write(pem_str.encode("utf-8"))
            tmp_file.close()
            decoded = ssl._ssl._test_decode_cert(tmp_file.name)
            return decoded or {}
        finally:
            if os.path.exists(tmp_file.name):
                os.remove(tmp_file.name)
    except Exception:
        return {}


def format_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Format success output dictionary matching SentinelScan schema.

    Args:
        data (Dict[str, Any]): Extracted SSL certificate data.

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


def fetch_ssl_details(
    target: str, port: int, timeout: float = DEFAULT_TIMEOUT
) -> Tuple[Dict[str, Any], str, str, bool]:
    """Establish SSL connection and retrieve certificate dictionary, protocol, and cipher.

    Attempts verified SSL context connection first. If certificate verification fails
    (e.g. self-signed or expired certificate), falls back to an unverified context
    connection to retrieve certificate metadata.

    Args:
        target (str): Target hostname or IP.
        port (int): Port number.
        timeout (float): Network socket timeout in seconds.

    Returns:
        Tuple[Dict[str, Any], str, str, bool]: Tuple containing:
            - cert (Dict[str, Any]): Parsed certificate dictionary.
            - protocol (str): Negotiated TLS protocol version.
            - cipher (str): Negotiated cipher suite name.
            - cert_verified (bool): True if verified by default SSL context, False otherwise.

    Raises:
        socket.gaierror: On DNS resolution failure.
        ConnectionRefusedError: On connection refused.
        socket.timeout: On connection timeout.
        ssl.SSLError: On fatal SSL handshake/protocol failure.
    """
    cert: Dict[str, Any] = {}
    protocol: str = ""
    cipher: str = ""
    cert_verified: bool = False

    # 1. Attempt verified connection
    try:
        context = ssl.create_default_context()
        with socket.create_connection((target, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=target) as sslsock:
                cert = sslsock.getpeercert() or {}
                protocol = sslsock.version() or ""
                cipher_info = sslsock.cipher()
                cipher = cipher_info[0] if cipher_info else ""
                cert_verified = True
                return cert, protocol, cipher, cert_verified
    except (ssl.SSLCertVerificationError, ssl.SSLError) as ssl_err:
        # 2. Fallback to unverified context for self-signed or expired certificates
        try:
            unverified_ctx = ssl.create_default_context()
            unverified_ctx.check_hostname = False
            unverified_ctx.verify_mode = ssl.CERT_NONE

            with socket.create_connection((target, port), timeout=timeout) as sock:
                with unverified_ctx.wrap_socket(sock, server_hostname=target) as sslsock:
                    raw_der = sslsock.getpeercert(binary_form=True)
                    if raw_der:
                        cert = decode_unverified_cert(raw_der)
                    protocol = sslsock.version() or ""
                    cipher_info = sslsock.cipher()
                    cipher = cipher_info[0] if cipher_info else ""
                    cert_verified = False
                    return cert, protocol, cipher, cert_verified
        except Exception:
            raise ssl_err


def perform_ssl_inspection(
    target: str, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """Execute SSL/TLS inspection for target host, port, and timeout.

    Args:
        target (str): Target domain name or IP address.
        port (int): Network port number.
        timeout (float): Connection timeout in seconds.

    Returns:
        Dict[str, Any]: Standardized response dictionary.
    """
    if not target or not isinstance(target, str) or not target.strip():
        return format_error_response("Target host must be a non-empty string.")

    clean_target = target.strip()

    try:
        cert, protocol, cipher, cert_verified = fetch_ssl_details(
            clean_target, port, timeout
        )
    except socket.gaierror as err:
        return format_error_response(
            f"DNS resolution failed for target '{clean_target}': {str(err)}"
        )
    except ConnectionRefusedError as err:
        return format_error_response(
            f"Connection refused for target '{clean_target}:{port}': {str(err)}"
        )
    except (socket.timeout, TimeoutError):
        return format_error_response(
            f"Connection timed out for target '{clean_target}:{port}' after {timeout}s."
        )
    except ssl.SSLError as err:
        return format_error_response(
            f"SSL handshake failed for target '{clean_target}:{port}': {str(err)}"
        )
    except (socket.error, OSError) as err:
        return format_error_response(
            f"Connection error for target '{clean_target}:{port}': {str(err)}"
        )
    except Exception as err:
        return format_error_response(f"SSL inspection failed: {str(err)}")

    if not cert:
        return format_error_response(
            f"No SSL certificate retrieved for target '{clean_target}:{port}'."
        )

    # Extract required fields
    issuer_str = format_dn(cert.get("issuer"))
    subject_str = format_dn(cert.get("subject"))
    serial_number = str(cert.get("serialNumber", ""))

    valid_from_dt = parse_cert_date(cert.get("notBefore"))
    valid_to_dt = parse_cert_date(cert.get("notAfter"))

    now_utc = datetime.now(timezone.utc)
    is_time_valid = bool(
        valid_from_dt and valid_to_dt and valid_from_dt <= now_utc <= valid_to_dt
    )
    is_valid = cert_verified and is_time_valid

    days_until_expiry = (valid_to_dt - now_utc).days if valid_to_dt else 0

    data = {
        "issuer": issuer_str,
        "subject": subject_str,
        "valid_from": valid_from_dt.isoformat() if valid_from_dt else None,
        "valid_to": valid_to_dt.isoformat() if valid_to_dt else None,
        "serial_number": serial_number,
        "protocol": protocol,
        "cipher": cipher,
        "is_valid": is_valid,
        "days_until_expiry": days_until_expiry,
    }

    return format_success_response(data)


def run_worker(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate input payload schema and execute worker task.

    Args:
        input_payload (Dict[str, Any]): Input payload dictionary containing 'target', optional 'port', and optional 'timeout'.

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

    port = input_payload.get("port", DEFAULT_PORT)
    try:
        port_int = int(port)
        if not (1 <= port_int <= 65535):
            return format_error_response("Port number must be between 1 and 65535.")
    except (ValueError, TypeError):
        return format_error_response("Port must be a valid integer.")

    timeout = input_payload.get("timeout", DEFAULT_TIMEOUT)
    try:
        timeout_float = float(timeout)
        if timeout_float <= 0:
            return format_error_response("Timeout must be a positive number.")
    except (ValueError, TypeError):
        return format_error_response("Timeout must be a valid number.")

    return perform_ssl_inspection(target, port_int, timeout_float)


def main() -> None:
    """CLI Entry point for executing the SSL worker.

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
