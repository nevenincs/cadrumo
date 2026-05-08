"""Live DOM exploration for Renta WEB Open beyond the identification page.

Per the standing rule (extend the driver to support full open-simulator
scenarios), this opt-in test drives the existing identification flow and
then dumps the post-identification Resumen page's HTML + button/link
inventory to ``.vault/audit/renta-web-open-resumen-dom.html`` and
``.vault/audit/renta-web-open-resumen-buttons.txt``.

The captured DOM is the input to the deeper-form driver extension —
without these selectors, per-scenario casilla overrides can't be wired.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast
from pathlib import Path

import pytest

from .....core.config import Settings
from .....core.paths import PROJECT_ROOT
from .....domain.calculations.registry import RentaWebOpenLivePayload
from .....entrypoints.cli._live import requires_live_enabled
from ..browser import default_browser_session_factory

pytestmark = [pytest.mark.live_read, pytest.mark.domain_outbound]

_DOM_OUTPUT = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-resumen-dom.html"
_BUTTONS_OUTPUT = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-resumen-buttons.txt"


async def _capture_resumen_dom() -> tuple[str, str]:
    from ._renta_web_open import (
        _click_expected,
        _fill_identification_profile,
        _expect_visible,
    )

    payload = RentaWebOpenLivePayload(timeout_ms=120_000)
    browser_session = await default_browser_session_factory(Settings())
    context = None
    try:
        context = await browser_session.create_context(storage_state={})
        page = cast(Any, await context.new_page())
        await page.set_viewport_size({"width": 1366, "height": 900})
        await browser_session.navigate(page, str(payload.app_url))
        await page.wait_for_load_state("networkidle", timeout=payload.timeout_ms)

        new_decl = page.locator(".z-window-modal button").filter(has_text="Nueva declaración")
        await _click_expected(
            new_decl, stage="explore:start", description="Nueva declaración",
            timeout_ms=payload.timeout_ms,
        )
        await _fill_identification_profile(page, payload.profile, timeout_ms=payload.timeout_ms)
        await _click_expected(
            page.get_by_role("button", name="Aceptar"),
            stage="explore:accept-id",
            description="Aceptar identification",
            timeout_ms=payload.timeout_ms,
        )
        await _expect_visible(
            page.get_by_text("Resumen de declaraciones"),
            stage="explore:wait-summary", description="Resumen de declaraciones",
            timeout_ms=payload.timeout_ms,
        )
        # Click "Buscar casilla" and capture the resulting dialog DOM.
        await _click_expected(
            page.get_by_role("button", name="Buscar casilla"),
            stage="explore:open-buscar-casilla",
            description="Buscar casilla button",
            timeout_ms=payload.timeout_ms,
        )
        # Wait briefly for the dialog to render.
        await page.wait_for_timeout(2000)

        # Capture full HTML + a button/link inventory.
        html_content = await page.content()
        button_inventory_lines: list[str] = []
        button_inventory_lines.append("=== <button> elements ===")
        buttons = await page.locator("button").all()
        for idx, btn in enumerate(buttons[:120]):
            try:
                text = (await btn.inner_text(timeout=1_000)).strip()
            except Exception:
                text = "(unreadable)"
            try:
                disabled = await btn.get_attribute("disabled")
            except Exception:
                disabled = None
            button_inventory_lines.append(f"  [{idx}] text={text!r} disabled={disabled!r}")
        button_inventory_lines.append("")
        button_inventory_lines.append("=== <a> link elements ===")
        anchors = await page.locator("a").all()
        for idx, anchor in enumerate(anchors[:120]):
            try:
                text = (await anchor.inner_text(timeout=1_000)).strip()
            except Exception:
                text = "(unreadable)"
            try:
                href = await anchor.get_attribute("href")
            except Exception:
                href = None
            button_inventory_lines.append(f"  [{idx}] text={text!r} href={href!r}")
        button_inventory_lines.append("")
        button_inventory_lines.append("=== ZK-shape elements with click handlers ===")
        # ZK uses .z-button and .z-toolbarbutton instead of native <button>.
        for cls in (".z-button", ".z-toolbarbutton", ".z-menuitem", ".z-listitem"):
            els = await page.locator(cls).all()
            button_inventory_lines.append(f"\n  -- {cls} ({len(els)} found) --")
            for idx, el in enumerate(els[:60]):
                try:
                    text = (await el.inner_text(timeout=1_000)).strip()
                except Exception:
                    text = "(unreadable)"
                button_inventory_lines.append(f"    [{idx}] text={text!r}")
        button_inventory_lines.append("\n=== input elements (dialog textboxes etc.) ===")
        inputs = await page.locator("input").all()
        for idx, inp in enumerate(inputs[:60]):
            try:
                title = await inp.get_attribute("title")
                placeholder = await inp.get_attribute("placeholder")
                input_type = await inp.get_attribute("type")
                name = await inp.get_attribute("name")
                value = await inp.input_value(timeout=500)
            except Exception:
                title = placeholder = input_type = name = value = "?"
            button_inventory_lines.append(
                f"  [{idx}] type={input_type!r} title={title!r} placeholder={placeholder!r} name={name!r} value={value!r}"
            )
        button_inventory_lines.append("\n=== visible dialogs / modals ===")
        for cls in (".z-window", ".z-window-modal", "[role='dialog']"):
            els = await page.locator(cls).all()
            for idx, el in enumerate(els[:10]):
                try:
                    visible = await el.is_visible()
                    text = (await el.inner_text(timeout=1_000))[:200]
                except Exception:
                    visible = False
                    text = "(unreadable)"
                if visible:
                    button_inventory_lines.append(f"  {cls}[{idx}] visible text-preview={text!r}")
        return html_content, "\n".join(button_inventory_lines)
    finally:
        if context is not None:
            await context.close()
        await browser_session.close()


def test_explore_renta_web_open_resumen_dom() -> None:
    """Live: capture the post-identification Resumen page DOM + button inventory.

    Persists outputs under .vault/audit/ for the developer to inspect when
    extending the driver to support deeper form navigation.
    """
    requires_live_enabled()
    html, buttons = asyncio.run(_capture_resumen_dom())
    _DOM_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _DOM_OUTPUT.write_text(html, encoding="utf-8")
    _BUTTONS_OUTPUT.write_text(buttons, encoding="utf-8")
    assert len(html) > 0
    assert "Resumen" in html or "resumen" in html.lower()
