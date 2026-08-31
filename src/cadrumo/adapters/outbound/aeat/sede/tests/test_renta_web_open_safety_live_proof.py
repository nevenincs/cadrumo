"""LIVE proof that the safety guard blocks a real filing-button click.

The Renta WEB Open Resumen page surfaces a ``Presentar declaración`` button
at the top-level toolbar. In production this button submits the declaration.
On the open simulator the button is still wired through AEAT's Sede infra
(synthetic data is accepted but the button mechanic is the real one).

This test attempts to click the button via ``_click_expected`` (which
routes through ``assert_click_target_safe``). The expected outcome is
that the safety guard blocks the click before Playwright issues it,
raising :class:`SedeNavigationError` with the matched forbidden token.

Running this test under ``CADRUMO_LIVE_TESTS_ENABLED=1`` confirms the
safety hardening works against the LIVE button — not just unit-test
fixtures.

If this test ever PASSES (i.e. the click goes through), the safety guard
is broken and a real submission could happen. The test is the canary in
the mine for #175 (filing-prevention belt-and-suspenders).
"""

from __future__ import annotations

import asyncio

import pytest

from ......core.config import Settings
from ......domain.calculations.registry.renta_web_open_oracle import RentaWebOpenLivePayload
from ......tests.live_gate import requires_live_enabled
from ...browser.factory import default_browser_session_factory
from .._renta_web_open_safety import install_page_safety_net
from ..errors import SedeNavigationError

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


async def _attempt_presentar_click() -> tuple[bool, str]:
    """Drive identification then attempt the Presentar click. Return
    (blocked, message) where ``blocked=True`` means the safety guard
    refused the click (the desired outcome).
    """
    from ..renta_web_open import (
        _click_expected,
        _expect_visible,
        _fill_identification_profile,
    )

    payload = RentaWebOpenLivePayload(timeout_ms=120_000)
    browser_session = await default_browser_session_factory(Settings())
    context = None
    try:
        context = await browser_session.create_context(storage_state={})
        from playwright.async_api import Page as _Page

        _raw = await context.new_page()
        assert isinstance(_raw, _Page), f"new_page() did not return a Playwright Page; got {type(_raw)}"
        page: _Page = _raw
        await install_page_safety_net(page)
        await page.set_viewport_size({"width": 1366, "height": 900})
        await browser_session.navigate(page, str(payload.app_url))
        await page.wait_for_load_state("networkidle", timeout=payload.timeout_ms)

        new_decl = page.locator(".z-window-modal button").filter(has_text="Nueva declaración")
        await _click_expected(
            new_decl,
            stage="safety-proof:start",
            description="Nueva declaración",
            timeout_ms=payload.timeout_ms,
        )
        await _fill_identification_profile(page, payload.profile, timeout_ms=payload.timeout_ms)
        await _click_expected(
            page.get_by_role("button", name="Aceptar"),
            stage="safety-proof:accept-id",
            description="Aceptar identification",
            timeout_ms=payload.timeout_ms,
        )
        await _expect_visible(
            page.get_by_text("Resumen de declaraciones"),
            stage="safety-proof:wait-resumen",
            description="Resumen de declaraciones",
            timeout_ms=payload.timeout_ms,
        )

        # Now the Resumen page is loaded. The Presentar declaración button
        # is rendered live. Try to click it through _click_expected — the
        # safety guard MUST block this.
        presentar = page.locator("button").filter(has_text="Presentar declaración").first
        try:
            await _click_expected(
                presentar,
                stage="safety-proof:attempt-presentar",
                description="Presentar declaración (FORBIDDEN — must be blocked)",
                timeout_ms=30_000,
            )
            return False, "click went through — SAFETY VIOLATION"
        except SedeNavigationError as exc:
            # Expected outcome: the safety guard blocked the click.
            return True, str(exc)
    finally:
        if context is not None:
            await context.close()
        await browser_session.close()


def test_safety_guard_blocks_presentar_declaracion_click_on_live_simulator() -> None:
    """Live proof: the safety guard refuses to click Presentar declaración.

    The Renta WEB Open Resumen page surfaces a ``Presentar declaración``
    button. This test attempts to click it via the canonical
    ``_click_expected`` wrapper. The expected outcome is that the click
    is blocked by ``assert_click_target_safe`` BEFORE Playwright dispatches
    the click event — raising ``SedeNavigationError`` with the matched
    forbidden token (``presentar``).

    Pass criteria:
      - blocked=True
      - the error message contains the matched token

    Failure criteria (CRITICAL — would indicate a regression in #175):
      - blocked=False (the click went through, meaning the safety
        guard is broken and a real submission could occur)
    """
    requires_live_enabled()
    blocked, message = asyncio.run(_attempt_presentar_click())
    assert blocked, (
        "SAFETY VIOLATION: Presentar declaración click was NOT blocked by "
        "the safety guard. This is a CRITICAL regression in #175 — a real "
        "filing could occur. Investigate immediately. Last message: " + message
    )
    assert "presentar" in message.lower(), (
        f"safety guard blocked the click but the matched token does not "
        f"include 'presentar'. Suspicious. Message: {message}"
    )
