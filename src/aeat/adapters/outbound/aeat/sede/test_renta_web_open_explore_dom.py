"""Live DOM exploration for Renta WEB Open beyond the identification page.

Per the standing rule (extend the driver to support full open-simulator
scenarios), this opt-in test drives the existing identification flow and
then dumps:
  - ``.vault/audit/renta-web-open-resumen-dom.html`` — full HTML
  - ``.vault/audit/renta-web-open-resumen-buttons.txt`` — DOM-visible
    inventory (buttons, links, inputs, dialogs)
  - ``.vault/audit/renta-web-open-resumen-a11y-tree.txt`` — accessibility
    tree, captures ZK-virtualised widgets the HTML may not surface

The accessibility-tree dump is the workaround for ZK lazy rendering: the
Buscar casilla dialog opens as a virtual widget that doesn't appear in
``page.content()`` but DOES appear in the accessibility tree.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from .....core.config import Settings
from .....core.paths import PROJECT_ROOT
from .....domain.calculations.registry import RentaWebOpenLivePayload
from .....entrypoints.cli._live import requires_live_enabled
from ..browser import default_browser_session_factory

pytestmark = [pytest.mark.live_read, pytest.mark.domain_outbound]

_DOM_OUTPUT = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-resumen-dom.html"
_BUTTONS_OUTPUT = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-resumen-buttons.txt"
_A11Y_OUTPUT = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-resumen-a11y-tree.txt"
_BUSCAR_DIALOG_OUTPUT = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-buscar-dialog.txt"
_APARTADOS_DIALOG_OUTPUT = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-apartados-dialog.txt"


async def _snapshot_zk_layer(page: Any, label: str) -> str:
    """Snapshot ZK dialog/popup state immediately after a dialog opens.

    Dumps every visible ZK window / popup / [role=dialog] container's
    inner HTML (truncated), every visible input's title/placeholder/type,
    and every frame URL. Run AT the moment a dialog is open — closing
    the dialog (e.g. by clicking another button) loses the snapshot.
    """
    lines: list[str] = [f"=== ZK layer snapshot: {label} ==="]
    for selector in (".z-window", ".z-window-modal", ".z-popup", "[role='dialog']"):
        try:
            elements = await page.locator(selector).all()
        except Exception as exc:
            lines.append(f"  selector {selector!r} error: {type(exc).__name__}: {exc}")
            continue
        for idx, el in enumerate(elements[:6]):
            try:
                visible = await el.is_visible()
            except Exception:
                visible = False
            if not visible:
                continue
            try:
                html = await el.inner_html(timeout=2_000)
            except Exception:
                html = "(unreadable)"
            lines.append(f"-- {selector}[{idx}] visible inner_html (first 8K chars):")
            lines.append(html[:8_000])
            lines.append("")
    lines.append("\n--- inputs visible at snapshot time ---")
    try:
        inputs = await page.locator("input:visible").all()
    except Exception:
        inputs = []
    for idx, inp in enumerate(inputs[:60]):
        try:
            title = await inp.get_attribute("title")
            placeholder = await inp.get_attribute("placeholder")
            input_type = await inp.get_attribute("type")
            name = await inp.get_attribute("name")
            value = await inp.input_value(timeout=500)
        except Exception:
            title = placeholder = input_type = name = value = "?"
        lines.append(
            f"  [{idx}] type={input_type!r} title={title!r} "
            f"placeholder={placeholder!r} name={name!r} value={value!r}"
        )
    lines.append("\n--- frames present at snapshot time ---")
    try:
        for frame in page.frames:
            lines.append(f"  url={frame.url!r}")
    except Exception as exc:
        lines.append(f"  (frame enumeration failed: {type(exc).__name__}: {exc})")
    return "\n".join(lines)


def _render_a11y_node(node: dict, depth: int = 0, lines: list[str] | None = None) -> list[str]:
    """Walk an accessibility-tree node and emit one line per descendant.

    Surfaces role + name + value + checked/expanded state for every node
    that has a name. Indented by tree depth.
    """
    if lines is None:
        lines = []
    if not isinstance(node, dict):
        return lines
    role = node.get("role", "(no-role)")
    name = node.get("name", "")
    value = node.get("value", "")
    checked = node.get("checked")
    expanded = node.get("expanded")
    extras = []
    if value:
        extras.append(f"value={value!r}")
    if checked is not None:
        extras.append(f"checked={checked!r}")
    if expanded is not None:
        extras.append(f"expanded={expanded!r}")
    if name or role not in ("none", "(no-role)"):
        prefix = "  " * depth
        extras_str = (" " + " ".join(extras)) if extras else ""
        lines.append(f"{prefix}[{role}] {name!r}{extras_str}")
    for child in node.get("children", []) or []:
        _render_a11y_node(child, depth + 1, lines)
    return lines


async def _capture_resumen_dom() -> tuple[str, str, str, str, str]:
    from ._renta_web_open import (
        _click_expected,
        _expect_visible,
        _fill_identification_profile,
    )
    from ._renta_web_open_safety import (
        assert_click_target_safe,
        install_page_safety_net,
    )

    payload = RentaWebOpenLivePayload(timeout_ms=120_000)
    browser_session = await default_browser_session_factory(Settings())
    context = None
    try:
        context = await browser_session.create_context(storage_state={})
        page = cast(Any, await context.new_page())
        # SAFETY-CRITICAL: install dialog dismissal + URL guards.
        await install_page_safety_net(page)
        await page.set_viewport_size({"width": 1366, "height": 900})
        await browser_session.navigate(page, str(payload.app_url))
        await page.wait_for_load_state("networkidle", timeout=payload.timeout_ms)

        new_decl = page.locator(".z-window-modal button").filter(has_text="Nueva declaración")
        await _click_expected(
            new_decl,
            stage="explore:start",
            description="Nueva declaración",
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
            stage="explore:wait-summary",
            description="Resumen de declaraciones",
            timeout_ms=payload.timeout_ms,
        )
        # The Resumen page already carries the editable form. Two
        # navigation primitives are visible:
        #   - "Buscar casilla" (toolbar button [10] in prior inventory)
        #     opens a dialog where you type a casilla number.
        #   - "Apartados declaración" opens the section navigator.
        # Try Buscar casilla via filtered locator (more robust than
        # get_by_role which timed out previously).
        # Buscar casilla lives on the secondary toolbar row that's hidden by
        # default — "Mostrar opciones" expands it. Click that first so the
        # subsequent Buscar locator resolves to a visible element.
        try:
            mostrar_btn = page.locator("button[title='Mostrar opciones']").first
            await mostrar_btn.wait_for(state="visible", timeout=10_000)
            await assert_click_target_safe(
                mostrar_btn,
                stage="explore:mostrar-opciones-safety",
                description="Mostrar opciones (toolbar expander)",
                timeout_ms=10_000,
            )
            await mostrar_btn.click(timeout=10_000)
            await page.wait_for_timeout(1_500)
        except Exception as exc:
            print(f"explore: Mostrar opciones unreachable: {type(exc).__name__}: {exc}")

        buscar_btn = page.locator("button").filter(has_text="Buscar casilla").first
        try:
            await buscar_btn.wait_for(state="visible", timeout=15_000)
            # Safety: the button label "Buscar casilla" doesn't trip the
            # forbidden-tokens denylist (no presentar/firmar/pagar/etc).
            await assert_click_target_safe(
                buscar_btn,
                stage="explore:buscar-casilla-safety",
                description="Buscar casilla",
                timeout_ms=15_000,
            )
            await buscar_btn.click(timeout=15_000)
            # Allow dialog to render.
            await page.wait_for_timeout(2_000)
            buscar_dialog_snapshot = await _snapshot_zk_layer(page, "buscar-casilla")
        except Exception as exc:
            # Soft-fail — DOM will still capture without dialog.
            print(f"explore: buscar casilla unreachable: {type(exc).__name__}: {exc}")
            buscar_dialog_snapshot = (
                f"=== ZK layer snapshot: buscar-casilla ===\n"
                f"(unreachable: {type(exc).__name__}: {exc})"
            )

        # Note: dialogs cannot be dismissed via the textual "Cancelar"
        # button because the safety guard intentionally denies "cancelar"
        # (state-mutating action in main-app context). The driver should
        # dismiss via the dialog's X-close icon (`.z-window-icon-close` or
        # equivalent), or via ZK JS API. For this exploration test we
        # leave the Buscar dialog open after capture — the Apartados
        # snapshot below will fail (modal interception), which is fine
        # because the Buscar dialog DOM capture is the primary deliverable.

        # Also drive "Apartados declaración" — the section navigator.
        # The a11y walker confirmed:
        #   <button title='Apartados declaración' cls='z-button'>
        # Clicking it opens a tree/list of declaration sections; this is
        # the navigation primitive the driver will use to reach individual
        # casillas section-by-section. Capture the dialog structure so the
        # next driver iteration can wire selector overrides.
        apartados_btn = page.locator("button[title='Apartados declaración']").first
        try:
            await apartados_btn.wait_for(state="visible", timeout=15_000)
            await assert_click_target_safe(
                apartados_btn,
                stage="explore:apartados-safety",
                description="Apartados declaración",
                timeout_ms=15_000,
            )
            await apartados_btn.click(timeout=15_000)
            await page.wait_for_timeout(2_500)
            apartados_dialog_snapshot = await _snapshot_zk_layer(page, "apartados")
        except Exception as exc:
            print(f"explore: apartados unreachable: {type(exc).__name__}: {exc}")
            apartados_dialog_snapshot = (
                f"=== ZK layer snapshot: apartados ===\n"
                f"(unreachable: {type(exc).__name__}: {exc})"
            )

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
        # Page-evaluate DOM walk: enumerate every element with role,
        # aria-label, title, or ZK-class attributes, including across
        # shadow roots. Captures the Buscar casilla dialog widgets that
        # ZK lazy-loads outside the main page.content() snapshot.
        a11y_lines: list[str] = []
        try:
            elements = await page.evaluate(
                """
                () => {
                  const out = [];
                  function walk(root, depth) {
                    if (!root) return;
                    const all = root.querySelectorAll('*');
                    for (const el of all) {
                      const role = el.getAttribute('role');
                      const aria = el.getAttribute('aria-label');
                      const title = el.getAttribute('title');
                      const cls = (el.className && typeof el.className === 'string') ? el.className : '';
                      const isZk = /\\bz-(window|popup|textbox|decimalbox|doublebox|combobox|button|toolbarbutton|menuitem|listitem)\\b/.test(cls);
                      if (role || aria || title || isZk) {
                        const text = (el.innerText || '').slice(0, 80).replace(/\\s+/g, ' ').trim();
                        out.push({
                          role: role || '',
                          aria: aria || '',
                          title: title || '',
                          cls: cls.slice(0, 60),
                          text: text,
                          tag: el.tagName.toLowerCase(),
                          visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
                        });
                      }
                      if (el.shadowRoot) walk(el.shadowRoot, depth + 1);
                    }
                  }
                  walk(document, 0);
                  return out;
                }
                """
            )
            for entry in elements[:400]:
                if not entry.get("visible"):
                    continue
                a11y_lines.append(
                    f"<{entry['tag']}> "
                    f"role={entry['role']!r} aria={entry['aria']!r} "
                    f"title={entry['title']!r} cls={entry['cls']!r} "
                    f"text={entry['text']!r}"
                )
        except Exception as exc:
            a11y_lines = [f"(page.evaluate walk failed: {type(exc).__name__}: {exc})"]
        return (
            html_content,
            "\n".join(button_inventory_lines),
            "\n".join(a11y_lines),
            buscar_dialog_snapshot,
            apartados_dialog_snapshot,
        )
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
    html, buttons, a11y, buscar_dialog, apartados_dialog = asyncio.run(_capture_resumen_dom())
    _DOM_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _DOM_OUTPUT.write_text(html, encoding="utf-8")
    _BUTTONS_OUTPUT.write_text(buttons, encoding="utf-8")
    _A11Y_OUTPUT.write_text(a11y, encoding="utf-8")
    _BUSCAR_DIALOG_OUTPUT.write_text(buscar_dialog, encoding="utf-8")
    _APARTADOS_DIALOG_OUTPUT.write_text(apartados_dialog, encoding="utf-8")
    assert len(html) > 0
    assert "Resumen" in html or "resumen" in html.lower()
