"""The compare-taxation transport payload refuses what its canonical model refuses.

:class:`~cadrumo.application.modelo.TaxationComparisonResult` carries finite
``Decimal`` amounts, a closed :class:`TaxationRecommendation`, and an always-on
disclosure that the individual branch is faithful only for a single-earner
household. The transport payload had redeclared every amount as an unconstrained
``str`` and dropped the scope flag, so a machine-facing row could carry ``NaN``,
arbitrary text, an unknown recommendation, and no indication that the individual
figure does not apply to a two-earner couple.

These tests assert the payload's accepted-value set against the canonical model's
own constraints. They construct payloads directly rather than through the CLI,
because what is under test is what the transport model ACCEPTS -- a value the
happy path never produces is exactly the one a broken producer would.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....application.modelo.taxation_comparison import TaxationComparisonResult, TaxationRecommendation
from ....core.modelo import Modelo
from .._payloads_modelo_reconcile import WorkCompareTaxationResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CANONICAL_FIELDS = {
    "filing_year": 2025,
    "modelo": Modelo.M100,
    "revision": "2025-y-siguientes",
    "conjunta_cuota_resultante": "1200.00",
    "individual_cuota_resultante": "1500.00",
    "conjunta_resultado": "-300.00",
    "individual_resultado": "150.00",
    "delta_resultado": "450.00",
    "recommendation": TaxationRecommendation.CONJUNTA,
    "recommendation_reason": "conjunta is 450.00 EUR cheaper",
    "individual_branch_single_earner_only": True,
}


def _payload(**overrides: object) -> WorkCompareTaxationResult:
    return WorkCompareTaxationResult.model_validate({**_CANONICAL_FIELDS, **overrides})


def test_canonical_row_is_accepted() -> None:
    """Positive control: a well-formed row validates.

    Without it an all-refused result would look like a working guard while
    actually meaning the base fixture is broken.
    """
    payload = _payload()

    assert payload.recommendation is TaxationRecommendation.CONJUNTA
    assert payload.modelo is Modelo.M100
    assert payload.individual_branch_single_earner_only is True
    assert payload.delta_resultado == "450.00"


@pytest.mark.parametrize(
    "field",
    [
        "conjunta_cuota_resultante",
        "individual_cuota_resultante",
        "conjunta_resultado",
        "individual_resultado",
        "delta_resultado",
    ],
)
@pytest.mark.parametrize("bad_value", ["NaN", "Infinity", "-Infinity", "not-a-number", "", "1,200.00", "1e3"])
def test_non_canonical_amount_text_is_refused(field: str, bad_value: str) -> None:
    """Every amount refuses what the canonical Decimal field cannot represent.

    ``TaxationComparisonResult`` types these as ``Decimal``; pydantic refuses a
    non-finite there. The transport carries the rendered text, so the same
    refusal has to be asserted on the string.
    """
    with pytest.raises(ValidationError):
        _payload(**{field: bad_value})


def test_canonical_result_also_refuses_non_finite_amounts() -> None:
    """Cross-check: the refusal above mirrors the canonical model, not a local rule."""
    with pytest.raises(ValidationError):
        TaxationComparisonResult(
            filing_year=2025,
            revision="2025-y-siguientes",
            conjunta_cuota_resultante=Decimal("NaN"),
            individual_cuota_resultante=Decimal("1500.00"),
            conjunta_resultado=Decimal("-300.00"),
            individual_resultado=Decimal("150.00"),
            delta_resultado=Decimal("450.00"),
            recommendation=TaxationRecommendation.CONJUNTA,
            recommendation_reason="reason",
        )


def test_unknown_recommendation_is_refused() -> None:
    """Only the closed TaxationRecommendation set is transportable."""
    with pytest.raises(ValidationError):
        _payload(recommendation="bogus")


def test_every_canonical_recommendation_is_transportable() -> None:
    """Anti-tautology for the refusal above: the whole closed set is accepted."""
    for member in TaxationRecommendation:
        assert _payload(recommendation=member).recommendation is member


def test_out_of_range_filing_year_is_refused() -> None:
    """A filing year the canonical WorkUnit refuses cannot ride the transport."""
    with pytest.raises(ValidationError):
        _payload(filing_year=0)


def test_blank_revision_and_reason_are_refused() -> None:
    """Empty coordinates and an empty reason are not a comparison result."""
    with pytest.raises(ValidationError):
        _payload(revision="")
    with pytest.raises(ValidationError):
        _payload(recommendation_reason="")


def test_single_earner_scope_flag_is_required() -> None:
    """The scope flag has no default, so a producer cannot silently omit it.

    Defaulting it would let a two-earner-invalid figure travel as though its
    validity domain had been asserted.
    """
    without_flag = {k: v for k, v in _CANONICAL_FIELDS.items() if k != "individual_branch_single_earner_only"}

    with pytest.raises(ValidationError):
        WorkCompareTaxationResult.model_validate(without_flag)


def test_payload_covers_every_canonical_amount_and_scope_field() -> None:
    """No canonical amount, recommendation, or scope field is dropped in transport.

    The finding was a silent omission, so the guard is a set comparison rather
    than a spot check on the fields that happened to be remembered.
    """
    canonical = set(TaxationComparisonResult.model_fields)
    transported = set(WorkCompareTaxationResult.model_fields)
    # The caveat PROSE rides the envelope notices channel, not the result.
    expected_missing = {"individual_branch_caveat"}

    assert canonical - transported == expected_missing
