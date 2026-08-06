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


__all__ = ["own_name_representation_selectors", "wait_for_own_name_representation_selector"]
