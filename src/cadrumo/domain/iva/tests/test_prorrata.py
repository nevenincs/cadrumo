"""Real-behaviour tests for the IVA prorrata substrate.

Every test in this module either grounds its expected value in an external
authority (the LIVA article cited inline or the AEAT "Manual Práctico IVA"
worked example reproduced inline), or asserts a structural / wiring /
error-path property. No test computes the expected value by re-applying the
same formula the production code applies.

Legal authorities cited:

* LIVA arts. 101, 102, 103, 104 and 109 — Ley 37/1992 del IVA
  (BOE-A-1992-28740).
* TJUE C-488/07 (Royal Bank of Scotland) — established that member states
  must round the prorrata up to the next whole percentage (the AEAT-cited
  authority for the ``ROUND_CEILING`` quantiser).
* AEAT Manual Práctico IVA — recurring worked example reproduced in the
  test docstrings.
"""

from __future__ import annotations

from datetime import date as _esp_date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.directory_scan import scan_directory
from ...calculations.registry.schema_base import ThresholdComparison
from ..errors import ProrrataInputError, ProrrataSectorError
from ..prorrata import (
    InputClassification,
    ProrrataInputDeduction,
    ProrrataInputs,
    ProrrataKind,
    ProrrataReference,
    ProrrataRegime,
    ProrrataResult,
    ProrrataSector,
    classify_input_deduction,
    compute_prorrata_general,
    compute_sectoral_prorrata,
    especial_mandatory_rule,
    is_especial_mandatory,
    requires_sectoral_separation,
    sum_deductible_amounts,
    validate_prorrata_reference,
)
from ..prorrata_especial_parameters import ProrrataEspecialMandatoryParameters

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


#: An explicit resolved margin. These tests exercise the PREDICATE and the
#: advisory wording, not the law; whether 10 inclusive is what art. 103.Dos.2
#: states is answered against the registry by the modelo 303 parameter gate.
_ESPECIAL_PARAMS = ProrrataEspecialMandatoryParameters(
    margin_percentage=Decimal("10"),
    comparison=ThresholdComparison.INCLUSIVE,
    modelo_id="303",
    revision_id="2025",
    resolved_on=_esp_date(2025, 12, 31),
)

_INPUT_DEDUCTION_CASES = (
    (
        InputClassification.EXCLUSIVELY_DEDUCTIBLE,
        Decimal("210.00"),
        Decimal("40"),
        Decimal("100"),
        Decimal("210.00"),
    ),
    (
        InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE,
        Decimal("210.00"),
        Decimal("80"),
        Decimal("0"),
        Decimal("0.00"),
    ),
    (
        InputClassification.COMMON,
        Decimal("210.00"),
        Decimal("70"),
        Decimal("70"),
        Decimal("147.00"),
    ),
)

# LIVA art. 103.Dos.2.º cases as ``(year, general, especial, expected)``.
#
# From filing year 2015 the provision (Ley 28/2014 art. 1.26, BOE-A-2014-12329)
# reads "exceda en un 10 por ciento o más", so the ten-percent margin is
# INCLUSIVE: a general deduction landing exactly on it already makes the
# especial regime mandatory. Before 2015 the original Ley 37/1992 redaction read
# "exceda en un 20 por 100" with no "o más", so that twenty-percent margin must
# be passed rather than merely reached.
_ESPECIAL_MANDATORY_CASES = (
    # Keyed by the resolved bundle rather than by year: the predicate no longer
    # decides a margin from a filing year, it applies the one it is handed.
    # The exclusive rows prove it honours the other comparison shape too, and
    # are NOT a claim about what any particular ejercicio's law says.
    ("inclusive", Decimal("110.01"), Decimal("100.00"), True),
    ("inclusive", Decimal("110.00"), Decimal("100.00"), True),
    ("inclusive", Decimal("109.99"), Decimal("100.00"), False),
    ("inclusive", Decimal("100.00"), Decimal("100.00"), False),
    ("exclusive", Decimal("110.01"), Decimal("100.00"), True),
    ("exclusive", Decimal("110.00"), Decimal("100.00"), False),
    ("exclusive", Decimal("109.99"), Decimal("100.00"), False),
    # A zero especial deduction is exceeded without bound under either shape.
    ("inclusive", Decimal("50.00"), Decimal("0.00"), True),
    ("exclusive", Decimal("50.00"), Decimal("0.00"), True),
    ("inclusive", Decimal("0.00"), Decimal("0.00"), False),
    ("exclusive", Decimal("0.00"), Decimal("0.00"), False),
)

