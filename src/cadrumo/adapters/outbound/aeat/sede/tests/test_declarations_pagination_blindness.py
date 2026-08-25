"""The declaraciones-register read refuses a page the grid itself calls partial.

``_parse_listbox`` reads one DOM snapshot of the *Consultar declaraciones
presentadas* grid captured after a single ``Buscar`` click, and the walker does
not click through pages. Every ``row_count`` downstream
(:class:`~application.live.FiledDataListingReport`,
:class:`~application.live.FiledDataCaptureReport`) is ``len(rows)`` over that
one parse, so a short page returned as an answer would report a partial filing
history with exactly the confidence of a complete one.

This module pins the opposite behaviour: the parse now carries the record total
the grid's own pager label declares, and the register read raises rather than
returning an undercount. Two cases matter equally. A page whose label declares
more records than it rendered must refuse. A page carrying no pager at all
renders everything it has, and must never be treated as short -- a detector that
fired on the ordinary single-page capture would be worse than the gap it closes.

Whether AEAT's real grid ever serves a paginated shape for this form is
unverified against a live capture; this module does not claim it does. What it
settles is narrower and answerable from static fixtures alone: GIVEN a page that
renders fewer rows than its own pager label claims exist, does the read notice?

See the provenance sidecar
``declaraciones-modelo-100-paginated-synthetic.json`` for the paginated
fixture's synthetic origin; the no-pager fixture is a real sanitised capture.
"""

from __future__ import annotations

import re

import pytest

from ......tests import FIXTURES_DIR
from .._declarations import _register_rows_from_snapshot
from .._declarations_listbox import _parse_listbox
from ..errors import SedeParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FIXTURE_ROOT = FIXTURES_DIR / "aeat-sede"

# Both cross-checks below are lifted from the fixture's own raw markup, never
# from anything the production parser computes, so the comparisons are genuine
# cross-checks rather than the parser measured against itself.
_TOTAL_REGISTROS_RE = re.compile(r"de (\d+) en total")
_LISTITEM_RE = re.compile(r'class="[^"]*\bz-listitem\b')


def _fixture_declared_total(html: str) -> int | None:
    """Return the record total the fixture's own pager label states, if it has one."""
    match = _TOTAL_REGISTROS_RE.search(html)
    return None if match is None else int(match.group(1))


def _fixture_rendered_rows(html: str) -> int:
    """Count the rendered grid rows straight out of the fixture markup."""
    return len(_LISTITEM_RE.findall(html))


def test_page_declaring_more_records_than_it_rendered_is_refused() -> None:
    """A register snapshot short of its own declared record total raises instead of returning rows.

    The paginated fixture's pager label states more filings than the captured
    page renders. Both numbers are read here independently out of the raw
    markup, so the refusal is checked against the fixture rather than against
    the parser's own arithmetic, and neither count is hardcoded -- if the
    fixture is regenerated at a different size the assertions travel with it.
    """
    html = (_FIXTURE_ROOT / "declaraciones-modelo-100-paginated-synthetic.html").read_text(encoding="utf-8")
    declared_total = _fixture_declared_total(html)
    rendered_rows = _fixture_rendered_rows(html)
    assert declared_total is not None, "fixture's pager label shape changed; this fixture must declare a total"
    assert rendered_rows < declared_total, (
        "fixture no longer renders fewer rows than its pager declares, so it cannot exercise a truncated read"
    )

    with pytest.raises(SedeParseError) as exc_info:
        _register_rows_from_snapshot(html, modelo="100", ejercicio=2026)

    context = exc_info.value.context
    assert context is not None
    assert context["rendered_count"] == rendered_rows
    assert context["declared_total"] == declared_total
    assert context["modelo"] == "100"
    assert context["ejercicio"] == 2026


def test_truncated_page_still_parses_its_rows_and_reports_the_declared_total() -> None:
    """The parse itself stays lossless: it reports the shortfall, the read is what refuses.

    Detection lives on the parsed page rather than inside the row loop, so the
    rows and the grid's declared total are both available to whatever consumes
    the parse. That separation is what would let a future page-traversal fix
    build on this plumbing instead of replacing it.
    """
    html = (_FIXTURE_ROOT / "declaraciones-modelo-100-paginated-synthetic.html").read_text(encoding="utf-8")

    page = _parse_listbox(html, modelo="100", ejercicio=2026)

    assert page.declared_total == _fixture_declared_total(html)
    assert len(page.rows) == _fixture_rendered_rows(html)
    assert page.truncated is True


def test_real_capture_without_a_pager_is_never_treated_as_truncated() -> None:
    """A grid carrying no pager rendered everything it has, and must read clean.

    The real sanitised capture in this tree has no pager markup at all. A grid
    with no pager states no total, so there is nothing to fall short of: the
    read must return its rows normally. A detector that refused here would fire
    on every ordinary capture, which is a worse failure than the silent
    undercount it exists to prevent.
    """
    html = (_FIXTURE_ROOT / "declaraciones-modelo-100-2022.html").read_text(encoding="utf-8")
    assert _fixture_declared_total(html) is None, "fixture grew a pager label; it can no longer pin the no-pager case"

    page = _parse_listbox(html, modelo="100", ejercicio=2022)
    rows = _register_rows_from_snapshot(html, modelo="100", ejercicio=2022)

    assert page.declared_total is None
    assert page.truncated is False
    assert rows == page.rows
    assert len(rows) == _fixture_rendered_rows(html)
    assert rows, "the real capture carries filing rows; an empty read would mean the parse regressed"
