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
from typing import TYPE_CHECKING, Final, cast

import pytest

from ......core.config import Settings
from ......core.logging import get_logger
from ......core.paths import PROJECT_ROOT
from ......domain.calculations.registry import RentaWebOpenLivePayload
from ......tests.live_gate import requires_live_enabled
from ...browser import default_browser_session_factory

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from typing import Protocol

    from playwright.async_api import Locator, Page

    class _ClickSafetyAssertion(Protocol):
        """Structural type of `assert_click_target_safe` from the safety module."""

        def __call__(
            self,
            locator: Locator,
            *,
            stage: str,
            description: str,
            timeout_ms: int = ...,
        ) -> Awaitable[None]: ...


_DOM_OUTPUT = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-resumen-dom.html"
_BUTTONS_OUTPUT = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-resumen-buttons.txt"
_A11Y_OUTPUT = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-resumen-a11y-tree.txt"
_BUSCAR_DIALOG_OUTPUT = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-buscar-dialog.txt"
_APARTADOS_DIALOG_OUTPUT = PROJECT_ROOT / ".vault" / "audit" / "renta-web-open-apartados-dialog.txt"
_log = get_logger(__name__)


async def _snapshot_zk_layer(page: Page, label: str) -> str:
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
            _log.debug("explore DOM selector lookup failed selector=%s", selector, exc_info=True)
            lines.append(f"  selector {selector!r} error: {type(exc).__name__}: {exc}")
            continue
        for idx, el in enumerate(elements[:6]):
            try:
                visible = await el.is_visible()
            except Exception:
                _log.debug("explore DOM visibility lookup failed selector=%s index=%d", selector, idx, exc_info=True)
                visible = False
            if not visible:
                continue
            try:
                html = await el.inner_html(timeout=2_000)
            except Exception:
                _log.debug("explore DOM inner_html lookup failed selector=%s index=%d", selector, idx, exc_info=True)
                html = "(unreadable)"
            lines.append(f"-- {selector}[{idx}] visible inner_html (first 8K chars):")
            lines.append(html[:8_000])
            lines.append("")
    lines.append("\n--- inputs visible at snapshot time ---")
    try:
        inputs = await page.locator("input:visible").all()
    except Exception:
        _log.debug("explore DOM input locator lookup failed", exc_info=True)
        inputs = []
    for idx, inp in enumerate(inputs[:60]):
        try:
            title = await inp.get_attribute("title")
            placeholder = await inp.get_attribute("placeholder")
            input_type = await inp.get_attribute("type")
            name = await inp.get_attribute("name")
            value = await inp.input_value(timeout=500)
        except Exception:
            _log.debug("explore DOM input metadata lookup failed index=%d", idx, exc_info=True)
            title = placeholder = input_type = name = value = "?"
        lines.append(
            f"  [{idx}] type={input_type!r} title={title!r} placeholder={placeholder!r} name={name!r} value={value!r}"
        )
    lines.append("\n--- frames present at snapshot time ---")
    try:
        for frame in page.frames:
            lines.append(f"  url={frame.url!r}")
    except Exception as exc:
        _log.debug("explore DOM frame enumeration failed", exc_info=True)
        lines.append(f"  (frame enumeration failed: {type(exc).__name__}: {exc})")
    return "\n".join(lines)


def _render_a11y_node(node: dict[str, object], depth: int = 0, lines: list[str] | None = None) -> list[str]:
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
    children = node.get("children", [])
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                # The Playwright a11y tree is untyped; isinstance narrows the
                # child to dict[Unknown, Unknown], which dict-invariance rejects
                # against dict[str, object]. The cast restores the str-keyed
                # node shape the recursion expects.
                _render_a11y_node(cast("dict[str, object]", child), depth + 1, lines)
    return lines


async def _try_expand_secondary_toolbar(page: Page, assert_click_target_safe: _ClickSafetyAssertion) -> None:
    """Click "Mostrar opciones" to reveal the secondary toolbar row.

    The button is the secondary-toolbar expander; failing to find or
    click it is non-fatal — the subsequent Buscar locator will simply
    soft-fail when the row stays hidden.
    """

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
        _log.debug("explore DOM Mostrar opciones unreachable: %s: %s", type(exc).__name__, exc, exc_info=True)


