from apps.backend.workers.report_worker import security_score_from_cvss, _severity_for_cvss


def test_none_and_zero_are_100():
    assert security_score_from_cvss(None) == 100
    assert security_score_from_cvss(0.0) == 100
    assert _severity_for_cvss(None) == "NONE"
    assert _severity_for_cvss(0.0) == "NONE"


def test_low_band():
    assert 60 <= security_score_from_cvss(3.9) <= 80
    assert 60 <= security_score_from_cvss(2.0) <= 80
    assert _severity_for_cvss(3.9) == "LOW"


def test_medium_band():
    assert security_score_from_cvss(4.0) == 60
    assert 30 <= security_score_from_cvss(5.3) <= 60
    assert security_score_from_cvss(6.9) == 30
    assert _severity_for_cvss(5.3) == "MEDIUM"


def test_high_band():
    assert security_score_from_cvss(7.0) == 30
    assert 10 <= security_score_from_cvss(8.0) <= 30
    assert security_score_from_cvss(8.9) == 10
    assert _severity_for_cvss(8.9) == "HIGH"


def test_critical_band():
    assert security_score_from_cvss(9.0) == 10
    assert security_score_from_cvss(10.0) == 0
    assert _severity_for_cvss(9.0) == "CRITICAL"
