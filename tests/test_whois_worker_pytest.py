
"""Pytest unit test suite for SentinelScan WHOIS Worker (whois_worker.py)."""

from datetime import datetime
import json
import socket
from unittest.mock import MagicMock, patch

import pytest
import whois

from apps.backend.workers.whois_worker import (
    extract_whois_fields,
    format_error_response,
    format_success_response,
    perform_whois_lookup,
    run_worker,
    serialize_value,
)


@pytest.fixture
def mock_whois_entry():
    """Fixture providing a mock WhoisEntry with complete standard fields."""
    entry = MagicMock()
    entry.registrar = "GoDaddy.com, LLC"
    entry.creation_date = datetime(2010, 3, 15, 10, 0, 0)
    entry.expiration_date = datetime(2030, 3, 15, 10, 0, 0)
    entry.updated_date = datetime(2023, 5, 20, 14, 30, 0)
    entry.domain_name = "example.com"
    entry.name_servers = ["NS1.EXAMPLE.COM", "NS2.EXAMPLE.COM"]
    entry.status = ["clientTransferProhibited", "clientUpdateProhibited"]
    return entry


class TestWhoisWorkerPytest:
    """Test suite covering whois_worker functionality using pytest."""

    # 1. Valid domain test
    @patch("apps.backend.workers.whois_worker.whois.whois")
    def test_valid_domain_lookup(self, mock_whois_call, mock_whois_entry):
        """Test WHOIS lookup for a valid domain returning expected extracted data."""
        mock_whois_call.return_value = mock_whois_entry

        input_payload = {"target": "example.com"}
        result = run_worker(input_payload)

        mock_whois_call.assert_called_once_with("example.com")
        assert result["status"] == "success"
        assert result["worker"] == "whois"
        assert result["error"] is None

        data = result["data"]
        assert data["registrar"] == "GoDaddy.com, LLC"
        assert data["creation_date"] == "2010-03-15T10:00:00"
        assert data["expiration_date"] == "2030-03-15T10:00:00"
        assert data["updated_date"] == "2023-05-20T14:30:00"
        assert data["domain_name"] == "example.com"
        assert data["name_servers"] == ["NS1.EXAMPLE.COM", "NS2.EXAMPLE.COM"]
        assert data["status"] == ["clientTransferProhibited", "clientUpdateProhibited"]

    # 2. Invalid domain test
    @patch("apps.backend.workers.whois_worker.whois.whois")
    def test_invalid_domain_lookup(self, mock_whois_call):
        """Test WHOIS lookup when requesting an invalid/non-existent domain."""
        error_cls = getattr(whois, "WhoisError", Exception)
        mock_whois_call.side_effect = error_cls(
            "No match for domain 'invalid-nonexistent-domain-xyz.com'"
        )

        input_payload = {"target": "invalid-nonexistent-domain-xyz.com"}
        result = run_worker(input_payload)

        assert result["status"] == "error"
        assert result["worker"] == "whois"
        assert result["data"] == {}
        assert "No match for domain" in result["error"]

    # 3. WHOIS timeout test
    @patch("apps.backend.workers.whois_worker.whois.whois")
    def test_whois_timeout_error(self, mock_whois_call):
        """Test socket timeout during WHOIS network request."""
        mock_whois_call.side_effect = socket.timeout("WHOIS server query timed out")

        input_payload = {"target": "slow-domain.com"}
        result = run_worker(input_payload)

        assert result["status"] == "error"
        assert result["worker"] == "whois"
        assert result["data"] == {}
        assert "timed out" in result["error"]

    @patch("apps.backend.workers.whois_worker.whois.whois")
    def test_whois_generic_timeout_exception(self, mock_whois_call):
        """Test TimeoutError exception handling."""
        mock_whois_call.side_effect = TimeoutError("Connection to port 43 timed out")

        input_payload = {"target": "timed-out-domain.com"}
        result = run_worker(input_payload)

        assert result["status"] == "error"
        assert result["worker"] == "whois"
        assert result["data"] == {}
        assert "timed out" in result["error"]

    # 4. Missing fields tests
    @pytest.mark.parametrize(
        "invalid_payload, expected_err_fragment",
        [
            ({}, "Missing required field 'target'"),
            ({"target": ""}, "Target domain must be a non-empty string"),
            ({"target": "   "}, "Target domain must be a non-empty string"),
            (None, "Input payload must be a JSON object"),
            ("not a dict", "Input payload must be a JSON object"),
        ],
    )
    def test_missing_input_fields(self, invalid_payload, expected_err_fragment):
        """Test validation error payloads when target input is missing or invalid."""
        result = run_worker(invalid_payload)

        assert result["status"] == "error"
        assert result["worker"] == "whois"
        assert result["data"] == {}
        assert expected_err_fragment in result["error"]

    @patch("apps.backend.workers.whois_worker.whois.whois")
    def test_missing_whois_record_fields(self, mock_whois_call):
        """Test WHOIS entry with missing/None fields (e.g. absent creation_date or registrar)."""
        entry_with_missing_fields = MagicMock()
        entry_with_missing_fields.registrar = None
        entry_with_missing_fields.creation_date = None
        entry_with_missing_fields.expiration_date = None
        entry_with_missing_fields.updated_date = None
        entry_with_missing_fields.domain_name = "partial-data.org"
        entry_with_missing_fields.name_servers = None
        entry_with_missing_fields.status = None

        mock_whois_call.return_value = entry_with_missing_fields

        result = run_worker({"target": "partial-data.org"})

        assert result["status"] == "success"
        assert result["worker"] == "whois"
        data = result["data"]
        assert data["domain_name"] == "partial-data.org"
        assert data["registrar"] is None
        assert data["creation_date"] is None
        assert data["expiration_date"] is None
        assert data["updated_date"] is None
        assert data["name_servers"] is None
        assert data["status"] is None

    # 5. Verify JSON schema test
    @patch("apps.backend.workers.whois_worker.whois.whois")
    def test_json_schema_compliance_success(self, mock_whois_call, mock_whois_entry):
        """Verify output strictly adheres to SentinelScan JSON schema on success."""
        mock_whois_call.return_value = mock_whois_entry

        result = run_worker({"target": "schema-check.com"})

        # Top-level keys verification
        expected_top_keys = {"worker", "status", "data", "error"}
        assert set(result.keys()) == expected_top_keys
        assert result["worker"] == "whois"
        assert result["status"] in ("success", "error")

        # Data schema keys verification
        expected_data_keys = {
            "registrar",
            "creation_date",
            "expiration_date",
            "updated_date",
            "domain_name",
            "name_servers",
            "status",
        }
        assert set(result["data"].keys()) == expected_data_keys

        # Ensure result is 100% JSON serializable
        json_output = json.dumps(result)
        parsed_json = json.loads(json_output)
        assert parsed_json["status"] == "success"
        assert parsed_json["worker"] == "whois"

    def test_json_schema_compliance_error(self):
        """Verify output strictly adheres to SentinelScan JSON schema on error."""
        result = run_worker({})

        expected_top_keys = {"worker", "status", "data", "error"}
        assert set(result.keys()) == expected_top_keys
        assert result["worker"] == "whois"
        assert result["status"] == "error"
        assert result["data"] == {}
        assert isinstance(result["error"], str)

        # Ensure error output is 100% JSON serializable
        json_output = json.dumps(result)
        parsed_json = json.loads(json_output)
        assert parsed_json["status"] == "error"
