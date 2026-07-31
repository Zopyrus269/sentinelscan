"""
Fallback-path test for the Port Scanner Worker.

This test simulates a SYN scan failure (as would happen on a system
where the calling process lacks admin/root privileges) by patching
just the SYN attempt to raise an error. The TCP connect fallback scan
still runs for real against 127.0.0.1 (localhost) -- completely safe,
since it's your own machine -- to verify the full real code path
actually works end to end, not just a mocked shortcut.

Run directly: python test_portscan_worker_fallback.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend', 'workers'))

import json
import nmap
import portscan_worker
from unittest.mock import patch

_real_scan = nmap.PortScanner.scan


def patched_scan(self, hosts, ports, arguments, timeout):
    if "-sS" in arguments:
        raise nmap.PortScannerError(
            "You requested a scan type which requires root privileges."
        )
    return _real_scan(self, hosts=hosts, ports=ports, arguments=arguments, timeout=timeout)


def test_fallback_to_connect_scan():
    with patch.object(nmap.PortScanner, "scan", new=patched_scan):
        result = portscan_worker.port_scan("127.0.0.1", "80,443")

    print("Fallback test result:")
    print(json.dumps(result, indent=2))

    scan_type = result.get("scan_type")
    host_status = result.get("host_status")

    assert scan_type == "connect", "Expected scan_type connect, got " + repr(scan_type)
    assert "error" not in result, "Did not expect an error: " + repr(result)
    assert host_status == "up", "Expected host_status up, got " + repr(host_status)

    print("")
    print("PASS: SYN scan failure was correctly caught, and the worker")
    print("fell back to a real TCP connect scan, which succeeded.")


if __name__ == "__main__":
    test_fallback_to_connect_scan()
