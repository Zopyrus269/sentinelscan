"""
DDoS Resilience Worker.

Passively assesses a target's DDoS mitigation infrastructure by analyzing
HTTP headers, DNS CNAME chains, Anycast routing indicators, and IP ASN/Org data.
"""

import urllib.parse
from typing import Dict, Any
import requests
import dns.resolver

# Common CDN/WAF header signatures
CDN_HEADERS = {
    "server": ["cloudflare", "akamai", "imperva", "incapsula", "awselb", "amazon"],
    "via": ["cloudflare", "akamai", "cloudfront", "fastly"],
    "x-amz-cf-id": ["cloudfront"],
    "cf-ray": ["cloudflare"],
    "x-akamai-transformed": ["akamai"],
    "x-edgeconnect-midmile-rtt": ["akamai"],
    "x-sucuri-id": ["sucuri"],
    "x-hw": ["highwinds"],
    "x-fastly-request-id": ["fastly"],
}

# Common CNAME signatures for CDNs
CDN_CNAMES = [
    ".cdn.cloudflare.net",
    ".akamai.net",
    ".edgesuite.net",
    ".akamaiedge.net",
    ".cloudfront.net",
    ".fastly.net",
    ".incapdns.net",
    ".impervadns.net",
    ".awsglobalaccelerator.com"
]

def check_headers_for_cdn(headers: requests.structures.CaseInsensitiveDict) -> list:
    """Check response headers for known CDN/WAF signatures."""
    findings = []
    for header, patterns in CDN_HEADERS.items():
        val = headers.get(header)
        if val:
            val_lower = val.lower()
            for pattern in patterns:
                if pattern in val_lower:
                    findings.append(f"{header.capitalize()} indicates {pattern}")
    return list(set(findings))

def check_rate_limit_headers(headers: requests.structures.CaseInsensitiveDict) -> bool:
    """Check for presence of common rate-limiting headers."""
    rl_headers = [
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "ratelimit-limit",
        "ratelimit-remaining",
        "retry-after",
    ]
    for h in rl_headers:
        if h in headers:
            return True
    return False

def check_cname_for_cdn(target_domain: str) -> list:
    """Check CNAME records for known CDN domains."""
    findings = []
    try:
        answers = dns.resolver.resolve(target_domain, 'CNAME')
        for rdata in answers:
            cname_str = rdata.target.to_text().lower()
            for cdn_cname in CDN_CNAMES:
                if cdn_cname in cname_str:
                    findings.append(f"CNAME {cname_str} indicates CDN/WAF")
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
        pass
    except Exception:
        pass
    return list(set(findings))

def check_anycast(target_domain: str) -> bool:
    """
    Check if the domain uses Anycast routing by querying different public resolvers.
    If the returned IPs differ significantly, it's likely Anycast.
    """
    resolvers = [
        '8.8.8.8',       # Google
        '1.1.1.1',       # Cloudflare
        '208.67.222.222' # OpenDNS
    ]
    
    ips_found = set()
    for resolver_ip in resolvers:
        res = dns.resolver.Resolver(configure=False)
        res.nameservers = [resolver_ip]
        res.timeout = 2
        res.lifetime = 2
        try:
            answers = res.resolve(target_domain, 'A')
            for rdata in answers:
                ips_found.add(rdata.to_text())
        except Exception:
            continue
            
    return len(ips_found) > 1

def check_asn(ip_address: str) -> Dict[str, str]:
    """Perform a passive RDAP lookup to find the ASN and Org name for an IP."""
    try:
        response = requests.get(f"https://rdap.arin.net/registry/ip/{ip_address}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "network_name": data.get("name", "Unknown"),
                "country": data.get("country", "Unknown")
            }
    except Exception:
        pass
    
    return {"network_name": "Unknown", "country": "Unknown"}

def ddos_resilience_worker(target: str) -> Dict[str, Any]:
    """
    Assesses a target's DDoS resilience passively.

    Args:
        target: The URL or domain to inspect (e.g. "https://example.com").

    Returns:
        On success: {"mitigation_detected": bool, "cdn_waf_evidence": [...],
                     "rate_limiting_detected": bool, "anycast_detected": bool,
                     "asn_info": {...}, "severity": "..."}
        On failure: {"error": "...", "details": "..."}
    """
    parsed = urllib.parse.urlparse(target)
    
    if not parsed.scheme or not parsed.netloc:
        url = "http://" + target
        domain = target.split("/")[0].split(":")[0]
    else:
        url = target
        domain = parsed.netloc.split(":")[0]

    result = {
        "mitigation_detected": False,
        "cdn_waf_evidence": [],
        "rate_limiting_detected": False,
        "anycast_detected": False,
        "asn_info": {},
        "severity": "Informational",
        "description": ""
    }

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "SentinelScan-SecurityBot/1.0"},
            timeout=10,
            allow_redirects=True,
        )
        
        header_evidence = check_headers_for_cdn(response.headers)
        if header_evidence:
            result["cdn_waf_evidence"].extend(header_evidence)
            result["mitigation_detected"] = True
            
        result["rate_limiting_detected"] = check_rate_limit_headers(response.headers)
        
    except requests.exceptions.RequestException as e:
         pass 
    except Exception as e:
         pass

    cname_evidence = check_cname_for_cdn(domain)
    if cname_evidence:
        result["cdn_waf_evidence"].extend(cname_evidence)
        result["mitigation_detected"] = True

    if check_anycast(domain):
        result["anycast_detected"] = True
        result["mitigation_detected"] = True

    try:
        ip_answers = dns.resolver.resolve(domain, 'A')
        if ip_answers:
             ip_address = ip_answers[0].to_text()
             asn_info = check_asn(ip_address)
             result["asn_info"] = asn_info
             
             org_name = asn_info.get("network_name", "").lower()
             cdn_keywords = ["cloudflare", "akamai", "fastly", "amazon", "google", "imperva", "incapsula"]
             for keyword in cdn_keywords:
                 if keyword in org_name:
                     result["cdn_waf_evidence"].append(f"IP belongs to known CDN/WAF network: {asn_info.get('network_name')}")
                     result["mitigation_detected"] = True
                     break
    except Exception:
        pass

    if not result["mitigation_detected"]:
        result["severity"] = "High"
        result["description"] = "No CDN, WAF, or Anycast DDoS mitigation detected. Origin IP is directly exposed and potentially vulnerable to volumetric or layer 7 DDoS attacks."
    else:
        result["severity"] = "Informational"
        mitigations = []
        if result["cdn_waf_evidence"]:
            mitigations.append("CDN/WAF presence")
        if result["anycast_detected"]:
            mitigations.append("Anycast routing")
        if result["rate_limiting_detected"]:
            mitigations.append("Rate-limiting headers")
        
        result["description"] = f"DDoS mitigation infrastructure detected: {', '.join(mitigations)}."

    return result
