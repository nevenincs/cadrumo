"""Previous-filing target-relative expanding-span selector grammar.

Covers the Modelo 130 casilla-05 carry primitive added by the
modelo-130-pagos-fraccionados-carry plan (P01): a target-relative
prior-quarter expanding span that emits every same-ejercicio quarter
strictly preceding the target into the existing multi-anchor sum path,
plus the per-anchor positive-part aggregation the casilla-05 identity
requires.

The expected anchor sets are enumerated by hand per target quarter (an
INDEPENDENT enumeration), never derived from the span function under test,
per no-tautological-calculation-tests.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .._bindings_previous_filing import (
    _aggregate_previous_filing_binding,
    _is_direct_previous_filing_binding,
    _PreviousModeloSelector,
)
from .._errors import RegistryValidationError
from .._schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DUMMY_LEGAL_ID = "rd-439-2007:art-110"
_DUMMY_SOURCE_ID = "aeat-modelo-130-instructions"


def _span_selector() -> _PreviousModeloSelector:
    return _PreviousModeloSelector.model_validate(
        {
            "source_modelo": "130",
            "source_casillas": ("07",),
            "prior_quarter_expanding_span": True,
            "max_year_delta": 0,
        },
    )


def _span_binding(*, source_casillas: tuple[str, ...]) -> DataBindingDefinition:
    return DataBindingDefinition(
        id="modelo-130-test-span-binding",
        source="previous_filing",
        selector={
            "source_modelo": "130",
            "source_casillas": tuple(source_casillas),
            "prior_quarter_expanding_span": True,
            "max_year_delta": 0,
        },
        aggregation={"op": "sum"},
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )


# Independently enumerated expected anchor sets (hand-written per target
# quarter from the AEAT "trimestres anteriores del mismo ejercicio" rule),
# NOT derived from the span function under test.
_EXPECTED_SPAN_ANCHORS: dict[str, tuple[tuple[int, str], ...]] = {
    "1T": (),
    "2T": ((0, "1T"),),
    "3T": ((0, "1T"), (0, "2T")),
    "4T": ((0, "1T"), (0, "2T"), (0, "3T")),
}


@pytest.mark.parametrize("target_period", ["1T", "2T", "3T", "4T"])
def test_expanding_span_emits_independently_enumerated_anchor_set(target_period: str) -> None:
    selector = _span_selector()
    assert selector.required_period_anchors_for_target(target_period) == _EXPECTED_SPAN_ANCHORS[target_period]


def test_expanding_span_first_quarter_is_empty() -> None:
    """1T has no same-ejercicio prior quarter; the span is empty (absent-by-design)."""
    assert _span_selector().required_period_anchors_for_target("1T") == ()


def test_expanding_span_classified_direct_previous_filing_binding() -> None:
    """The span carry stays a DIRECT previous_filing binding (source_casillas anchor).

    The relation-source collision gate (validate_slot_source_hygiene) and the
    requirement-derivation path both route through this predicate; the span mode
    must classify direct so it needs no carve-out.
    """
    binding = _span_binding(source_casillas=("07",))
    assert _is_direct_previous_filing_binding(binding) is True


def test_expanding_span_mutually_exclusive_with_offset() -> None:
    with pytest.raises(ValidationError, match="mutually exclusive"):
        _PreviousModeloSelector.model_validate(
            {
                "source_modelo": "130",
                "source_casillas": ("07",),
                "prior_quarter_expanding_span": True,
                "source_period_offset_from_target": -1,
            },
        )


def test_expanding_span_mutually_exclusive_with_source_periods() -> None:
    with pytest.raises(ValidationError, match="mutually exclusive"):
        _PreviousModeloSelector.model_validate(
            {
                "source_modelo": "130",
                "source_casillas": ("07",),
                "prior_quarter_expanding_span": True,
                "source_periods": ("1T", "2T"),
            },
        )


def test_expanding_span_rejects_non_quarterly_target() -> None:
    with pytest.raises(RegistryValidationError, match="only quarterly codes"):
        _span_selector().required_period_anchors_for_target("0A")


def _prior_pagos_binding() -> DataBindingDefinition:
    return DataBindingDefinition(
        id="modelo-130-pagos-fraccionados-anteriores",
        source="previous_filing",
        selector={
            "source_modelo": "130",
            "source_casillas": ("07", "16"),
            "prior_quarter_expanding_span": True,
            "max_year_delta": 0,
        },
        aggregation={"op": "prior_pagos_fraccionados"},
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )


def test_prior_pagos_fraccionados_op_computes_positive_07_minus_16() -> None:
    """casilla 05 = Σ max(0, 07_q) − Σ 16_q from per-anchor [07_q, 16_q] pairs.

    Three prior quarters (1T, 2T, 3T) for a 4T target. The expected value is
    computed in-test from the per-quarter inputs via the verbatim AEAT identity
    (positive-part per quarter, then minus the sum of casilla 16) - a different
    code path than the op under test, and the fixture is chosen so the identity
    (480) does NOT equal the raw-07 sum (450), so a binding that skipped the
    per-quarter max-0 OR dropped the minus-16 term fails loudly rather than
    coinciding.
    """
    binding = _prior_pagos_binding()
    # Per-quarter (07, 16) pairs. 2T is a loss (negative 07 -> contributes 0).
    quarters = (
        (Decimal("300"), Decimal("40")),
        (Decimal("-100"), Decimal("0")),
        (Decimal("250"), Decimal("30")),
    )
    flat_values = [value for pair in quarters for value in pair]
    expected = sum((max(Decimal("0"), c07) for c07, _c16 in quarters), Decimal("0")) - sum(
        (c16 for _c07, c16 in quarters), Decimal("0")
    )
    raw_07_sum = sum((c07 for c07, _c16 in quarters), Decimal("0"))
    assert expected != raw_07_sum, "fixture must make the identity differ from a raw-07 sum"

    result = _aggregate_previous_filing_binding(binding, flat_values, source_casillas=("07", "16"))
    assert result == expected


def test_prior_pagos_fraccionados_op_negative_07_contributes_zero_not_value() -> None:
    """Anti-regression: a single negative prior 07 must contribute 0, not its value.

    One prior quarter, 07=-500, 16=0. The identity gives max(0,-500) − 0 = 0.
    A raw sum would give -500, so a non-zero (negative) result fails loudly.
    """
    binding = _prior_pagos_binding()
    result = _aggregate_previous_filing_binding(
        binding,
        [Decimal("-500"), Decimal("0")],
        source_casillas=("07", "16"),
    )
    assert result == Decimal("0")


def test_prior_pagos_fraccionados_op_subtracts_nonzero_minoracion() -> None:
    """Anti-regression: a non-zero prior 16 is subtracted (minoración never dropped).

    One prior quarter, 07=+700, 16=120. Identity: 700 − 120 = 580.
    """
    binding = _prior_pagos_binding()
    result = _aggregate_previous_filing_binding(
        binding,
        [Decimal("700"), Decimal("120")],
        source_casillas=("07", "16"),
    )
    assert result == Decimal("580")


def test_prior_pagos_fraccionados_op_requires_two_source_casillas() -> None:
    binding = _prior_pagos_binding()
    with pytest.raises(RegistryValidationError, match="requires exactly two source casillas"):
        _aggregate_previous_filing_binding(binding, [Decimal("100")], source_casillas=("07",))
