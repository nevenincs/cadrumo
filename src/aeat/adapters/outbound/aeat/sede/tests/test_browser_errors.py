"""Real-behavior tests for BrowserAdapterTypeError at the three sede adapter raises.

Each test synthesizes a minimal hand-rolled BrowserContext stand-in whose
``new_page()`` coroutine returns a non-Page sentinel object. The stand-in
satisfies only the interface required by the code under test and avoids any
import from ``unittest.mock``.

Coverage:
- contract-A: BrowserAdapterTypeError is bound in ERROR_REGISTRY.
- contract-B: build_error_envelope produces a valid envelope for BrowserAdapterTypeError.
- contract-C: _open_renta_web_open_session raises BrowserAdapterTypeError when
  new_page() returns a non-Page.
- contract-D: collect_nif_iva_check_observations raises BrowserAdapterTypeError when
  new_page() returns a non-Page.
- contract-E: collect_groi_observations raises BrowserAdapterTypeError when
  new_page() returns a non-Page.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from ......core.config import Settings
from ......core.errors import ERROR_REGISTRY, build_error_envelope
from .._errors import BrowserAdapterTypeError
from .._groi_check import collect_groi_observations
from .._nif_iva_check import collect_nif_iva_check_observations
from .._renta_web_open import _open_renta_web_open_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# ---------------------------------------------------------------------------
# Hand-rolled stand-ins — NOT unittest.mock objects
# ---------------------------------------------------------------------------


class _NonPageSentinel:
    """A deliberately wrong return type for BrowserContext.new_page()."""


class _FakeBrowserContext:
    """Minimal BrowserContext stand-in that returns a non-Page from new_page()."""

    async def new_page(self) -> _NonPageSentinel:
        return _NonPageSentinel()

    async def close(self) -> None:
        pass


class _FakeBrowserSession:
    """Minimal browser-session stand-in that vends _FakeBrowserContext."""

    async def create_context(self, **_kwargs: Any) -> _FakeBrowserContext:
        return _FakeBrowserContext()

    async def close(self) -> None:
        pass


class _FakeLivePayload:
    """Minimal live-payload stand-in (only fields accessed before new_page())."""

    timeout_ms: int = 5_000
    app_url: str = Settings.external_constants().aeat.oracles.renta_web_open_app_template.format(year=2026)
    casilla_overrides: dict[str, object] = {}
    scrape_casillas: tuple[str, ...] = ()


async def _fake_browser_factory(_settings: Any) -> _FakeBrowserSession:
    return _FakeBrowserSession()


# ---------------------------------------------------------------------------
# contract-A: registry binding
# ---------------------------------------------------------------------------


def test_browser_adapter_type_error_is_registered_in_error_registry() -> None:
    assert "ERROR_SEDE_BROWSER_ADAPTER_TYPE" in ERROR_REGISTRY


# ---------------------------------------------------------------------------
# contract-B: envelope round-trip
# ---------------------------------------------------------------------------


def test_browser_adapter_type_error_round_trips_through_build_error_envelope() -> None:
    err = BrowserAdapterTypeError(
        "BrowserContext.new_page() did not return a Playwright Page; got <class 'str'>",
        context={"actual_type": "str"},
    )
    envelope = build_error_envelope(err)
    assert envelope.code == "ERROR_SEDE_BROWSER_ADAPTER_TYPE"
    assert envelope.retryable is False
    assert "actual_type" in (envelope.context or {})


# ---------------------------------------------------------------------------
# contract-C: _renta_web_open_session raise
# ---------------------------------------------------------------------------


def test_open_renta_web_open_session_raises_browser_adapter_type_error_on_wrong_page_type() -> None:
    """_open_renta_web_open_session must raise BrowserAdapterTypeError when
    the stand-in BrowserContext.new_page() returns a non-Page object."""

    fake_session = _FakeBrowserSession()
    fake_payload = _FakeLivePayload()

    with pytest.raises(BrowserAdapterTypeError) as exc_info:
        asyncio.run(
            _open_renta_web_open_session(
                fake_session,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # test double
                live_payload=fake_payload,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # test double
            )
        )

    assert "actual_type" in (exc_info.value.context or {})
    assert exc_info.value.context is not None
    assert exc_info.value.context["actual_type"] == "_NonPageSentinel"


# ---------------------------------------------------------------------------
# contract-D: nif_iva_check raise
# ---------------------------------------------------------------------------


def test_collect_nif_iva_check_observations_raises_browser_adapter_type_error_on_wrong_page_type() -> None:
    """collect_nif_iva_check_observations must raise BrowserAdapterTypeError when
    the injected BrowserContext.new_page() returns a non-Page object.

    A fake factory is passed via the production
    ``browser_session_factory`` DI parameter.
    """

    with pytest.raises(BrowserAdapterTypeError) as exc_info:
        asyncio.run(
            collect_nif_iva_check_observations(
                b"",
                expected={"ES12345678A": None},
                # test double: factory vends a fake session, not a real BrowserSession
                browser_session_factory=_fake_browser_factory,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            )
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["actual_type"] == "_NonPageSentinel"


# ---------------------------------------------------------------------------
# contract-E: groi_check raise
# ---------------------------------------------------------------------------


def test_collect_groi_observations_raises_browser_adapter_type_error_on_wrong_page_type() -> None:
    """collect_groi_observations must raise BrowserAdapterTypeError when
    the injected BrowserContext.new_page() returns a non-Page object.

    A fake factory is passed via the production
    ``browser_session_factory`` DI parameter.
    """

    with pytest.raises(BrowserAdapterTypeError) as exc_info:
        asyncio.run(
            collect_groi_observations(
                b"",
                expected={"B12345678": None},
                # test double: factory vends a fake session, not a real BrowserSession
                browser_session_factory=_fake_browser_factory,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            )
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["actual_type"] == "_NonPageSentinel"