_ACCEPTED_PRORRATA_REFERENCE_CASES = (
    (
        "prorrata:2026:provisional:general",
        ProrrataKind.PROVISIONAL,
        ProrrataRegime.GENERAL,
        None,
    ),
    (
        "prorrata:2026:definitiva:especial:sector-retail",
        ProrrataKind.DEFINITIVA,
        ProrrataRegime.ESPECIAL,
        "sector-retail",
    ),
)

_INVALID_SECTOR_ID_CASES = (
    ("", "empty id"),
    ("has spaces and unicode ñ", "bad pattern"),
)


# ---------------------------------------------------------------------------
# Identity / boundary tests — anchored in the LIVA formula's mathematical
# extremes, not in author-computed arithmetic.
# ---------------------------------------------------------------------------


def test_general_percentage_is_100_when_all_operations_grant_right() -> None:
    """LIVA art. 104.Dos identity: ratio = total / total = 100%."""

    inputs = ProrrataInputs(
        operaciones_con_derecho_deduccion=Decimal("100000"),
        operaciones_sin_derecho_deduccion=Decimal("0"),
    )
    result = compute_prorrata_general(
        inputs,
        year=2026,
        kind=ProrrataKind.DEFINITIVA,
    )
    assert result.percentage == Decimal("100")
    assert result.regime is ProrrataRegime.GENERAL
    assert result.kind is ProrrataKind.DEFINITIVA
    assert result.inputs == inputs


def test_general_percentage_is_zero_when_no_operations_grant_right() -> None:
    """LIVA art. 104.Dos identity: ratio = 0 / total = 0%."""

    inputs = ProrrataInputs(
        operaciones_con_derecho_deduccion=Decimal("0"),
        operaciones_sin_derecho_deduccion=Decimal("50000"),
    )
    result = compute_prorrata_general(
        inputs,
        year=2026,
        kind=ProrrataKind.DEFINITIVA,
    )
    assert result.percentage == Decimal("0")


def test_general_percentage_aeat_manual_practico_iva_worked_example() -> None:
    """AEAT Manual Práctico IVA recurring worked example.

    A taxable person reports total annual operations of 100,000 €, of
    which 30,000 € correspond to exempt operations without the right to
    deduct. The manual states the prorrata percentage is 70%
    (= 70,000 / 100,000). This test verifies the substrate produces the
    same 70% value the AEAT manual publishes for those inputs.
    """

    inputs = ProrrataInputs(
        operaciones_con_derecho_deduccion=Decimal("70000"),
        operaciones_sin_derecho_deduccion=Decimal("30000"),
    )
    result = compute_prorrata_general(
        inputs,
        year=2026,
        kind=ProrrataKind.DEFINITIVA,
    )
    assert result.percentage == Decimal("70")


def test_general_percentage_zero_total_defaults_to_100() -> None:
    """Division-by-zero defence: when the taxpayer has no operations in
    the year the substrate returns 100% (the long-standing AEAT
    administrative criterion that the taxpayer may not lose the right to
    deduct in a no-operations year)."""

    inputs = ProrrataInputs(
        operaciones_con_derecho_deduccion=Decimal("0"),
        operaciones_sin_derecho_deduccion=Decimal("0"),
    )
    result = compute_prorrata_general(
        inputs,
        year=2026,
        kind=ProrrataKind.DEFINITIVA,
    )
    assert result.percentage == Decimal("100")


