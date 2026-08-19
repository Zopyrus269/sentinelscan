#!/usr/bin/env python3
"""
SentinelScan Security Setup Script
Installs pre-commit security hooks to prevent accidental secret leaks.
"""

import subprocess
import sys

def main():
    print("[*] Installing pre-commit security hooks for SentinelScan...")
    try:
        # Install pre-commit hook into .git/hooks/pre-commit
        result = subprocess.run(["pre-commit", "install"], check=True, capture_output=True, text=True)
        print(f"[+] Success: {result.stdout.strip()}")
        
        print("[*] Testing pre-commit hooks against project configuration...")
        test_res = subprocess.run(["pre-commit", "validate-config"], check=True, capture_output=True, text=True)
        print("[+] Configuration validated successfully.")
    except FileNotFoundError:
        print("[-] Error: 'pre-commit' executable not found in PATH.")
        print("    Please run: pip install pre-commit")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[-] Hook installation failed: {e.stderr}")
        sys.exit(1)

if __name__ == "__main__":
    main()
