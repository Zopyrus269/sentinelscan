from unittest.mock import Mock, patch

from apps.backend.workers.ddos_worker import ddos_resilience_check


def _response(headers=None, status=200, text="ok", url="https://example.com/"):
    response = Mock()
    response.headers = headers or {}
    response.status_code = status
    response.text = text
    response.url = url
    response.cookies = []
    return response


def test_detects_cloudflare_from_concrete_header():
    with patch("apps.backend.workers.ddos_worker.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]), \
         patch("apps.backend.workers.ddos_worker.socket.gethostbyaddr", side_effect=OSError), \
         patch("apps.backend.workers.ddos_worker.requests.get", return_value=_response({"Server": "cloudflare", "CF-Ray": "abc"})):
        result = ddos_resilience_check("example.com")

    assert result["status"] == "COMPLETED"
    assert result["evidence"]["posture"] == "DETECTED"
    assert "cloudflare" in result["evidence"]["provider_indicators"]
    assert result["findings"] == []


def test_no_provider_is_honest_not_vulnerability():
    with patch("apps.backend.workers.ddos_worker.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]), \
         patch("apps.backend.workers.ddos_worker.socket.gethostbyaddr", side_effect=OSError), \
         patch("apps.backend.workers.ddos_worker.requests.get", return_value=_response({"Server": "nginx"})):
        result = ddos_resilience_check("example.com")

    assert result["status"] == "COMPLETED"
    assert result["evidence"]["posture"] == "NOT_OBSERVED"
    assert result["evidence"]["cdn_or_waf_detected"] is False
    assert "does not prove" in result["summary"].lower()
    assert result["findings"] == []


def test_html_text_does_not_fake_provider_detection():
    with patch("apps.backend.workers.ddos_worker.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]), \
         patch("apps.backend.workers.ddos_worker.socket.gethostbyaddr", side_effect=OSError), \
         patch("apps.backend.workers.ddos_worker.requests.get", return_value=_response({"Server": "nginx"}, text="This page mentions Cloudflare in an article.")):
        result = ddos_resilience_check("example.com")

    assert result["evidence"]["provider_indicators"] == []
    assert result["evidence"]["posture"] == "NOT_OBSERVED"