# ---------------------------------------------------------------------------
# ROUND_CEILING contract — anchored in TJUE C-488/07 (Royal Bank of Scotland)
# and the closing paragraph of LIVA art. 104.Dos.
# ---------------------------------------------------------------------------


def test_general_percentage_rounds_up_when_fraction_exceeds_whole() -> None:
    """LIVA art. 104.Dos: any fraction above a whole integer rounds UP.

    Inputs producing exactly 76.0001% must yield 77%, not 76%. This is
    the TJUE C-488/07 (Royal Bank of Scotland) rounding-up obligation
    transposed by AEAT and tested here as the implementation contract.
    """

    # 7,600,001 / 10,000,000 = 76.00001%, well below 77% mathematically
    # but above the whole-integer floor of 76 — therefore rounded up.
    inputs = ProrrataInputs(
        operaciones_con_derecho_deduccion=Decimal("7600001"),
        operaciones_sin_derecho_deduccion=Decimal("2399999"),
    )
    result = compute_prorrata_general(
        inputs,
        year=2026,
        kind=ProrrataKind.DEFINITIVA,
    )
    assert result.percentage == Decimal("77")


def test_general_percentage_does_not_round_up_exact_whole_integer() -> None:
    """A ratio that is already an exact whole percentage stays as-is.

    ``ROUND_CEILING`` only rounds up when there is a fractional part.
    25,000 / 50,000 = 50.000% exactly, so the result must be 50, not 51.
    """

    inputs = ProrrataInputs(
        operaciones_con_derecho_deduccion=Decimal("25000"),
        operaciones_sin_derecho_deduccion=Decimal("25000"),
    )
    result = compute_prorrata_general(
        inputs,
        year=2026,
        kind=ProrrataKind.DEFINITIVA,
    )
    assert result.percentage == Decimal("50")


# ---------------------------------------------------------------------------
# Per-input classification under art. 106.Uno LIVA.
# ---------------------------------------------------------------------------


def test_classify_input_deduction_cases() -> None:
    """LIVA art. 106.Uno classification rules for exclusive and common inputs."""

    for case in _INPUT_DEDUCTION_CASES:
        classification, input_iva_amount, general_percentage, expected_percentage, expected_amount = case
        deduction = classify_input_deduction(
            classification,
            input_iva_amount=input_iva_amount,
            general_percentage=general_percentage,
        )
        assert deduction.deductible_percentage == expected_percentage, classification
        assert deduction.deductible_amount == expected_amount, classification


# ---------------------------------------------------------------------------
# Especial-mandatory threshold (LIVA art. 103.Dos.2.º).
# ---------------------------------------------------------------------------


def _params(comparison: str, year: int = 2025) -> ProrrataEspecialMandatoryParameters:
    """A bundle carrying a ten-point margin with the named comparison, for ``year``.

    The rule now refuses a bundle resolved for a different filing year, so the
    year is a parameter rather than a fixed 2025.
    """
    return ProrrataEspecialMandatoryParameters(
        margin_percentage=Decimal("10"),
        comparison=ThresholdComparison(comparison),
        modelo_id="303",
        revision_id="2025",
        resolved_on=_esp_date(year, 12, 31),
    )


def test_especial_mandatory_cases() -> None:
    """The predicate applies the margin AND the comparison direction it is handed."""
    for comparison, general_deduction, especial_deduction, expected in _ESPECIAL_MANDATORY_CASES:
        assert (
            is_especial_mandatory(
                general_deduction,
                especial_deduction,
                year=2025,
                parameters=_params(comparison),
            )
            is expected
        ), (comparison, general_deduction, especial_deduction)


