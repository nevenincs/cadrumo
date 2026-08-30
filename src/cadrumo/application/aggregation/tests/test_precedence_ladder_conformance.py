"""Conformance: the caller-override guard sets are the declared precedence ladder.

The calculate-path caller-override precedence ladder is declared once as
ordered tier data, ``CALLER_OVERRIDE_PRECEDENCE_LADDER`` in
:mod:`cadrumo.application.aggregation._source_mesh`. The two caller-override guard
invocations in the calculate orchestrator consume the lock / carry source sets
exported by :mod:`cadrumo.application.modelo._calculation_source_policy`, which are
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

import pytest

from ....core.aggregation import BindingSourceKind
from ...modelo._calculation_source_policy import (
    BUCKET_AGGREGATION_LOCK_SOURCES,
    CALLER_OVERRIDABLE_CARRY_SOURCES,
)
from .._source_mesh import (
    CALLER_OVERRIDE_PRECEDENCE_LADDER,
    CallerOverrideDisposition,
    precedence_ladder_sources,
)

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
    families, inventory projection, and annual summary) are caller-locked; carry sources are
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
                BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY,
                BindingSourceKind.INVENTORY,
            },
        )
        == BUCKET_AGGREGATION_LOCK_SOURCES
    )
    assert (
        frozenset(
            {
                BindingSourceKind.PREVIOUS_FILING,
                BindingSourceKind.RELATION_PREFILL,
                BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION,
                BindingSourceKind.PRORRATA_REGULARIZACION,
            },
        )
        == CALLER_OVERRIDABLE_CARRY_SOURCES
    )
