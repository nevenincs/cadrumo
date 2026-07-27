"""Modelo 100 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_m100_support import (
    _M100_2021_EXPECTED_VALUES,
    _M100_CORPUS_IDS,
    _M100_CORPUS_PARAMS,
    _M100_EXPECTED_CASILLAS,
)
from ._parser_boundary_support import (
    FIXTURES_DIR,
    Decimal,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize(
    "pdf_stem,year",
    _M100_CORPUS_PARAMS,
    ids=_M100_CORPUS_IDS,
)
def test_parser_extracts_modelo_100_profile_targets_from_corpus(pdf_stem: str, year: int) -> None:
    """Round-trip: parse M100 IRPF annual corpus PDFs and verify all 21 covered casillas.

    Four delivery chunks:
    - Chunk 1 (10 casillas): cuota-chain closure -- 0545/0546/0505/0585/0586/0587/0595/0604/0610/0670.
    - Chunk 2 (4 casillas): apartado-summary bases -- 0235/0432/0500/0510.
    - Chunk 3 (6 casillas): actividades-economicas ED detail -- 0180/0218/0223/0224/0226/0231.
    - Chunk 4 (1 casilla): ED leaf input -- 0171 (ingresos de explotacion).

    Ground truth is derived from reading the printed declaracion PDF text directly.

    What each specimen can be asserted against differs, and the difference is
    the point. 2022-0A and 2023-0A are sanitised real renders: the redaction
    pipeline wrote one constant into every money box, so every target holds the
    same number and an exact-value assertion would distinguish nothing -- a
    pattern that drifted onto the line above would satisfy it. Those two are
    asserted as ``isinstance(..., Decimal)`` only. 2021-0A is a generated
    replacement (the real 2021 render carried an identity the sanitiser never
    overwrote) and its amounts are all DISTINCT, so each value identifies the
    line it came from and the exact map IS assertable.

    Both AEAT renders print the box number in a smaller font overlapping the
    amount, which ``extract_text`` merges into one token
    (``1.001.000,005045``); the generated specimen reproduces that overlap, so
    all three exercise the word-based amount capture that keeps the two apart.

    Casillas deferred (0570/0571 cuota liquida estatal/autonomica pre-incrementada):
    both body and summary sections carry identical short labels in 2023 with no
    formula-bracket anchor available.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "100" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="100",
        año_override=year,
        period_override="0A",
    )

    assert filing.modelo == "100"
    assert filing.period == _expected_period(year, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "100"
    assert filing.registry_snapshot_ref.modelo_year == year
    assert filing.registry_snapshot_ref.period == "0A"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # All 21 covered casillas must be present: 10 cuota-chain closure casillas (first chunk),
    # 4 apartado-summary casillas (second chunk), 6 actividades-economicas ED detail (third chunk),
    # 1 ED leaf input (fourth chunk).
    # 0435 (base imponible general) is deferred: the IRPF form prints the line twice
    # (body section + base liquidable section), both identical, so the parser rejects it as
    # ambiguous. It remains a candidate for a future chunk with multiline context anchoring.
    assert set(values.keys()) == _M100_EXPECTED_CASILLAS

    # Ground truth: the label patterns locate the correct body line in the printed form.
    for casilla_id in values:
        assert isinstance(values[casilla_id], Decimal), (
            f"{pdf_stem}: casilla {casilla_id!r} expected a Decimal instance, got {values[casilla_id]!r}"
        )

    if pdf_stem != "2021-0A":
        # A sanitised real render: one constant in every box, so there is
        # nothing an exact-value assertion could tell apart.
        return

    extracted = {str(casilla_id): value for casilla_id, value in values.items()}
    expected = {casilla_id: Decimal(amount) for casilla_id, amount in _M100_2021_EXPECTED_VALUES.items()}

    assert extracted == expected, (
        f"{pdf_stem}: extraction read a different amount than the document prints. "
        f"Every printed amount here is distinct, so a mismatch names the target that "
        f"drifted onto a neighbouring line rather than merely changing value."
    )
