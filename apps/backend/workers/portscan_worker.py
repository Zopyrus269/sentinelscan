"""
SentinelScan - Bounded Port Scan Worker

Performs a small authorized TCP port assessment.

Primary method:
    Nmap TCP connect scan (-sT)

Fallback:
    Native Python TCP socket checks

The worker does NOT:
    - exploit services
    - perform UDP scanning
    - perform OS fingerprinting
    - perform banner grabbing
    - scan all 65,535 ports
"""

from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# python-nmap is optional.
# SentinelScan must still work if nmap.exe is not installed.
try:
    import nmap
except Exception:
    nmap = None


WORKER_NAME = "port_scan"

# Keep this bounded for the SentinelScan passive/lightweight assessment.
DEFAULT_PORTS = (
    "21,22,25,53,80,110,143,443,445,"
    "993,995,3306,3389,5432,5900,6379,8080,8443"
)

MAX_PORTS = 100

SOCKET_TIMEOUT_SECONDS = 1.25
MAX_SOCKET_WORKERS = 20

NMAP_HOST_TIMEOUT = "45s"


# ---------------------------------------------------------------------
# Target handling
# ---------------------------------------------------------------------

def _normalize_target(target: str) -> str:
    """
    Accepts:

        example.com
        www.example.com
        https://example.com
        https://example.com/path

    and returns:

        example.com
    """

    value = str(target or "").strip()

    if not value:
        return ""

    parsed = urlparse(
        value if "://" in value else f"//{value}"
    )

    if parsed.hostname:
        return parsed.hostname.strip().rstrip(".")

    return (
        value
        .split("/")[0]
        .split(":")[0]
        .strip()
        .rstrip(".")
    )


# ---------------------------------------------------------------------
# Port parsing
# ---------------------------------------------------------------------

def _parse_ports(port_spec: Optional[str]) -> List[int]:

    text = str(port_spec or DEFAULT_PORTS).strip()

    ports: List[int] = []

    for part in text.split(","):

        part = part.strip()

        if not part:
            continue

        # Allow small ranges, e.g. 80-90
        if "-" in part:

            left, right = part.split("-", 1)

            start = int(left.strip())
            end = int(right.strip())

            if start > end:
                start, end = end, start

            for port in range(start, end + 1):

                if 1 <= port <= 65535 and port not in ports:

                    ports.append(port)

                    if len(ports) >= MAX_PORTS:
                        return ports

        else:

            port = int(part)

            if 1 <= port <= 65535 and port not in ports:

                ports.append(port)

                if len(ports) >= MAX_PORTS:
                    return ports

    if not ports:
        raise ValueError("No valid TCP ports supplied.")

    return ports


# ---------------------------------------------------------------------
# Service name
# ---------------------------------------------------------------------

def _service_name(port: int) -> str:

    try:
        return socket.getservbyport(port, "tcp")

    except OSError:
        return "unknown"


# ---------------------------------------------------------------------
# DNS resolution
# ---------------------------------------------------------------------

def _resolve_target(host: str) -> List[str]:

    addresses: List[str] = []

    results = socket.getaddrinfo(
        host,
        None,
        type=socket.SOCK_STREAM,
    )

    for result in results:

        address = result[4][0]

        if address not in addresses:
            addresses.append(address)

    return addresses


# ---------------------------------------------------------------------
# Nmap scan
# ---------------------------------------------------------------------

def _scan_with_nmap(
    host: str,
    ports: List[int],
) -> Dict[str, Any]:

    if nmap is None:
        raise RuntimeError(
            "python-nmap package is unavailable."
        )

    # IMPORTANT:
    # This line can fail if nmap.exe itself is not installed.
    scanner = nmap.PortScanner()

    port_string = ",".join(
        str(port) for port in ports
    )

    # TCP connect scan.
    #
    # -sT avoids administrator/root requirement.
    # -Pn prevents ICMP blocking from making a website appear offline.
    # -T3 keeps it moderate.
    # --max-retries 1 keeps it bounded.
    # --host-timeout prevents hanging.
    scanner.scan(
        hosts=host,
        ports=port_string,
        arguments=(
            "-sT "
            "-Pn "
            "-T3 "
            "--max-retries 1 "
            f"--host-timeout {NMAP_HOST_TIMEOUT}"
        ),
    )

    hosts = scanner.all_hosts()

    # A firewall/CDN may produce no host record.
    # That is not a worker crash.
    if not hosts:

        return {
            "host_status": "unknown",
            "scan_type": "connect",
            "scanner_backend": "nmap",
            "open_ports": [],
        }

    host_key = (
        host
        if host in hosts
        else hosts[0]
    )

    host_data = scanner[host_key]

    open_ports: List[Dict[str, Any]] = []

    for protocol in host_data.all_protocols():

        if protocol != "tcp":
            continue

        for port in sorted(
            host_data[protocol].keys()
        ):

            info = host_data[protocol][port]

            if info.get("state") == "open":

                open_ports.append(
                    {
                        "port": int(port),
                        "service": (
                            info.get("name")
                            or _service_name(int(port))
                        ),
                        "state": "open",
                    }
                )

    try:
        host_status = host_data.state() or "unknown"

    except Exception:
        host_status = "unknown"

    return {
        "host_status": host_status,
        "scan_type": "connect",
        "scanner_backend": "nmap",
        "open_ports": open_ports,
    }


