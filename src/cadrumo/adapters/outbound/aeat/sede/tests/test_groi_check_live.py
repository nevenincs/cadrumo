"""Opt-in live form-shape drift detector for the GROI Spanish-ROI driver.

Runs only when ``CADRUMO_LIVE_TESTS_ENABLED=1`` is set. The test navigates
to the live GROI form via the project's authenticated BrowserSession
and asserts every selector the offline driver depends on is still
present in the rendered DOM. AEAT silently changing the form input id,
submit name, or action URL breaks this test loudly so the offline
driver can be repaired before its next live run.

The GROI surface is reachable under cl@ve-movil; the live test loads
the persisted cl@ve-movil storage state, so a reasonably-fresh session
must be present at ``settings.cadrumo_token_dir`` before the test runs.

The drift detector ALSO runs an end-to-end verdict-parser sanity check
against a known public NIF (Telefónica's A28015865, registered ROI
operator) so a parser that diverges from the live response phrasing is
flagged independently from the selector check.
"""

from __future__ import annotations

import asyncio

import pytest

from ......core.config import Settings
from ......tests.live_gate import requires_live_enabled
from .._adapter_utils import extract_marker_verdict
from ...browser.factory import default_browser_session_factory
from ..groi_check import (
    GroiSedeDriver,
    _POSITIVE_MARKERS,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]

# Telefónica SA — public, ROI-registered Spanish corporate NIF; the
# verdict for this NIF is stable as long as Telefónica stays registered.
_PROBE_NIF: str = "A28015865"


def test_groi_form_selectors_still_match_live_dom() -> None:
    """Form input#nif, submit#enviar, and action URL must all still resolve."""

    requires_live_enabled()
    asyncio.run(_assert_form_shape())


def test_groi_driver_returns_valid_verdict_for_registered_telefonica_nif() -> None:
    """End-to-end: the live driver classifies a known ROI-registered NIF as valid."""

    requires_live_enabled()
    result = GroiSedeDriver().collect(payload=b"", expected={_PROBE_NIF: "valid"}, timeout_ms=30_000)
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.nif == _PROBE_NIF
    assert observation.verdict == "valid", observation


def test_groi_verdict_parser_recognises_live_telefonica_certification() -> None:
    """Parser sanity: the body text AEAT renders today still contains the certification phrase."""

    requires_live_enabled()
    body_text = asyncio.run(_query_live_body_text(_PROBE_NIF))
    assert extract_marker_verdict(body_text, positive_markers=_POSITIVE_MARKERS) == "valid", body_text[:500]


async def _assert_form_shape() -> None:
    settings = Settings()
    session = await default_browser_session_factory(settings)
    context = None
    try:
        context = await session.create_context()
        from playwright.async_api import Page as _Page

        _raw = await context.new_page()
        assert isinstance(_raw, _Page), f"new_page() did not return a Playwright Page; got {type(_raw)}"
        page: _Page = _raw
        await page.set_viewport_size({"width": 1366, "height": 900})
        await session.navigate(page, Settings.external_constants().aeat.oracles.groi_check)
        await page.wait_for_load_state("networkidle", timeout=20_000)

        # Asserting the actual elements the offline driver expects to find.
        # Each missing element is a real AEAT shape change and must fail loudly.
        nif_input = page.locator("input#nif").first
        await nif_input.wait_for(state="visible", timeout=10_000)
        assert (await nif_input.get_attribute("name")) == "nif"
        assert (await nif_input.get_attribute("maxlength")) == "9"

        submit = page.locator("input#enviar").first
        await submit.wait_for(state="visible", timeout=10_000)
        assert (await submit.get_attribute("name")) == "enviar"
        assert (await submit.get_attribute("type")) == "submit"

        form = page.locator("form").first
        action = await form.get_attribute("action")
        assert action == Settings.external_constants().aeat.oracles.groi_check.rsplit("/", maxsplit=1)[-1], action
    finally:
        if context is not None:
            await context.close()
        await session.close()


async def _query_live_body_text(nif: str) -> str:
    settings = Settings()
    session = await default_browser_session_factory(settings)
    context = None
    try:
        context = await session.create_context()
        from playwright.async_api import Page as _Page

        _raw = await context.new_page()
        assert isinstance(_raw, _Page), f"new_page() did not return a Playwright Page; got {type(_raw)}"
        page: _Page = _raw
        await page.set_viewport_size({"width": 1366, "height": 900})
        await session.navigate(page, Settings.external_constants().aeat.oracles.groi_check)
        await page.wait_for_load_state("networkidle", timeout=20_000)
        await page.locator("input#nif").fill(nif, timeout=10_000)
        await page.locator("input#enviar").click(timeout=10_000)
        await page.wait_for_load_state("networkidle", timeout=20_000)
        return await page.locator("body").inner_text(timeout=10_000)
    finally:
        if context is not None:
            await context.close()
        await session.close()
