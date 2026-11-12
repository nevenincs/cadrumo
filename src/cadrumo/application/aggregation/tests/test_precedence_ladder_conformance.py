"""Conformance: the caller-override guard sets are the declared precedence ladder.

The calculate-path caller-override precedence ladder is declared once as
ordered tier data, ``CALLER_OVERRIDE_PRECEDENCE_LADDER`` in
:mod:`cadrumo.application.aggregation.source_mesh`. The two caller-override guard
invocations in the calculate orchestrator consume the lock / carry source sets
exported by :mod:`cadrumo.application.modelo.calculation_source_policy`, which are
DERIVED from that declaration via :func:`precedence_ladder_sources`.

This gate binds the guard's sets to the declaration so the two cannot silently
diverge: if the policy re-hand-lists a set, or the ladder's tier membership
drifts from the frozen aggregation-taxonomy behaviour, one of these assertions
fails. The frozen memberships asserted here are the aggregation-taxonomy
behaviour this suite preserves (the deterministic ledger, invoice, inventory,
and annual-summary resolvers are LOCK; the carry sources — previous_filing, relation_prefill,
iva-compensation annual partition, and prorrata regularizacion — are CARRY);
they are the behavioural anchor, not a restatement of the ladder literal.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import validated_casilla_id
from ....domain.modelos.source_disagreement import SourceDisagreementRole
from ...modelo.action_errors import ModeloAggregationBindingError
from ...modelo.calculation_source_guards import reject_caller_overrides_of_source_bindings
from ...modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES, CALLER_OVERRIDABLE_CARRY_SOURCES
from ...modelo.edit_admission import permitted_binding_entry
from ...modelo.edit_models import ModeloEditNonWritableBindingOverrideSurfaceEntryV1, ModeloEditNonWritableReason
from ..source_mesh import CalculationSourceResolution
from ..source_precedence import (
    CALLER_OVERRIDE_PRECEDENCE_LADDER,
    PRECEDENCE_OVERLAY_ORDER,
    CallerOverrideDisposition,
    precedence_ladder_sources,
)
from ..source_resolution_operations import PrecedenceTier, merge_source_resolutions_by_precedence

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_lock_policy_set_is_derived_from_the_ladder() -> None:
    """The policy LOCK set is exactly the union of the ladder's LOCK-disposition tiers."""
    assert precedence_ladder_sources(CallerOverrideDisposition.LOCK) == BUCKET_AGGREGATION_LOCK_SOURCES


def test_carry_policy_set_is_derived_from_the_ladder() -> None:
    """The policy CARRY set is exactly the union of the ladder's CARRY-disposition tiers."""
    assert precedence_ladder_sources(CallerOverrideDisposition.CARRY) == CALLER_OVERRIDABLE_CARRY_SOURCES


def test_lock_and_carry_dispositions_are_disjoint() -> None:
    """No source kind may be both caller-locked and caller-overridable-carry."""
    assert not (BUCKET_AGGREGATION_LOCK_SOURCES & CALLER_OVERRIDABLE_CARRY_SOURCES)


def test_ladder_is_ordered_named_and_covers_both_dispositions() -> None:
    """The ladder is a non-empty ordered tuple with unique tier names spanning both dispositions."""
    assert isinstance(CALLER_OVERRIDE_PRECEDENCE_LADDER, tuple)
    assert CALLER_OVERRIDE_PRECEDENCE_LADDER  # non-empty
    names = [tier.name for tier in CALLER_OVERRIDE_PRECEDENCE_LADDER]
    assert len(names) == len(set(names)), f"tier names must be unique, got {names}"
    dispositions = {tier.disposition for tier in CALLER_OVERRIDE_PRECEDENCE_LADDER}
    assert dispositions == {CallerOverrideDisposition.LOCK, CallerOverrideDisposition.CARRY}
    # Every tier carries at least one source kind, all valid members.
    for tier in CALLER_OVERRIDE_PRECEDENCE_LADDER:
        assert tier.source_kinds, f"tier {tier.name!r} declares no source kinds"
        assert tier.source_kinds <= set(BindingSourceKind)