def test_especial_mandatory_ten_percent_margin_is_inclusive_from_2015() -> None:
    """Ley 28/2014 art. 1.26 reads "exceda en un 10 por ciento o más", so the margin is reached, not passed.

    A general-regime deduction of exactly 110 against an especial-regime
    deduction of 100 exceeds it by exactly ten percent. "O más" includes that
    boundary, so the especial regime is mandatory. The immediately-below case
    (109.99, a 9.99 percent excess) must stay outside it, so the assertion
    cannot be satisfied by a predicate that simply answers ``True``.
    """
    assert is_especial_mandatory(Decimal("110.00"), Decimal("100.00"), year=2026, parameters=_params("inclusive", 2026)) is True
    assert is_especial_mandatory(Decimal("109.99"), Decimal("100.00"), year=2026, parameters=_params("inclusive", 2026)) is False


def test_an_exclusive_margin_must_be_passed_not_merely_reached() -> None:
    """The comparison direction is load-bearing, so both shapes are exercised.

    This replaces a test that asserted the repealed pre-2015 twenty-percent
    redaction. That redaction is declared nowhere in this tree -- no modelo 303
    revision covers a pre-2015 filing year and the consolidated corpus carries
    only the text in force -- so asserting it here would be a legal claim with
    no citable authority behind it. What survives, and is what the predicate is
    actually responsible for, is that an exclusive bundle and an inclusive one
    disagree at exactly the boundary.
    """
    on_the_margin, especial = Decimal("110.00"), Decimal("100.00")
    assert is_especial_mandatory(on_the_margin, especial, year=2025, parameters=_params("exclusive")) is False
    assert is_especial_mandatory(on_the_margin, especial, year=2025, parameters=_params("inclusive")) is True


def test_especial_mandatory_rule_reports_the_margin_the_predicate_applied() -> None:
    """The margin an operator message quotes is the one the bundle carried.

    Probed with a figure that is deliberately NOT the shipped one, so a rule
    that ignored its bundle and reinstated a hardcoded margin would fail.
    """
    arbitrary = ProrrataEspecialMandatoryParameters(
        margin_percentage=Decimal("37"),
        comparison=ThresholdComparison.EXCLUSIVE,
        modelo_id="303",
        revision_id="2025",
        resolved_on=_esp_date(2025, 12, 31),
    )
    rule = especial_mandatory_rule(2025, parameters=arbitrary)
    assert (rule.year, rule.multiple, rule.margin_percentage, rule.inclusive) == (
        2025,
        Decimal("1.37"),
        Decimal("37"),
        False,
    )


def test_is_especial_mandatory_rejects_negative_amounts() -> None:
    with pytest.raises(ProrrataInputError, match=r"deduction amounts must be non-negative"):
        is_especial_mandatory(Decimal("-1"), Decimal("100"), year=2026, parameters=_ESPECIAL_PARAMS)
    with pytest.raises(ProrrataInputError, match=r"deduction amounts must be non-negative"):
        is_especial_mandatory(Decimal("100"), Decimal("-1"), year=2026, parameters=_ESPECIAL_PARAMS)


def test_is_especial_mandatory_rejects_out_of_range_year() -> None:
    """The year selects the applicable redaction, so an unsupported year refuses rather than guessing one."""
    with pytest.raises(ProrrataInputError, match=r"year out of supported range"):
        is_especial_mandatory(Decimal("200"), Decimal("100"), year=1999, parameters=_ESPECIAL_PARAMS)
    with pytest.raises(ProrrataInputError, match=r"year out of supported range"):
        especial_mandatory_rule(2101, parameters=_ESPECIAL_PARAMS)


# ---------------------------------------------------------------------------
# Sectoral separation (LIVA art. 9.1.c).
# ---------------------------------------------------------------------------


