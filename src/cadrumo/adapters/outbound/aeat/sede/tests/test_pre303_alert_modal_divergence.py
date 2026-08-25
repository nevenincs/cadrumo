"""Characterisation of the pre303 alert-modal dismissal, post-collapse.

Round-3 semantic duplicate discovery found `_dismiss_pre303_alert_modal_if_present`
implemented twice -- once in `auth._clave_movil_page_flow` (a method on
`_ClaveMovilPageFlowMixin`), once in `sede._iva_compensation_wallet` (a free
function) -- with no cross-reference between the two, and TWO real
behavioural divergences rather than a calling-convention difference: (1) the
auth copy checked the modal's CSS `"show"` class before acting at all, the
wallet copy did a raw substring check on the page HTML with no class-state
test; (2) the auth copy tried several continue-button selector variants with
a generic fallback, the wallet copy tried exactly one constructed selector
with no fallback.

This module started as a CHARACTERISATION pass -- pinning what each
implementation did, not what it should do -- so the class-gate question (1)
could be decided on evidence rather than argument. The four cells it produced:

    ==========  =================  ===================
                shown              present-but-hidden
    ==========  =================  ===================
    auth        clicks             declines
    wallet      clicks             ALSO clicks
    ==========  =================  ===================

Two separate rulings followed, on two different timelines. The fallback
axis (2) was judged STRICTLY ADDITIVE -- a candidate selector can only
succeed where the current code already failed, so no working click path can
regress -- and was promoted immediately. The class-gate axis (1) was
initially HELD: it REMOVES an action (the wallet declining to click), and
the synthetic fixture below cannot prove that removal safe on AEAT's actual
page. That hold was subsequently OVERRIDDEN by operator directive: the two
independent implementations were ruled a critical double declaration, and
the auth predicate -- checking the modal actually carries `"show"` before
acting -- was ruled canonical. The wallet's substring-only version is
deleted, not kept as an alternative, per
:func:`~adapters.outbound.aeat.dismiss_pre303_alert_modal_if_present`.

**The residual risk the override accepts does not disappear because the
directive arrived.** The synthetic fixture proves the two implementations
differed on the structure their own selector-construction code expects, not
that the class-check is correct against AEAT's real page. If the wallet's
modal can render shown WITHOUT the `"show"` class on that specific page, this
collapse trades a demonstrated over-click risk for an undemonstrated hang
risk. That is why the wallet caller now supplies a diagnostic
(`on_declined_hidden_modal`) that must surface in its own log output when it
declines -- see `test_wallet_surfaces_a_diagnostic_when_it_declines_the_hidden_modal`
below. The evidence that would close this gap for good -- a real capture of
the modal in both states, or an observed live run -- still does not exist.

## Fixture provenance

No recorded AEAT capture of the pre303 alert modal exists in
`src/cadrumo/tests/fixtures/aeat-sede/` (checked: the closest fixture,
`dialogo-representacion-gate.html`, is a real capture of the representation
DISPATCHER page, not the alert modal, and no test references it). The HTML
below is therefore SYNTHETIC: hand-built to carry only the structure both
implementations actually inspect (`#alertsModal`, its `class` attribute, and
one continue button), using the real configured selectors
(`Settings.external_constants().aeat.pre303.alert_modal_selector` /
`.alert_continue_button_text`) rather than invented ones. It proves the two
implementations differ (and, post-collapse, now agree) on the structure AS WE
UNDERSTAND IT from reading their selector-construction code -- which is
weaker than proving their behaviour matches AEAT's real page, since the real
page's exact markup (surrounding modal framework classes, whether the button
carries additional wrapper elements) is unverified. Treat every assertion
below as "given this reasonable synthetic shape," not "given AEAT's actual
page."
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any, cast

import pytest

from ......application.auth.protocols import BrowserPagePort
from ......core.config import Settings, load_settings
from ..._playwright import Page
from ...auth.clave_movil import ClaveMovilAuthProvider
from .._iva_compensation_wallet import _dismiss_pre303_alert_modal_if_present as _wallet_dismiss

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PRE303 = Settings.external_constants().aeat.pre303
# "#alertsModal" and "continuar" as of this writing; read live rather than
# hardcoded so this module tracks a config change instead of silently testing
# a stale selector.
_MODAL_SELECTOR = _PRE303.alert_modal_selector
_BUTTON_TEXT = _PRE303.alert_continue_button_text

# SYNTHETIC — hand-built, not captured from AEAT. See module docstring.
_HTML_SHOWN = f"""
<html><body>
  <div id="{_MODAL_SELECTOR.lstrip("#")}" class="modal show" role="dialog">
    <div class="modal-footer">
      <button type="button">{_BUTTON_TEXT.capitalize()}</button>
    </div>
  </div>
