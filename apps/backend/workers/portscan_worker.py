"""
Port Scanner Worker for SentinelScan.

Discovers open ports and running services on an authorized target host
using Nmap (via the python-nmap wrapper library). Attempts a fast SYN
scan first (requires elevated/admin privileges); if that's unavailable,
falls back automatically to a TCP connect scan, which works without
elevated privileges.

This worker contains NO business logic or target-selection logic — it
only scans whatever target string it is given by the caller (the AI
Agent), which is responsible for ensuring all targets are authorized
per SentinelScan's usage policy (see docs/PRD.md, docs/AGENTS.md).
"""

from typing import Dict, Any, Optional
import nmap


# Default port set: a reasonable, fast set of the most common ports,
# rather than a full 1-65535 sweep, to keep scan time practical.
DEFAULT_PORTS = "21,22,23,25,53,80,110,111,135,139,143,443,445,993,995,1723,3306,3389,5900,8080"

# Nmap scan timeout, in seconds. Passed to python-nmap as a host_timeout arg.
SCAN_TIMEOUT_SECONDS = 60


def port_scan(target: str, ports: Optional[str] = None) -> Dict[str, Any]:
    """
    Scans a target host for open ports and identifies running services.

    Attempts an Nmap SYN scan (-sS) first, since it is faster and less
    intrusive. If SYN scanning is unavailable (typically because the
    calling process lacks admin/root privileges), automatically falls
    back to a TCP connect scan (-sT), which does not require elevated
    privileges.

    Args:
        target: The domain name or IP address to scan.
        ports: Optional port specification string (e.g. "80,443" or
            "1-1000"). If omitted, a default set of common ports is used.

    Returns:
        On success:
            {
                "host_status": "up" | "down",
                "scan_type": "syn" | "connect",
                "open_ports": [
                    {"port": 80, "service": "http", "state": "open"},
                    ...
                ]
            }
        On invalid target input:
            {"error": "Invalid target", "details": "<what was wrong>"}
        On scan execution failure (both scan types failed, Nmap not
        found, etc.):
            {"error": "Port scan failed", "details": "<exception message>"}
    """
    target = (target or "").strip()
    if not target:
        return {"error": "Invalid target", "details": "Target cannot be empty"}

    port_spec = ports.strip() if ports else DEFAULT_PORTS

    scanner = nmap.PortScanner()

    # Try SYN scan first, then fall back to TCP connect scan.
    for scan_type, nmap_args in (("syn", "-sS"), ("connect", "-sT")):
        try:
            scanner.scan(
                hosts=target,
                ports=port_spec,
                arguments=f"{nmap_args} -T4",
                timeout=SCAN_TIMEOUT_SECONDS,
            )
        except nmap.PortScannerError as e:
            # SYN scan commonly fails here due to lack of privileges.
            # Fall through to try the next scan_type (connect scan).
            if scan_type == "syn":
                continue
            return {"error": "Port scan failed", "details": str(e)}
        except Exception as e:
            if scan_type == "syn":
                continue
            return {"error": "Port scan failed", "details": str(e)}

        # If we get here, the scan command itself ran without raising.
        # Verify the host actually appears in the results (SYN scans
        # without privileges sometimes "succeed" at the library level
        # but return no usable host data).
        if target not in scanner.all_hosts() and _resolve_no_match(scanner, target) is None:
            if scan_type == "syn":
                continue
            return {
                "host_status": "down",
                "scan_type": scan_type,
                "open_ports": [],
            }

        host_key = target if target in scanner.all_hosts() else _resolve_no_match(scanner, target)
        host_data = scanner[host_key]

        if host_data.state() != "up":
            return {
                "host_status": "down",
                "scan_type": scan_type,
                "open_ports": [],
            }

        open_ports = []
        for proto in host_data.all_protocols():
            for port in sorted(host_data[proto].keys()):
                port_info = host_data[proto][port]
                if port_info.get("state") == "open":
                    open_ports.append(
                        {
                            "port": port,
                            "service": port_info.get("name", "unknown"),
                            "state": port_info.get("state", "unknown"),
                        }
                    )

        return {
            "host_status": "up",
            "scan_type": scan_type,
            "open_ports": open_ports,
        }

    # Both scan types failed to produce results.
    return {
        "error": "Port scan failed",
        "details": "Both SYN and TCP connect scans failed to produce results.",
    }


def _resolve_no_match(scanner: "nmap.PortScanner", target: str) -> Optional[str]:
    """
    python-nmap sometimes keys scan results by resolved IP rather than
    the original hostname passed in. If the exact target string isn't
    a key in all_hosts(), but exactly one host was scanned, assume
    that's our target and return its key. Returns None if no
    unambiguous match can be found.
    """
    hosts = scanner.all_hosts()
    if len(hosts) == 1:
        return hosts[0]
    return None