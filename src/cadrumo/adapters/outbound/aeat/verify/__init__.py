"""Read-only CSV verification against AEAT's Sede electrónica.

The :func:`verify_csv` helper is opt-in: it only runs when the caller supplies
or constructs a :class:`adapters.outbound.aeat.browser.DefaultBrowserSession`.
It is guarded by :class:`domain.calculations.registry.RemoteStateGuardPolicy`
and never mutates AEAT-side state. The contract is:

* open the CSV-keyed Sede viewer,
* read back the server response,
* return ``True`` iff AEAT confirms the document as valid.

The function degrades gracefully when a browser cannot be
constructed and surfaces the underlying error to the caller via
:class:`domain.justificante.JustificanteVerificationError`.

Public surface: :func:`verify_csv` plus the Playwright protocol types
(:class:`VerifyBrowserPageLike`, :class:`VerifyBrowserContextLike`,
:class:`VerifyBrowserSessionLike`, and :class:`VerifyBrowserSessionFactory`)
shared by the concrete browser adapters.

See Also:
    :func:`adapters.outbound.aeat.browser.default_browser_session_factory`
        Production factory used by :data:`DEFAULT_BROWSER_SESSION_FACTORY`.
    :class:`adapters.outbound.aeat.browser.BrowserSession`
        Concrete browser session whose context/page surface these protocols
        mirror.
    :func:`domain.calculations.registry.assert_remote_operation_allowed`
        Guard used to allow only the reviewed read-only CSV verification URL.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeGuard, runtime_checkable
from urllib.parse import parse_qs, urlencode, urlsplit

from pydantic import AnyUrl

from .....core import is_aeat_csv as _is_aeat_csv
from .....core import normalise_aeat_csv as _normalise_aeat_csv
from .....core.async_cleanup import close_async_resources as _close_async_resources
from .....core.config import Settings as _Settings
from .....core.errors import CadrumoError as _CadrumoError
from .....core.logging import get_logger as _get_logger
from .....domain.calculations.registry.remote_state_guard import RemoteOperation as _RemoteOperation
from .....domain.calculations.registry.remote_state_guard import RemoteStateGuardPolicy as _RemoteStateGuardPolicy
from .....domain.calculations.registry.remote_state_guard import (
    assert_remote_operation_allowed as _assert_remote_operation_allowed,
)
from .....domain.justificante import JustificanteVerificationError as _JustificanteVerificationError
from .._html import parse_html as _parse_html
from .._playwright import PlaywrightError as _PlaywrightError
from ..sede.errors import BrowserAdapterTypeError as _BrowserAdapterTypeError

_logger = _get_logger(__name__)

_VERIFY_EXTERNAL = _Settings.external_constants()
_VERIFY_URL = f"{_VERIFY_EXTERNAL.aeat.domains.www2}{_VERIFY_EXTERNAL.aeat.sede_paths.cotejo_query}"
_VERIFY_HOST = _VERIFY_EXTERNAL.aeat.domains.www2.removeprefix("https://")
_VERIFY_GUARD_POLICY = _RemoteStateGuardPolicy(
    id="aeat-csv-verifier-read",
    evidence_tier="official_source_guidance",
    classification="public_read_surface",
    allowed_hosts=(_VERIFY_HOST,),
    allowed_browser_action_patterns=(),
    synthetic_data_allowed=False,
    requires_authentication=False,
    requires_aeat_authorization=False,
)


class VerifyBrowserPageLike(Protocol):
    """Subset of Playwright's ``Page`` API used by :func:`verify_csv`.

    The page surface is intentionally small: navigation to the reviewed
    CSV-keyed Sede URL and HTML content capture for exact result-URL and
    document-viewer validation.
    """

    @property
    def url(self) -> str:
        """Return the page's current absolute URL."""
        ...

    async def goto(self, url: str) -> object | None:
        """Navigate the page to ``url`` and return the primary response."""
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
    :meth:`adapters.outbound.aeat.browser.BrowserSession.create_context`
    so static checkers see no unsafe overlap between this protocol and
    the concrete browser sessions. ``verify_csv`` itself calls
    ``create_context()`` with no arguments; production and test
    sessions accept the same optional kwargs as the central
    :class:`adapters.outbound.aeat.browser.BrowserSession` so the protocol
    stays structurally honest.
    """

    # ADAPTER-INTERNAL-ALIAS-RATIONALE-BROWSER-CONTEXT: mirrors optional Playwright/browser session kwargs.
    async def create_context(
        self,
        *,
        provisioner: Any | None = None,
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
    pyrefly flags when a concrete class shares method names but has
    covariant return types).
    """
    return callable(getattr(obj, "create_context", None)) and callable(getattr(obj, "close", None))