</body></html>
"""

# SYNTHETIC — identical to _HTML_SHOWN except the modal carries no "show"
# class: present in the DOM, not visually up. This is the state the two
# pre-collapse implementations treated differently, and the collapsed
# canonical predicate now treats identically for both callers.
_HTML_HIDDEN = f"""
<html><body>
  <div id="{_MODAL_SELECTOR.lstrip("#")}" class="modal" role="dialog">
    <div class="modal-footer">
      <button type="button">{_BUTTON_TEXT.capitalize()}</button>
    </div>
  </div>
</body></html>
"""

# SYNTHETIC — shown, but the continue button's own text does not contain the
# configured button text at all (an icon-only or differently-worded button is
# a real AEAT UI possibility not excluded by anything either implementation
# checks). Isolates the generic ".modal-footer button[type=\"button\"]"
# fallback selector.
_HTML_SHOWN_UNLABELLED_BUTTON = f"""
<html><body>
  <div id="{_MODAL_SELECTOR.lstrip("#")}" class="modal show" role="dialog">
    <div class="modal-footer">
      <button type="button">&times;</button>
    </div>
  </div>
</body></html>
"""


class _ScriptedPage:
    """Minimal page double exposing only `content()` / `click()`.

    `click()` decides success by an explicit, hand-declared predicate over the
    exact selector strings the real implementation is known to construct
    (read from source, not reimplemented) -- it is not a CSS engine.
    `PlaywrightError` is raised for a selector this predicate says would not
    match, mirroring the timeout-then-raise behaviour of a real Playwright
    `page.click()` against a selector with zero matches.
    """

    def __init__(self, html: str, *, click_matches: Callable[[str], bool]) -> None:
        self._html = html
        self._click_matches = click_matches
        self.attempted_selectors: list[str] = []

    async def content(self) -> str:
        return self._html

    async def click(self, selector: str) -> None:
        self.attempted_selectors.append(selector)
        if not self._click_matches(selector):
            from ..._playwright import PlaywrightError

            raise PlaywrightError(f"no element matches {selector!r}")


def _matches_when_shown_and_labelled(selector: str) -> bool:
    """Playwright would match any selector requiring `.show` plus the labelled button."""
    return ".show" in selector


def _matches_when_shown_unlabelled(selector: str) -> bool:
    """Only the generic `.modal-footer button[type="button"]` fallback matches an unlabelled button."""
    return ".show" in selector and "modal-footer" in selector


async def _run_auth(page: _ScriptedPage) -> None:
    provider = ClaveMovilAuthProvider(load_settings())
    # Reaches the private method deliberately: this test characterises that method itself.
    # The fake implements only the two members the delegation path touches; the
    # declared page protocol is wider than that path needs, so the substitution is
    # asserted here rather than loosening the production annotation to fit a double.
    await provider._dismiss_pre303_alert_modal_if_present(cast("BrowserPagePort", page))


async def _run_wallet(page: _ScriptedPage) -> None:
    # Same substitution as the auth path above: the fake implements exactly the
    # members this call touches, and the mypy-shaped suppression it carried
    # silences nothing in the checkers actually running.
    await _wallet_dismiss(cast("Page", page))


def _run(coro_factory: Callable[[], Coroutine[Any, Any, None]]) -> None:
    import asyncio

    asyncio.run(coro_factory())


def test_auth_dismisses_the_modal_when_shown() -> None:
    """Cell 1/4: auth clicks through when the modal carries the "show" class."""
    page = _ScriptedPage(_HTML_SHOWN, click_matches=_matches_when_shown_and_labelled)

    _run(lambda: _run_auth(page))

    assert page.attempted_selectors, "auth path did not attempt to dismiss a shown modal"


def test_auth_declines_when_the_modal_is_present_but_hidden() -> None:
    """Cell 2/4: auth performs ZERO clicks when the modal lacks the "show" class.

    This is now the CANONICAL predicate, not merely "auth's own behaviour" --
    both callers share this check post-collapse.
    """
    page = _ScriptedPage(_HTML_HIDDEN, click_matches=_matches_when_shown_and_labelled)

    _run(lambda: _run_auth(page))

    assert page.attempted_selectors == [], "auth path clicked a modal with no 'show' class"


def test_wallet_dismisses_the_modal_when_shown() -> None:
    """Cell 3/4: wallet clicks through when the modal is genuinely shown.

    Post-collapse, the wallet's selectors are ``.show``-scoped too (the
    canonical predicate is unconditional, not parameterised per caller), so
    the matching predicate here is the SAME one the auth test above uses --
    before the collapse this used a `.show`-agnostic predicate instead.
    """
    page = _ScriptedPage(_HTML_SHOWN, click_matches=_matches_when_shown_and_labelled)

    _run(lambda: _run_wallet(page))

    assert page.attempted_selectors, "wallet path did not attempt to dismiss a shown modal"


def test_wallet_now_declines_when_the_modal_is_present_but_hidden() -> None:
    """Cell 4/4, POST-COLLAPSE: wallet now performs ZERO clicks on a present-but-hidden modal.

    This is the cell the four-cell table names as CHANGED. Before the
    collapse this test (as `test_wallet_ALSO_clicks_when_the_modal_is_present_but_hidden`)
    asserted the opposite -- that the wallet clicked here too, demonstrating
    the divergence the operator later ruled a critical double declaration.
    The assertion is inverted deliberately, not silently: if it fails, the
    collapse has been undone (a second implementation reappeared, or the
    canonical predicate stopped checking `"show"`), which is exactly the
    regression this module exists to catch.
    """
    page = _ScriptedPage(_HTML_HIDDEN, click_matches=_matches_when_shown_and_labelled)

    _run(lambda: _run_wallet(page))

    assert page.attempted_selectors == [], (
        f"wallet path clicked a modal with no 'show' class: {page.attempted_selectors} "
        "-- the collapse to the auth predicate has regressed"
    )


def test_wallet_surfaces_a_diagnostic_when_it_declines_the_hidden_modal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The wallet's decline must be visible in its own log output, not silent.

    Declining is NEW behaviour for the wallet reader (the deleted
    substring-only version would have clicked in exactly this case), on a
    live AEAT money-surface reader with an unproven-on-the-real-page
    predicate, so a decline here must be diagnosable from the wallet's own
    output rather than read off a stack trace three layers away if the read
    subsequently stalls. The auth caller passes no diagnostic callback
    (matching its own unchanged pre-collapse behaviour); this test is
    wallet-specific.
    """
    page = _ScriptedPage(_HTML_HIDDEN, click_matches=_matches_when_shown_and_labelled)

    with caplog.at_level(logging.WARNING, logger="cadrumo.adapters.outbound.aeat.sede._iva_compensation_wallet"):
        _run(lambda: _run_wallet(page))

    assert any(
        "declining to dismiss" in record.message and _MODAL_SELECTOR in record.message for record in caplog.records
    ), f"expected a WARNING naming the declined modal, got: {[r.message for r in caplog.records]}"