def _sector(sector_id: str, *, con_derecho: str, sin_derecho: str) -> ProrrataSector:
    return ProrrataSector(
        sector_id=sector_id,
        name=f"sector-{sector_id}",
        inputs=ProrrataInputs(
            operaciones_con_derecho_deduccion=Decimal(con_derecho),
            operaciones_sin_derecho_deduccion=Decimal(sin_derecho),
        ),
    )


def test_sectoral_separation_required_when_spread_exceeds_50_points() -> None:
    """LIVA art. 9.1.c: sectoral separation required when general
    prorratas across sectors differ by more than 50 percentage points."""

    # Sector A: 95% deductible operations → general prorrata 95%.
    # Sector B: 20% deductible operations → general prorrata 20%.
    # Spread: 75 points, well above the 50-point threshold.
    sectors = (
        _sector("A", con_derecho="95000", sin_derecho="5000"),
        _sector("B", con_derecho="20000", sin_derecho="80000"),
    )
    assert requires_sectoral_separation(sectors) is True


def test_sectoral_separation_not_required_when_spread_at_or_below_50_points() -> None:
    """LIVA art. 9.1.c boundary at exactly 50 points: not required.

    Sector A: 100% deductible → general 100%.
    Sector B: 50% deductible → general 50%.
    Spread: exactly 50 points → not required (rule is "more than 50").
    """

    sectors = (
        _sector("A", con_derecho="100000", sin_derecho="0"),
        _sector("B", con_derecho="50000", sin_derecho="50000"),
    )
    assert requires_sectoral_separation(sectors) is False


def test_sectoral_separation_returns_false_for_single_sector() -> None:
    sectors = (_sector("only", con_derecho="100", sin_derecho="0"),)
    assert requires_sectoral_separation(sectors) is False


def test_sectoral_separation_returns_false_for_empty_sector_list() -> None:
    assert requires_sectoral_separation(()) is False


def test_sectoral_separation_rejects_duplicate_sector_ids() -> None:
    sectors = (
        _sector("duplicate", con_derecho="100", sin_derecho="0"),
        _sector("duplicate", con_derecho="50", sin_derecho="50"),
    )
    with pytest.raises(ProrrataSectorError, match=r"duplicate sector_id"):
        requires_sectoral_separation(sectors)


def test_compute_sectoral_prorrata_produces_one_result_per_sector() -> None:
    sectors = (
        _sector("retail", con_derecho="800000", sin_derecho="200000"),
        _sector("rental", con_derecho="0", sin_derecho="100000"),
    )
    results = compute_sectoral_prorrata(
        sectors,
        year=2026,
        kind=ProrrataKind.DEFINITIVA,
    )
    assert len(results) == len(sectors)
    assert tuple(r.sector_id for r in results) == ("retail", "rental")
    # Retail: 800,000 / 1,000,000 = 80% exact → 80.
    # Rental: 0 / 100,000 = 0% → 0.
    assert results[0].percentage == Decimal("80")
    assert results[1].percentage == Decimal("0")
    assert all(r.regime is ProrrataRegime.GENERAL for r in results)


def test_compute_sectoral_prorrata_rejects_empty_input() -> None:
    with pytest.raises(ProrrataSectorError, match=r"sectors sequence must not be empty"):
        compute_sectoral_prorrata((), year=2026, kind=ProrrataKind.DEFINITIVA)


# ---------------------------------------------------------------------------
# Schema / validation / error-path tests.
# ---------------------------------------------------------------------------


def test_inputs_rejects_negative_amounts() -> None:
    with pytest.raises(ValidationError, match=r"greater than or equal to 0"):
        ProrrataInputs(
            operaciones_con_derecho_deduccion=Decimal("-1"),
            operaciones_sin_derecho_deduccion=Decimal("0"),
        )
    with pytest.raises(ValidationError, match=r"greater than or equal to 0"):
        ProrrataInputs(
            operaciones_con_derecho_deduccion=Decimal("0"),
            operaciones_sin_derecho_deduccion=Decimal("-1"),
        )


