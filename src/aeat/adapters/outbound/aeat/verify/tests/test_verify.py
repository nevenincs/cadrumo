"""Unit tests for :func:`aeat.adapters.outbound.aeat.verify.verify_csv`.

Exercises the borrowed-vs-self-owned browser-session lifecycle of
:func:`verify_csv` using lightweight recording doubles that satisfy the
:class:`aeat.adapters.outbound.aeat.verify.VerifyBrowserSessionLike` shape.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from ......domain.calculations.registry import RegistryValidationError
from ... import verify as verify_module
from .. import (
    VerifyBrowserKeyboardLike,
    verify_csv,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _RecordingKeyboard:
    """Recording double mirroring the Playwright keyboard surface."""

    def __init__(self) -> None:
        self.typed: list[str] = []
        self.pressed: list[str] = []

    async def type(self, value: str) -> None:
        self.typed.append(value)

    async def press(self, key: str) -> None:
        self.pressed.append(key)


class _RecordingPage:
    """Recording double mirroring the Playwright page surface used by ``verify_csv``."""

    def __init__(self, body: str) -> None:
        self._body = body
        self.goto_calls: list[str] = []
        self.fill_calls: list[tuple[str, str]] = []
        self.press_calls: list[tuple[str, str]] = []
        self.keyboard: VerifyBrowserKeyboardLike = _RecordingKeyboard()

    async def goto(self, url: str) -> None:
        self.goto_calls.append(url)

    async def fill(self, selector: str, value: str) -> None:
        self.fill_calls.append((selector, value))

    async def press(self, selector: str, key: str) -> None:
        self.press_calls.append((selector, key))

    async def content(self) -> str:
        return self._body


class _RecordingContext:
    """Recording double for a Playwright browser context, returning a fixed page."""

    def __init__(self, page: _RecordingPage) -> None:
        self._page = page
        self.close_calls = 0

    async def new_page(self) -> _RecordingPage:
        return self._page

    async def close(self) -> None:
        self.close_calls += 1


class _RecordingBrowserSession:
    """Recording double satisfying the ``VerifyBrowserSessionLike`` shape consumed by ``verify_csv``."""

    def __init__(self, body: str) -> None:
        self.page = _RecordingPage(body)
        self.context = _RecordingContext(self.page)
        self.create_context_calls = 0
        self.close_calls = 0

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> _RecordingContext:
        del provisioner, storage_state_path, storage_state
        self.create_context_calls += 1
        return self.context

    async def close(self) -> None:
        self.close_calls += 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body, expected",
    [
        # AEAT confirmation tokens — each alone is sufficient.
        ("<html><p>Documento válido en el Registro General.</p></html>", True),
        ("<html><p>El CSV introducido es correcto.</p></html>", True),
        # ASCII fallback without diacritics.
        ("<html><p>Documento valido en el Registro.</p></html>", True),
        # Unknown / not-found response.
        ("<html><p>El CSV no se encuentra en el registro.</p></html>", False),
        # Completely empty body.
        ("", False),
    ],
)
async def test_verify_csv_parse_contract(body: str, expected: bool) -> None:
    """The AEAT response parser identifies valid documents by the presence
    of the Spanish confirmation tokens ('válido', 'valido', 'correcto').
    Any other body — including an empty or unknown response — returns False.

    These assertions exercise the production parse path end-to-end through
    the recording double; the exact HTML fragments mirror the categories
    AEAT returns in practice so a regression in token matching fails here.
    """
    session = _RecordingBrowserSession(body)

    result = await verify_csv(" abcd1234 ", browser=session)

    assert result is expected, f"body {body!r} → expected {expected}, got {result}"


@pytest.mark.asyncio
async def test_verify_csv_does_not_close_borrowed_browser_session() -> None:
    """Borrowed sessions remain caller-owned: the context is closed but
    the session itself is NOT closed.

    Parse result is a side-effect of the body; the session-lifetime
    assertions are the primary contract here.  The body is chosen to
    produce a known True result so the caller does not receive a
    surprising value alongside the lifecycle guarantee.
    """
    session = _RecordingBrowserSession("<html>documento válido</html>")

    assert isinstance(session, verify_module.VerifyBrowserSessionLike)
    result = await verify_csv(" abcd1234 ", browser=session)

    # Session-lifetime contract.
    assert session.create_context_calls == 1
    assert session.context.close_calls == 1  # context is always closed
    assert session.close_calls == 0  # borrowed → caller keeps ownership
    assert session.page.goto_calls == [verify_module._VERIFY_URL]
    # Confirm parse result is coherent with the body (covered in detail
    # by test_verify_csv_parse_contract).
    assert result is True


@pytest.mark.asyncio
async def test_verify_csv_closes_self_owned_session_and_playwright() -> None:
    """Self-owned sessions must be closed after the round-trip completes.

    The body produces a False parse result (no confirmation token) which
    verifies the self-ownership path is exercised on an unknown-document
    response — the more common real-world outcome for a mis-typed CSV.
    """
    session = _RecordingBrowserSession("<html>documento desconocido</html>")
    assert isinstance(session, verify_module.VerifyBrowserSessionLike)
    session_like = session

    async def _factory() -> verify_module.VerifyBrowserSessionLike:
        return session_like

    original_factory = verify_module.DEFAULT_BROWSER_SESSION_FACTORY
    verify_module.DEFAULT_BROWSER_SESSION_FACTORY = _factory
    try:
        result = await verify_module.verify_csv("ABCD1234EFGH5678")
    finally:
        verify_module.DEFAULT_BROWSER_SESSION_FACTORY = original_factory

    # Session-lifetime contract: self-owned session AND context are closed.
    assert session.create_context_calls == 1
    assert session.context.close_calls == 1
    assert session.close_calls == 1  # self-owned → must close
    # Parse result matches the body (no confirmation token → False).
    assert result is False


@pytest.mark.asyncio
async def test_build_default_browser_session_raises_browser_adapter_type_error_on_wrong_type() -> None:
    """When default_browser_session_factory returns a non-VerifyBrowserSessionLike
    object, _build_default_browser_session must raise BrowserAdapterTypeError —
    a typed, registered envelope — not the bare built-in TypeError.

    A hand-rolled sentinel that is not a VerifyBrowserSessionLike is returned
    by a factory passed via the production DI seam; the raised exception
    class is asserted directly so any regression to bare TypeError fails
    this test.
    """
    from ......core.config import Settings

    class _NotASession:
        """Intentionally wrong type — satisfies no browser-session protocol."""

    sentinel = _NotASession()

    async def _bad_factory(settings: Settings) -> object:
        return sentinel

    with pytest.raises(verify_module._BrowserAdapterTypeError) as exc_info:
        await verify_module._build_default_browser_session(factory=_bad_factory)

    assert "_NotASession" in str(exc_info.value)


def test_browser_adapter_type_error_is_registered() -> None:
    """BrowserAdapterTypeError must be present in ERROR_REGISTRY under the
    expected code so the error infrastructure can build a typed envelope
    without KeyError at runtime.
    """
    from ......core.errors import ERROR_REGISTRY

    assert "ERROR_SEDE_BROWSER_ADAPTER_TYPE" in ERROR_REGISTRY, (
        "'ERROR_SEDE_BROWSER_ADAPTER_TYPE' not found in ERROR_REGISTRY; "
        "add it to src/aeat/core/errors/registry/_adapters.py"
    )


def test_browser_adapter_type_error_round_trips_build_error_envelope() -> None:
    """build_error_envelope must produce a valid ErrorEnvelope for BrowserAdapterTypeError
    without raising — confirming the registry binding covers the full envelope pipeline.
    """
    from ......core.errors import build_error_envelope
    from ...sede._errors import BrowserAdapterTypeError

    exc = BrowserAdapterTypeError("default_browser_session_factory returned an incompatible type: <class 'object'>")
    envelope = build_error_envelope(exc)

    assert envelope.code == "ERROR_SEDE_BROWSER_ADAPTER_TYPE"
    assert envelope.category == "ERROR"


def test_verify_csv_guard_rejects_non_read_method() -> None:
    with pytest.raises(RegistryValidationError, match="remote write method"):
        verify_module._assert_verify_http("POST", verify_module._VERIFY_URL)


def test_verify_csv_guard_rejects_mutating_action() -> None:
    with pytest.raises(RegistryValidationError, match="browser action token"):
        verify_module._assert_verify_action("Presentar declaracion")


def test_verify_csv_guard_rejects_unclassified_action() -> None:
    with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
        verify_module._assert_verify_action("new-unreviewed-csv-action")
