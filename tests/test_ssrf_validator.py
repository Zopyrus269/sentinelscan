from unittest.mock import patch

from apps.backend.utils.ssrf_validator import is_safe_target


def _addr_info(*ips):
    return [(None, None, None, "", (ip, 0)) for ip in ips]


def test_public_ipv4_is_safe():
    with patch("socket.getaddrinfo", return_value=_addr_info("93.184.216.34")):
        is_safe, _ = is_safe_target("example.com")
    assert is_safe is True


def test_loopback_is_rejected():
    with patch("socket.getaddrinfo", return_value=_addr_info("127.0.0.1")):
        is_safe, msg = is_safe_target("localhost")
    assert is_safe is False
    assert "loopback" in msg.lower()


def test_private_ip_is_rejected():
    with patch("socket.getaddrinfo", return_value=_addr_info("10.0.0.5")):
        is_safe, msg = is_safe_target("internal.example.com")
    assert is_safe is False
    assert "private" in msg.lower()


def test_link_local_is_rejected():
    # ipaddress classifies 169.254.0.0/16 as both is_private and is_link_local;
    # is_private is checked first, so that's the message this hits in practice.
    with patch("socket.getaddrinfo", return_value=_addr_info("169.254.1.1")):
        is_safe, msg = is_safe_target("link-local.example.com")
    assert is_safe is False
    assert "private" in msg.lower() or "link-local" in msg.lower()


def test_any_unsafe_resolved_ip_rejects_multi_a_record_target():
    with patch("socket.getaddrinfo", return_value=_addr_info("93.184.216.34", "127.0.0.1")):
        is_safe, msg = is_safe_target("multi-a.example.com")
    assert is_safe is False
    assert "loopback" in msg.lower()


def test_malformed_target_is_rejected():
    is_safe, msg = is_safe_target("http://")
    assert is_safe is False
    assert "invalid" in msg.lower()


def test_dns_failure_is_rejected():
    import socket as socket_module

    with patch("socket.getaddrinfo", side_effect=socket_module.gaierror):
        is_safe, msg = is_safe_target("thisdomaindoesnotexist12345xyz.invalid")
    assert is_safe is False
    assert "dns" in msg.lower()
