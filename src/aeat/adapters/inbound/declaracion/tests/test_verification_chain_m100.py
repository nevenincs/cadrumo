from __future__ import annotations

import pytest

from ._verification_chain_m100_support import (
    _EXPECTED_CASILLAS_M100,
    _M100_CORPUS_YEAR_IDS,
    _M100_CORPUS_YEARS,
    _parse_m100_corpus,
)
from ._verification_chain_support import Decimal

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize("year", _M100_CORPUS_YEARS, ids=_M100_CORPUS_YEAR_IDS)
def test_verification_chain_m100_parser_extracts_declaracion_pdf_casillas(year: int) -> None:
    """Parser extracts M100 cuota-chain, actividades-economicas, and 0171 leaf casillas.

    GROUNDED authority: real AEAT corpus PDFs (sanitised) committed at
    src/aeat/tests/fixtures/justificantes/100/2021-0A.pdf,
    2022-0A.pdf, 2023-0A.pdf.

    Extraction verdict: VERIFIED - 20 casilla IDs extracted from each corpus PDF.
    The declaracion_pdf profile covers 20 casillas including casilla 0171
    (ingresos de explotacion), the only individually-printed 017x leaf input.

    Formula verdict: EXTRACTION-ONLY (CORPUS-LIMITED) - the declaracion_pdf profile
    now includes the one printable 017x leaf (0171), but casillas 0172-0179 are
    absent from this summary form (only their total 0180 is shown). More
    critically, the corpus sanitisation (all amounts replaced with ~1.001.000,00
    plus adjacent box numbers appended by pdfplumber) makes arithmetic verification
    of any closure impossible. See test_verification_chain_m100_engine_corpus_limited
    for the empirical confirmation of the sanitisation artefact.
    """
    label = f"M100/{year}-0A"
    extracted = _parse_m100_corpus(year, label)
    assert set(extracted.keys()) == _EXPECTED_CASILLAS_M100, (
        f"PARSER-GAP [{label}]: unexpected casilla set.\n"
        f"  got: {sorted(extracted)}\n  expected: {sorted(_EXPECTED_CASILLAS_M100)}"
    )
    for casilla_id, value in extracted.items():
        assert isinstance(value, Decimal), (
            f"PARSER-GAP [{label}]: casilla {casilla_id!r} is not Decimal: "
            f"{type(value).__name__!r} = {value!r}"
        )
