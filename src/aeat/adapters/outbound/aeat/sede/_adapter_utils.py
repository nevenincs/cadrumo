"""Shared private helpers for AEAT sede browser drivers.

Hosts the small text-normalisation, error-formatting, and selector-probe
helpers consumed by every sede driver. Drivers (``_groi_check``,
``_nif_iva_check``, future siblings) inject their own surface label and
shape-change suggestion so the helper output remains diagnostic without
re-implementing the same logic per driver.
"""

from __future__ import annotations

from collections.abc import Mapping
from re import compile
from typing import TYPE_CHECKING
from unicodedata import category, normalize

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

from .....core.logging import get_logger
from .._playwright import PlaywrightError, PlaywrightTimeoutError
from ._errors import SedeFailureMode, SedeParseError

_log = get_logger(__name__)
_WHITESPACE_RE = compile(r"\s+")


def normalize_response_text(text: str) -> str:
    """Casefold + strip diacritics + collapse whitespace for marker matching."""
    if not text:
        return ""
    decomposed = normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if category(ch) != "Mn")
    return _WHITESPACE_RE.sub(" ", without_accents.casefold()).strip()


def registry_failure_message(exc: BaseException) -> str:
    """Build a registry-facing error string enriched with the failure_mode context field.

    Sede driver exceptions carry a ``context`` mapping; this helper
    extracts ``failure_mode`` (falling back to a ``site_health:<state>``
    label when only a ``state`` key is present) and appends it to the
    base ``str(exc)`` so callers wrapping the exception into a
    :class:`RegistryValidationError` preserve the diagnostic context.
    Returns ``str(exc)`` unchanged when no ``failure_mode`` is derivable.
    """
    context = getattr(exc, "context", None)
    if not isinstance(context, Mapping) or not context:
        return str(exc)
    failure_mode = context.get("failure_mode")
    if failure_mode is None and "state" in context:
        failure_mode = f"site_health:{context['state']}"
    if failure_mode is None:
        return str(exc)
    return f"{exc} (failure_mode={failure_mode})"


async def first_visible_locator(
    page: Page,
    selectors: tuple[str, ...],
    *,
    stage: str,
    description: str,
    timeout_ms: int,
    probe_timeout_ms: int,
    surface_label: str,
    shape_suggestion: str,
) -> Locator:
    """Return the first selector in ``selectors`` that resolves to a visible element.

    Probes each selector in order using a short ``probe_timeout_ms``
    deadline. If a selector is not visible within that window,
    ``PlaywrightError`` / ``PlaywrightTimeoutError`` is caught and the
    next selector is tried. When no selector resolves,
    :class:`SedeParseError` is raised with
    ``SedeFailureMode.EXTERNAL_SHAPE_CHANGED`` so callers can distinguish
    "AEAT changed the page layout" from transient network timeouts.

    Args:
        page: Playwright ``Page`` on which to probe the selectors.
        selectors: CSS selector strings tried in declaration order.
        stage: Opaque label for the current driver stage, included in
            the error context.
        description: Human-readable description of the expected element,
            used in the error message.
        timeout_ms: Overall operation timeout (ms); ``probe_timeout_ms``
            is capped to this value.
        probe_timeout_ms: Per-selector visibility probe budget (ms).
        surface_label: Sede surface name included in log and error
            messages (e.g. ``"GROI"``).
        shape_suggestion: Localised guidance string appended to
            :class:`SedeParseError` when all selectors fail.

    Returns:
        The first ``Locator`` from ``selectors`` whose element was
        visible within ``probe_timeout_ms``.

    Raises:
        SedeParseError: When every selector probe timed out or failed.
    """
    probe_timeout = min(timeout_ms, probe_timeout_ms)
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=probe_timeout)
        except (PlaywrightError, PlaywrightTimeoutError) as probe_exc:
            _log.debug(
                "%s: selector %r not visible during probe (%s); trying next",
                surface_label,
                selector,
                probe_exc,
            )
            continue
        return locator
    raise SedeParseError(
        f"{surface_label} expected page element was not visible: {description}",
        failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
        context={"stage": stage, "expected": description, "timeout_ms": timeout_ms},
        suggestion=shape_suggestion,
    )


__all__ = [
    "first_visible_locator",
    "normalize_response_text",
    "registry_failure_message",
]
