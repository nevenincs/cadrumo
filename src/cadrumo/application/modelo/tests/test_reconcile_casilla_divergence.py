"""Real-behavior tests for the casilla-level divergence-detection framework.

These lock the pure ``detect_casilla_divergences`` contract in isolation from
any registry snapshot, work unit, or parsed declaración: a computed mapping and
a filed mapping in, a typed, deterministic divergence tuple out. The
``modelo_reconcile`` integration (which wires this framework to a real registry
snapshot and a persisted revision for Modelo 130) is covered separately in
``test_reconcile_declaracion_casillas.py``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._reconcile_casilla import (
    CasillaDivergenceKind,
    detect_casilla_divergences,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_matching_casillas_produce_no_divergences() -> None:
    computed = {"01": Decimal("1000.00"), "03": Decimal("500.00")}
    filed = {"01": Decimal("1000.00"), "03": Decimal("500.00")}

    divergences = detect_casilla_divergences(computed=computed, filed=filed)

    assert divergences == ()


def test_value_mismatch_is_detected_with_signed_delta() -> None:
    """A casilla present on both sides but with different values is a
    VALUE_MISMATCH carrying the signed filed-minus-computed delta."""
    computed = {"19": Decimal("900.00")}
    filed = {"19": Decimal("950.00")}

    divergences = detect_casilla_divergences(computed=computed, filed=filed)

    assert len(divergences) == 1
    divergence = divergences[0]
    assert divergence.casilla_id == "19"
    assert divergence.kind is CasillaDivergenceKind.VALUE_MISMATCH
    assert divergence.computed_value == Decimal("900.00")
    assert divergence.filed_value == Decimal("950.00")
    assert divergence.delta == Decimal("50.00")


def test_missing_in_filed_is_detected_when_computed_carries_a_value() -> None:
    """The computed revision resolved casilla 19 but the filed declaración omitted it."""
    computed = {"19": Decimal("900.00")}
    filed: dict[str, Decimal] = {}

    divergences = detect_casilla_divergences(computed=computed, filed=filed)

    assert len(divergences) == 1
    divergence = divergences[0]
    assert divergence.casilla_id == "19"
    assert divergence.kind is CasillaDivergenceKind.MISSING_IN_FILED
    assert divergence.computed_value == Decimal("900.00")
    assert divergence.filed_value is None
    assert divergence.delta is None


def test_extra_in_filed_is_detected_when_filed_carries_a_value() -> None:
    """The filed declaración printed casilla 19 but the computed revision never resolved it."""
    computed: dict[str, Decimal] = {}
    filed = {"19": Decimal("900.00")}

    divergences = detect_casilla_divergences(computed=computed, filed=filed)

    assert len(divergences) == 1
    divergence = divergences[0]
    assert divergence.casilla_id == "19"
    assert divergence.kind is CasillaDivergenceKind.EXTRA_IN_FILED
    assert divergence.computed_value is None
    assert divergence.filed_value == Decimal("900.00")
    assert divergence.delta is None


def test_divergence_within_tolerance_is_not_flagged() -> None:
    computed = {"19": Decimal("900.00")}
    filed = {"19": Decimal("900.01")}

    divergences = detect_casilla_divergences(computed=computed, filed=filed, tolerance=Decimal("0.01"))

    assert divergences == ()


def test_divergence_outside_tolerance_is_flagged() -> None:
    computed = {"19": Decimal("900.00")}
    filed = {"19": Decimal("900.02")}

    divergences = detect_casilla_divergences(computed=computed, filed=filed, tolerance=Decimal("0.01"))

    assert len(divergences) == 1
    assert divergences[0].kind is CasillaDivergenceKind.VALUE_MISMATCH


def test_scope_restricts_comparison_to_declared_casillas() -> None:
    """A casilla the scope does not declare never surfaces a divergence, even
    when the two sides disagree on it — the registry's own reconciliation
    scope, not an ad hoc union of both sides' keys, decides what is compared."""
    computed = {"01": Decimal("1000.00"), "99": Decimal("1.00")}
    filed = {"01": Decimal("1000.00"), "99": Decimal("999.00")}

    divergences = detect_casilla_divergences(
        computed=computed,
        filed=filed,
        scope={"01": None},
    )

    assert divergences == ()


def test_scope_still_flags_missing_when_computed_declares_a_scoped_casilla() -> None:
    computed = {"01": Decimal("1000.00")}
    filed: dict[str, Decimal] = {}

    divergences = detect_casilla_divergences(
        computed=computed,
        filed=filed,
        scope={"01": None},
    )

    assert len(divergences) == 1
    assert divergences[0].kind is CasillaDivergenceKind.MISSING_IN_FILED


def test_multiple_divergences_are_ordered_by_casilla_id() -> None:
    computed = {"19": Decimal("900.00"), "01": Decimal("1000.00")}
    filed = {"19": Decimal("950.00"), "01": Decimal("1100.00")}

    divergences = detect_casilla_divergences(computed=computed, filed=filed)

    assert [d.casilla_id for d in divergences] == ["01", "19"]


def test_empty_inputs_produce_no_divergences() -> None:
    assert detect_casilla_divergences(computed={}, filed={}) == ()