# ---------------------------------------------------------------------
# Python socket fallback
# ---------------------------------------------------------------------

def _probe_port(
    host: str,
    port: int,
) -> Optional[Dict[str, Any]]:

    try:

        with socket.create_connection(
            (host, port),
            timeout=SOCKET_TIMEOUT_SECONDS,
        ):

            return {
                "port": port,
                "service": _service_name(port),
                "state": "open",
            }

    except (
        socket.timeout,
        TimeoutError,
        ConnectionRefusedError,
        OSError,
    ):

        return None


def _scan_with_python_sockets(
    host: str,
    ports: List[int],
) -> Dict[str, Any]:

    open_ports: List[Dict[str, Any]] = []

    worker_count = min(
        MAX_SOCKET_WORKERS,
        max(1, len(ports)),
    )

    with ThreadPoolExecutor(
        max_workers=worker_count
    ) as executor:

        futures = {
            executor.submit(
                _probe_port,
                host,
                port,
            ): port
            for port in ports
        }

        for future in as_completed(futures):

            result = future.result()

            if result is not None:
                open_ports.append(result)

    open_ports.sort(
        key=lambda item: item["port"]
    )

    # No open ports does NOT mean host is down.
    #
    # It could simply mean:
    # - firewall filtering
    # - CDN edge behavior
    # - none of our bounded ports are open
    host_status = (
        "up"
        if open_ports
        else "unknown"
    )

    return {
        "host_status": host_status,
        "scan_type": "connect",
        "scanner_backend": "python_socket",
        "open_ports": open_ports,
    }


# ---------------------------------------------------------------------
# Public worker
# ---------------------------------------------------------------------

def port_scan(
    target: str,
    ports: Optional[str] = None,
) -> Dict[str, Any]:

    host = _normalize_target(target)

    if not host:

        return {
            "error": "Invalid target",
            "details": "Target cannot be empty.",
        }

    # -------------------------------------------------------------
    # Parse bounded ports
    # -------------------------------------------------------------

    try:

        port_list = _parse_ports(ports)

    except (ValueError, TypeError) as exc:

        return {
            "error": "Invalid port specification",
            "details": str(exc),
        }

    # -------------------------------------------------------------
    # Resolve target first
    # -------------------------------------------------------------

    try:

        resolved_addresses = _resolve_target(host)

    except socket.gaierror as exc:

        return {
            "error": "Target resolution failed",
            "details": str(exc),
        }

    except OSError as exc:

        return {
            "error": "Target resolution failed",
            "details": str(exc),
        }

    # -------------------------------------------------------------
    # First try Nmap
    # -------------------------------------------------------------

    nmap_warning = None

    try:

        result = _scan_with_nmap(
            host,
            port_list,
        )

    except Exception as exc:

        # ---------------------------------------------------------
        # Nmap missing / nmap.exe missing / execution failure
        #
        # DO NOT fail the worker.
        #
        # Use Python TCP sockets instead.
        # ---------------------------------------------------------

        nmap_warning = str(exc)

        result = _scan_with_python_sockets(
            host,
            port_list,
        )

    # -------------------------------------------------------------
    # Common output
    # -------------------------------------------------------------

    result.update(
        {
            "target": host,
            "resolved_addresses": resolved_addresses,
            "ports_tested": port_list,
            "ports_tested_count": len(port_list),
            "bounded": True,
        }
    )

    # IMPORTANT:
    #
    # warning != error
    #
    # Your orchestrator treats "error" as worker failure.
    # Therefore Nmap fallback information must only be a warning.
    if nmap_warning:

        result["warning"] = (
            "Nmap was unavailable or could not execute. "
            "SentinelScan automatically used its built-in "
            "bounded Python TCP-connect fallback. "
            f"Nmap detail: {nmap_warning}"
        )

    return result