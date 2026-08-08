"""Pytest unit test suite for SentinelScan SSL Worker (ssl_worker.py)."""

from datetime import datetime, timezone
import json
import socket
import ssl
import sys
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.workers.ssl_worker import (
    decode_der_certificate,
    format_dn,
    format_error_response,
    format_success_response,
    main,
    parse_cert_date,
    perform_ssl_inspection,
    run_worker,
)


@pytest.fixture
def valid_cert_dict():
    """Fixture providing a mock valid peer certificate dictionary."""
    return {
        "subject": ((("commonName", "example.com"),),),
        "issuer": (
            (("countryName", "US"),),
            (("organizationName", "DigiCert Inc"),),
            (("commonName", "DigiCert TLS RSA SHA256 2020 CA1"),),
        ),
        "version": 3,
        "serialNumber": "0C3668AC28E619E4A962E3B215E1D4A7",
        "notBefore": "Jan 01 00:00:00 2025 GMT",
        "notAfter": "Dec 31 23:59:59 2030 GMT",
    }


@pytest.fixture
def expired_cert_dict():
    """Fixture providing a mock expired peer certificate dictionary."""
    return {
        "subject": ((("commonName", "expired-example.com"),),),
        "issuer": ((("commonName", "Expired CA"),),),
        "version": 3,
        "serialNumber": "1234567890ABCDEF",
        "notBefore": "Jan 01 00:00:00 2020 GMT",
        "notAfter": "Jan 01 00:00:00 2021 GMT",
    }


