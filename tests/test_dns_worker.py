import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend', 'workers'))

import json
from dns_worker import dns_lookup

def test_dns_worker():
    print("Testing DNS Worker...")
    print("-" * 40)
    
    # 1. Test a well-known real domain with lots of records
    domain1 = "google.com"
    print(f"1. Testing well-known domain: {domain1}")
    result1 = dns_lookup(domain1)
    print(json.dumps(result1, indent=2))
    print("-" * 40)
    
    # 2. Test a domain that definitely does not exist
    domain2 = "thisdomaindoesnotexist12345xyz.com"
    print(f"2. Testing non-existent domain: {domain2}")
    result2 = dns_lookup(domain2)
    print(json.dumps(result2, indent=2))
    print("-" * 40)
    
    # 3. Test a domain likely missing specific record types (e.g. example.com doesn't usually have MX or CNAME)
    domain3 = "example.com"
    print(f"3. Testing domain missing some records: {domain3}")
    result3 = dns_lookup(domain3)
    print(json.dumps(result3, indent=2))
    print("-" * 40)

if __name__ == "__main__":
    test_dns_worker()
