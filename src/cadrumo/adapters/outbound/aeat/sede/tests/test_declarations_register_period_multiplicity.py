"""One period can carry more than one filing, and an empty grid is still an answer.

Two register shapes are pinned here, both authored as synthetic fixtures because
neither existed in this tree.

The first is a period with MORE THAN ONE filing. Every other declaraciones
fixture renders one row per period, so the assumption that a period maps to a
single declaration was structurally untestable — and it is wrong: an original
plus a later-presented amendment for the same quarter both sit in the grid, each
with its own expediente id and presentation timestamp, both registered ALTA. The
parse must surface every row rather than collapsing or refusing, because
collapsing is a downstream decision (the history selector owns it) and refusing
would reject a legitimate filing history.

The second is a grid for a pair the taxpayer never filed. That comes back fully
formed and carries zero rows, and it must stay distinguishable from the two
shapes that genuinely are failures: a grid whose pager declares more records
than it rendered, and markup carrying no grid at all. An empty answer read as an
error would make "you filed nothing" indistinguishable from "the read broke".

Expectations are derived from each fixture's own raw markup rather than
hardcoded, so a regenerated fixture carries its assertions with it and no tally
is frozen into this module. See the provenance sidecars
``declaraciones-modelo-303-duplicated-period-synthetic.json`` and
``declaraciones-modelo-303-no-results-synthetic.json`` for their synthetic
origin: no real capture may be used here.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest

from ......tests import FIXTURES_DIR
from .._declarations_listbox import _parse_listbox
from ..declarations import _register_rows_from_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FIXTURE_ROOT = FIXTURES_DIR / "aeat-sede"

_DUPLICATED_PERIOD_FIXTURE = "declaraciones-modelo-303-duplicated-period-synthetic.html"
_NO_RESULTS_FIXTURE = "declaraciones-modelo-303-no-results-synthetic.html"

_MODELO = "303"
_EJERCICIO = 2024

_LISTITEM_RE = re.compile(r'class="[^"]*\bz-listitem\b')
_NO_RESULTS_SENTENCE = "No se han encontrado resultados"


def _fixture_html(filename: str) -> str:
    return (_FIXTURE_ROOT / filename).read_text(encoding="utf-8")


def _fixture_rendered_rows(html: str) -> int:
    """Count the rendered grid rows straight out of the fixture markup."""
    return len(_LISTITEM_RE.findall(html))


def test_register_parse_surfaces_every_filing_of_a_duplicated_period() -> None:
    """A period holding two filings parses to two rows, each with its own identity.

    The grid mixes duplicated and single-filing periods on purpose, so a parse
    that collapsed duplicates would still satisfy a fixture made only of
    duplicates. Both halves are asserted: at least one period yields more than
    one row, and at least one yields exactly one.
    """
    html = _fixture_html(_DUPLICATED_PERIOD_FIXTURE)

    rows = _register_rows_from_snapshot(html, modelo=_MODELO, ejercicio=_EJERCICIO)

    assert len(rows) == _fixture_rendered_rows(html), (
        "the register read dropped or duplicated rows relative to the fixture's own markup"
    )
    rows_per_period = Counter(row.period for row in rows)
    duplicated_periods = {period for period, count in rows_per_period.items() if count > 1}
    single_periods = {period for period, count in rows_per_period.items() if count == 1}
    assert duplicated_periods, "fixture no longer carries a period with more than one filing"
    assert single_periods, "fixture no longer carries an ordinary single-filing period alongside the duplicates"

    for period in duplicated_periods:
        same_period = [row for row in rows if row.period == period]
        expediente_ids = {row.expediente_id for row in same_period}
        presented_at = {row.presented_at for row in same_period}
        assert len(expediente_ids) == len(same_period), (
            f"filings for {period!s} share an expediente id, so they are not distinct declarations"
        )
        assert len(presented_at) == len(same_period), (
            f"filings for {period!s} share a presentation timestamp, so neither can be called the later one"
        )
        assert {row.estado.upper() for row in same_period} == {"ALTA"}, (
            "both filings of a duplicated period are registered active; a superseded-by-BAJA shape is a different case"
        )


def test_register_parse_carries_the_request_type_signal_on_every_row() -> None:
    """``tipo_solicitud`` is read off the grid and reaches the boundary record populated.

    AEAT states its own request type per row, which is the signal that could
    eventually tell an original from an amendment. The property asserted is that
    the parse carries it rather than dropping it, and that the later filing of a
    duplicated period carries a DIFFERENT value than the earlier one — the
    fixture's exact wording is not AEAT-verified and is never asserted
    literally.
    """
    html = _fixture_html(_DUPLICATED_PERIOD_FIXTURE)

    rows = _register_rows_from_snapshot(html, modelo=_MODELO, ejercicio=_EJERCICIO)

    assert all(row.tipo_solicitud for row in rows), "the register parse dropped the request-type cell"
    rows_per_period = Counter(row.period for row in rows)
    for period, count in rows_per_period.items():
        if count < 2:
            continue
        by_presentation = sorted(
            (row for row in rows if row.period == period),
            key=lambda row: row.presented_at,
        )
        assert by_presentation[0].tipo_solicitud != by_presentation[-1].tipo_solicitud, (
            f"the earlier and later filings of {period!s} carry the same request type, "
            "so the fixture cannot exercise the signal that distinguishes them"
        )


def test_empty_register_grid_reads_as_a_complete_answer_not_a_short_one() -> None:
    """A pair the taxpayer never filed yields zero rows, no declared total, no refusal.

    The no-results sentence sits in the grid's empty-body section rather than in
    a single-cell row, which is the markup AEAT serves and a different parse
    branch than the inline sentinel shape covered elsewhere. With no pager there
    is no record total to fall short of, so the read must return the empty tuple
    instead of raising — that is what keeps "filed nothing" separable from "the
    read failed".
    """
    html = _fixture_html(_NO_RESULTS_FIXTURE)
    assert _fixture_rendered_rows(html) == 0, "fixture grew a rendered row; it can no longer pin the empty grid"
    assert _NO_RESULTS_SENTENCE in html, "fixture lost the no-results sentence AEAT renders for an empty grid"
    assert not re.search(
        rf'class="[^"]*\bz-listitem\b[^>]*>(?:(?!</tr>).)*{re.escape(_NO_RESULTS_SENTENCE)}',
        html,
        flags=re.DOTALL,
    ), "the no-results sentence moved inside a z-listitem, which is the inline sentinel shape, not this one"

    page = _parse_listbox(html, modelo=_MODELO, ejercicio=_EJERCICIO)
    rows = _register_rows_from_snapshot(html, modelo=_MODELO, ejercicio=_EJERCICIO)

    assert page.rows == ()
    assert page.declared_total is None
    assert page.truncated is False
    assert rows == ()
