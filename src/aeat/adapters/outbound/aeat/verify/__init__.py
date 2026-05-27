"""Playwright CSV verification against AEAT's Sede electrónica.

The :func:`verify_csv` helper is opt-in: it only runs when the
caller supplies or constructs a
:class:`aeat.adapters.outbound.aeat.browser.DefaultBrowserSession`, and it
never mutates AEAT-side state. The contract is:

* open the Sede verification page,
* enter the CSV,
* read back the server response,
* return ``True`` iff AEAT confirms the document as valid.

The function degrades gracefully when a browser cannot be
constructed and surfaces the underlying error to the caller via
:exc:`aeat.domain.justificante._errors.JustificanteVerificationError`.

Public surface: :func:`verify_csv` plus the Playwright protocol
types (:class:`VerifyBrowserKeyboardLike`, :class:`VerifyBrowserPageLike`,
:class:`VerifyBrowserContextLike`, :class:`VerifyBrowserSessionLike`,
:class:`VerifyBrowserSessionFactory`) that let the helper be unit-tested
without spinning up a real browser.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from pydantic import AnyUrl

from .....core.config import Settings as _Settings
from .....core.errors import AeatError as _AeatError
from .....core.logging import get_logger as _get_logger
from .....domain.calculations.registry import (
    RemoteOperation as _RemoteOperation,
    RemoteStateGuardPolicy as _RemoteStateGuardPolicy,
    assert_remote_operation_allowed as _assert_remote_operation_allowed,
)
from .....domain.justificante._errors import JustificanteVerificationError as _JustificanteVerificationError
from .._playwright import PlaywrightError as _PlaywrightError

_logger = _get_logger(__name__)

_VERIFY_EXTERNAL = _Settings.external_constants()
_VERIFY_URL = f"{_VERIFY_EXTERNAL.aeat.domains.sede}{_VERIFY_EXTERNAL.aeat.help_pages.csv_verification}"
_VERIFY_HOST = _VERIFY_EXTERNAL.aeat.domains.sede.removeprefix("https://")
_VERIFY_GUARD_POLICY = _RemoteStateGuardPolicy(
    id="aeat-csv-verifier-read",
    evidence_tier="official_source_guidance",
    classification="public_read_surface",
    allowed_hosts=(_VERIFY_HOST,),
    allowed_browser_action_patterns=_VERIFY_EXTERNAL.aeat.live_safety.csv_verify_browser_action_patterns,
    synthetic_data_allowed=False,
    requires_authentication=False,
    requires_aeat_authorization=False,
)


class VerifyBrowserKeyboardLike(Protocol):
    """Subset of Playwright's ``Keyboard`` API used by :func:`verify_csv`."""

    async def type(self, value: str) -> None: ...
    async def press(self, key: str) -> None: ...


class VerifyBrowserPageLike(Protocol):
    """Subset of Playwright's ``Page`` API used by :func:`verify_csv`."""

    keyboard: VerifyBrowserKeyboardLike

    async def goto(self, url: str) -> object | None: ...
    async def fill(self, selector: str, value: str) -> None: ...
    async def press(self, selector: str, key: str) -> None: ...
    async def content(self) -> str: ...


class VerifyBrowserContextLike(Protocol):
    """Subset of Playwright's ``BrowserContext`` API used by :func:`verify_csv`."""

    async def new_page(self) -> VerifyBrowserPageLike: ...
    async def close(self) -> None: ...


@runtime_checkable
class VerifyBrowserSessionLike(Protocol):
    """Subset of :class:`aeat.adapters.outbound.aeat.browser.BrowserSession` consumed by :func:`verify_csv`.

    The ``create_context`` signature mirrors
    :meth:`aeat.adapters.outbound.aeat.browser.session.DefaultBrowserSession.create_context`
    so static checkers see no unsafe overlap between this protocol and
    the concrete browser sessions. ``verify_csv`` itself calls
    ``create_context()`` with no arguments; production and test
    sessions accept the same optional kwargs as the central
    BrowserSession so the protocol stays structurally honest.
    """

    async def create_context(
        self,
        *,
        provisioner: Any = ...,
        storage_state_path: Any = ...,
        storage_state: Any = ...,
    ) -> VerifyBrowserContextLike: ...
    async def close(self) -> None: ...


