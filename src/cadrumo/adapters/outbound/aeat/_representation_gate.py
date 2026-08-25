"""AEAT own-name representation-gate logic, shared across flows.

AEAT's representation-choice screen -- where the authenticated profile must
act in its own name rather than as a represented third party -- appears on
more than one authenticated flow: Cl@ve Móvil login
(:mod:`adapters.outbound.aeat.auth`) and the IVA compensation wallet reader
(:mod:`adapters.outbound.aeat.sede`) both drive through it. Both sites
independently implemented the same logic before this module existed, with no
cross-reference between them (round-3 semantic duplicate discovery, this
session); this is now the single implementation for all three pieces of that
screen:

* :func:`wait_for_own_name_representation_selector` -- waiting for AEAT to
  render the own-name selector, parameterised by the settings-derived
  selector strings and by the caller's own error identity, so
  :class:`~cadrumo.core.errors.AeatLoginAssertionError`
  and :class:`~adapters.outbound.aeat.sede.SedeNavigationError` remain
  distinct domain errors rather than being collapsed into one.
* :func:`continue_button_selectors` / :func:`click_first_matching_selector`
  -- the continue-button selector-fallback chain for AEAT's pre303 alert
  modal, parameterised by ``scoped_to_shown`` so each caller keeps its own
  selector-matching scope.
* :func:`dismiss_pre303_alert_modal_if_present` -- the alert-modal dismissal
  itself, using the auth caller's ``"show"``-class predicate as the single
  canonical check (operator directive: the wallet's prior raw substring test,
  with no class-state check at all, was ruled the incorrect half of the pair
  and deleted outright, not merged as an alternative). See that function's
  own docstring for the residual, still-open evidence gap this ruling
  accepts rather than resolves.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import NoReturn, Protocol, cast

from ._html import parse_html
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


class ClickablePage(Protocol):
    """The one page capability :func:`click_first_matching_selector` requires.

    Declared rather than accepting ``object`` and reaching through it: the
    function needs exactly one method, and saying so lets a caller pass any page
    that provides it while keeping the call site checkable.
    """

    async def click(self, selector: str) -> None: ...


async def click_first_matching_selector(page: ClickablePage, selectors: tuple[str, ...]) -> None:
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
            await page.click(selector)
            return
        except PlaywrightError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error


def _absent_attribute(_name: str, default: object = None) -> object:
    """Stand in for ``node.get`` on a node that has no attribute accessor.

    A named function rather than a lambda: lambda parameters cannot carry
    annotations, so the fallback erased the type of everything read through it.
    """
    return default


def _html_node_has_class(node: object, class_name: str) -> bool:
    getter = getattr(node, "get", _absent_attribute)
    classes = getter("class", [])
    if isinstance(classes, str):
        return class_name in classes.split()
    if isinstance(classes, Iterable):
        # CAST-RATIONALE-HTML-CLASS-ATTR: third-party boundary -- the node is
        # whatever the HTML parser returned, so its class attribute is an
        # iterable of unknown element type. The runtime check above establishes
        # the iterability; the element type cannot be recovered and is compared
        # as an opaque value.
        entries = cast("Iterable[object]", classes)
        return any(class_name == entry for entry in entries)
    # Neither a class string nor an iterable of names: the node declares no
    # usable class attribute, which is an absence rather than a match.
    return False


async def dismiss_pre303_alert_modal_if_present(
    page: object,
    *,
    alert_modal_selector: str,
    alert_continue_button_text: str,
    on_declined_hidden_modal: Callable[[], None] | None = None,
) -> None:
    """Dismiss AEAT's pre303 alert modal, but only when it genuinely carries ``"show"``.

    Collapses the two independent implementations this session found (round-3
    semantic duplicate discovery): the auth caller checked the modal's
    ``"show"`` CSS class before acting; the wallet caller did a raw substring
    test for the modal id anywhere in the page HTML, with no class-state
    check at all, so it could not distinguish a modal that is genuinely up
    from one merely present in the DOM. Four-cell characterisation
    (``sede/tests/test_pre303_alert_modal_divergence.py``) proved the
    divergence rather than arguing it: the wallet path clicked in BOTH the
    shown and the present-but-hidden state, the auth path only in the shown
    state. Per operator directive, the auth predicate is canonical; the
    wallet's substring-only version is deleted, not kept as an alternative.

    The residual risk this collapse accepts, not resolves: no recorded AEAT
    capture of this modal exists in either visibility state, so the
    class-check predicate is verified against a synthetic fixture built from
    the two implementations' own selector-construction code, not against
    AEAT's real page. The class-check being the legally/structurally correct
    question to ask ("is this modal actually up") is not the same claim as
    "this is how AEAT's real markup behaves". If the wallet's pre303 modal
    can render shown WITHOUT the ``"show"`` class (a different visibility
    mechanism on that specific page), this collapse would make the wallet
    decline to dismiss a modal it must dismiss -- trading the demonstrated
    over-click risk for an undemonstrated hang risk. That is why a decline
    caused by ``on_declined_hidden_modal`` must surface, not pass quietly:
    the evidence that would close this gap for good is a real capture of the
    modal in both states, or an observed live run, neither of which exists
    yet.

    Args:
        page: A Playwright ``Page`` or a page-like object exposing async
            ``content()`` and ``click(selector)`` methods.
        alert_modal_selector: The modal container's CSS selector
            (e.g. ``"#alertsModal"``).
        alert_continue_button_text: The configured continue-button text.
        on_declined_hidden_modal: Called (never awaited, never passed
            arguments) when the modal element is present in the DOM but does
            not carry ``"show"``, so this function declines to click and
            returns without acting. ``None`` (the default) declines silently,
            matching the auth caller's original behaviour, which this
            collapse does not change; the wallet caller MUST supply a
            diagnostic callback, because declining is new behaviour there and
            must be visible in its output rather than read off a stack trace
            three layers away.
    """
    content = getattr(page, "content", None)
    click = getattr(page, "click", None)
    if content is None or click is None:
        return
    html = await content()
    soup = parse_html(html)
    modal = soup.select_one(alert_modal_selector)
    if modal is None:
        return
    if not _html_node_has_class(modal, "show"):
        if on_declined_hidden_modal is not None:
            on_declined_hidden_modal()
        return
    selectors = continue_button_selectors(alert_modal_selector, alert_continue_button_text, scoped_to_shown=True)
    # CAST-RATIONALE-DUCK-TYPED-PAGE: the getattr probes above already
    # established that this page provides click; this function stays
    # duck-typed by design, returning early for a page that does not, so the
    # capability is proven here rather than declared.
    await click_first_matching_selector(cast("ClickablePage", page), selectors)


__all__ = [
    "click_first_matching_selector",
    "continue_button_selectors",
    "dismiss_pre303_alert_modal_if_present",
    "own_name_representation_selectors",
    "wait_for_own_name_representation_selector",
]
