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
from typing import TYPE_CHECKING

import pytest

from .._reconcile_casilla import (
    CasillaDivergenceKind,
    detect_casilla_divergences,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from ....domain.calculations.registry.schema import ModeloRevision


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


class TestExportExemptCasillasAreOutOfPdfScope:
    """An export-exempt casilla files no slot, so a printed declaración cannot carry it.

    The reconcile path narrows ``computed_casilla_ids`` by this predicate before
    comparing. These tests pin the predicate's two directions against the live
    registry rather than a synthetic fixture, because the property being asserted
    is that the REAL enrolled set is reconcilable — a hand-built pair of casillas
    would prove the arithmetic and nothing about the registry.
    """

    @staticmethod
    def _m303_revision() -> ModeloRevision:
        # Resolved from (modelo, filing year, period) rather than indexed by a
        # literal revision id. AEAT re-cuts revision layouts -- this modelo's
        # a broad M303 revision was decomposed into four narrower revisions -- and
        # a literal key dies the moment that happens, on a test whose subject is
        # unrelated to the re-cut.
        from ....domain.calculations.registry.authority import bundled_authority

        return bundled_authority().snapshot("303", filing_year=2025, period="1T").revision

    def test_no_enrolled_casilla_is_both_exempt_and_extractable(self) -> None:
        """The predicate never excludes something the extractor can actually supply.

        This is the precision half: if an exempt casilla were extractable, the
        exclusion would silence an observable comparison.
        """
        revision = self._m303_revision()
        exempt = {c.id for c in revision.casillas if getattr(c, "export_exemption_reason", None) is not None}
        targets = {getattr(t, "casilla_id", None) or t for p in revision.extraction_profiles for t in p.target_casillas}

        assert exempt & targets == set(), (
            f"casillas are both export-exempt and extraction targets: {sorted(exempt & targets)}. "
            "The exclusion would drop an observable comparison."
        )

    def test_every_reconcilable_enrolled_casilla_is_extractable(self) -> None:
        """The completeness half: after excluding exempt ids, the scope is fully comparable.

        Precision alone would not prove the fix sufficient — it would still allow
        an enrolled, non-exempt casilla that no profile targets, which would go on
        raising MISSING_IN_FILED whatever the taxpayer filed.
        """
        revision = self._m303_revision()
        enrolled: set[str] = set()
        for expectation in revision.verification_expectations:
            enrolled |= set(getattr(expectation, "computed_casilla_ids", ()) or ())
        by_id = {c.id: c for c in revision.casillas}
        reconcilable = {c for c in enrolled if getattr(by_id.get(c), "export_exemption_reason", None) is None}
        targets = {getattr(t, "casilla_id", None) or t for p in revision.extraction_profiles for t in p.target_casillas}

        assert reconcilable - targets == set(), (
            f"enrolled and non-exempt but never extracted: {sorted(reconcilable - targets)}. "
            "These raise MISSING_IN_FILED regardless of what was filed."
        )