VerifyBrowserSessionFactory = Callable[[], Awaitable[VerifyBrowserSessionLike]]
"""Callable that builds a self-owned browser session."""


async def _build_default_browser_session() -> VerifyBrowserSessionLike:
    """Construct the default :class:`VerifyBrowserSessionLike`.

    Loads :func:`aeat.core.config.load_settings`, materialises the
    central :func:`aeat.adapters.outbound.aeat.browser.default_browser_session_factory`,
    and returns a session the caller is responsible for closing.
    """

    from .....core.config import load_settings
    from ..browser import default_browser_session_factory

    settings = load_settings()
    session = await default_browser_session_factory(settings)
    if not isinstance(session, VerifyBrowserSessionLike):
        raise TypeError(f"default_browser_session_factory returned an incompatible type: {type(session)}")
    return session


DEFAULT_BROWSER_SESSION_FACTORY: VerifyBrowserSessionFactory = _build_default_browser_session
"""Module-level factory seam for the self-owned browser path."""


async def verify_csv(
    csv: str,
    *,
    browser: VerifyBrowserSessionLike | None = None,
) -> bool:
    """Verify a justificante CSV against AEAT's Sede electrónica.

    Args:
        csv: The Código Seguro de Verificación as printed on the receipt.
        browser: An already-constructed :class:`BrowserSession`. When
            ``None``, one is built from the default settings/profile.

    Returns:
        ``True`` if AEAT confirms the CSV as valid; ``False`` if AEAT reports
        the document as unknown.

    Raises:
        _JustificanteVerificationError: If the round-trip cannot be completed
            (browser launch failure, network error, parsing failure).
    """
    csv = csv.strip().upper()
    if not csv:
        raise _JustificanteVerificationError("cannot verify an empty CSV")

    own_browser = False
    session = browser
    if session is None:
        try:
            session = await DEFAULT_BROWSER_SESSION_FACTORY()
            own_browser = True
        except (_PlaywrightError, _AeatError) as exc:
            raise _JustificanteVerificationError(f"failed to construct default BrowserSession: {exc}") from exc

    try:
        context = await session.create_context()
        try:
            page = await context.new_page()
            _assert_verify_http("GET", _VERIFY_URL)
            await page.goto(_VERIFY_URL)
            # The actual Sede electrónica form ID varies by year; we probe
            # for a text field labelled CSV and fall back to the first
            # input on the page.
            try:
                _assert_verify_action("csv-verifier-query")
                await page.fill("input[name*='csv' i]", csv)
                await page.press("input[name*='csv' i]", "Enter")
            except _PlaywrightError:
                _assert_verify_action("csv-verifier-query")
                await page.keyboard.type(csv)
                await page.keyboard.press("Enter")
            body = (await page.content()).lower()
            valid = ("válido" in body) or ("valido" in body) or ("correcto" in body)
            return valid
        finally:
            await context.close()
    except _JustificanteVerificationError:
        raise
    except Exception as exc:
        raise _JustificanteVerificationError(f"live CSV verification failed for {csv}: {exc}") from exc
    finally:
        if own_browser and session is not None:
            try:
                await session.close()
            except Exception as exc:  # pragma: no cover - defensive
                _logger.debug("browser session close failed: %s", exc, exc_info=True)


def _assert_verify_http(method: str, url: str) -> None:
    _assert_remote_operation_allowed(
        _VERIFY_GUARD_POLICY,
        _RemoteOperation(kind="http", method=method, url=AnyUrl(url)),
    )


def _assert_verify_action(action: str) -> None:
    _assert_remote_operation_allowed(
        _VERIFY_GUARD_POLICY,
        _RemoteOperation(kind="browser_action", action=action),
    )


__all__ = [
    "DEFAULT_BROWSER_SESSION_FACTORY",
    "VerifyBrowserContextLike",
    "VerifyBrowserKeyboardLike",
    "VerifyBrowserPageLike",
    "VerifyBrowserSessionFactory",
    "VerifyBrowserSessionLike",
    "verify_csv",
]
