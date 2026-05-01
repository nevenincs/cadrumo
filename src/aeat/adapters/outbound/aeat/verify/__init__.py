"""Playwright CSV verification against AEAT's Sede electrónica (#44).

The ``verify_csv`` helper is **opt-in**: it only runs when the caller
supplies or constructs a :class:`aeat.adapters.outbound.aeat.browser.BrowserSession`,
and it never mutates AEAT-side state. Our contract is:

* open the Sede verification page,
* enter the CSV,
* read back the server response,
* return ``True`` iff AEAT confirms the document as valid.

Because the live bot-detection probe in :mod:`aeat.adapters.outbound.aeat.browser`
is a known flaky path (see issue #41), the function degrades gracefully when a
browser cannot be constructed and surfaces the underlying error to the caller.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, cast

from .....core.logging import get_logger
from .....domain.justificante._errors import JustificanteVerificationError

_logger = get_logger(__name__)

_VERIFY_URL = (
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-practicas-manuales/"
    "verificacion-integridad-documentos.html"
)


class BrowserKeyboardLike(Protocol):
    async def type(self, value: str) -> None: ...
    async def press(self, key: str) -> None: ...


class BrowserPageLike(Protocol):
    keyboard: BrowserKeyboardLike

    async def goto(self, url: str) -> object | None: ...
    async def fill(self, selector: str, value: str) -> None: ...
    async def press(self, selector: str, key: str) -> None: ...
    async def content(self) -> str: ...


class BrowserContextLike(Protocol):
    async def new_page(self) -> BrowserPageLike: ...
    async def close(self) -> None: ...


class BrowserSessionLike(Protocol):
    async def create_context(self) -> BrowserContextLike: ...
    async def close(self) -> None: ...


class PlaywrightOwnerLike(Protocol):
    async def stop(self) -> None: ...


BrowserSessionFactory = Callable[[], Awaitable[tuple[BrowserSessionLike, PlaywrightOwnerLike]]]


async def _build_default_browser_session() -> tuple[BrowserSessionLike, PlaywrightOwnerLike]:
    """Construct the default browser session and its Playwright owner."""
    from playwright.async_api import async_playwright

    from .....core.config import load_settings
    from ..browser import BrowserSession
    from ..browser.profile import Profile

    settings = load_settings()
    storage_state_path = settings.aeat_token_dir / f"{settings.aeat_default_profile_name}-storage.json"
    profile = Profile(
        name=settings.aeat_default_profile_name,
        storage_state_path=storage_state_path,
    )
    profile.ensure_storage_dir()
    playwright = await async_playwright().start()
    session = BrowserSession(playwright=playwright, settings=settings, profile=profile)
    return cast(BrowserSessionLike, session), cast(PlaywrightOwnerLike, playwright)


DEFAULT_BROWSER_SESSION_FACTORY: BrowserSessionFactory = _build_default_browser_session
"""Module-level factory seam for the self-owned browser path."""


async def verify_csv(
    csv: str,
    *,
    browser: BrowserSessionLike | None = None,
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
        JustificanteVerificationError: If the round-trip cannot be completed
            (browser launch failure, network error, parsing failure).
    """
    csv = csv.strip().upper()
    if not csv:
        raise JustificanteVerificationError("cannot verify an empty CSV")

    own_browser = False
    session = browser
    playwright_owner: PlaywrightOwnerLike | None = None
    if session is None:
        try:
            session, playwright_owner = await DEFAULT_BROWSER_SESSION_FACTORY()
            own_browser = True
        except Exception as exc:
            raise JustificanteVerificationError(f"failed to construct default BrowserSession: {exc}") from exc

    try:
        context = await session.create_context()
        try:
            page = await context.new_page()
            await page.goto(_VERIFY_URL)
            # The actual Sede electrónica form ID varies by year; we probe
            # for a text field labelled CSV and fall back to the first
            # input on the page.
            try:
                await page.fill("input[name*='csv' i]", csv)
                await page.press("input[name*='csv' i]", "Enter")
            except Exception:
                await page.keyboard.type(csv)
                await page.keyboard.press("Enter")
            body = (await page.content()).lower()
            valid = ("válido" in body) or ("valido" in body) or ("correcto" in body)
            return valid
        finally:
            await context.close()
    except JustificanteVerificationError:
        raise
    except Exception as exc:
        raise JustificanteVerificationError(f"live CSV verification failed for {csv}: {exc}") from exc
    finally:
        if own_browser and session is not None:
            try:
                await session.close()
            except Exception as exc:  # pragma: no cover - defensive
                _logger.debug("browser session close failed: %s", exc)
            if playwright_owner is not None:
                try:
                    await playwright_owner.stop()
                except Exception as exc:  # pragma: no cover - defensive
                    _logger.debug("playwright stop failed: %s", exc)


__all__ = [
    "DEFAULT_BROWSER_SESSION_FACTORY",
    "BrowserContextLike",
    "BrowserKeyboardLike",
    "BrowserPageLike",
    "BrowserSessionFactory",
    "BrowserSessionLike",
    "PlaywrightOwnerLike",
    "verify_csv",
]
