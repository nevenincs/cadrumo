"""Read-only CSV verification against AEAT's Sede electrónica.

The :func:`verify_csv` helper is opt-in: it only runs when the caller supplies
or constructs a :class:`aeat.adapters.outbound.aeat.browser.DefaultBrowserSession`.
It is guarded by :class:`aeat.domain.calculations.registry.RemoteStateGuardPolicy`
and never mutates AEAT-side state. The contract is:

* open the Sede verification page,
* enter the CSV,
* read back the server response,
* return ``True`` iff AEAT confirms the document as valid.

The function degrades gracefully when a browser cannot be
constructed and surfaces the underlying error to the caller via
:class:`aeat.domain.justificante.JustificanteVerificationError`.

Public surface: :func:`verify_csv` plus the Playwright protocol
types (:class:`VerifyBrowserKeyboardLike`, :class:`VerifyBrowserPageLike`,
:class:`VerifyBrowserContextLike`, :class:`VerifyBrowserSessionLike`,
:class:`VerifyBrowserSessionFactory`) that let the helper be unit-tested
without spinning up a real browser.

See Also:
    :func:`aeat.adapters.outbound.aeat.browser.default_browser_session_factory`
        Production factory used by :data:`DEFAULT_BROWSER_SESSION_FACTORY`.
    :class:`aeat.adapters.outbound.aeat.browser.BrowserSession`
        Concrete browser session whose context/page surface these protocols
        mirror.
    :func:`aeat.domain.calculations.registry.assert_remote_operation_allowed`
        Guard used to allow only the reviewed read-only CSV verification URL and
        browser action token.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeGuard, runtime_checkable

from pydantic import AnyUrl

from .....core.config import Settings as _Settings
from .....core.errors import AeatError as _AeatError
from .....core.logging import get_logger as _get_logger
from .....domain.calculations.registry import (
    RemoteOperation as _RemoteOperation,
)
from .....domain.calculations.registry import (
    RemoteStateGuardPolicy as _RemoteStateGuardPolicy,
)
from .....domain.calculations.registry import (
    assert_remote_operation_allowed as _assert_remote_operation_allowed,
)
from .....domain.justificante._errors import JustificanteVerificationError as _JustificanteVerificationError
from .._playwright import PlaywrightError as _PlaywrightError
from ..sede._errors import BrowserAdapterTypeError as _BrowserAdapterTypeError

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
    """Subset of Playwright's ``Keyboard`` API used by :func:`verify_csv`.

    The protocol keeps the fallback query path testable without importing a
    concrete Playwright ``Keyboard`` at runtime.
    """

    async def type(self, value: str) -> None:
        """Type ``value`` into the focused element character by character."""
        ...

    async def press(self, key: str) -> None:
        """Dispatch a key-press event for ``key`` (e.g. ``"Enter"``)."""
        ...


class VerifyBrowserPageLike(Protocol):
    """Subset of Playwright's ``Page`` API used by :func:`verify_csv`.

    The page surface is intentionally small: navigation to the reviewed Sede URL,
    CSV entry through a selector or keyboard fallback, and HTML content capture
    for the confirmation-token parse.
    """

    keyboard: VerifyBrowserKeyboardLike

    async def goto(self, url: str) -> object | None:
        """Navigate the page to ``url`` and return the primary response."""
        ...

    async def fill(self, selector: str, value: str) -> None:
        """Clear and fill the element matched by ``selector`` with ``value``."""
        ...

    async def press(self, selector: str, key: str) -> None:
        """Focus the element matched by ``selector`` and press ``key``."""
        ...

    async def content(self) -> str:
        """Return the full HTML content of the page."""
        ...


class VerifyBrowserContextLike(Protocol):
    """Subset of Playwright's ``BrowserContext`` API used by :func:`verify_csv`.

    Context ownership depends on the caller: :func:`verify_csv` always closes the
    context it opens, while the surrounding session is closed only when the
    helper created it through :data:`DEFAULT_BROWSER_SESSION_FACTORY`.
    """

    async def new_page(self) -> VerifyBrowserPageLike:
        """Open a new :class:`VerifyBrowserPageLike` within this browser context."""
        ...

    async def close(self) -> None:
        """Close the browser context and release its resources."""
        ...


@runtime_checkable
class VerifyBrowserSessionLike(Protocol):
    """Browser-session surface consumed by :func:`verify_csv`.

    The ``create_context`` signature mirrors
    :meth:`aeat.adapters.outbound.aeat.browser.BrowserSession.create_context`
    so static checkers see no unsafe overlap between this protocol and
    the concrete browser sessions. ``verify_csv`` itself calls
    ``create_context()`` with no arguments; production and test
    sessions accept the same optional kwargs as the central
    :class:`~aeat.adapters.outbound.aeat.browser.BrowserSession` so the protocol
    stays structurally honest.
    """

    # ADAPTER-INTERNAL-ALIAS-RATIONALE-BROWSER-CONTEXT: mirrors optional Playwright/browser session kwargs.
    async def create_context(
        self,
        *,
        provisioner: Any | None = None,
        storage_state_path: Any | None = None,
        storage_state: Any | None = None,
    ) -> VerifyBrowserContextLike:
        """Create and return a configured :class:`VerifyBrowserContextLike`."""
        ...

    async def close(self) -> None:
        """Close the browser session and release all underlying resources."""
        ...


VerifyBrowserSessionFactory = Callable[[], Awaitable[VerifyBrowserSessionLike]]
"""Callable that builds a self-owned :class:`VerifyBrowserSessionLike`."""


def _is_verify_browser_session_like(obj: object) -> TypeGuard[VerifyBrowserSessionLike]:
    """Return ``True`` when ``obj`` structurally satisfies :class:`VerifyBrowserSessionLike`.

    Checks the two method names the protocol requires; a
    :class:`TypeGuard` annotation tells the type checker the narrowed
    type after the guard without relying on
    :func:`isinstance` against a ``@runtime_checkable`` protocol (which
    pyright flags when a concrete class shares method names but has
    covariant return types).
    """
    return callable(getattr(obj, "create_context", None)) and callable(getattr(obj, "close", None))


async def _build_default_browser_session(
    factory: Callable[..., Awaitable[object]] | None = None,
) -> VerifyBrowserSessionLike:
    """Construct the default :class:`VerifyBrowserSessionLike`.

    Loads :func:`aeat.core.config.load_settings`, materialises the
    central :func:`aeat.adapters.outbound.aeat.browser.default_browser_session_factory`,
    checks the result with :func:`_is_verify_browser_session_like`, and returns
    a session the caller is responsible for closing.

    The ``factory`` parameter is a DI seam for the type-guard test that
    asserts the boundary raises :class:`_BrowserAdapterTypeError` when
    the factory returns an incompatible type; production callers omit
    it and the central browser factory is used.
    """
    from .....core.config import load_settings
    from ..browser import default_browser_session_factory

    settings = load_settings()
    resolved_factory = factory or default_browser_session_factory
    session = await resolved_factory(settings)
    if not _is_verify_browser_session_like(session):
        raise _BrowserAdapterTypeError(
            f"default_browser_session_factory returned an incompatible type: {type(session)}",
        )
    return session


DEFAULT_BROWSER_SESSION_FACTORY: VerifyBrowserSessionFactory = _build_default_browser_session
"""Module-level factory seam for the self-owned :func:`verify_csv` path."""


async def verify_csv(
    csv: str,
    *,
    browser: VerifyBrowserSessionLike | None = None,
    browser_session_factory: VerifyBrowserSessionFactory | None = None,
) -> bool:
    """Verify a justificante CSV against AEAT's Sede electrónica.

    The helper normalises the CSV, opens the reviewed public Sede verification
    URL under the read-only guard, submits the CSV, and parses the returned HTML
    for AEAT confirmation tokens. Passing ``browser`` borrows the session from
    the caller; omitting it builds a self-owned session through
    ``browser_session_factory`` or :data:`DEFAULT_BROWSER_SESSION_FACTORY` and
    closes that session after the round-trip.

    Args:
        csv: The Código Seguro de Verificación as printed on the receipt.
        browser: An already-constructed :class:`VerifyBrowserSessionLike`.
            When ``None``, one is built from the default settings/profile.
        browser_session_factory: Optional no-argument factory for the
            self-owned path. Ignored when ``browser`` is supplied.

    Returns:
        ``True`` if AEAT confirms the CSV as valid; ``False`` if AEAT reports
        the document as unknown.

    Raises:
        JustificanteVerificationError: If the round-trip cannot be completed
            because browser construction, navigation, the guard, or parsing
            fails.
    """
    csv = csv.strip().upper()
    if not csv:
        raise _JustificanteVerificationError("cannot verify an empty CSV")

    own_browser = False
    session = browser
    if session is None:
        try:
            factory = browser_session_factory or DEFAULT_BROWSER_SESSION_FACTORY
            session = await factory()
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
