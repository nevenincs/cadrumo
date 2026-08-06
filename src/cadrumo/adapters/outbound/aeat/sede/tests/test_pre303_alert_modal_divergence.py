"""Characterisation of the pre303 alert-modal dismissal divergence.

Round-3 semantic duplicate discovery found `_dismiss_pre303_alert_modal_if_present`
implemented twice -- once in `auth._clave_movil_page_flow` (a method on
`_ClaveMovilPageFlowMixin`), once in `sede._iva_compensation_wallet` (a free
function) -- with no cross-reference between the two, and a real behavioural
divergence rather than a calling-convention difference: the auth copy checks
the modal's CSS `"show"` class before acting and tries several continue-button
selector variants; the wallet copy does a raw substring check on the page HTML
(no class-state test at all) and clicks exactly one constructed selector with
no fallback.

Neither implementation had any test coverage before this module. This is a
CHARACTERISATION pass, not a fix: every test here asserts what each
implementation DOES TODAY, not what it should do. The point is to make the
divergence measurable so the canonical-behaviour question can be decided on
evidence rather than reasoning.

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
implementations differ on the structure AS WE UNDERSTAND IT from reading their
selector-construction code -- which is weaker than proving they differ on
AEAT's real page, since the real page's exact markup (surrounding modal
framework classes, whether the button carries additional wrapper elements) is
unverified. Treat every assertion below as "given this reasonable synthetic
shape," not "given AEAT's actual page."
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest

from ......core.config import Settings, load_settings
from ...auth._clave_movil import ClaveMovilAuthProvider
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
  <div id="{_MODAL_SELECTOR.lstrip('#')}" class="modal show" role="dialog">
    <div class="modal-footer">
      <button type="button">{_BUTTON_TEXT.capitalize()}</button>
    </div>
  </div>
</body></html>
"""

# SYNTHETIC — identical to _HTML_SHOWN except the modal carries no "show"
# class: present in the DOM, not visually up. This is the state the two
# implementations are hypothesised to treat differently.
_HTML_HIDDEN = f"""
<html><body>
  <div id="{_MODAL_SELECTOR.lstrip('#')}" class="modal" role="dialog">
    <div class="modal-footer">
      <button type="button">{_BUTTON_TEXT.capitalize()}</button>
    </div>
  </div>
</body></html>
"""

# SYNTHETIC — shown, but the continue button's own text does not contain the
# configured button text at all (an icon-only or differently-worded button is
# a real AEAT UI possibility not excluded by anything either implementation
# checks). Isolates the auth path's ".modal-footer button[type=\"button\"]"
# fallback selector, which the wallet path has no equivalent for.
_HTML_SHOWN_UNLABELLED_BUTTON = f"""
<html><body>
  <div id="{_MODAL_SELECTOR.lstrip('#')}" class="modal show" role="dialog">
    <div class="modal-footer">
      <button type="button">&times;</button>
    </div>
  </div>
</body></html>
"""


class _FakePage:
    """Minimal page double exposing only `content()` / `click()`.

    `click()` decides success by an explicit, hand-declared predicate over the
    exact selector strings the two real implementations are known to
    construct (read from their source, not reimplemented) -- it is not a CSS
    engine. `PlaywrightError` is raised for a selector this predicate says
    would not match, mirroring the timeout-then-raise behaviour of a real
    Playwright `page.click()` against a selector with zero matches.
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


def _matches_regardless_of_show_class(selector: str) -> bool:
    """The wallet's selector never requires `.show`, so it matches whenever the modal id and button text agree."""
    return _MODAL_SELECTOR in selector


async def _run_auth(page: _FakePage) -> None:
    provider = ClaveMovilAuthProvider(load_settings())
    await provider._dismiss_pre303_alert_modal_if_present(page)  # noqa: SLF001 -- characterisation of the private method itself


async def _run_wallet(page: _FakePage) -> None:
    await _wallet_dismiss(page)  # type: ignore[arg-type] -- _FakePage satisfies the narrow surface used


def _run(coro_factory: Callable[[], Awaitable[None]]) -> None:
    import asyncio

    asyncio.run(coro_factory())


