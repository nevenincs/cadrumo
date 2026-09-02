"""Modelo 130 parser boundary corpus sweeps.

See Also:
    :func:`~adapters.inbound.declaracion.parser.parse_declaracion`
        Public parser boundary exercised against every M130 corpus PDF.
    :mod:`~adapters.inbound.declaracion.tests._parser_boundary_m130_support`
        Shared parameter list and expected casilla values for this corpus.
    :mod:`~adapters.inbound.declaracion.tests.test_verification_chain_m130`
        Downstream engine recomputation tests that consume the same parsed
        fixtures.
    :class:`~adapters.inbound.declaracion.InboundDeclaracionObservation`
        Observation aggregate returned by the parser and asserted here.
"""

from __future__ import annotations

import pytest

from ._parser_boundary_m130_support import (
    _M130_CORPUS_GROUND_TRUTH,
    _M130_CORPUS_IDS,
    _M130_CORPUS_PARAMS,
)
from ._parser_boundary_support import FIXTURES_DIR, _expected_period, parse_declaracion

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize("pdf_stem,year,period", _M130_CORPUS_PARAMS, ids=_M130_CORPUS_IDS)
def test_parser_extracts_modelo_130_casillas_from_corpus(pdf_stem: str, year: int, period: str) -> None:
    """Round-trip all M130 corpus PDFs through the production bbox_anchored profile.

    See Also:
        :class:`~adapters.inbound.declaracion.TemplateRevision`
            Parser-resolved modelo/year/revision coordinate stamped onto each
            returned observation.
    """
    expected = _M130_CORPUS_GROUND_TRUTH[pdf_stem]
    pdf_path = FIXTURES_DIR / "justificantes" / "130" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="130",
        año_override=year,
        period_override=period,
    )

    assert filing.modelo == "130", f"{pdf_stem}: expected modelo='130', got {filing.modelo!r}"
    assert filing.period == _expected_period(year, period), (
        f"{pdf_stem}: expected period={period!r}, got {filing.period!r}"
    )
    assert filing.tax_id == "Y0000001S", f"{pdf_stem}: expected tax_id='Y0000001S', got {filing.tax_id!r}"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "130"
    assert filing.registry_snapshot_ref.modelo_year == year

    extracted = {value.casilla_id: value.printed_value for value in filing.values}
    assert extracted == expected, (
        f"{pdf_stem}: extracted casillas do not match ground truth.\n  expected: {expected}\n  got:      {extracted}"
    )
