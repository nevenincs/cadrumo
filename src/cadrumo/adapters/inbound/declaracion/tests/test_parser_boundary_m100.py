"""Modelo 100 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_m100_support import (
    _M100_CORPUS_IDS,
    _M100_CORPUS_PARAMS,
    _M100_EXPECTED_CASILLAS,
    _M100_EXPECTED_VALUES_BY_STEM,
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

    All three specimens are generated replacements: the real renders carried
    personal data the redaction pipeline never wrote and could not stay in the
    repository. Each reproduces the layout facts the profile depends on --
    notably that AEAT prints the box number in a smaller font overlapping the
    amount, which ``extract_text`` merges into one token
    (``1.001.000,005045``) and only the word-based capture keeps apart.

    Because a generated render can print DISTINCT amounts where the redaction
    pipeline wrote one constant everywhere, the exact per-casilla map is
    assertable here for the first time. That is the assertion that catches a
    label pattern drifting onto a neighbouring line, which the old
    ``isinstance(..., Decimal)`` check could not.

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

    extracted = {str(casilla_id): value for casilla_id, value in values.items()}
    expected = {casilla_id: Decimal(amount) for casilla_id, amount in _M100_EXPECTED_VALUES_BY_STEM[pdf_stem].items()}

    assert extracted == expected, (
        f"{pdf_stem}: extraction read a different amount than the document prints. "
        f"Every printed amount here is distinct, so a mismatch names the target that "
        f"drifted onto a neighbouring line rather than merely changing value."
    )


def test_the_expected_maps_keep_their_discriminating_power() -> None:
    """The guard on the guard: the expected amounts must stay distinct.

    The exact-map assertion above is only stronger than the constant-substitution
    check it replaced BECAUSE the amounts differ. Measured on the withdrawn
    renders, which printed one redaction constant into every box, a target that
    drifted onto a neighbouring line read the same number and the old check
    passed; with distinct amounts the same drift fails. A well-meaning edit that
    made these uniform -- or that copied one year's block over another -- would
    leave every test in this module green while silently restoring exactly the
    blindness the replacement removed.

    Two properties, because two different mistakes are possible. Within a
    specimen, distinctness is what catches a cross-LINE misread. Across the
    three, per-casilla distinctness is what catches a test or a fixture reading
    the wrong YEAR.
    """
    for stem, amounts in _M100_EXPECTED_VALUES_BY_STEM.items():
        values = list(amounts.values())
        assert len(set(values)) == len(values), (
            f"{stem}: expected amounts must be pairwise distinct, or the exact-map assertion "
            f"cannot tell a cross-line misread from a correct read; "
            f"{len(values) - len(set(values))} duplicate(s)"
        )

    stems = sorted(_M100_EXPECTED_VALUES_BY_STEM)
    shared_casillas = set.intersection(*(set(_M100_EXPECTED_VALUES_BY_STEM[stem]) for stem in stems))
    assert shared_casillas, "the specimens must declare overlapping casillas for this to assert anything"
    for casilla_id in sorted(shared_casillas):
        per_year = [_M100_EXPECTED_VALUES_BY_STEM[stem][casilla_id] for stem in stems]
        assert len(set(per_year)) == len(per_year), (
            f"casilla {casilla_id!r} carries the same amount in more than one ejercicio "
            f"({dict(zip(stems, per_year, strict=True))}), so a fixture or test reading the "
            f"wrong year's specimen would go unnoticed"
        )
