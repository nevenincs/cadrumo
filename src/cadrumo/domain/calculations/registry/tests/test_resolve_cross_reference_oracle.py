"""Tests for ``resolve_cross_reference_oracle``.

The resolver is the single gate between a registry-level oracle binding
and the runtime catalogue. It must:

- raise when no binding is declared on the cross-reference,
- name the cross-reference id alongside the oracle id in every error,
- delegate environment-mismatch and unknown-oracle decisions to the
  catalogue while re-framing the resulting message.
"""

from __future__ import annotations

import pytest
from dev.registry.maintenance_support import LiveParityCatalogue, OracleEnvironment, collect_orphan_oracle_ids

from .....tests.aeat_nif_iva_oracle import ORACLE_ID, AeatNifIvaCheckerOracle
from .....tests.groi_oracle import GROI_ORACLE_ID, GroiOracle
from ..schema_verification import LiveCrossReferenceDecision, ProfilePredicateDefinition
from ._registry_schema_support import _committed_registry_tree
from ._remote_guard_support import AEAT_WRITE_FORBIDDEN_ACTIONS

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _catalogue_with_production_oracle() -> LiveParityCatalogue:
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)
    return catalogue


def _catalogue_with_test_environment_oracle() -> LiveParityCatalogue:
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.TEST_ENVIRONMENT)
    return catalogue


def _gated_decision() -> LiveCrossReferenceDecision:
    """A LiveCrossReferenceDecision with an applicability predicate gating it."""

    return LiveCrossReferenceDecision(
        id="modelo-349-nif-iva-check",
        evidence_tier="executable_parity_evidence",
        surface="open_simulator",
        guard_policy_id="modelo-349-nif-iva-check-policy",
        allowed_hosts=("ec.europa.eu",),
        allowed_methods=("GET",),
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=("orden-eha-769-2010:art-1",),
        source_refs=("aeat-modelo-349-procedure",),
        oracle_id=ORACLE_ID,
        applicability_predicates=(
            ProfilePredicateDefinition(
                field="does_intracomunitario",
                op="equals",
                value=True,
                explanation="NIF-IVA check applies only to intracom subjects.",
                legal_refs=("orden-eha-769-2010:art-1",),
                source_refs=("aeat-modelo-349-procedure",),
            ),
        ),
    )


def test_orphan_oracle_collector_flags_unbound_catalogue_entries() -> None:
    """Catalogue entries with no cross-reference binding surface as orphans.

    Test against an empty modelo list so every registered oracle is
    by definition unbound. This isolates the collector's set-difference
    logic from whichever oracle happens to be bound today; today both
    NIF-IVA and GROI are bound by Modelo 349.
    """

    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)
    catalogue.register(GroiOracle(), environment=OracleEnvironment.PRODUCTION)

    orphans = collect_orphan_oracle_ids([], catalogue)

    assert set(orphans) == {ORACLE_ID, GROI_ORACLE_ID}
    assert orphans == tuple(sorted(orphans)), "orphans must be alphabetically sorted"


def test_orphan_oracle_collector_returns_empty_when_every_oracle_is_bound() -> None:
    """When every catalogue oracle is referenced by some cross-reference,
    the collector returns an empty tuple. Today the production registry
    binds both NIF-IVA (Modelo 349 IXVI) and GROI (Modelo 349 GROI), so
    a catalogue containing both produces no orphans."""

    modelos, _ = _committed_registry_tree()
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)
    catalogue.register(GroiOracle(), environment=OracleEnvironment.PRODUCTION)

    orphans = collect_orphan_oracle_ids(modelos, catalogue)

    assert orphans == ()
