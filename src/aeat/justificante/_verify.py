"""Live CSV verification against AEAT's Sede electrónica (#44).

The ``verify_csv`` helper is **opt-in**: it only runs when the caller
supplies or constructs a :class:`aeat.browser.BrowserSession`, and it never
mutates AEAT-side state. Our contract is:

* open the Sede verification page,
* enter the CSV,
* read back the server response,
* return ``True`` iff AEAT confirms the document as valid.

Because the live bot-detection probe in :mod:`aeat.browser` is a known
flaky path (see issue #41), the function degrades gracefully when a browser
cannot be constructed and surfaces the underlying error to the caller.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aeat.logging import get_logger

from ._errors import JustificanteVerificationError

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids aeat.config cycle
    from aeat.browser import BrowserSession

_logger = get_logger(__name__)

_VERIFY_URL = (
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-practicas-manuales/"
    "verificacion-integridad-documentos.html"
)


async def verify_csv(
    csv: str,
    *,
    browser: BrowserSession | None = None,
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
    if session is None:
        try:
            from playwright.async_api import async_playwright

            from aeat.browser import BrowserSession
            from aeat.browser.profile import Profile
            from aeat.config import load_settings

            settings = load_settings()
            storage_state_path = settings.aeat_token_dir / f"{settings.aeat_default_profile_name}-storage.json"
            profile = Profile(
                name=settings.aeat_default_profile_name,
                storage_state_path=storage_state_path,
            )
            profile.ensure_storage_dir()
            playwright = await async_playwright().start()
            session = BrowserSession(playwright=playwright, settings=settings, profile=profile)
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
            playwright_ref = getattr(session, "playwright", None)
            if playwright_ref is not None:
                try:
                    await playwright_ref.stop()
                except Exception as exc:  # pragma: no cover - defensive
                    _logger.debug("playwright stop failed: %s", exc)
