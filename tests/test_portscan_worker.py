"""
Simple manual self-test for the Port Scanner Worker.
Run directly: python test_portscan_worker.py

Uses 127.0.0.1 (localhost) as the test target, since this is
unambiguously a target you're authorized to scan (it's your own
machine) and avoids any question of external-target authorization.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend', 'workers'))

import json
from portscan_worker import port_scan


def run_test(label: str, target: str, ports: str = None) -> None:
    print(f"\n{'-' * 40}")
    print(label)
    print(f"Target: {target!r}  Ports: {ports!r}")
    result = port_scan(target, ports)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    print("Testing Port Scanner Worker")

    # Test 1: localhost, default port set
    run_test("Test 1: localhost (127.0.0.1), default ports", "127.0.0.1")

    # Test 2: localhost, explicit small port range
    run_test("Test 2: localhost (127.0.0.1), explicit ports", "127.0.0.1", "22,80,443")

    # Test 3: invalid/empty target
    run_test("Test 3: empty target string", "")

    print(f"\n{'-' * 40}")
    print("Done. If host_status is 'down' with no open ports, that's expected")
    print("if nothing is listening on localhost — that's a valid, correct result,")
    print("not a bug. Check the 'scan_type' field to see whether SYN or TCP")
    print("connect scan actually ran (tells you if admin privileges were available).")