async def _try_open_and_snapshot_dialog(
    page: Page,
    *,
    locator: Locator,
    stage: str,
    description: str,
    timeout_ms: int,
    wait_after_click_ms: int,
    assert_click_target_safe: _ClickSafetyAssertion,
) -> str:
    """Wait, safety-gate, click ``locator`` and snapshot the resulting ZK layer.

    Soft-fails: when the dialog cannot be opened, returns a
    "(unreachable: …)" snapshot string instead of raising. The DOM
    capture still proceeds.
    """

    try:
        await locator.wait_for(state="visible", timeout=timeout_ms)
        await assert_click_target_safe(
            locator,
            stage=f"explore:{stage}-safety",
            description=description,
            timeout_ms=timeout_ms,
        )
        await locator.click(timeout=timeout_ms)
        await page.wait_for_timeout(wait_after_click_ms)
        return await _snapshot_zk_layer(page, stage)
    except Exception as exc:
        _log.debug("explore DOM %s unreachable: %s: %s", stage, type(exc).__name__, exc, exc_info=True)
        return f"=== ZK layer snapshot: {stage} ===\n(unreachable: {type(exc).__name__}: {exc})"


async def _capture_resumen_dom() -> tuple[str, str, str, str, str]:
    from .._renta_web_open import (
        _click_expected,
        _expect_visible,
        _fill_identification_profile,
    )
    from .._renta_web_open_safety import (
        assert_click_target_safe,
        install_page_safety_net,
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
        await _try_expand_secondary_toolbar(page, assert_click_target_safe)
        buscar_dialog_snapshot = await _try_open_and_snapshot_dialog(
            page,
            locator=page.locator("button").filter(has_text="Buscar casilla").first,
            stage="buscar-casilla",
            description="Buscar casilla",
            timeout_ms=15_000,
            wait_after_click_ms=2_000,
            assert_click_target_safe=assert_click_target_safe,
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
        apartados_dialog_snapshot = await _try_open_and_snapshot_dialog(
            page,
            locator=page.locator("button[title='Apartados declaración']").first,
            stage="apartados",
            description="Apartados declaración",
            timeout_ms=15_000,
            wait_after_click_ms=2_500,
            assert_click_target_safe=assert_click_target_safe,
        )

        html_content = await page.content()
        inventory_text = await _capture_dom_inventory(page)
        a11y_text = await _capture_a11y_tree(page)
        return (
            html_content,
            inventory_text,
            a11y_text,
            buscar_dialog_snapshot,
            apartados_dialog_snapshot,
        )
    finally:
        if context is not None:
            await context.close()
        await browser_session.close()


async def _safe_inner_text(locator: Locator, *, stage: str) -> str:
    """Read ``locator.inner_text`` with a fallback string on any failure."""
    try:
        return (await locator.inner_text(timeout=1_000)).strip()
    except Exception:
        _log.debug("explore DOM inner_text unreadable: %s", stage, exc_info=True)
        return "(unreadable)"


async def _safe_get_attribute(locator: Locator, attr: str, *, stage: str) -> str | None:
    """Read ``locator.get_attribute(attr)`` with a fallback on any failure."""
    try:
        return await locator.get_attribute(attr)
    except Exception:
        _log.debug("explore DOM attribute %r unreadable: %s", attr, stage, exc_info=True)
        return None


async def _capture_button_inventory(page: Page) -> list[str]:
    """Inventory native ``<button>`` elements with their text + disabled attribute."""
    lines: list[str] = ["=== <button> elements ==="]
    buttons = await page.locator("button").all()
    for idx, btn in enumerate(buttons[:120]):
        stage = f"button[{idx}]"
        text = await _safe_inner_text(btn, stage=stage)
        disabled = await _safe_get_attribute(btn, "disabled", stage=stage)
        lines.append(f"  [{idx}] text={text!r} disabled={disabled!r}")
    return lines


async def _capture_anchor_inventory(page: Page) -> list[str]:
    """Inventory ``<a>`` link elements with their text + href."""
    lines: list[str] = ["=== <a> link elements ==="]
    anchors = await page.locator("a").all()
    for idx, anchor in enumerate(anchors[:120]):
        stage = f"anchor[{idx}]"
        text = await _safe_inner_text(anchor, stage=stage)
        href = await _safe_get_attribute(anchor, "href", stage=stage)
        lines.append(f"  [{idx}] text={text!r} href={href!r}")
    return lines


async def _capture_zk_inventory(page: Page) -> list[str]:
    """Inventory ZK-class clickable elements (.z-button / .z-toolbarbutton / etc.)."""
    lines: list[str] = ["=== ZK-shape elements with click handlers ==="]
    for cls in (".z-button", ".z-toolbarbutton", ".z-menuitem", ".z-listitem"):
        els = await page.locator(cls).all()
        lines.append(f"\n  -- {cls} ({len(els)} found) --")
        for idx, el in enumerate(els[:60]):
            text = await _safe_inner_text(el, stage=f"{cls}[{idx}]")
            lines.append(f"    [{idx}] text={text!r}")
    return lines


async def _capture_input_inventory(page: Page) -> list[str]:
    """Inventory ``<input>`` elements (dialog textboxes etc.)."""
    lines: list[str] = ["\n=== input elements (dialog textboxes etc.) ==="]
    inputs = await page.locator("input").all()
    for idx, inp in enumerate(inputs[:60]):
        try:
            title = await inp.get_attribute("title")
            placeholder = await inp.get_attribute("placeholder")
            input_type = await inp.get_attribute("type")
            name = await inp.get_attribute("name")
            value = await inp.input_value(timeout=500)
        except Exception:
            _log.debug("explore DOM input inventory metadata unreadable index=%d", idx, exc_info=True)
            title = placeholder = input_type = name = value = "?"
        lines.append(
            f"  [{idx}] type={input_type!r} title={title!r} placeholder={placeholder!r} name={name!r} value={value!r}"
        )
    return lines


async def _capture_dialog_inventory(page: Page) -> list[str]:
    """Inventory visible dialog / modal containers."""
    lines: list[str] = ["\n=== visible dialogs / modals ==="]
    for cls in (".z-window", ".z-window-modal", "[role='dialog']"):
        els = await page.locator(cls).all()
        for idx, el in enumerate(els[:10]):
            try:
                visible = await el.is_visible()
                text = (await el.inner_text(timeout=1_000))[:200]
            except Exception:
                _log.debug(
                    "explore DOM visible dialog metadata unreadable selector=%s index=%d",
                    cls,
                    idx,
                    exc_info=True,
                )
                visible = False
                text = "(unreadable)"
            if visible:
                lines.append(f"  {cls}[{idx}] visible text-preview={text!r}")
    return lines


async def _capture_dom_inventory(page: Page) -> str:
    """Concatenate the five DOM-inventory views into one newline-joined string."""
    sections = (
        await _capture_button_inventory(page),
        [""],
        await _capture_anchor_inventory(page),
        [""],
        await _capture_zk_inventory(page),
        await _capture_input_inventory(page),
        await _capture_dialog_inventory(page),
    )
    return "\n".join(line for section in sections for line in section)


# Page-evaluate DOM walk: enumerate every element carrying role /
# aria-label / title / ZK-class attributes, including across shadow
# roots. Captures the Buscar casilla dialog widgets that ZK lazy-loads
# outside the main page.content() snapshot.
_A11Y_WALK_JS: Final[str] = """
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
      const _zkRe1 = /\\bz-(window|popup|textbox|decimalbox|doublebox|combobox)\\b/;
      const _zkRe2 = /\\bz-(button|toolbarbutton|menuitem|listitem)\\b/;
      const isZk = _zkRe1.test(cls) || _zkRe2.test(cls);
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


async def _capture_a11y_tree(page: Page) -> str:
    """Walk the accessibility tree across shadow roots; return one line per visible entry."""
    try:
        elements = await page.evaluate(_A11Y_WALK_JS)
    except Exception as exc:
        _log.debug("explore DOM page.evaluate walk failed", exc_info=True)
        return f"(page.evaluate walk failed: {type(exc).__name__}: {exc})"
    lines: list[str] = []
    for entry in elements[:400]:
        if not entry.get("visible"):
            continue
        lines.append(
            f"<{entry['tag']}> "
            f"role={entry['role']!r} aria={entry['aria']!r} "
            f"title={entry['title']!r} cls={entry['cls']!r} "
            f"text={entry['text']!r}"
        )
    return "\n".join(lines)


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