def test_inputs_is_frozen_and_forbids_extras() -> None:
    inputs = ProrrataInputs(
        operaciones_con_derecho_deduccion=Decimal("100"),
        operaciones_sin_derecho_deduccion=Decimal("50"),
    )
    with pytest.raises(ValidationError, match=r"frozen"):
        inputs.operaciones_con_derecho_deduccion = Decimal("0")
    with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
        extra_kwargs: dict[str, object] = {"unexpected_field": Decimal("1")}
        ProrrataInputs.model_validate(
            {
                "operaciones_con_derecho_deduccion": Decimal("100"),
                "operaciones_sin_derecho_deduccion": Decimal("50"),
                **extra_kwargs,
            },
        )


def test_result_provisional_requires_period() -> None:
    inputs = ProrrataInputs(
        operaciones_con_derecho_deduccion=Decimal("100"),
        operaciones_sin_derecho_deduccion=Decimal("0"),
    )
    with pytest.raises(ValidationError, match=r"provisional prorrata result must carry a period"):
        ProrrataResult(
            regime=ProrrataRegime.GENERAL,
            kind=ProrrataKind.PROVISIONAL,
            percentage=Decimal("100"),
            inputs=inputs,
            year=2026,
            period=None,
        )


def test_result_definitiva_rejects_non_annual_period() -> None:
    inputs = ProrrataInputs(
        operaciones_con_derecho_deduccion=Decimal("100"),
        operaciones_sin_derecho_deduccion=Decimal("0"),
    )
    with pytest.raises(ValidationError, match=r"definitiva prorrata result period must be 'annual' or omitted"):
        ProrrataResult(
            regime=ProrrataRegime.GENERAL,
            kind=ProrrataKind.DEFINITIVA,
            percentage=Decimal("100"),
            inputs=inputs,
            year=2026,
            period="Q1",
        )


def test_validate_prorrata_reference_accepts_canonical_values() -> None:
    for reference_id, expected_kind, expected_regime, expected_sector_id in _ACCEPTED_PRORRATA_REFERENCE_CASES:
        reference = validate_prorrata_reference(reference_id)

        assert isinstance(reference, ProrrataReference)
        assert reference.reference_id == reference_id
        assert reference.year == 2026
        assert reference.kind is expected_kind
        assert reference.regime is expected_regime
        assert reference.sector_id == expected_sector_id


def test_validate_prorrata_reference_rejects_usage_ratio_and_malformed_values() -> None:
    for reference_id in (
        "telefonia_movil",
        "usage_ratio:telefonia_movil",
        "prorrata:1999:provisional:general",
        "prorrata:2026:usage_ratio_personal:general",
        "prorrata:2026:provisional:usage_ratio_personal",
        "prorrata:2026:provisional:general:sector with spaces",
    ):
        with pytest.raises(ProrrataInputError):
            validate_prorrata_reference(reference_id)


def test_prorrata_reference_schema_rejects_noncanonical_payload() -> None:
    with pytest.raises(ValidationError, match=r"does not match canonical"):
        ProrrataReference(
            reference_id="prorrata:2026:definitiva:general",
            year=2026,
            kind=ProrrataKind.PROVISIONAL,
            regime=ProrrataRegime.GENERAL,
        )


def test_compute_general_rejects_year_out_of_range() -> None:
    inputs = ProrrataInputs(
        operaciones_con_derecho_deduccion=Decimal("100"),
        operaciones_sin_derecho_deduccion=Decimal("0"),
    )
    with pytest.raises(ProrrataInputError, match=r"year out of supported range 2000..2100"):
        compute_prorrata_general(inputs, year=1999, kind=ProrrataKind.DEFINITIVA)
    with pytest.raises(ProrrataInputError, match=r"year out of supported range 2000..2100"):
        compute_prorrata_general(inputs, year=2101, kind=ProrrataKind.DEFINITIVA)


