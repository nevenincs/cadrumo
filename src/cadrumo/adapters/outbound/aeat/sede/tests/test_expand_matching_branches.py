"""Real-browser regression for the modelo-scoped procedure-tree expansion.

AEAT's *Mis Expedientes* procedure tree can list the same modelo code under
more than one category branch (distinct autoliquidación / declaración
informativa / recargo procedure entries all carrying the same ``Modelo <N>``
label). ``_expand_matching_branches`` must expand every matching branch, not
just the first one found in document order — otherwise an expediente nested
only under a later sibling branch never enters the DOM snapshot
``walk_expedientes_tree`` parses, and a period-correct declaration resolved
against that incomplete tree fails with "not present in the expedientes
tree" even though the expediente genuinely exists.

These tests drive a real, local, headless Chromium page (no AEAT network
contact — the content is a synthetic in-memory fixture) so the assertion
exercises the actual click-selection JavaScript rather than a Python-side
stand-in for it.
"""

from __future__ import annotations

import asyncio

import pytest
from playwright.async_api import async_playwright

from ..walker import _expand_matching_branches

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# A local stub for AEAT's real ``mostrarListado()`` handler (which lives in a
# script bundle this test never loads) records every id it is invoked with,
# so the assertions can see exactly which anchors were clicked.
_PAGE_CONTENT = """
<!DOCTYPE html>
<html>
<body>
<script>
window.__clicked = [];
function mostrarListado(imgId, divId) { window.__clicked.push(divId); }
</script>
<a href="#" onclick="mostrarListado('imgA','branch-303-a');return false;">Modelo 303. IVA. Autoliquidación.</a>
<a href="#" onclick="mostrarListado('imgB','branch-303-b');return false;">Modelo 303. IVA. Recargo de equivalencia.</a>
<a href="#" onclick="mostrarListado('imgC','branch-100');return false;">Modelo 100. IRPF. Declaración.</a>
</body>
</html>
"""


async def _run_expand(modelo: str | None) -> list[str]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content(_PAGE_CONTENT)
            await _expand_matching_branches(page, modelo=modelo)
            raw_clicked = await page.evaluate("() => window.__clicked")
            assert isinstance(raw_clicked, list)
            clicked: list[str] = []
            for item in raw_clicked:
                assert isinstance(item, str)
                clicked.append(item)
            return clicked
        finally:
            await browser.close()


def test_every_matching_branch_is_expanded_not_just_the_first() -> None:
    """Two Modelo 303 branches both get expanded; the sibling Modelo 100 branch does not."""
    clicked = asyncio.run(_run_expand("303"))
    assert sorted(clicked) == ["branch-303-a", "branch-303-b"]


def test_unrelated_modelo_branch_is_left_alone() -> None:
    """Scoping by modelo="100" clicks only the Modelo 100 branch."""
    clicked = asyncio.run(_run_expand("100"))
    assert clicked == ["branch-100"]


def test_no_modelo_filter_expands_every_branch() -> None:
    """A ``None`` modelo filter still expands the whole corpus (pre-existing behaviour)."""
    clicked = asyncio.run(_run_expand(None))
    assert sorted(clicked) == ["branch-100", "branch-303-a", "branch-303-b"]