class TestSSLWorker:
    """Test suite covering ssl_worker functionality using pytest."""

    # 1. Helper function tests
    def test_format_dn(self):
        """Test formatting Distinguished Name (DN) sequences into strings."""
        assert format_dn(None) == ""
        assert format_dn([]) == ""
        dn_seq = ((("commonName", "example.com"),), (("organizationName", "Org"),))
        assert format_dn(dn_seq) == "commonName=example.com, organizationName=Org"

    def test_parse_cert_date(self):
        """Test parsing GMT date strings into timezone-aware datetime objects."""
        assert parse_cert_date(None) is None
        assert parse_cert_date("invalid date") is None
        
        parsed = parse_cert_date("May 15 12:30:00 2025 GMT")
        assert parsed == datetime(2025, 5, 15, 12, 30, 0, tzinfo=timezone.utc)

    @patch("apps.backend.workers.ssl_worker.os.remove")
    @patch("apps.backend.workers.ssl_worker.tempfile.NamedTemporaryFile")
    @patch("apps.backend.workers.ssl_worker.ssl._ssl._test_decode_cert")
    @patch("apps.backend.workers.ssl_worker.ssl.DER_cert_to_PEM_cert")
    def test_decode_der_certificate(
        self, mock_pem_conv, mock_decode, mock_tmp, mock_remove
    ):
        """Test decoding binary DER certificate bytes into a dictionary."""
        mock_pem_conv.return_value = "-----BEGIN CERTIFICATE-----\n..."
        mock_tmp_file = MagicMock()
        mock_tmp_file.name = "/tmp/test.pem"
        mock_tmp.return_value = mock_tmp_file
        mock_decode.return_value = {"subject": "test"}

        result = decode_der_certificate(b"der_data")
        assert result == {"subject": "test"}

    # 2. Valid Certificate Success Test
    @patch("apps.backend.workers.ssl_worker.verified_tls_connection")
    def test_success_valid_certificate(self, mock_fetch, valid_cert_dict):
        """Test SSL inspection success response for a valid certificate."""
        mock_fetch.return_value = {
            "certificate": valid_cert_dict,
            "protocol": "TLSv1.3",
            "cipher": "TLS_AES_256_GCM_SHA384",
        }

        input_payload = {"target": "example.com", "port": 443, "timeout": 5.0}
        result = run_worker(input_payload)

        assert result["worker"] == "ssl"
        assert result["status"] == "success"
        assert result["error"] is None

        data = result["data"]
        assert data["issuer"] == "countryName=US, organizationName=DigiCert Inc, commonName=DigiCert TLS RSA SHA256 2020 CA1"
        assert data["subject"] == "commonName=example.com"
        assert data["valid_from"] == "2025-01-01T00:00:00+00:00"
        assert data["valid_to"] == "2030-12-31T23:59:59+00:00"
        assert data["serial_number"] == "0C3668AC28E619E4A962E3B215E1D4A7"
        assert data["protocol"] == "TLSv1.3"
        assert data["cipher"] == "TLS_AES_256_GCM_SHA384"
        assert data["is_valid"] is True
        assert data["days_until_expiry"] > 0

    # 3. Expired Certificate Test
    @patch("apps.backend.workers.ssl_worker.verified_tls_connection")
    def test_expired_certificate(self, mock_fetch, expired_cert_dict):
        """Test SSL inspection response for an expired certificate."""
        mock_fetch.return_value = {
            "certificate": expired_cert_dict,
            "protocol": "TLSv1.2",
            "cipher": "ECDHE-RSA-AES128-GCM-SHA256",
        }

        input_payload = {"target": "expired-example.com"}
        result = run_worker(input_payload)

        assert result["worker"] == "ssl"
        assert result["status"] == "success"
        assert result["error"] is None

        data = result["data"]
        assert data["is_valid"] is False
        assert data["days_until_expiry"] < 0

    # 4. Self-signed Certificate Test
    @patch("apps.backend.workers.ssl_worker.verified_tls_connection")
    @patch("apps.backend.workers.ssl_worker.unverified_tls_connection")
    def test_self_signed_certificate(self, mock_unverified, mock_fetch, valid_cert_dict):
        """Test response for self-signed certificate where verification failed but cert retrieved."""
        # cert_verified = False indicates certificate verification failed (self-signed/untrusted)
        mock_fetch.side_effect = __import__("ssl").SSLCertVerificationError("self-signed")

        mock_unverified.return_value = {
            "certificate": valid_cert_dict,
            "protocol": "TLSv1.3",
            "cipher": "TLS_AES_256_GCM_SHA384",
            "certificate_present": True,
        }

        input_payload = {"target": "self-signed.local"}
        result = run_worker(input_payload)

        assert result["worker"] == "ssl"
        assert result["status"] == "success"
        assert result["data"]["is_valid"] is False

    # 5. DNS Failure Test
    @patch("apps.backend.workers.ssl_worker.verified_tls_connection")
    def test_dns_failure(self, mock_fetch):
        """Test handling of DNS resolution failures."""
        mock_fetch.side_effect = socket.gaierror("Name or service not known")

        input_payload = {"target": "nonexistent-domain-xyz.invalid"}
        result = run_worker(input_payload)

        assert result["worker"] == "ssl"
        assert result["status"] == "error"
        assert result["data"] == {}
        assert "DNS resolution failed" in result["error"]

    # 6. Socket Timeout Test
    @patch("apps.backend.workers.ssl_worker.verified_tls_connection")
    def test_socket_timeout(self, mock_fetch):
        """Test handling of connection timeouts."""
        mock_fetch.side_effect = socket.timeout("timed out")

        input_payload = {"target": "slow-server.com", "timeout": 2.0}
        result = run_worker(input_payload)

        assert result["worker"] == "ssl"
        assert result["status"] == "error"
        assert result["data"] == {}
        assert "TLS connection timed out" in result["error"]

    # 7. Connection Refused Test
    @patch("apps.backend.workers.ssl_worker.verified_tls_connection")
    def test_connection_refused(self, mock_fetch):
        """Test handling of connection refused errors."""
        mock_fetch.side_effect = ConnectionRefusedError("Connection refused")

        input_payload = {"target": "127.0.0.1", "port": 8443}
        result = run_worker(input_payload)

        assert result["worker"] == "ssl"
        assert result["status"] == "error"
        assert result["data"] == {}
        assert "Connection refused" in result["error"]

    # 8. SSL Handshake Failure Test
    @patch("apps.backend.workers.ssl_worker.verified_tls_connection")
    def test_ssl_handshake_failure(self, mock_fetch):
        """Test handling of fatal SSL handshake errors."""
        mock_fetch.side_effect = ssl.SSLError("SSL handshake failed")

        input_payload = {"target": "bad-ssl.com"}
        result = run_worker(input_payload)

        assert result["worker"] == "ssl"
        assert result["status"] == "error"
        assert result["data"] == {}
        assert "SSL handshake failed" in result["error"]

    # 9. Invalid Input Payload Tests
    @pytest.mark.parametrize(
        "invalid_payload, expected_err_fragment",
        [
            (None, "Input payload must be a JSON object"),
            ("invalid string", "Input payload must be a JSON object"),
            ({}, "Missing required field 'target'"),
            ({"target": ""}, "Target domain must be a non-empty string"),
            ({"target": "   "}, "Target domain must be a non-empty string"),
            ({"target": "example.com", "port": 99999}, "Port number must be between 1 and 65535"),
            ({"target": "example.com", "port": "abc"}, "Port must be a valid integer"),
            ({"target": "example.com", "timeout": -5}, "Timeout must be a positive number"),
            ({"target": "example.com", "timeout": "abc"}, "Timeout must be a valid number"),
        ],
    )
    def test_invalid_input_payloads(self, invalid_payload, expected_err_fragment):
        """Test schema validation for various invalid input payloads."""
        result = run_worker(invalid_payload)

        assert result["worker"] == "ssl"
        assert result["status"] == "error"
        assert result["data"] == {}
        assert expected_err_fragment in result["error"]

    # 10. Verify JSON Schema & Serializability
    @patch("apps.backend.workers.ssl_worker.verified_tls_connection")
    def test_json_schema_and_serializability(self, mock_fetch, valid_cert_dict):
        """Verify output dictionary structure and ensure 100% JSON serializability."""
        mock_fetch.return_value = {
            "certificate": valid_cert_dict,
            "protocol": "TLSv1.3",
            "cipher": "TLS_AES_256_GCM_SHA384",
        }

        result = run_worker({"target": "schema-check.com"})

        # Top-level keys verification
        assert set(result.keys()) == {"worker", "status", "data", "error"}
        assert result["worker"] == "ssl"
        assert result["status"] == "success"

        # Data keys verification
        expected_data_keys = {
            "target",
            "port",
            "issuer",
            "subject",
            "serial_number",
            "valid_from",
            "valid_to",
            "days_until_expiry",
            "protocol",
            "cipher",
            "certificate_verified",
            "trust_verified",
            "hostname_valid",
            "time_valid",
            "certificate_expired",
            "certificate_not_yet_valid",
            "certificate_present",
            "is_valid",
            "verification_error",
            "verification_code",
            "validation_issue",
            "fallback_metadata_error",
        }
        assert set(result["data"].keys()) == expected_data_keys

        # Ensure json.dumps works without error
        json_output = json.dumps(result)
        parsed = json.loads(json_output)
        assert parsed["status"] == "success"

    # 11. Test fetch_ssl_details with socket mocks
    @patch("apps.backend.workers.ssl_worker.socket.create_connection")
    @patch("apps.backend.workers.ssl_worker.ssl.create_default_context")
    def test_verified_tls_connection_flow(self, mock_create_ctx, mock_create_conn):
        """Test low-level verified_tls_connection flow."""
        mock_sock = MagicMock()
        mock_create_conn.return_value.__enter__.return_value = mock_sock

        mock_sslsock = MagicMock()
        mock_sslsock.getpeercert.return_value = {"subject": ((("commonName", "example.com"),),)}
        mock_sslsock.version.return_value = "TLSv1.3"
        mock_sslsock.cipher.return_value = ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)

        mock_ctx = MagicMock()
        mock_ctx.wrap_socket.return_value.__enter__.return_value = mock_sslsock
        mock_create_ctx.return_value = mock_ctx

        from apps.backend.workers.ssl_worker import verified_tls_connection
        result = verified_tls_connection("example.com", 443, 5.0)

        assert result["certificate"] == {"subject": ((("commonName", "example.com"),),)}
        assert result["protocol"] == "TLSv1.3"
        assert result["cipher"] == "TLS_AES_256_GCM_SHA384"

    # 12. Test CLI main() function
    @patch("apps.backend.workers.ssl_worker.run_worker")
    @patch("sys.argv", ["ssl_worker.py", '{"target": "example.com"}'])
    def test_main_cli_argument(self, mock_run):
        """Test CLI main entry point using command line argument."""
        mock_run.return_value = {"worker": "ssl", "status": "success", "data": {}, "error": None}
        
        with patch("builtins.print") as mock_print:
            main()
            mock_print.assert_called_once()
            mock_run.assert_called_once_with({"target": "example.com"})


if __name__ == "__main__":
    pytest.main()
