"""
SentinelScan SSL/TLS Worker

Performs a bounded external TLS inspection for an authorized target.

The worker checks:

- TLS connection availability
- certificate trust validation
- hostname validation
- certificate validity period
- certificate issuer / subject where available
- negotiated TLS protocol
- negotiated cipher
- days until certificate expiry

Important behavior:

If the normal verified TLS connection fails because of a certificate
verification problem such as:

- expired certificate
- self-signed certificate
- untrusted issuer
- hostname mismatch
- incomplete trust chain

the worker RETAINS that verification failure as real evidence.

It then attempts an unverified connection only to collect additional
certificate metadata.

Failure of the metadata fallback does NOT erase the original
certificate-verification evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import socket
import ssl
import sys
import tempfile
from typing import Any, Dict, Optional


WORKER_NAME = "ssl"

DEFAULT_PORT = 443

DEFAULT_TIMEOUT = 15.0


# ============================================================
# Response helpers
# ============================================================

def format_success_response(
    data: Dict[str, Any],
) -> Dict[str, Any]:

    return {
        "worker": WORKER_NAME,
        "status": "success",
        "data": data,
        "error": None,
    }


def format_error_response(
    error_message: str,
) -> Dict[str, Any]:

    return {
        "worker": WORKER_NAME,
        "status": "error",
        "data": {},
        "error": error_message,
    }


# ============================================================
# Certificate helpers
# ============================================================

def format_dn(
    dn_sequence: Any,
) -> str:

    if not dn_sequence:

        return ""

    parts = []

    if isinstance(
        dn_sequence,
        (tuple, list),
    ):

        for rdn in dn_sequence:

            if not isinstance(
                rdn,
                (tuple, list),
            ):

                continue

            for item in rdn:

                if (
                    isinstance(
                        item,
                        (tuple, list),
                    )
                    and len(item) == 2
                ):

                    key, value = item

                    parts.append(
                        f"{key}={value}"
                    )

    return ", ".join(parts)


def parse_cert_date(
    date_str: Optional[str],
) -> Optional[datetime]:

    if not date_str:

        return None

    if not isinstance(
        date_str,
        str,
    ):

        return None

    try:

        parsed = datetime.strptime(
            date_str,
            "%b %d %H:%M:%S %Y GMT",
        )

        return parsed.replace(
            tzinfo=timezone.utc
        )

    except ValueError:

        return None


def decode_der_certificate(
    der_bytes: bytes,
) -> Dict[str, Any]:
    """
    Decode a DER certificate using Python's built-in SSL decoder.

    Failure here is intentionally non-fatal.
    """

    if not der_bytes:

        return {}

    temp_path = None

    try:

        pem_text = (
            ssl.DER_cert_to_PEM_cert(
                der_bytes
            )
        )

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".pem",
            delete=False,
        ) as temp_file:

            temp_path = (
                temp_file.name
            )

            temp_file.write(
                pem_text
            )

        decoded = (
            ssl._ssl._test_decode_cert(
                temp_path
            )
        )

        if isinstance(
            decoded,
            dict,
        ):

            return decoded

        return {}

    except Exception:

        return {}

    finally:

        if (
            temp_path
            and os.path.exists(
                temp_path
            )
        ):

            try:

                os.remove(
                    temp_path
                )

            except OSError:

                pass


# ============================================================
# Verification classification
# ============================================================

def classify_verification_failure(
    message: str,
) -> str:

    lowered = str(
        message or ""
    ).lower()

    if "expired" in lowered:

        return (
            "CERTIFICATE_EXPIRED"
        )

    if (
        "not yet valid"
        in lowered
    ):

        return (
            "CERTIFICATE_NOT_YET_VALID"
        )

    if (
        "hostname"
        in lowered
        or "doesn't match"
        in lowered
        or "does not match"
        in lowered
        or "ip address mismatch"
        in lowered
    ):

        return (
            "HOSTNAME_MISMATCH"
        )

    if (
        "self-signed"
        in lowered
        or "self signed"
        in lowered
    ):

        return (
            "SELF_SIGNED_CERTIFICATE"
        )

    if (
        "unable to get local issuer"
        in lowered
        or "unable to get issuer"
        in lowered
        or "certificate verify failed"
        in lowered
    ):

        return (
            "CERTIFICATE_TRUST_FAILURE"
        )

    return (
        "CERTIFICATE_VERIFICATION_FAILED"
    )


# ============================================================
# Verified TLS connection
# ============================================================

def verified_tls_connection(
    target: str,
    port: int,
    timeout: float,
) -> Dict[str, Any]:
    """
    Attempt a fully verified TLS connection.

    Raises SSLCertVerificationError if certificate validation fails.
    """

    context = (
        ssl.create_default_context()
    )

    context.check_hostname = True

    context.verify_mode = (
        ssl.CERT_REQUIRED
    )

    with socket.create_connection(
        (target, port),
        timeout=timeout,
    ) as raw_socket:

        with context.wrap_socket(
            raw_socket,
            server_hostname=target,
        ) as tls_socket:

            certificate = (
                tls_socket.getpeercert()
                or {}
            )

            cipher_info = (
                tls_socket.cipher()
            )

            return {
                "certificate":
                    certificate,

                "protocol":
                    tls_socket.version()
                    or "",

                "cipher":
                    (
                        cipher_info[0]
                        if cipher_info
                        else ""
                    ),
            }


# ============================================================
# Unverified metadata connection
# ============================================================

def unverified_tls_connection(
    target: str,
    port: int,
    timeout: float,
) -> Dict[str, Any]:
    """
    Connect without certificate verification.

    This is ONLY used after a certificate verification failure
    so SentinelScan can retain metadata from the invalid certificate.

    It does not make the connection trusted.
    """

    context = (
        ssl.SSLContext(
            ssl.PROTOCOL_TLS_CLIENT
        )
    )

    context.check_hostname = False

    context.verify_mode = (
        ssl.CERT_NONE
    )

    with socket.create_connection(
        (target, port),
        timeout=timeout,
    ) as raw_socket:

        with context.wrap_socket(
            raw_socket,
            server_hostname=target,
        ) as tls_socket:

            der_certificate = (
                tls_socket.getpeercert(
                    binary_form=True
                )
            )

            decoded_certificate = (
                decode_der_certificate(
                    der_certificate
                    or b""
                )
            )

            cipher_info = (
                tls_socket.cipher()
            )

            return {
                "certificate":
                    decoded_certificate,

                "certificate_present":
                    bool(
                        der_certificate
                    ),

                "protocol":
                    tls_socket.version()
                    or "",

                "cipher":
                    (
                        cipher_info[0]
                        if cipher_info
                        else ""
                    ),
            }


# ============================================================
# Hostname validation helper
# ============================================================

def check_hostname_from_certificate(
    certificate: Dict[str, Any],
    target: str,
) -> Optional[bool]:

    if not certificate:

        return None

    try:

        ssl.match_hostname(
            certificate,
            target,
        )

        return True

    except (
        ssl.CertificateError,
        ValueError,
    ):

        return False

    except Exception:

        return None


# ============================================================
# Build normalized evidence
# ============================================================

def build_certificate_data(
    certificate: Dict[str, Any],
    target: str,
    protocol: str,
    cipher: str,
    certificate_verified: bool,
    verification_error: Optional[str],
    verification_code: Optional[int],
    fallback_metadata_error: Optional[str] = None,
    certificate_present: Optional[bool] = None,
) -> Dict[str, Any]:

    issuer = format_dn(
        certificate.get(
            "issuer"
        )
    )

    subject = format_dn(
        certificate.get(
            "subject"
        )
    )

    serial_number = str(
        certificate.get(
            "serialNumber",
            "",
        )
    )

    valid_from = (
        parse_cert_date(
            certificate.get(
                "notBefore"
            )
        )
    )

    valid_to = (
        parse_cert_date(
            certificate.get(
                "notAfter"
            )
        )
    )

    now = datetime.now(
        timezone.utc
    )

    not_yet_valid = False

    expired = False

    if valid_from:

        not_yet_valid = (
            now < valid_from
        )

    if valid_to:

        expired = (
            now > valid_to
        )

    time_valid: Optional[bool]

    if (
        valid_from is None
        or valid_to is None
    ):

        time_valid = None

    else:

        time_valid = (
            not not_yet_valid
            and not expired
        )

    if valid_to:

        days_until_expiry = (
            valid_to
            - now
        ).days

    else:

        days_until_expiry = None

    hostname_valid = (
        check_hostname_from_certificate(
            certificate,
            target,
        )
    )

    # --------------------------------------------------------
    # Overall certificate validity
    #
    # Verified system trust is authoritative here.
    #
    # If normal certificate verification failed, the
    # certificate must NOT become valid merely because the
    # second unverified metadata connection succeeded.
    # --------------------------------------------------------

    is_valid = bool(
        certificate_verified
        and (
            time_valid
            is not False
        )
        and (
            hostname_valid
            is not False
        )
    )

    validation_issue = None

    if verification_error:

        validation_issue = (
            classify_verification_failure(
                verification_error
            )
        )

    elif expired:

        validation_issue = (
            "CERTIFICATE_EXPIRED"
        )

    elif not_yet_valid:

        validation_issue = (
            "CERTIFICATE_NOT_YET_VALID"
        )

    elif hostname_valid is False:

        validation_issue = (
            "HOSTNAME_MISMATCH"
        )

    return {

        "target":
            target,

        "port":
            None,

        "issuer":
            issuer,

        "subject":
            subject,

        "serial_number":
            serial_number,

        "valid_from":
            (
                valid_from.isoformat()
                if valid_from
                else None
            ),

        "valid_to":
            (
                valid_to.isoformat()
                if valid_to
                else None
            ),

        "days_until_expiry":
            days_until_expiry,

        "protocol":
            protocol,

        "cipher":
            cipher,

        # Core flags
        "certificate_verified":
            certificate_verified,

        "trust_verified":
            certificate_verified,

        "hostname_valid":
            hostname_valid,

        "time_valid":
            time_valid,

        "certificate_expired":
            expired,

        "certificate_not_yet_valid":
            not_yet_valid,

        "certificate_present":
            (
                certificate_present
                if certificate_present
                is not None
                else bool(
                    certificate
                )
            ),

        "is_valid":
            is_valid,

        # Evidence describing why verification failed
        "verification_error":
            verification_error,

        "verification_code":
            verification_code,

        "validation_issue":
            validation_issue,

        "fallback_metadata_error":
            fallback_metadata_error,
    }


# ============================================================
# Main TLS inspection
# ============================================================

def perform_ssl_inspection(
    target: str,
    port: int = DEFAULT_PORT,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:

    if (
        not isinstance(
            target,
            str,
        )
        or not target.strip()
    ):

        return format_error_response(
            "Target host must be a non-empty string."
        )

    clean_target = (
        target.strip()
        .rstrip(".")
    )

    # ========================================================
    # 1. Normal verified connection
    # ========================================================

    try:

        verified = (
            verified_tls_connection(
                clean_target,
                port,
                timeout,
            )
        )

        certificate = (
            verified.get(
                "certificate"
            )
            or {}
        )

        data = (
            build_certificate_data(

                certificate=
                    certificate,

                target=
                    clean_target,

                protocol=
                    verified.get(
                        "protocol"
                    )
                    or "",

                cipher=
                    verified.get(
                        "cipher"
                    )
                    or "",

                certificate_verified=
                    True,

                verification_error=
                    None,

                verification_code=
                    None,

                certificate_present=
                    bool(
                        certificate
                    ),
            )
        )

        data[
            "port"
        ] = port

        return format_success_response(
            data
        )

    # ========================================================
    # Certificate validation failure
    #
    # THIS IS SECURITY EVIDENCE.
    #
    # Do NOT return worker failure here.
    # ========================================================

    except ssl.SSLCertVerificationError as exc:

        verification_message = (
            getattr(
                exc,
                "verify_message",
                None,
            )
            or str(exc)
        )

        verification_code = (
            getattr(
                exc,
                "verify_code",
                None,
            )
        )

        # ----------------------------------------------------
        # Attempt to collect metadata from the same
        # certificate without trusting it.
        # ----------------------------------------------------

        try:

            fallback = (
                unverified_tls_connection(
                    clean_target,
                    port,
                    timeout,
                )
            )

            certificate = (
                fallback.get(
                    "certificate"
                )
                or {}
            )

            data = (
                build_certificate_data(

                    certificate=
                        certificate,

                    target=
                        clean_target,

                    protocol=
                        fallback.get(
                            "protocol"
                        )
                        or "",

                    cipher=
                        fallback.get(
                            "cipher"
                        )
                        or "",

                    certificate_verified=
                        False,

                    verification_error=
                        verification_message,

                    verification_code=
                        verification_code,

                    certificate_present=
                        fallback.get(
                            "certificate_present"
                        ),
                )
            )

            data[
                "port"
            ] = port

            # Critical:
            #
            # verification failure remains authoritative even
            # though we used an unverified socket for metadata.

            data[
                "is_valid"
            ] = False

            return format_success_response(
                data
            )

        # ----------------------------------------------------
        # Metadata fallback failed.
        #
        # Still retain the verified certificate-validation
        # failure instead of incorrectly turning it into
        # worker failure / CVSS N/A.
        # ----------------------------------------------------

        except Exception as fallback_exc:

            data = (
                build_certificate_data(

                    certificate=
                        {},

                    target=
                        clean_target,

                    protocol=
                        "",

                    cipher=
                        "",

                    certificate_verified=
                        False,

                    verification_error=
                        verification_message,

                    verification_code=
                        verification_code,

                    fallback_metadata_error=
                        str(
                            fallback_exc
                        ),

                    certificate_present=
                        None,
                )
            )

            data[
                "port"
            ] = port

            data[
                "is_valid"
            ] = False

            return format_success_response(
                data
            )

    # ========================================================
    # DNS errors
    # ========================================================

    except socket.gaierror as exc:

        return format_error_response(
            (
                f"DNS resolution failed for "
                f"target '{clean_target}': "
                f"{exc}"
            )
        )

    # ========================================================
    # Connection refused
    # ========================================================

    except ConnectionRefusedError as exc:

        return format_error_response(
            (
                f"TLS connection refused for "
                f"target "
                f"'{clean_target}:{port}': "
                f"{exc}"
            )
        )

    # ========================================================
    # Timeout
    # ========================================================

    except (
        socket.timeout,
        TimeoutError,
    ):

        return format_error_response(
            (
                f"TLS connection timed out for "
                f"target "
                f"'{clean_target}:{port}' "
                f"after {timeout} seconds."
            )
        )

    # ========================================================
    # Generic TLS handshake errors
    #
    # Unlike certificate-verification failures, a generic
    # handshake error does NOT prove an invalid certificate.
    # ========================================================

    except ssl.SSLError as exc:

        return format_error_response(
            (
                f"TLS handshake failed for "
                f"target "
                f"'{clean_target}:{port}': "
                f"{exc}"
            )
        )

    # ========================================================
    # Network errors
    # ========================================================

    except OSError as exc:

        return format_error_response(
            (
                f"TLS connection error for "
                f"target "
                f"'{clean_target}:{port}': "
                f"{exc}"
            )
        )

    except Exception as exc:

        return format_error_response(
            (
                "SSL/TLS inspection failed: "
                f"{exc}"
            )
        )


# ============================================================
# Worker entry point
# ============================================================

def run_worker(
    input_payload: Dict[str, Any],
) -> Dict[str, Any]:

    if not isinstance(
        input_payload,
        dict,
    ):

        return format_error_response(
            "Input payload must be a JSON object."
        )

    if "target" not in input_payload:

        return format_error_response(
            (
                "Missing required field "
                "'target' in input payload."
            )
        )

    target = (
        input_payload.get(
            "target"
        )
    )

    if (
        not isinstance(
            target,
            str,
        )
        or not target.strip()
    ):

        return format_error_response(
            (
                "Target domain must be "
                "a non-empty string."
            )
        )

    # --------------------------------------------------------
    # Port
    # --------------------------------------------------------

    port = (
        input_payload.get(
            "port",
            DEFAULT_PORT,
        )
    )

    try:

        port = int(
            port
        )

    except (
        TypeError,
        ValueError,
    ):

        return format_error_response(
            "Port must be a valid integer."
        )

    if not (
        1
        <= port
        <= 65535
    ):

        return format_error_response(
            (
                "Port number must be "
                "between 1 and 65535."
            )
        )

    # --------------------------------------------------------
    # Timeout
    # --------------------------------------------------------

    timeout = (
        input_payload.get(
            "timeout",
            DEFAULT_TIMEOUT,
        )
    )

    try:

        timeout = float(
            timeout
        )

    except (
        TypeError,
        ValueError,
    ):

        return format_error_response(
            "Timeout must be a valid number."
        )

    if timeout <= 0:

        return format_error_response(
            (
                "Timeout must be "
                "a positive number."
            )
        )

    return perform_ssl_inspection(
        target=target,
        port=port,
        timeout=timeout,
    )


# ============================================================
# CLI
# ============================================================

def main() -> None:

    raw_input = ""

    if len(
        sys.argv
    ) > 1:

        raw_input = (
            sys.argv[1]
        )

    elif not sys.stdin.isatty():

        raw_input = (
            sys.stdin.read()
        )

    if not raw_input.strip():

        result = (
            format_error_response(
                "No JSON input supplied."
            )
        )

        print(
            json.dumps(
                result,
                indent=2,
            )
        )

        return

    try:

        payload = (
            json.loads(
                raw_input
            )
        )

    except json.JSONDecodeError as exc:

        result = (
            format_error_response(
                (
                    "Invalid JSON input: "
                    f"{exc}"
                )
            )
        )

        print(
            json.dumps(
                result,
                indent=2,
            )
        )

        return

    result = (
        run_worker(
            payload
        )
    )

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":

    main()