"""
Domain ownership verification utility for SentinelScan.
Ensures that targets are explicitly authorized before scanning.
"""

import logging
from typing import Optional

import dns.resolver
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DomainVerifier:
    """
    Utility class to verify domain ownership via DNS TXT records or HTML meta tags.
    """

    @staticmethod
    def verify_via_dns_txt(domain: str, expected_token: str, timeout: float = 10.0) -> bool:
        """
        Verify ownership by checking the TXT records of a domain for the expected token.
        
        Args:
            domain (str): The domain name to check.
            expected_token (str): The token expected to be present in the TXT records.
            timeout (float): DNS resolution timeout in seconds.
            
        Returns:
            bool: True if the token is found, False otherwise.
        """
        if not domain or not expected_token:
            return False

        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = timeout
            resolver.lifetime = timeout
            
            answers = resolver.resolve(domain, 'TXT')
            for rdata in answers:
                for txt_string in rdata.strings:
                    # rdata.strings are bytes in dnspython
                    decoded_string = txt_string.decode('utf-8')
                    if expected_token in decoded_string:
                        return True
                        
        except dns.resolver.NXDOMAIN:
            logger.warning(f"DNS Verification failed: Domain {domain} does not exist.")
        except dns.resolver.NoAnswer:
            logger.warning(f"DNS Verification failed: No TXT records found for {domain}.")
        except dns.resolver.Timeout:
            logger.warning(f"DNS Verification failed: Timeout querying TXT records for {domain}.")
        except Exception as e:
            logger.warning(f"DNS Verification failed for {domain} with unexpected error: {e}")
            
        return False

    @staticmethod
    def verify_via_meta_tag(url: str, expected_token: str, timeout: float = 10.0) -> bool:
        """
        Verify ownership by checking for a specific meta tag on the target URL.
        Looks for: <meta name="sentinelscan-verification" content="{expected_token}">
        
        Args:
            url (str): The URL to fetch and check.
            expected_token (str): The token expected in the meta tag content.
            timeout (float): Request timeout in seconds.
            
        Returns:
            bool: True if the correct meta tag is found, False otherwise.
        """
        if not url or not expected_token:
            return False
            
        # Ensure scheme is present
        clean_url = url.strip()
        if not clean_url.startswith(('http://', 'https://')):
            clean_url = f'https://{clean_url}'

        try:
            headers = {
                'User-Agent': 'SentinelScan Verification Agent/1.0'
            }
            response = requests.get(clean_url, headers=headers, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            meta_tag = soup.find('meta', attrs={'name': 'sentinelscan-verification'})
            
            if meta_tag:
                content = meta_tag.get('content', '')
                if expected_token in content:
                    return True
                    
        except requests.exceptions.Timeout:
            logger.warning(f"Meta tag verification failed: Timeout fetching {clean_url}.")
        except requests.exceptions.ConnectionError:
            logger.warning(f"Meta tag verification failed: Connection error fetching {clean_url}.")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Meta tag verification failed: HTTP error for {clean_url}: {e}")
        except Exception as e:
            logger.warning(f"Meta tag verification failed for {clean_url} with unexpected error: {e}")
            
        return False