def test_auth_dismisses_the_modal_when_shown() -> None:
    """Today: the auth path clicks through when the modal carries the "show" class."""
    page = _FakePage(_HTML_SHOWN, click_matches=_matches_when_shown_and_labelled)

    _run(lambda: _run_auth(page))

    assert page.attempted_selectors, "auth path did not attempt to dismiss a shown modal"


def test_auth_declines_when_the_modal_is_present_but_hidden() -> None:
    """Today: the auth path performs ZERO clicks when the modal lacks the "show" class.

    This is the class-state check the wallet path lacks. It is the auth
    path's correct-looking behaviour, not asserted here as "correct" -- only
    as what it currently does.
    """
    page = _FakePage(_HTML_HIDDEN, click_matches=_matches_when_shown_and_labelled)

    _run(lambda: _run_auth(page))

    assert page.attempted_selectors == [], "auth path clicked a modal with no 'show' class"


def test_wallet_dismisses_the_modal_when_shown() -> None:
    """Today: the wallet path clicks through when the modal is genuinely shown."""
    page = _FakePage(_HTML_SHOWN, click_matches=_matches_regardless_of_show_class)

    _run(lambda: _run_wallet(page))

    assert page.attempted_selectors, "wallet path did not attempt to dismiss a shown modal"


def test_wallet_ALSO_clicks_when_the_modal_is_present_but_hidden() -> None:
    """Today: the wallet path clicks the SAME selector even when the modal has no "show" class.

    This is the demonstrated divergence, not an inference: `_wallet_dismiss`
    performs a raw substring check for the modal id anywhere in the page HTML
    -- present in both `_HTML_SHOWN` and `_HTML_HIDDEN` -- and constructs one
    selector with no `.show` qualifier, so it cannot distinguish the two
    states the auth path's class check separates. On AEAT's real live money
    surface, this is the direction the team lead's ruling identified as
    dangerous: clicking a continue button because a hidden element's markup
    happened to be present in the DOM.
    """
    page = _FakePage(_HTML_HIDDEN, click_matches=_matches_regardless_of_show_class)

    _run(lambda: _run_wallet(page))

    assert page.attempted_selectors, (
        "wallet path declined to click a hidden modal -- if this assertion ever fails, "
        "the divergence characterised by this module has been closed and this test (and "
        "the finding it pins) should be revisited, not silently left red"
    )


def test_auth_falls_back_to_the_generic_modal_footer_button_when_unlabelled() -> None:
    """Today: the auth path's third selector variant catches a button with no matching text.

    `_alert_continue_button_selectors` appends
    `f'{modal_selector}.show .modal-footer button[type="button"]'` as a final
    fallback after the two text-matching variants. This fixture's button
    carries no text matching the configured button text at all, isolating
    that fallback.
    """
    page = _FakePage(_HTML_SHOWN_UNLABELLED_BUTTON, click_matches=_matches_when_shown_unlabelled)

    _run(lambda: _run_auth(page))

    assert page.attempted_selectors, "auth path did not reach its generic modal-footer fallback selector"
    assert "modal-footer" in page.attempted_selectors[-1], (
        f"expected the fallback selector to be tried last, got {page.attempted_selectors}"
    )


def test_wallet_has_no_fallback_for_an_unlabelled_continue_button() -> None:
    """Today: the wallet path's single selector cannot find an unlabelled continue button.

    `_wallet_dismiss` constructs exactly one selector,
    `f'{modal_selector} button:has-text("{button_text}")'`, with no fallback
    equivalent to the auth path's generic `.modal-footer` selector. Against a
    modal whose button carries no matching text, the click raises, and
    `_wallet_dismiss` does not catch it -- the exception propagates to the
    caller uncaught, which is itself part of the divergence: the auth path
    only raises after exhausting every variant, the wallet path raises on its
    first and only attempt.
    """
    page = _FakePage(_HTML_SHOWN_UNLABELLED_BUTTON, click_matches=lambda _selector: False)

    with pytest.raises(Exception, match="no element matches"):
        _run(lambda: _run_wallet(page))

    assert len(page.attempted_selectors) == 1, (
        f"expected exactly one attempt with no fallback, got {page.attempted_selectors}"
    )
