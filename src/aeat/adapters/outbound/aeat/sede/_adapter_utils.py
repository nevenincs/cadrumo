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
from typing import Any
from unicodedata import category, normalize

from .._playwright import PlaywrightError, PlaywrightTimeoutError
from ._errors import SedeFailureMode, SedeParseError

_WHITESPACE_RE = compile(r"\s+")


def normalize_response_text(text: str) -> str:
    """Casefold + strip diacritics + collapse whitespace for marker matching."""

    if not text:
        return ""
    decomposed = normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if category(ch) != "Mn")
    return _WHITESPACE_RE.sub(" ", without_accents.casefold()).strip()


def registry_failure_message(exc: BaseException) -> str:
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
    page: Any,
    selectors: tuple[str, ...],
    *,
    stage: str,
    description: str,
    timeout_ms: int,
    probe_timeout_ms: int,
    surface_label: str,
    shape_suggestion: str,
) -> Any:
    probe_timeout = min(timeout_ms, probe_timeout_ms)
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=probe_timeout)
        except (PlaywrightError, PlaywrightTimeoutError):
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
