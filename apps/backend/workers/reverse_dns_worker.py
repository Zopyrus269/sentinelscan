import socket
import ipaddress
from typing import Dict, Any, List

def reverse_dns_lookup(ip: str) -> Dict[str, Any]:
    """
    Resolves an IP address back to its hostname(s) via PTR DNS record lookup.
    
    Args:
        ip (str): The IPv4 or IPv6 address to lookup.
        
    Returns:
        dict: A dictionary containing the results.
        - On success: {"hostnames": ["host1.example.com", ...]}
        - When no PTR record exists: {"hostnames": []}
        - On invalid IP input: {"error": "Invalid IP address", "details": "<what was wrong>"}
        - On lookup timeout/failure: {"error": "Reverse DNS lookup failed", "details": "<exception message>"}
    """
    try:
        # Validate that the string is a properly formatted IP address
        ipaddress.ip_address(ip)
    except ValueError as e:
        return {"error": "Invalid IP address", "details": str(e)}

    # Save the default timeout and set a new one to prevent hanging
    default_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(5.0)  # 5 seconds reasonable timeout
        
        try:
            # socket.gethostbyaddr returns (hostname, aliaslist, ipaddrlist)
            hostname, aliases, _ = socket.gethostbyaddr(ip)
            
            hostnames: List[str] = [hostname]
            if aliases:
                hostnames.extend(aliases)
                
            return {"hostnames": hostnames}
            
        except socket.herror:
            # socket.herror is raised for address-related errors (like no PTR record)
            return {"hostnames": []}
            
        except socket.timeout:
            return {"error": "Reverse DNS lookup failed", "details": "Timeout"}
            
        except Exception as e:
            # Catch other potential exceptions (like gaierror or OSError)
            return {"error": "Reverse DNS lookup failed", "details": str(e)}
            
    finally:
        # Restore the original default timeout
        socket.setdefaulttimeout(default_timeout)
