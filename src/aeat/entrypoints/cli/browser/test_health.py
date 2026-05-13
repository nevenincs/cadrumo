"""Unit tests for ``aeat browser health``.

Every test uses the explicit probe-factory override seam exposed by
:mod:`aeat.entrypoints.cli.browser.health`. The doubles raise real
:class:`aeat.core.errors.SiteHealthError` instances constructed from real
HTML fixtures under ``src/aeat/tests/fixtures/site_health/``. No monkeypatching
or ``unittest`` usage.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.outbound.aeat.browser._site_health import SiteHealthState
from ....adapters.outbound.aeat.browser._site_health_parsers import evaluate_response
from ....core.config import Settings
from ....core.errors import SiteHealthError
from ....tests import FIXTURES_DIR
from . import app
from .health import HealthProbeLike, ProbeFactory, _RealProbe, override_probe_factory

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()
_FIXTURES_ROOT = FIXTURES_DIR / "site_health"


def _unwrap_result(output: str):
    return json.loads(output)["result"]


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


def _probe_factory(probe_builder: Callable[[], HealthProbeLike]) -> ProbeFactory:
    async def _factory(settings: Settings) -> HealthProbeLike:
        del settings
        return probe_builder()

    return _factory


def test_health_ok_exits_zero() -> None:
    with override_probe_factory(_probe_factory(_HealthyProbe)):
        result = _RUNNER.invoke(app, [])
    assert result.exit_code == 0
    assert "State=ok" in result.stdout


def test_health_ok_json_exits_zero() -> None:
    with override_probe_factory(_probe_factory(_HealthyProbe)):
        result = _RUNNER.invoke(app, ["--json"])
    assert result.exit_code == 0
    payload = _unwrap_result(result.stdout)
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

    with override_probe_factory(_probe_factory(_builder)):
        result = _RUNNER.invoke(app, [])
    assert result.exit_code == expected_exit
    assert f"State={expected_state.value}" in result.stdout


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
        from ....core.errors import AeatError

        class _SimulatedPlaywrightError(AeatError):
            pass

        raise _SimulatedPlaywrightError("boom from create_context")

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
        from ....core.errors import AeatError

        class _SimulatedPlaywrightError(AeatError):
            pass

        raise _SimulatedPlaywrightError("boom from new_page")


class TestRealProbeCleanup:
    """``_RealProbe`` must always release the central browser session on early errors."""

    def test_session_close_runs_when_create_context_raises(self) -> None:
        session = _RaisingCreateContextSession()
        probe = _RealProbe(session=session)
        from ....core.errors import AeatError

        with pytest.raises(AeatError, match="boom from create_context"):
            asyncio.run(probe.probe("https://sede.agenciatributaria.gob.es/"))
        assert session.create_context_calls == 1
        assert session.close_calls == 1

    def test_session_and_context_close_run_when_new_page_raises(self) -> None:
        context = _RaisingNewPageContext()
        session = _RaisingNewPageSession(context=context)
        probe = _RealProbe(session=session)
        from ....core.errors import AeatError

        with pytest.raises(AeatError, match="boom from new_page"):
            asyncio.run(probe.probe("https://sede.agenciatributaria.gob.es/"))
        assert context.close_calls == 1
        assert session.close_calls == 1


def test_health_json_emits_parseable_payload() -> None:
    error = _status_from_fixture(
        _FIXTURES_ROOT / "mantenimiento" / "interstitial.html",
        http_status=200,
    )
    with override_probe_factory(_probe_factory(lambda: _RaisingProbe(error))):
        result = _RUNNER.invoke(app, ["--json"])
    assert result.exit_code == 2
    payload = _unwrap_result(result.stdout)
    assert payload["state"] == "mantenimiento"
    assert payload["evidence"]["http_status"] == 200
