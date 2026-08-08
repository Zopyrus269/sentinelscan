import json
from pathlib import Path

from apps.backend.workers.report_worker import generate_report


def _load_report(result):
    assert "error" not in result
    return json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))


def test_unscored_medium_cannot_coexist_with_na_max_cvss():
    report = _load_report(generate_report(
        target="example.test",
        findings=[{
            "worker": "ssl_check",
            "title": "Potential TLS issue",
            "severity": "MEDIUM",
            "summary": "Potential TLS issue",
            "what_it_means": "Needs scoring.",
            "recommendation": "Review.",
            "actionable": True,
            "evidence": {"protocol": "TLSv1.2"},
        }],
        cvss_scores=[],
    ))
    assert report["maximum_cvss"] is None
    assert report["security_score"] == 100
    assert report["overall_risk_summary"]["MEDIUM"] == 0
    assert report["overall_risk_summary"]["INFORMATIONAL"] == 1
    assert report["findings"][0]["severity"] == "INFORMATIONAL"
    assert report["findings"][0]["cvss_status"] == "UNSCORED"


def test_validated_medium_score_drives_both_badge_and_gauge():
    report = _load_report(generate_report(
        target="example.test",
        findings=[{
            "worker": "ssl_check",
            "title": "Validated TLS issue",
            "severity": "MEDIUM",
            "summary": "Validated TLS issue",
            "what_it_means": "Validated issue.",
            "recommendation": "Review.",
            "actionable": True,
            "evidence": {"protocol": "TLSv1.0"},
        }],
        cvss_scores=[{
            "finding": "Validated TLS issue",
            "base_score": 5.3,
            "severity": "MEDIUM",
            "vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:L/A:N",
        }],
    ))
    assert report["maximum_cvss"] == 5.3
    assert report["security_score"] == 47
    assert report["overall_risk_summary"]["MEDIUM"] == 1
    assert report["overall_risk_summary"]["INFORMATIONAL"] == 0
    assert report["findings"][0]["severity"] == "MEDIUM"
    assert report["findings"][0]["cvss_base_score"] == 5.3


def test_dns_observation_can_never_create_cvss_risk():
    report = _load_report(generate_report(
        target="example.test",
        findings=[{
            "worker": "dns_lookup",
            "title": "Public DNS records",
            "severity": "MEDIUM",
            "summary": "DNS resolved normally.",
            "actionable": True,
            "evidence": {"A": ["192.0.2.1"]},
        }],
        cvss_scores=[{
            "finding": "Public DNS records",
            "base_score": 5.3,
            "severity": "MEDIUM",
            "vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:L/A:N",
        }],
    ))
    assert report["maximum_cvss"] is None
    assert report["security_score"] == 100
    assert report["overall_risk_summary"]["MEDIUM"] == 0
    assert report["overall_risk_summary"]["INFORMATIONAL"] == 1
    assert report["cvss_scores"] == []
