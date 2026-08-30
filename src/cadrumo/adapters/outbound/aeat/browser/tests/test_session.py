"""Fixture-backed site-health contracts used by browser navigation.

Browser ownership, storage-state loading, certificate provisioning, and
process teardown are exercised against real Playwright in ``test_factory``.
This module keeps the deterministic on-disk AEAT response corpus bound to the
production health classifier used by ``BrowserSession.navigate``.
"""

import pytest

from ......core.config import Settings
from ......core.errors.hierarchy import SiteHealthError, SiteHealthState
from ......tests import FIXTURES_DIR
from .._site_health_probe import probe_response

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FIXTURES_ROOT = FIXTURES_DIR / "site_health"
_PROBE_URL = f"{Settings.external_constants().aeat.domains.sede}/"


def _probe_or_raise(
    url: str,
    http_status: int,
    headers: dict[str, str],
    body: str,
    *,
    rate_limit_retry_after_default: int,
) -> None:
    """Call the production classifier and surface its typed health error."""
    result = probe_response(
        url,
        http_status,
        headers,
        body,
        rate_limit_retry_after_default=rate_limit_retry_after_default,
    )
    if result is not None:
        raise SiteHealthError(status=result)


def test_navigate_probe_raises_on_mantenimiento_fixture() -> None:
    body = (_FIXTURES_ROOT / "mantenimiento" / "interstitial.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError, match=r"(?i)mantenimiento") as excinfo:
        _probe_or_raise(_PROBE_URL, 200, {}, body, rate_limit_retry_after_default=300)
    assert excinfo.value.status.state is SiteHealthState.MANTENIMIENTO
    assert excinfo.value.context is not None
    assert excinfo.value.context["url"] == _PROBE_URL
    assert excinfo.value.context["http_status"] == 200
    assert "detected_markers" in excinfo.value.context


def test_navigate_probe_raises_on_waf_fixture() -> None:
    body = (_FIXTURES_ROOT / "waf_challenge" / "request_blocked.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError, match=r"(?i)waf[ _]?challenge") as excinfo:
        _probe_or_raise(_PROBE_URL, 403, {}, body, rate_limit_retry_after_default=300)
    assert excinfo.value.status.state is SiteHealthState.WAF_CHALLENGE


def test_navigate_probe_raises_on_rate_limit_fixture() -> None:
    body = (_FIXTURES_ROOT / "rate_limited" / "429_retry_after.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError, match=r"(?i)rate[ _]?limited") as excinfo:
        _probe_or_raise(
            _PROBE_URL,
            429,
            {"Retry-After": "120"},
            body,
            rate_limit_retry_after_default=300,
        )
    assert excinfo.value.status.state is SiteHealthState.RATE_LIMITED
    assert excinfo.value.status.retry_after_seconds == 120


def test_navigate_probe_passes_on_ok_fixture() -> None:
    body = (_FIXTURES_ROOT / "ok" / "sede_landing.html").read_text(encoding="utf-8")
    assert body, "ok fixture body must be non-empty for the probe test to be meaningful"
    result = _probe_or_raise(_PROBE_URL, 200, {}, body, rate_limit_retry_after_default=300)
    assert result is None
