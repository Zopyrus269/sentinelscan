import json
from reverse_dns_worker import reverse_dns_lookup

def run_tests():
    print("Testing Reverse DNS Worker\n")
    print("-" * 40)

    # 1. Test a known IP with a valid PTR record (Google Public DNS)
    print("Test 1: Known IP with PTR record (8.8.8.8)")
    res1 = reverse_dns_lookup("8.8.8.8")
    print(f"Input: '8.8.8.8'\nOutput:\n{json.dumps(res1, indent=2)}\n")
    print("-" * 40)

    # 2. Test a known IP likely without a PTR record (TEST-NET-1)
    print("Test 2: Known IP without PTR record (192.0.2.1)")
    res2 = reverse_dns_lookup("192.0.2.1")
    print(f"Input: '192.0.2.1'\nOutput:\n{json.dumps(res2, indent=2)}\n")
    print("-" * 40)

    # 3. Test an invalid IP string
    print("Test 3: Invalid IP string ('not.an.ip')")
    res3 = reverse_dns_lookup("not.an.ip")
    print(f"Input: 'not.an.ip'\nOutput:\n{json.dumps(res3, indent=2)}\n")
    print("-" * 40)

if __name__ == "__main__":
    run_tests()