def test_frozen_disposition_membership_matches_aggregation_taxonomy() -> None:
    """Behavioural anchor: the LOCK / CARRY memberships are the frozen sets.

    Deterministic bucket-owned resolvers (ledger aggregations, invoice
    families, inventory projection, let-property rows and annual summary) are caller-locked; carry sources are
    caller-overridable. A membership change here is behavioural drift, not a
    representation change, and must be a conscious, reviewed decision rather
    than an accidental edit.
    """
    assert (
        frozenset(
            {
                BindingSourceKind.LEDGER_IVA_AGGREGATION,
                BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
                BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
                BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
                BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
                BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,
                BindingSourceKind.LEDGER_OSS_AGGREGATION,
                BindingSourceKind.COLLECTIBLE_INVOICE,
                BindingSourceKind.PAYABLE_INVOICE,
                BindingSourceKind.M347_THIRD_PARTY_OPERATION,
                BindingSourceKind.M349_INTRACOMMUNITY_OPERATION,
                BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY,
                BindingSourceKind.INVENTORY,
                BindingSourceKind.RENTA_INMUEBLE,
                BindingSourceKind.RETENCION_SOPORTADA,
            },
        )
        == BUCKET_AGGREGATION_LOCK_SOURCES
    )
    assert (
        frozenset(
            {
                BindingSourceKind.ACTIVITY_ASSET_DISPOSAL,
                BindingSourceKind.PREVIOUS_FILING,
                BindingSourceKind.RELATION_PREFILL,
                BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION,
                BindingSourceKind.PRORRATA_REGULARIZACION,
            },
        )
        == CALLER_OVERRIDABLE_CARRY_SOURCES
    )


def _m100_revision():
    return published_snapshot("100", filing_year=newest_authored_edition("100"), period="0A").revision


@pytest.mark.usefixtures("operation")
def test_a_caller_cannot_state_a_suffered_withholding_credit_before_the_mesh_runs() -> None:
    """The payer records own casilla 0596: neither its binding nor the box takes a caller value."""
    revision = _m100_revision()
    with pytest.raises(ModeloAggregationBindingError):
        reject_caller_overrides_of_source_bindings(
            revision=revision,
            owned_sources=BUCKET_AGGREGATION_LOCK_SOURCES,
            caller_binding_values={"renta-retencion-soportada-trabajo": Decimal("1.00")},
            caller_casilla_inputs={},
            subject_leaf_key="modelo.work.calculate",
        )
    with pytest.raises(ModeloAggregationBindingError):
        reject_caller_overrides_of_source_bindings(
            revision=revision,
            owned_sources=BUCKET_AGGREGATION_LOCK_SOURCES,
            caller_binding_values={},
            caller_casilla_inputs={validated_casilla_id("0596"): Decimal("1.00")},
            subject_leaf_key="modelo.work.calculate",
        )


@pytest.mark.usefixtures("operation")
def test_the_editor_reports_a_suffered_withholding_binding_as_source_locked() -> None:
    """The edit surface reads the same ladder, so the override is locked, not undecided."""
    revision = _m100_revision()
    binding = next(item for item in revision.bindings if item.id == "renta-retencion-soportada-trabajo")

    entry = permitted_binding_entry(binding, revision=revision, period="0A", row_filled=frozenset())

    assert isinstance(entry, ModeloEditNonWritableBindingOverrideSurfaceEntryV1)
    assert entry.reason is ModeloEditNonWritableReason.SOURCE_LOCKED


def test_overlay_order_is_profile_then_backend_then_borrador_then_caller() -> None:
    """The overlay order the screen admits is the ladder's later-tier-wins order, stated independently here."""
    assert [role.value for role in PRECEDENCE_OVERLAY_ORDER] == ["profile", "backend", "borrador", "caller"]


def test_a_caller_override_of_a_carry_source_reaches_the_overlay_as_the_caller_tier_over_the_backend() -> None:
    """A CARRY source lets the caller through the guard, and the overlay then compares the two values."""
    carried = "test-previous-filing-carry"
    assert BindingSourceKind.PREVIOUS_FILING in precedence_ladder_sources(CallerOverrideDisposition.CARRY)
    overlay = merge_source_resolutions_by_precedence(
        (
            PrecedenceTier(
                role=SourceDisagreementRole.BACKEND,
                resolution=CalculationSourceResolution(
                    resolver_id="previous_filing", binding_values={carried: Decimal("10")}
                ),
                source_family=BindingSourceKind.PREVIOUS_FILING.value,
            ),
            PrecedenceTier(
                role=SourceDisagreementRole.CALLER,
                resolution=CalculationSourceResolution(resolver_id="caller", binding_values={carried: Decimal("12")}),
                source_family="operator_input",
            ),
        )
    )

    (divergence,) = overlay.divergences
    assert divergence.selected_role is SourceDisagreementRole.CALLER
    assert [source.source_family for source in divergence.sources] == ["previous_filing", "operator_input"]