def test_auth_falls_back_to_the_generic_modal_footer_button_when_unlabelled() -> None:
    """The canonical predicate's third selector variant catches a button with no matching text.

    `continue_button_selectors` appends
    `f'{modal_selector}.show .modal-footer button[type="button"]'` as a final
    fallback after the two text-matching variants. This fixture's button
    carries no text matching the configured button text at all, isolating
    that fallback.
    """
    page = _ScriptedPage(_HTML_SHOWN_UNLABELLED_BUTTON, click_matches=_matches_when_shown_unlabelled)

    _run(lambda: _run_auth(page))

    assert page.attempted_selectors, "auth path did not reach its generic modal-footer fallback selector"
    assert "modal-footer" in page.attempted_selectors[-1], (
        f"expected the fallback selector to be tried last, got {page.attempted_selectors}"
    )


def test_wallet_shares_the_generic_modal_footer_fallback() -> None:
    """The wallet reaches the SAME fallback the auth path does, via the one shared implementation.

    Post-collapse, the wallet's selectors are also ``.show``-scoped (the
    canonical predicate is unconditional), so this uses the same matching
    predicate as the auth-side fallback test above -- before the collapse
    this used a `.show`-agnostic predicate, since the wallet's own selectors
    were unscoped then.
    """
    page = _ScriptedPage(_HTML_SHOWN_UNLABELLED_BUTTON, click_matches=_matches_when_shown_unlabelled)

    _run(lambda: _run_wallet(page))

    assert page.attempted_selectors, "wallet path did not reach the shared generic modal-footer fallback"
    assert "modal-footer" in page.attempted_selectors[-1], (
        f"expected the fallback selector to be tried last, got {page.attempted_selectors}"
    )
