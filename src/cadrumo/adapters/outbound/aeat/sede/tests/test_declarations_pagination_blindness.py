"""The declaraciones-register parser is blind to AEAT-side pagination.

``_parse_listbox`` reads one DOM snapshot of the *Consultar declaraciones
presentadas* grid captured after a single ``Buscar`` click. There is no pager
loop, no assertion that the rendered page size covers the grid's own total,
and no reconciliation between "rows we captured" and "rows AEAT says exist".
Every ``row_count`` downstream (:class:`~application.live.FiledDataListingReport`,
:class:`~application.live.FiledDataCaptureReport`) is ``len(rows)`` from that
one parse, so a caller reading those reports has no signal that a page was
truncated.

The one real capture in this tree
(``declaraciones-modelo-100-2022.html``) carries exactly one row and no pager
markup at all, so it cannot exercise this gap. Whether AEAT's real grid
actually paginates in this ZK "paging" mold shape is unverified against a live
capture; this module does not claim it does. What it settles is narrower and
answerable from static fixtures alone: GIVEN a page that renders fewer rows
than its own pager label claims exist, does the parser notice? Today, no.

See the provenance sidecar
``declaraciones-modelo-100-paginated-synthetic.json`` for the fixture's
synthetic origin.
"""

from __future__ import annotations

import re

import pytest

from ......tests import FIXTURES_DIR
from .._declarations_listbox import _parse_listbox

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FIXTURE_ROOT = FIXTURES_DIR / "aeat-sede"

# Independent of the production parser: lifted directly from the fixture's own
# pager label text ("Pagina 1/3, registros 1-3 de 8 en total"), never from
# anything `_parse_listbox` itself computes. This is what makes the
# discrepancy assertion below a genuine cross-check rather than a comparison
# of the parser against itself.
_TOTAL_REGISTROS_RE = re.compile(r"de (\d+) en total")


def _fixture_declared_total(html: str) -> int:
    """Return the total-filing count the fixture's own pager label states."""
    match = _TOTAL_REGISTROS_RE.search(html)
    assert match is not None, "fixture's pager label shape changed; regex needs updating"
    return int(match.group(1))


def test_parser_silently_drops_every_row_the_pagers_own_label_says_exists() -> None:
    """The parser returns only the rendered page, with no signal that AEAT claims more rows exist.

    The fixture's own text states 8 filings across 3 pages; the rendered
    ``z-listitem`` count on this single captured page is 3. A parser that
    noticed pagination would either walk the remaining pages or surface some
    signal that the capture is partial. `_parse_listbox` does neither: it
    returns exactly the rendered rows, and the returned :class:`Declaracion`
    tuple carries no field of any kind recording the pager's total or page
    count -- there is nothing left to inspect after the call that could tell
    a caller the page was truncated.

    If a later fix teaches the parser to walk pages or to reconcile against
    the pager's stated total, this assertion is the one that must flip: `len(rows)`
    should then equal `declared_total`, not fall short of it. Until that lands,
    a fall-short here is not a bug in this test -- it is the gap the test
    exists to pin.
    """
    html = (_FIXTURE_ROOT / "declaraciones-modelo-100-paginated-synthetic.html").read_text(encoding="utf-8")
    declared_total = _fixture_declared_total(html)
    assert declared_total == 8, "fixture pager label drifted from the value this test was authored against"

    rows = _parse_listbox(html, modelo="100", ejercicio=2026)

    assert len(rows) == 3, "fixture's rendered z-listitem count drifted from the value this test was authored against"
    assert len(rows) < declared_total, (
        f"expected the single-snapshot parser to under-report against the page's own total "
        f"({len(rows)} rows captured vs {declared_total} the pager label claims) -- "
        "if this now holds equal, the parser has learned to reconcile against pagination and "
        "this characterisation test should be retired, not adjusted"
    )

    # None of the returned rows, and no wrapper around the tuple, carries a
    # page-count, total-count, or truncation field a caller could consult.
    for row in rows:
        assert not hasattr(row, "page_count")
        assert not hasattr(row, "total_registros")
        assert not hasattr(row, "truncated")
