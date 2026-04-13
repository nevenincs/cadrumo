"""Unit tests for ``aeat browser health`` (#95).

Every test replaces the module-level :data:`PROBE_FACTORY` attribute
on :mod:`aeat.cli.browser.health` with a concrete async factory that
returns a real test-double class implementing the
:class:`HealthProbeLike` protocol. The double raises a real
:class:`aeat.errors.SiteHealthError` constructed from real HTML
fixtures under ``tests/fixtures/site_health/``. No ``unittest.mock``
usage.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.cli.browser import app
from aeat.cli.browser import health as health_module
from aeat.config import PROJECT_ROOT, Settings
from aeat.errors import SiteHealthError
from aeat.status import SiteHealthState
from aeat.status._site_health_parsers import evaluate_response

_RUNNER = CliRunner()
_FIXTURES_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "site_health"


class _HealthyProbe:
    """Concrete probe double: always classifies the target as healthy."""

    async def probe(self, url: str) -> None:
        del url
        return None


class _RaisingProbe:
    """Concrete probe double: raises a pre-built ``SiteHealthError``."""

    def __init__(self, error: SiteHealthError) -> None:
        self._error = error

    async def probe(self, url: str) -> None:
        del url
        raise self._error


def _status_from_fixture(fixture_path: Path, *, http_status: int) -> SiteHealthError:
    body = fixture_path.read_text(encoding="utf-8")
    status = evaluate_response(
        "https://sede.agenciatributaria.gob.es/",
        http_status,
        {},
        body,
        rate_limit_retry_after_default=300,
    )
    assert status is not None
    return SiteHealthError(status=status)


def _install_factory(
    monkeypatch: pytest.MonkeyPatch,
    probe_builder: Callable[[], object],
) -> None:
    async def _factory(settings: Settings) -> object:
        del settings
        return probe_builder()

    monkeypatch.setattr(health_module, "PROBE_FACTORY", _factory)


@pytest.mark.unit
def test_health_ok_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_factory(monkeypatch, _HealthyProbe)
    result = _RUNNER.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "state=ok" in result.stdout


@pytest.mark.unit
def test_health_ok_json_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_factory(monkeypatch, _HealthyProbe)
    result = _RUNNER.invoke(app, ["health", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "ok"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("fixture_rel", "http_status", "expected_state", "expected_exit"),
    [
        ("mantenimiento/interstitial.html", 200, SiteHealthState.MANTENIMIENTO, 2),
        ("waf_challenge/request_blocked.html", 403, SiteHealthState.WAF_CHALLENGE, 3),
        ("rate_limited/429_retry_after.html", 429, SiteHealthState.RATE_LIMITED, 4),
    ],
)
def test_health_exit_code_table(
    monkeypatch: pytest.MonkeyPatch,
    fixture_rel: str,
    http_status: int,
    expected_state: SiteHealthState,
    expected_exit: int,
) -> None:
    error = _status_from_fixture(_FIXTURES_ROOT / fixture_rel, http_status=http_status)
    # rate-limited fixtures need headers for Retry-After extraction:
    if expected_state is SiteHealthState.RATE_LIMITED:
        body = (_FIXTURES_ROOT / fixture_rel).read_text(encoding="utf-8")
        status = evaluate_response(
            "https://sede.agenciatributaria.gob.es/",
            http_status,
            {"Retry-After": "120"},
            body,
            rate_limit_retry_after_default=300,
        )
        assert status is not None
        error = SiteHealthError(status=status)

    def _builder() -> _RaisingProbe:
        return _RaisingProbe(error)

    _install_factory(monkeypatch, _builder)
    result = _RUNNER.invoke(app, ["health"])
    assert result.exit_code == expected_exit
    assert f"state={expected_state.value}" in result.stdout


@pytest.mark.unit
def test_health_json_emits_parseable_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    error = _status_from_fixture(
        _FIXTURES_ROOT / "mantenimiento" / "interstitial.html",
        http_status=200,
    )
    _install_factory(monkeypatch, lambda: _RaisingProbe(error))
    result = _RUNNER.invoke(app, ["health", "--json"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["state"] == "mantenimiento"
    assert payload["evidence"]["http_status"] == 200