def test_compute_general_rejects_invalid_period_with_prorrata_error() -> None:
    inputs = ProrrataInputs(
        operaciones_con_derecho_deduccion=Decimal("100"),
        operaciones_sin_derecho_deduccion=Decimal("0"),
    )

    with pytest.raises(ProrrataInputError, match=r"invalid prorrata result window"):
        compute_prorrata_general(
            inputs,
            year=2026,
            kind=ProrrataKind.DEFINITIVA,
            period="Q1",
        )


def test_classify_input_rejects_negative_iva_amount() -> None:
    with pytest.raises(ProrrataInputError, match=r"input_iva_amount must be non-negative"):
        classify_input_deduction(
            InputClassification.COMMON,
            input_iva_amount=Decimal("-1.00"),
            general_percentage=Decimal("50"),
        )


def test_classify_input_rejects_out_of_range_general_percentage() -> None:
    with pytest.raises(ProrrataInputError, match=r"general_percentage out of range 0..100"):
        classify_input_deduction(
            InputClassification.COMMON,
            input_iva_amount=Decimal("10.00"),
            general_percentage=Decimal("-1"),
        )
    with pytest.raises(ProrrataInputError, match=r"general_percentage out of range 0..100"):
        classify_input_deduction(
            InputClassification.COMMON,
            input_iva_amount=Decimal("10.00"),
            general_percentage=Decimal("101"),
        )


def test_sector_rejects_invalid_sector_ids() -> None:
    for sector_id, name in _INVALID_SECTOR_ID_CASES:
        with pytest.raises(ValidationError, match=r"sector_id"):
            ProrrataSector(
                sector_id=sector_id,
                name=name,
                inputs=ProrrataInputs(
                    operaciones_con_derecho_deduccion=Decimal("100"),
                    operaciones_sin_derecho_deduccion=Decimal("0"),
                ),
            )


# ---------------------------------------------------------------------------
# Aggregation helper (sum_deductible_amounts) — Python primitive contract.
# ---------------------------------------------------------------------------


def test_sum_deductible_amounts_threads_through_decimal_addition() -> None:
    """The helper is a thin wrapper around ``sum``; this test verifies
    the Python primitive contract (Decimal preservation, empty-iterable
    handling) rather than re-applying the prorrata formula."""

    deductions = (
        ProrrataInputDeduction(
            classification=InputClassification.EXCLUSIVELY_DEDUCTIBLE,
            input_iva_amount=Decimal("10.00"),
            deductible_percentage=Decimal("100"),
            deductible_amount=Decimal("10.00"),
        ),
        ProrrataInputDeduction(
            classification=InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE,
            input_iva_amount=Decimal("5.00"),
            deductible_percentage=Decimal("0"),
            deductible_amount=Decimal("0.00"),
        ),
        ProrrataInputDeduction(
            classification=InputClassification.COMMON,
            input_iva_amount=Decimal("20.00"),
            deductible_percentage=Decimal("70"),
            deductible_amount=Decimal("14.00"),
        ),
    )
    total = sum_deductible_amounts(deductions)
    assert isinstance(total, Decimal)
    assert total == Decimal("24.00")


def test_sum_deductible_amounts_returns_zero_for_empty_iterable() -> None:
    total = sum_deductible_amounts(())
    assert total == Decimal("0")
    assert isinstance(total, Decimal)


# ---------------------------------------------------------------------------
# Boundary / non-existence assertions.
#
# The IVA-prorrata domain substrate is the unique owner of prorrata logic.
# These tests assert the boundary contract: no shadow duplicates, no shim
# translating usage_ratios into prorrata, no parallel CLI surface. They
# regress-protect the rollout against future "convenience" wrappers that
# would re-introduce the rejected shapes.
# ---------------------------------------------------------------------------


