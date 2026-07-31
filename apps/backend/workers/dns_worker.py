import dns.resolver
import dns.exception
from typing import Dict, Any, List

def dns_lookup(target: str) -> Dict[str, Any]:
    """
    Retrieves DNS records for a target domain.
    
    Queries A, AAAA, MX, NS, TXT, and CNAME records independently.
    
    Args:
        target (str): The domain name to look up.
        
    Returns:
        dict: A dictionary containing the results.
        - On success: {"A": [...], "AAAA": [...], "MX": [...], "NS": [...], "TXT": [...], "CNAME": [...]}
        - When domain does not exist: {"error": "Domain does not exist", "details": "<target>"}
        - On lookup timeout/failure: {"error": "DNS lookup failed", "details": "<exception message>"}
    """
    target = target.strip()
    if not target:
        return {"error": "Invalid input", "details": "Target domain cannot be empty"}
        
    record_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME"]
    results: Dict[str, Any] = {rtype: [] for rtype in record_types}
    
    # Configure resolver with a reasonable timeout
    resolver = dns.resolver.Resolver()
    resolver.timeout = 5.0
    resolver.lifetime = 5.0
    
    for rtype in record_types:
        try:
            answers = resolver.resolve(target, rtype)
            for rdata in answers:
                # rdata.to_text() provides a string representation of the record
                # We strip outer quotes that are often present in TXT records
                text_val = rdata.to_text()
                if text_val.startswith('"') and text_val.endswith('"'):
                    text_val = text_val[1:-1]
                results[rtype].append(text_val)
        except dns.resolver.NoAnswer:
            # The domain exists but has no records of this type
            pass
        except dns.resolver.NXDOMAIN:
            # The domain itself does not exist. We can stop querying.
            return {"error": "Domain does not exist", "details": target}
        except (dns.resolver.NoNameservers, dns.exception.Timeout) as e:
            return {"error": "DNS lookup failed", "details": str(e)}
        except Exception as e:
            # Catch other potential dnspython exceptions
            return {"error": "DNS lookup failed", "details": str(e)}
            
    return results
