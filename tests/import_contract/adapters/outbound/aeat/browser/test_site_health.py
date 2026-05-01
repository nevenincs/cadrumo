"""Colocated unit tests for site-health models and parsers (#95).

The module is marked ``unit`` / ``domain_outbound`` and drives the parser suite
from real HTML strings loaded off disk under
``tests/fixtures/site_health/``. No mocks, patches, fakes, or stubs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aeat.application.workflow import SiteHealthAlert, WorkflowStage
from aeat.core.config import PROJECT_ROOT
from aeat.adapters.outbound.aeat.browser import (
    SiteHealthEvidence,
    SiteHealthState,
    SiteHealthStatus,
    evaluate_response,
    parse_mantenimiento_banner,
    parse_rate_limit_response,
    parse_waf_challenge,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]

_FIXTURES_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "site_health"
_PROBE_URL = "https://sede.agenciatributaria.gob.es/"
_RATE_LIMIT_DEFAULT = 300


def _load_case(path: Path, *, default_status: int) -> tuple[int, dict[str, str], str]:
    """Return ``(http_status, headers, body)`` for a fixture file."""
    headers_path = path.with_suffix(".headers.json")
    if headers_path.exists():
        payload = json.loads(headers_path.read_text(encoding="utf-8"))
        http_status = int(payload["http_status"])
        headers_raw = payload.get("headers", {})
        headers = {str(k): str(v) for k, v in headers_raw.items()}
    else:
        http_status = default_status
        headers = {}
    body = path.read_text(encoding="utf-8")
    return http_status, headers, body


def _fixture_files(state_dir: str) -> tuple[Path, ...]:
    folder = _FIXTURES_ROOT / state_dir
    return tuple(sorted(folder.glob("*.html")))


_MANTENIMIENTO_FILES = _fixture_files("mantenimiento")
_WAF_FILES = _fixture_files("waf_challenge")
_RATE_LIMITED_FILES = _fixture_files("rate_limited")
_OK_FILES = _fixture_files("ok")


class TestFixtureCorpusShape:
    """Guardrails: ensure the fixture corpus meets the plan minimums."""

    def test_mantenimiento_has_five_positives(self) -> None:
        assert len(_MANTENIMIENTO_FILES) >= 5

    def test_waf_has_five_positives(self) -> None:
        assert len(_WAF_FILES) >= 5

    def test_rate_limited_has_five_positives(self) -> None:
        assert len(_RATE_LIMITED_FILES) >= 5

    def test_ok_has_five_negatives(self) -> None:
        assert len(_OK_FILES) >= 5


@pytest.mark.parametrize("path", _MANTENIMIENTO_FILES, ids=lambda p: p.name)
def test_mantenimiento_fixtures_classify(path: Path) -> None:
    http_status, headers, body = _load_case(path, default_status=200)
    status = evaluate_response(
        _PROBE_URL,
        http_status,
        headers,
        body,
        rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
    )
    assert status is not None, f"mantenimiento fixture {path.name} did not classify"
    assert status.state is SiteHealthState.MANTENIMIENTO
    assert status.evidence.detected_markers
    single = parse_mantenimiento_banner(
        _PROBE_URL,
        http_status,
        headers,
        body,
        rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
    )
    assert single is not None
    assert single.state is SiteHealthState.MANTENIMIENTO


@pytest.mark.parametrize("path", _WAF_FILES, ids=lambda p: p.name)
def test_waf_fixtures_classify(path: Path) -> None:
    http_status, headers, body = _load_case(path, default_status=403)
    status = evaluate_response(
        _PROBE_URL,
        http_status,
        headers,
        body,
        rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
    )
    assert status is not None, f"waf fixture {path.name} did not classify"
    assert status.state is SiteHealthState.WAF_CHALLENGE
    assert status.evidence.detected_markers
    single = parse_waf_challenge(
        _PROBE_URL,
        http_status,
        headers,
        body,
        rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
    )
    assert single is not None
    assert single.state is SiteHealthState.WAF_CHALLENGE


@pytest.mark.parametrize("path", _RATE_LIMITED_FILES, ids=lambda p: p.name)
def test_rate_limited_fixtures_classify(path: Path) -> None:
    http_status, headers, body = _load_case(path, default_status=429)
    status = evaluate_response(
        _PROBE_URL,
        http_status,
        headers,
        body,
        rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
    )
    assert status is not None, f"rate-limited fixture {path.name} did not classify"
    assert status.state is SiteHealthState.RATE_LIMITED
    assert status.retry_after_seconds is not None
    assert status.retry_after_seconds >= 1
    # The single parser must produce the same verdict.
    single = parse_rate_limit_response(
        _PROBE_URL,
        http_status,
        headers,
        body,
        rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
    )
    assert single is not None
    assert single.state is SiteHealthState.RATE_LIMITED


@pytest.mark.parametrize("path", _OK_FILES, ids=lambda p: p.name)
def test_ok_fixtures_do_not_classify(path: Path) -> None:
    http_status, headers, body = _load_case(path, default_status=200)
    status = evaluate_response(
        _PROBE_URL,
        http_status,
        headers,
        body,
        rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
    )
    assert status is None, f"ok fixture {path.name} unexpectedly classified as {status}"


class TestMantenimientoTitleOnlyGuard:
    """ADR Decision 2.1: title-only hits must never classify."""

    def test_title_only_is_not_classified_as_mantenimiento(self) -> None:
        # Title carries the "interrupcion" marker, body carries none.
        # Note: _matches_mantenimiento scans the full lowered HTML so
        # any body-equivalent marker in the title counts as a body hit;
        # we therefore use "interrupcion" in the title (a title-only
        # marker per _MANTENIMIENTO_TITLE_MARKERS) rather than
        # "mantenimiento" (which is also a body marker).
        html = (
            "<html><head><title>Interrupcion</title></head>"
            "<body><p>Welcome to our tax portal. All services are up.</p>"
            "<p>Please log in to continue.</p></body></html>"
        )
        from aeat.adapters.outbound.aeat.browser._site_health_parsers import _extract_title, _matches_mantenimiento

        lowered = html.lower()
        title = _extract_title(html, lowered)
        hits = _matches_mantenimiento(lowered, title)
        assert any(h.startswith("title:") for h in hits)
        assert not any(not h.startswith("title:") for h in hits)

        status = parse_mantenimiento_banner(
            _PROBE_URL,
            200,
            {},
            html,
            rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
        )
        assert status is None

        via_evaluate = evaluate_response(
            _PROBE_URL,
            200,
            {},
            html,
            rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
        )
        assert via_evaluate is None

    def test_one_body_marker_plus_title_classifies(self) -> None:
        html = (
            "<html><head><title>Interrupcion del servicio</title></head>"
            "<body><p>Estamos realizando tareas de mantenimiento.</p></body></html>"
        )
        status = parse_mantenimiento_banner(
            _PROBE_URL,
            503,
            {},
            html,
            rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
        )
        assert status is not None
        assert status.state is SiteHealthState.MANTENIMIENTO


class TestRateLimitRetryAfter:
    def test_default_used_when_header_missing(self) -> None:
        path = _FIXTURES_ROOT / "rate_limited" / "429_no_header.html"
        http_status, headers, body = _load_case(path, default_status=429)
        status = parse_rate_limit_response(
            _PROBE_URL,
            http_status,
            headers,
            body,
            rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
        )
        assert status is not None
        assert status.retry_after_seconds == _RATE_LIMIT_DEFAULT

    def test_header_value_parsed_when_present(self) -> None:
        path = _FIXTURES_ROOT / "rate_limited" / "429_retry_after.html"
        http_status, headers, body = _load_case(path, default_status=429)
        status = parse_rate_limit_response(
            _PROBE_URL,
            http_status,
            headers,
            body,
            rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
        )
        assert status is not None
        assert status.retry_after_seconds == 120

    def test_http_date_retry_after_computes_delta(self) -> None:
        """An RFC 9110 HTTP-date ``Retry-After`` yields a positive delta."""
        now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC)
        future = now + timedelta(seconds=180)
        http_date = format_datetime(future, usegmt=True)
        body = "<html><body>slow down</body></html>"
        status = parse_rate_limit_response(
            _PROBE_URL,
            429,
            {"Retry-After": http_date},
            body,
            rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
            now=now,
        )
        assert status is not None
        assert status.retry_after_seconds == 180
        assert any("http-date" in m for m in status.evidence.detected_markers)

    def test_http_date_retry_after_in_past_falls_back_to_default(self) -> None:
        """A past HTTP-date clamps to zero and falls back to the default."""
        now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC)
        past = now - timedelta(seconds=600)
        http_date = format_datetime(past, usegmt=True)
        body = "<html><body>slow down</body></html>"
        status = parse_rate_limit_response(
            _PROBE_URL,
            429,
            {"Retry-After": http_date},
            body,
            rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
            now=now,
        )
        assert status is not None
        assert status.retry_after_seconds == _RATE_LIMIT_DEFAULT

    def test_invalid_retry_after_falls_back_to_default(self) -> None:
        status = parse_rate_limit_response(
            _PROBE_URL,
            429,
            {"Retry-After": "not-a-number-nor-a-date"},
            "<html></html>",
            rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
        )
        assert status is not None
        assert status.retry_after_seconds == _RATE_LIMIT_DEFAULT

    def test_503_with_mantenimiento_yields_to_mantenimiento(self) -> None:
        """A 503 carrying mantenimiento markers must classify as MANTENIMIENTO."""
        body = (_FIXTURES_ROOT / "mantenimiento" / "interstitial.html").read_text(encoding="utf-8")
        status = evaluate_response(
            _PROBE_URL,
            503,
            {"Retry-After": "45"},
            body,
            rate_limit_retry_after_default=_RATE_LIMIT_DEFAULT,
        )
        assert status is not None
        assert status.state is SiteHealthState.MANTENIMIENTO


# ── Model-shape tests ──────────────────────────────────────────────────


def _evidence(**overrides: object) -> SiteHealthEvidence:
    from aeat.adapters.outbound.aeat.browser._site_health import _URL_ADAPTER

    base: dict[str, object] = {
        "url": _URL_ADAPTER.validate_python("https://sede.agenciatributaria.gob.es/"),
        "http_status": 200,
        "html_fragment": "<html></html>",
        "detected_markers": ("marker",),
    }
    base.update(overrides)
    return SiteHealthEvidence(**base)  # type: ignore[arg-type]


class TestSiteHealthModels:
    def test_evidence_accepts_valid_kwargs(self) -> None:
        ev = _evidence()
        assert ev.http_status == 200
        assert ev.detected_markers == ("marker",)

    def test_evidence_rejects_unknown_key(self) -> None:
        from aeat.adapters.outbound.aeat.browser._site_health import _URL_ADAPTER

        valid_url = _URL_ADAPTER.validate_python("https://sede.agenciatributaria.gob.es/")
        with pytest.raises(ValidationError):
            SiteHealthEvidence.model_validate(
                {
                    "url": valid_url,
                    "http_status": 200,
                    "html_fragment": "",
                    "detected_markers": (),
                    "bogus": "field",
                }
            )

    def test_evidence_rejects_out_of_bounds_status(self) -> None:
        with pytest.raises(ValidationError):
            _evidence(http_status=99)
        with pytest.raises(ValidationError):
            _evidence(http_status=600)

    def test_evidence_rejects_over_long_fragment(self) -> None:
        with pytest.raises(ValidationError):
            _evidence(html_fragment="x" * 4097)

    def test_evidence_rejects_empty_marker(self) -> None:
        with pytest.raises(ValidationError):
            _evidence(detected_markers=("",))

    def test_evidence_rejects_over_long_marker(self) -> None:
        with pytest.raises(ValidationError):
            _evidence(detected_markers=("x" * 129,))

    def test_status_requires_observed_at_tzaware(self) -> None:
        ev = _evidence()
        status = SiteHealthStatus(
            state=SiteHealthState.OK,
            evidence=ev,
            observed_at=datetime.now(tz=UTC),
        )
        assert status.state is SiteHealthState.OK

    def test_status_rejects_zero_retry_after(self) -> None:
        ev = _evidence()
        with pytest.raises(ValidationError):
            SiteHealthStatus(
                state=SiteHealthState.RATE_LIMITED,
                evidence=ev,
                observed_at=datetime.now(tz=UTC),
                retry_after_seconds=0,
            )

    def test_alert_composes_stage_and_status(self) -> None:
        ev = _evidence()
        status = SiteHealthStatus(
            state=SiteHealthState.MANTENIMIENTO,
            evidence=ev,
            observed_at=datetime.now(tz=UTC),
        )
        alert = SiteHealthAlert(
            stage=WorkflowStage.BUILDING_DRAFT,
            status=status,
            run_id="run-1234",
        )
        assert alert.stage is WorkflowStage.BUILDING_DRAFT
        assert alert.status.state is SiteHealthState.MANTENIMIENTO

    def test_alert_rejects_empty_run_id(self) -> None:
        ev = _evidence()
        status = SiteHealthStatus(
            state=SiteHealthState.MANTENIMIENTO,
            evidence=ev,
            observed_at=datetime.now(tz=UTC),
        )
        with pytest.raises(ValidationError):
            SiteHealthAlert(
                stage=WorkflowStage.BUILDING_DRAFT,
                status=status,
                run_id="",
            )
