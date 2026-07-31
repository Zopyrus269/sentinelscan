"""
Test script for the Report Generator Worker.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend', 'workers'))

import json
from report_worker import generate_report


def run_tests():
    print("Testing Report Generator Worker...")

    target = "example.com"
    
    findings = [
        {
            "worker": "dns_worker",
            "summary": "The target domain resolves to 93.184.215.14 and has valid MX records.",
            "raw_data": {
                "A": ["93.184.215.14"],
                "MX": ["0 mx.example.com"]
            }
        },
        {
            "worker": "reverse_dns_worker",
            "summary": "Reverse DNS lookup returned example.com for the primary IP.",
            "raw_data": {
                "hostnames": ["example.com"]
            }
        },
        {
            "worker": "portscan_worker",
            "summary": "Discovered open ports 80 and 443; no unexpected services exposed.",
            "raw_data": {
                "host_status": "up",
                "scan_type": "syn",
                "open_ports": [
                    {"port": 80, "service": "http", "state": "open"},
                    {"port": 443, "service": "https", "state": "open"}
                ]
            }
        }
    ]

    cvss_scores = [
        {
            "finding": "Missing HSTS Header",
            "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N",
            "base_score": 5.3,
            "severity": "MEDIUM"
        },
        {
            "finding": "Software Version Disclosure",
            "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N",
            "base_score": 5.3,
            "severity": "LOW"
        },
        {
            "finding": "Open Port 80 (HTTP)",
            "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N",
            "base_score": 0.0,
            "severity": "INFORMATIONAL"
        }
    ]

    result = generate_report(target, findings, cvss_scores)
    
    print("\n--- Worker Result ---")
    print(json.dumps(result, indent=2))
    
    if "error" in result:
        print("\nTest failed due to worker error.")
        return

    # Verify files exist
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    pdf_path = os.path.join(project_root, result["pdf_path"])
    json_path = os.path.join(project_root, result["json_path"])

    print("\n--- File Existence Check ---")
    print(f"PDF exists: {os.path.exists(pdf_path)} ({pdf_path})")
    if os.path.exists(pdf_path):
        print(f"PDF size: {os.path.getsize(pdf_path)} bytes")
    print(f"JSON exists: {os.path.exists(json_path)} ({json_path})")
    
    if os.path.exists(json_path):
        print("\n--- JSON Report Content ---")
        with open(json_path, 'r', encoding='utf-8') as f:
            print(f.read())


if __name__ == "__main__":
    run_tests()
