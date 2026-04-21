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

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...config import PROJECT_ROOT, Settings
from ...errors import SiteHealthError
from ...status import SiteHealthState
from ...status._site_health_parsers import evaluate_response
from . import app
from . import health as health_module
from .health import _RealProbe

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

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


def test_health_ok_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_factory(monkeypatch, _HealthyProbe)
    result = _RUNNER.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "state=ok" in result.stdout


def test_health_ok_json_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_factory(monkeypatch, _HealthyProbe)
    result = _RUNNER.invoke(app, ["health", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "ok"


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


class _StubPlaywright:
    """Concrete recorder: counts stop() invocations. Never mocked."""

    def __init__(self) -> None:
        self.stop_calls = 0

    async def stop(self) -> None:
        self.stop_calls += 1


class _StubContext:
    """Concrete page-producing context that records close() calls."""

    def __init__(self) -> None:
        self.close_calls = 0

    async def new_page(self) -> object:
        class _Page:
            pass

        return _Page()

    async def close(self) -> None:
        self.close_calls += 1


class _RaisingCreateContextSession:
    """Session double whose create_context() always raises RuntimeError."""

    def __init__(self) -> None:
        self.create_context_calls = 0
        self.close_calls = 0

    async def create_context(self) -> object:
        self.create_context_calls += 1
        raise RuntimeError("boom from create_context")

    async def close(self) -> None:
        self.close_calls += 1

    async def navigate(self, page: object, url: str) -> None:
        del page, url
        raise AssertionError("navigate must not be reached when create_context raises")


class _RaisingNewPageSession:
    """Session double where create_context() succeeds but new_page() raises."""

    def __init__(self, context: _StubContext) -> None:
        self._context = context
        self.close_calls = 0

    async def create_context(self) -> _StubContext:
        return self._context

    async def close(self) -> None:
        self.close_calls += 1

    async def navigate(self, page: object, url: str) -> None:
        del page, url
        raise AssertionError("navigate must not be reached when new_page raises")


class _RaisingNewPageContext(_StubContext):
    async def new_page(self) -> object:
        raise RuntimeError("boom from new_page")


class TestRealProbeCleanup:
    """``_RealProbe`` must always release Playwright even on early errors."""

    def test_playwright_stop_runs_when_create_context_raises(self) -> None:
        session = _RaisingCreateContextSession()
        playwright = _StubPlaywright()
        probe = _RealProbe(session=session, playwright=playwright)
        with pytest.raises(RuntimeError, match="boom from create_context"):
            asyncio.run(probe.probe("https://sede.agenciatributaria.gob.es/"))
        assert session.create_context_calls == 1
        assert session.close_calls == 1
        assert playwright.stop_calls == 1

    def test_playwright_stop_and_context_close_run_when_new_page_raises(self) -> None:
        context = _RaisingNewPageContext()
        session = _RaisingNewPageSession(context=context)
        playwright = _StubPlaywright()
        probe = _RealProbe(session=session, playwright=playwright)
        with pytest.raises(RuntimeError, match="boom from new_page"):
            asyncio.run(probe.probe("https://sede.agenciatributaria.gob.es/"))
        assert context.close_calls == 1
        assert session.close_calls == 1
        assert playwright.stop_calls == 1


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
