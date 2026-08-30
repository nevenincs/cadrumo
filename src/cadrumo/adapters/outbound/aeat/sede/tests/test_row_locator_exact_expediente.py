"""Real-browser regression for the row-scoped expediente locator.

``_row_locator_for_expediente`` selects the ONE register row whose Expediente
cell carries a given id, and every per-row artefact fetch is scoped through it:
the click that opens a justificante's cotejo popup happens inside that row, so
this locator is what binds a fetched receipt to the declaration it is recorded
against. If it can match two rows, a fetch can pick up another filing's receipt
while every downstream consumer still believes the pairing is fixed.

It filtered with a substring ``has_text``, so a row whose expediente id merely
contained the target satisfied it. AEAT expediente ids are long tracking numbers
with no known reachable collision, so this covers a latent hazard rather than an
observed defect — which is the right posture for a sole binding mechanism.

These tests drive a real, local, headless Chromium page. The markup is a
synthetic in-memory fixture reproducing the ZK listbox shape AEAT renders, and
no AEAT network contact occurs, so the assertion exercises Playwright's actual
selector engine rather than a Python-side stand-in for it.
"""

from __future__ import annotations

import asyncio

import pytest
from playwright.async_api import async_playwright

from ..declarations import _row_locator_for_expediente

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TARGET = "202613000000101A"
#: Contains ``_TARGET`` as a proper substring, which is exactly what the old
#: filter could not tell apart from the target itself.
_SUPERSTRING = f"{_TARGET}99"

_PAGE_CONTENT = f"""
<!DOCTYPE html>
<html>
<body>
<div class="z-listbox">
  <div class="z-listitem" id="row-superstring">
    <div class="z-listcell">{_SUPERSTRING}</div>
    <div class="z-listcell">Ver</div>
  </div>
  <div class="z-listitem" id="row-target">
    <div class="z-listcell">  {_TARGET}  </div>
    <div class="z-listcell">Ver</div>
  </div>
</div>
</body>
</html>
"""


async def _matched_row_ids(expediente_id: str) -> list[str]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content(_PAGE_CONTENT)
            locator = _row_locator_for_expediente(page, expediente_id=expediente_id)
            return [await locator.nth(index).get_attribute("id") or "" for index in range(await locator.count())]
        finally:
            await browser.close()


def test_the_locator_matches_only_the_row_whose_expediente_id_is_exactly_the_target() -> None:
    """One row matches, and it is not the row that merely contains the id.

    The fixture is ordered with the superstring row FIRST, so a substring filter
    would not only match two rows, it would resolve ``.first`` to the wrong one —
    which is how a wrong-artefact fetch would actually happen.
    """
    assert _SUPERSTRING.startswith(_TARGET), (
        "the second row no longer contains the target as a substring, so this fixture "
        "cannot exercise the substring hazard"
    )

    assert asyncio.run(_matched_row_ids(_TARGET)) == ["row-target"]


def test_the_locator_matches_the_superstring_row_when_that_is_the_target() -> None:
    """Asking for the longer id selects the longer id's row, and only that one.

    Without this, an anchored pattern that simply failed to match anything would
    satisfy the test above while breaking every real capture.
    """
    assert asyncio.run(_matched_row_ids(_SUPERSTRING)) == ["row-superstring"]


def test_the_locator_matches_nothing_for_an_absent_expediente_id() -> None:
    """An id no row carries selects no row, rather than falling back to a partial hit."""
    assert asyncio.run(_matched_row_ids("202613000000999Z")) == []
