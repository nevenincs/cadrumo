"""AEAT own-name representation-gate selector logic, shared across flows.

AEAT's representation-choice screen -- where the authenticated profile must
act in its own name rather than as a represented third party -- appears on
more than one authenticated flow: Cl@ve Móvil login
(:mod:`adapters.outbound.aeat.auth`) and the IVA compensation wallet reader
(:mod:`adapters.outbound.aeat.sede`) both drive through it. Both sites
independently implemented the same selector-trying logic before this module
existed; this is now the single implementation, parameterised by the
settings-derived selector strings and by the caller's own error identity, so
:class:`~adapters.outbound.aeat.auth._authenticator_types.AeatLoginAssertionError`
and :class:`~adapters.outbound.aeat.sede.SedeNavigationError` remain distinct
domain errors rather than being collapsed into one.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn

from ._playwright import PlaywrightError


def own_name_representation_selectors(*selectors: str) -> tuple[str, ...]:
    """Return ``selectors``, order-preserving, blank-and-duplicate-free."""
    deduped: list[str] = []
    for selector in selectors:
        value = selector.strip()
        if value and value not in deduped:
            deduped.append(value)
    return tuple(deduped)


async def wait_for_own_name_representation_selector(
    page: object,
    *,
    own_name_label_selector: str,
    own_name_selector: str,
    probe_timeout_ms: float,
    raise_configuration_error: Callable[[str], NoReturn],
) -> str:
    """Return the configured own-name selector that AEAT renders first.

    Tries ``own_name_label_selector`` then ``own_name_selector`` (deduped, in
    that order), waiting up to ``probe_timeout_ms`` for each candidate via
    Playwright's ``wait_for_selector``. A :class:`PlaywrightError` raised by
    the last-tried candidate propagates unchanged -- that is a real
    navigation failure, not a configuration problem. ``raise_configuration_error``
    is called (and must raise) only for the two configuration-shaped failures:
    ``page`` exposing no ``wait_for_selector`` capability, or both selector
    strings being blank.

    Args:
        page: A Playwright ``Page`` or a page-like object exposing an async
            ``wait_for_selector(selector, *, timeout=...)`` method.
        own_name_label_selector: The primary (label) selector to try first.
        own_name_selector: The fallback (input) selector.
        probe_timeout_ms: Per-selector wait timeout in milliseconds.
        raise_configuration_error: Called with a diagnostic message to raise
            the caller's own domain error for a configuration-shaped failure.

    Returns:
        The selector string that resolved.
    """
    wait_for = getattr(page, "wait_for_selector", None)
    if wait_for is None:
        raise_configuration_error(
            "page does not expose wait_for_selector(); cannot drive AEAT own-name representation gate",
        )
        raise AssertionError("raise_configuration_error must raise")  # pragma: no cover
    last_error: PlaywrightError | None = None
    for selector in own_name_representation_selectors(own_name_label_selector, own_name_selector):
        try:
            await wait_for(selector, timeout=probe_timeout_ms)
            return selector
        except PlaywrightError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise_configuration_error("AEAT own-name representation selector configuration is empty")
    raise AssertionError("raise_configuration_error must raise")  # pragma: no cover


def continue_button_selectors(
    modal_selector: str,
    button_text: str,
    *,
    scoped_to_shown: bool,
) -> tuple[str, ...]:
    """Return continue-button selector variants for an AEAT alert modal.

    Generates the title-case and as-given renderings of ``button_text`` plus a
    generic ``.modal-footer`` fallback for a button whose own text does not
    match either variant (the auth caller's original third selector). When
    ``scoped_to_shown`` is True every selector is qualified with ``.show``, so
    it matches only while the modal carries that CSS state -- the auth
    caller's convention, applied there only after it has already gated on the
    modal's ``"show"`` class itself. ``scoped_to_shown=False`` (the wallet
    caller) omits the qualifier, preserving that caller's existing
    unconditional match -- this function changes what is TRIED, never what is
    REQUIRED to be present for a click to succeed.

    Args:
        modal_selector: The modal container's CSS selector (e.g. ``"#alertsModal"``).
        button_text: The configured continue-button text to match.
        scoped_to_shown: Whether every generated selector is qualified with ``.show``.

    Returns:
        A tuple of candidate selectors, in try-order, deduplicated.
    """
    scope = ".show" if scoped_to_shown else ""
    title_case = button_text[:1].upper() + button_text[1:] if button_text else button_text
    selectors: list[str] = []
    for text in (title_case, button_text):
        value = text.strip()
        if not value:
            continue
        selector = f'{modal_selector}{scope} button:has-text("{value}")'
        if selector not in selectors:
            selectors.append(selector)
    fallback = f'{modal_selector}{scope} .modal-footer button[type="button"]'
    if fallback not in selectors:
        selectors.append(fallback)
    return tuple(selectors)


async def click_first_matching_selector(page: object, selectors: tuple[str, ...]) -> None:
    """Click the first selector in ``selectors`` that resolves.

    Tries each selector via ``page.click`` in order, catching
    :class:`PlaywrightError` and trying the next; re-raises the LAST error
    only once every candidate has failed. A single-element ``selectors``
    tuple reproduces raise-on-first-miss exactly (today's wallet behaviour);
    a multi-element tuple adds fallback attempts strictly on top of that --
    this never removes a selector that used to be tried, only adds more
    chances to succeed before giving up.

    Args:
        page: A Playwright ``Page`` or a page-like object exposing an async
            ``click(selector)`` method (both current callers' page types
            declare this unconditionally, unlike ``wait_for_selector`` above).
        selectors: Candidate selectors, in try-order.

    Raises:
        PlaywrightError: If every selector failed to resolve.
    """
    last_error: PlaywrightError | None = None
    for selector in selectors:
        try:
            await page.click(selector)  # type: ignore[attr-defined]
            return
        except PlaywrightError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error


__all__ = [
    "click_first_matching_selector",
    "continue_button_selectors",
    "own_name_representation_selectors",
    "wait_for_own_name_representation_selector",
]
