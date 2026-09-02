"""One fold owns the reconciliation-total axis, and it refuses ambiguity.

Three surfaces need "which casilla is this revision's ingresar/devolver total":
the verification policy, the filing subview and the result summary. Each used to
open-code its own loop over the expectations, and the three did not agree on
what to do when two expectations named the same kind — two kept the first, one
kept the last. Nothing in the committed registry exercises that difference
today, which is exactly why it was worth closing: the divergence was latent, and
a latent divergence surfaces as two surfaces disagreeing about a filing's
result casilla rather than as an error.

The fold refuses the ambiguity instead of resolving it. The other folded axes
have a defensible ordering — union for a set, strictest for a tolerance — but
there is no stricter of two casilla ids, so any tie-break would be an invention.
"""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ..errors import RegistryValidationError
from ..schema_base import SettlementDirection
from ..schema_verification import (
    DiscrepancyCause,
    VerificationExpectationDefinition,
    fold_reconciliation_total_casilla_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL = ("ley-37-1992:art-1",)
_SOURCE = ("aeat-dr-303-2026",)


def _expectation(
    identifier: str,
    totals: dict[SettlementDirection, str],
    *,
    computed: tuple[str, ...] = ("01",),
) -> VerificationExpectationDefinition:
    """Build one expectation declaring ``totals``; only that axis varies."""
    return VerificationExpectationDefinition(
        id=identifier,
        computed_casilla_ids=tuple(validated_casilla_id(value, surface="computed_casilla_ids") for value in computed),
        reconciliation_total_casilla_ids={
            kind: validated_casilla_id(value, surface="reconciliation_total_casilla_ids")
            for kind, value in totals.items()
        },
        tolerance="0.01",
        rounding="money-2",
        min_coverage="1",
        discrepancy_causes=(DiscrepancyCause.ROUNDING,),
        legal_refs=_LEGAL,
        source_refs=_SOURCE,
    )


def test_totals_from_several_expectations_merge_into_one_mapping() -> None:
    """The fold is a union across expectations, not a pick of one."""
    folded = fold_reconciliation_total_casilla_ids(
        (
            _expectation("e1", {SettlementDirection.INGRESAR: "15"}),
            _expectation("e2", {SettlementDirection.DEVOLVER: "16"}),
        ),
    )

    assert dict(folded) == {SettlementDirection.DEVOLVER: "16", SettlementDirection.INGRESAR: "15"}


def test_the_same_casilla_declared_twice_is_not_a_conflict() -> None:
    """Repetition is harmless; only disagreement is a fault."""
    folded = fold_reconciliation_total_casilla_ids(
        (
            _expectation("e1", {SettlementDirection.INGRESAR: "15"}),
            _expectation("e2", {SettlementDirection.INGRESAR: "15"}),
        ),
    )

    assert dict(folded) == {SettlementDirection.INGRESAR: "15"}


def test_conflicting_totals_for_one_kind_are_refused() -> None:
    """Two expectations naming different casillas for one kind must not fold silently.

    This is the case the three open-coded loops answered differently. Whichever
    tie-break the fold adopted would have made one surface's answer authoritative
    by accident, so it raises and names both sides.
    """
    with pytest.raises(RegistryValidationError) as exc_info:
        fold_reconciliation_total_casilla_ids(
            (
                _expectation("e1", {SettlementDirection.INGRESAR: "15"}),
                _expectation("e2", {SettlementDirection.INGRESAR: "99"}),
            ),
        )

    message = str(exc_info.value)
    assert "ingresar" in message
    assert "15" in message
    assert "99" in message


def test_no_expectations_folds_to_an_empty_mapping() -> None:
    """An empty fold is a legitimate answer, not an error.

    The subview and the result summary both call this on revisions that may
    declare no expectations at all, so raising here would convert a normal state
    into a failure on two surfaces.
    """
    assert dict(fold_reconciliation_total_casilla_ids(())) == {}


def test_the_fold_is_ordered_so_two_surfaces_cannot_differ_by_iteration() -> None:
    """Deterministic key order: the subview serialises this mapping."""
    folded = fold_reconciliation_total_casilla_ids(
        (
            _expectation("e1", {SettlementDirection.INGRESAR: "15"}),
            _expectation("e2", {SettlementDirection.DEVOLVER: "16"}),
        ),
    )

    assert list(folded) == sorted(folded)