async def _build_default_browser_session() -> VerifyBrowserSessionLike:
    """Construct the default :class:`VerifyBrowserSessionLike`.

    Loads :func:`core.config.load_settings`, materialises the
    central :func:`adapters.outbound.aeat.browser.default_browser_session_factory`,
    checks the result with :func:`_is_verify_browser_session_like`, and returns
    a session the caller is responsible for closing.
    """
    from .....core.config import load_settings
    from ..browser import default_browser_session_factory

    settings = load_settings()
    session = await default_browser_session_factory(settings)
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

    The helper normalises the CSV, opens AEAT's reviewed CSV-keyed public viewer
    under the read-only guard, and parses the returned HTML for the exact
    CSV-bound document iframe. Passing ``browser`` borrows the
    session from the caller; omitting it builds a self-owned session through
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
    csv = _normalise_aeat_csv(csv)
    if not _is_aeat_csv(csv):
        raise _JustificanteVerificationError(
            f"cannot verify {csv!r}: an AEAT CSV is 8-32 uppercase alphanumeric characters",
        )

    own_browser = False
    session = browser
    if session is None:
        try:
            factory = browser_session_factory or DEFAULT_BROWSER_SESSION_FACTORY
            session = await factory()
            own_browser = True
        except (_PlaywrightError, _CadrumoError) as exc:
            raise _JustificanteVerificationError(f"failed to construct default BrowserSession: {exc}") from exc

    context: VerifyBrowserContextLike | None = None
    try:
        context = await session.create_context()
        page = await context.new_page()
        verification_url = f"{_VERIFY_URL}?{urlencode({'CSV': csv})}"
        _assert_verify_http("GET", verification_url)
        await page.goto(verification_url)
        return _response_confirms_valid_csv(
            await page.content(),
            expected_csv=csv,
            final_url=page.url,
        )
    except _JustificanteVerificationError:
        raise
    except Exception as exc:
        raise _JustificanteVerificationError(f"live CSV verification failed for {csv}: {exc}") from exc
    finally:
        await _close_async_resources(
            context,
            session if own_browser else None,
            task_name="cadrumo-verify-csv-close",
        )


def _response_confirms_valid_csv(body: str, *, expected_csv: str, final_url: str) -> bool:
    """Return whether AEAT rendered a concrete document viewer.

    The live-grounded AEAT verifier reference records this exact viewer route
    and its CSV-bound document iframe. Unknown HTML fails closed rather than
    trusting generic words such as ``válido`` or ``correcto``.

    ``expected_csv`` is re-checked against the canonical shape here as well as
    at the entry point: this comparison is what turns a rendered iframe into a
    "valid" verdict, so a malformed expectation reaching it would let any page
    echoing that same malformed value confirm a document that cannot exist.
    """
    if not _is_aeat_csv(expected_csv):
        return False
    final = urlsplit(final_url)
    if final.scheme != "https" or final.netloc != _VERIFY_HOST:
        return False
    if final.path != _VERIFY_EXTERNAL.aeat.sede_paths.cotejo_query:
        return False

    soup = _parse_html(body)
    viewer = soup.find("iframe", id="iframe-visualiza")
    if viewer is None:
        return False
    source = str(viewer.get("src", ""))
    parsed = urlsplit(source)
    if parsed.netloc and parsed.netloc != _VERIFY_HOST:
        return False
    if parsed.path != _VERIFY_EXTERNAL.aeat.sede_paths.cotejo_document:
        return False
    return parse_qs(parsed.query).get("CSV") == [expected_csv]


def _assert_verify_http(method: str, url: str) -> None:
    _assert_remote_operation_allowed(
        _VERIFY_GUARD_POLICY,
        _RemoteOperation(kind="http", method=method, url=AnyUrl(url)),
    )


__all__ = [
    "DEFAULT_BROWSER_SESSION_FACTORY",
    "VerifyBrowserContextLike",
    "VerifyBrowserPageLike",
    "VerifyBrowserSessionFactory",
    "VerifyBrowserSessionLike",
    "verify_csv",
]
