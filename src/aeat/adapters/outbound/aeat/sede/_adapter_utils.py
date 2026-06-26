"""Shared private helpers for AEAT sede browser drivers.

Hosts the small text-normalisation, error-formatting, and selector-probe
helpers consumed by every sede driver. Drivers (``_groi_check``,
``_nif_iva_check``, future siblings) inject their own surface label and
shape-change suggestion so the helper output remains diagnostic without
re-implementing the same logic per driver.

:func:`make_locate_helper` and :func:`assert_query_browser_action_for` factor
out the two private helper shapes that each checker driver used to duplicate.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from re import compile
from typing import TYPE_CHECKING, Any, Protocol
from unicodedata import category, normalize

from .....core import STRICT_FROZEN_CONFIG

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

from pydantic import BaseModel

from .....core.logging import get_logger
from .....domain.calculations.registry import RemoteOperation, RemoteStateGuardPolicy, assert_remote_operation_allowed
from .._playwright import PlaywrightError, PlaywrightTimeoutError
from ._errors import BrowserAdapterTypeError, SedeFailureMode, SedeParseError

_log = get_logger(__name__)
_WHITESPACE_RE = compile(r"\s+")


class _LocateHelper(Protocol):
    """Callable protocol for the ``_locate`` helper produced by :func:`make_locate_helper`.

    Both ``_groi_check`` and ``_nif_iva_check`` previously defined this Protocol
    locally; it is canonical here so drivers import one shared definition.

    Parameters are positional-only to match the
    ``Callable[[Page, tuple[str, ...], str, str, int], Coroutine[Any, Any, Locator]]``
    return annotation on :func:`make_locate_helper`.
    """

    def __call__(
        self,
        page: Page,
        selectors: tuple[str, ...],
        stage: str,
        description: str,
        timeout_ms: int,
        /,
    ) -> Coroutine[Any, Any, Locator]: ...


class _SedeCheckerModel(BaseModel):
    """Strict frozen base for sede checker observation and result models.

    Every per-NIF observation type and aggregate result type in the sede
    browser drivers (``_groi_check``, ``_nif_iva_check``, future siblings)
    inherits this base to guarantee a consistent strict-frozen-forbid Pydantic
    config across all checker surfaces without repeating the ``model_config``
    declaration in each module.
    """

    model_config = STRICT_FROZEN_CONFIG


def assert_query_browser_action_for(policy: RemoteStateGuardPolicy, action: str) -> None:
    """Assert that ``action`` is permitted under ``policy``.

    Raises :class:`~aeat.domain.calculations.registry.RegistryValidationError`
    via :func:`~aeat.domain.calculations.registry.assert_remote_operation_allowed`
    if the action pattern is not allowed. Both the GROI and NIF-IVA drivers close
    over their own :class:`~aeat.domain.calculations.registry.RemoteStateGuardPolicy`
    objects; this shared helper removes the duplicate ``_assert_query_browser_action``
    bodies they used to carry.

    Args:
        policy: The guard policy the driver was initialised with.
        action: Browser action label to validate (e.g. ``"open-groi-form"``).
    """
    assert_remote_operation_allowed(policy, RemoteOperation(kind="browser_action", action=action))


def require_playwright_page(raw_page: object) -> Page:
    """Return ``raw_page`` as a Playwright ``Page`` or raise a typed adapter error."""
    from playwright.async_api import Page as _Page

    if not isinstance(raw_page, _Page):
        raise BrowserAdapterTypeError(
            f"BrowserContext.new_page() did not return a Playwright Page; got {type(raw_page)}",
            context={"actual_type": type(raw_page).__name__},
        )
    return raw_page


def make_locate_helper(
    surface_label: str,
    shape_suggestion: str,
) -> Callable[[Page, tuple[str, ...], str, str, int], Coroutine[Any, Any, Locator]]:
    """Return a ``_locate`` coroutine pre-bound to ``surface_label`` and ``shape_suggestion``.

    Both the GROI and NIF-IVA drivers wrap :func:`first_visible_locator` with the
    same body, differing only in the ``surface_label`` and ``shape_suggestion``
    strings they inject. This factory eliminates that duplicate; each driver calls::

        _locate = make_locate_helper("GROI", _groi_shape_suggestion())

    and then uses ``_locate(page, selectors, stage=..., description=..., timeout_ms=...)``
    directly.

    Args:
        surface_label: Sede surface name for log and error messages.
        shape_suggestion: Localised guidance string appended to
            :class:`~._errors.SedeParseError` when all selectors fail.

    Returns:
        An async callable with the same signature as the internal ``_locate``
        helpers the drivers previously defined individually.
    """
    from ._browser_constants import selector_probe_timeout_ms  # local import to avoid circular

    async def _locate(
        page: Page,
        selectors: tuple[str, ...],
        stage: str,
        description: str,
        timeout_ms: int,
    ) -> Locator:
        return await first_visible_locator(
            page,
            selectors,
            stage=stage,
            description=description,
            timeout_ms=timeout_ms,
            probe_timeout_ms=selector_probe_timeout_ms(),
            surface_label=surface_label,
            shape_suggestion=shape_suggestion,
        )

    return _locate


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
    "_LocateHelper",
    "_SedeCheckerModel",
    "assert_query_browser_action_for",
    "first_visible_locator",
    "make_locate_helper",
    "normalize_response_text",
    "registry_failure_message",
    "require_playwright_page",
]