def test_no_parallel_prorrata_implementation_exists() -> None:
    """Only ``cadrumo.domain.iva.prorrata`` owns prorrata semantics.

    Walk the source tree and assert that ``compute_prorrata_general``,
    ``classify_input_deduction``, ``is_especial_mandatory``, and
    ``requires_sectoral_separation`` exist exclusively in the canonical
    module. Any other module declaring a function with the same name is
    a duplicate implementation and must be removed before this test
    re-passes.
    """

    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    source_root = repo_root / "src" / "cadrumo"
    canonical_module = source_root / "domain" / "iva" / "prorrata.py"

    canonical_symbols = (
        "compute_prorrata_general",
        "classify_input_deduction",
        "is_especial_mandatory",
        "requires_sectoral_separation",
        "compute_sectoral_prorrata",
    )

    for py_file in scan_directory(source_root, pattern="*.py", recursive=True):
        if py_file == canonical_module:
            continue
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for symbol in canonical_symbols:
            assert f"def {symbol}" not in text, (
                f"shadow prorrata implementation detected: "
                f"{py_file} defines `def {symbol}`; the canonical "
                f"owner is `cadrumo.domain.iva.prorrata`."
            )


def test_no_usage_ratios_to_prorrata_shim_exists() -> None:
    """``domain.usage_ratios`` and ``cadrumo.domain.iva.prorrata`` are
    distinct concepts. No module may translate usage-ratios values into
    prorrata percentages: usage-ratios is the proportional-expense
    allocation surface (LIRPF deductibility), prorrata is the LIVA
    deduction mechanism. Bridging them in the same module is a
    structural shim and is rejected here.
    """

    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    source_root = repo_root / "src" / "cadrumo"

    forbidden_patterns = (
        # An import that pulls both modules together is a structural
        # signal that the importer is about to bridge them.
        ("from cadrumo.domain.usage_ratios", "ProrrataInputs"),
        ("from cadrumo.domain.usage_ratios", "ProrrataResult"),
        ("from ...domain.usage_ratios", "ProrrataInputs"),
        ("from ...domain.usage_ratios", "ProrrataResult"),
        ("from ..usage_ratios", "ProrrataInputs"),
        ("from ..usage_ratios", "ProrrataResult"),
    )

    for py_file in scan_directory(source_root, pattern="*.py", recursive=True):
        # Test files may legitimately reference both module names while
        # asserting boundary contracts (this very test does so).
        if py_file.name.startswith("test_"):
            continue
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for first, second in forbidden_patterns:
            assert not (first in text and second in text), (
                f"shim detected: {py_file} imports both "
                f"`{first}` and `{second}`. "
                f"usage_ratios is proportional-expense allocation; "
                f"prorrata is the legal LIVA arts. 101-103 deduction "
                f"mechanism. They MUST NOT be bridged."
            )


def test_no_parallel_prorrata_cli_surface_exists() -> None:
    """No ``aeat ... prorrata`` CLI verb survives.

    The canonical operator path for prorrata is `aeat app modelo bindings
    list --modelo 303` (or 390) which surfaces a "prorrata percentage
    missing" readiness category. A standalone `app prorrata`,
    `app ledger prorrata`, or `app modelo prorrata` verb would create a
    parallel surface for a value that already has a binding-level entry
    point and must not appear in the entrypoints CLI tree.
    """

    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    cli_root = repo_root / "src" / "cadrumo" / "entrypoints" / "cli"

    forbidden_command_decorations = (
        '@app.command("prorrata"',
        '@app_app.command("prorrata"',
        '.command(name="prorrata"',
        # Add typer sub-app registration spelled `prorrata` as the name.
        ".add_typer(_prorrata",
        "add_typer(prorrata_module",
        'name="prorrata"',
    )

    for py_file in scan_directory(cli_root, pattern="*.py", recursive=True):
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden_command_decorations:
            assert needle not in text, (
                f"rejected prorrata CLI surface detected in {py_file}: "
                f"`{needle}`. Prorrata is consumed via "
                f"`app modelo bindings list`."
            )
