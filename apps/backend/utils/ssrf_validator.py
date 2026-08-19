import socket
import ipaddress
from urllib.parse import urlparse

def is_safe_target(target_input: str):
    """
    Validates if a given target URL or IP resolves to a safe, non-internal IP.
    """
    if not target_input.startswith(('http://', 'https://')):
        # Assume http to parse hostname correctly
        url = 'http://' + target_input
    else:
        url = target_input

    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        return False, "Invalid target format."

    try:
        # Validate all resolved IP addresses (IPv4 & IPv6)
        for entry in addr_info:
            ip_str = entry[4][0]
            ip = ipaddress.ip_address(ip_str)

            if ip.is_loopback:
                return False, "Target resolves to a loopback address."
            if ip.is_private:
                return False, "Target resolves to a private IP address."
            if ip.is_link_local:
                return False, "Target resolves to a link-local address."
            if ip.is_reserved or ip.is_unspecified or ip.is_multicast:
                return False, "Target resolves to a reserved or unspecified address."
        
        return True, "Target is safe."
    except socket.gaierror:
        return False, "DNS resolution failed."
    except ValueError:
        return False, "Invalid IP address returned."
