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

from ..aeat_nif_iva_oracle import ORACLE_ID, AeatNifIvaCheckerOracle
from ..errors import RegistryValidationError
from ..groi_oracle import GROI_ORACLE_ID, GroiOracle
from ..live_parity import (
    LiveParityCatalogue,
    LiveParityOracle,
    OracleEnvironment,
    collect_orphan_oracle_ids,
    resolve_cross_reference_oracle,
)
from ..remote_state_guard import AEAT_WRITE_FORBIDDEN_ACTIONS
from ..schema_verification import LiveCrossReferenceDecision, ProfilePredicateDefinition
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _catalogue_with_production_oracle() -> LiveParityCatalogue:
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)
    return catalogue


def _catalogue_with_test_environment_oracle() -> LiveParityCatalogue:
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.TEST_ENVIRONMENT)
    return catalogue


def test_resolves_registered_oracle_under_matching_environment() -> None:
    catalogue = _catalogue_with_production_oracle()

    resolved = resolve_cross_reference_oracle(
        cross_reference_id="modelo-130-static-official",
        oracle_id=ORACLE_ID,
        catalogue=catalogue,
        environment=OracleEnvironment.PRODUCTION,
    )

    assert isinstance(resolved, LiveParityOracle)
    assert resolved.oracle_id == ORACLE_ID


def test_raises_when_cross_reference_has_no_binding() -> None:
    catalogue = _catalogue_with_production_oracle()

    with pytest.raises(RegistryValidationError, match="has no oracle binding to resolve"):
        resolve_cross_reference_oracle(
            cross_reference_id="modelo-130-static-official",
            oracle_id=None,
            catalogue=catalogue,
            environment=OracleEnvironment.PRODUCTION,
        )


def test_unknown_oracle_error_names_cross_reference_and_oracle() -> None:
    catalogue = LiveParityCatalogue()  # empty

    with pytest.raises(RegistryValidationError, match=r"oracle|cross-reference|applicable") as exc_info:
        resolve_cross_reference_oracle(
            cross_reference_id="modelo-349-nif-iva-check",
            oracle_id="aeat-nif-iva-checker",
            catalogue=catalogue,
            environment=OracleEnvironment.PRODUCTION,
        )

    message = str(exc_info.value)
    assert "modelo-349-nif-iva-check" in message
    assert "aeat-nif-iva-checker" in message


def test_environment_mismatch_error_names_cross_reference_and_oracle() -> None:
    catalogue = _catalogue_with_test_environment_oracle()

    with pytest.raises(RegistryValidationError, match=r"oracle|cross-reference|applicable") as exc_info:
        resolve_cross_reference_oracle(
            cross_reference_id="modelo-100-test-only-binding",
            oracle_id=ORACLE_ID,
            catalogue=catalogue,
            environment=OracleEnvironment.PRODUCTION,
        )

    message = str(exc_info.value)
    assert "modelo-100-test-only-binding" in message
    assert ORACLE_ID in message
    assert "test_environment" in message


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


def test_resolver_passes_when_applicability_gate_satisfied() -> None:
    """When decision + profile_facts are supplied AND the gate passes,
    the resolver behaves identically to the legacy catalogue-only path."""

    catalogue = _catalogue_with_production_oracle()
    decision = _gated_decision()

    resolved = resolve_cross_reference_oracle(
        cross_reference_id=decision.id,
        oracle_id=ORACLE_ID,
        catalogue=catalogue,
        environment=OracleEnvironment.PRODUCTION,
        decision=decision,
        profile_facts={"does_intracomunitario": True},
    )

    assert resolved.oracle_id == ORACLE_ID


def test_resolver_raises_when_applicability_gate_says_not_applicable() -> None:
    """When the profile fails the predicate the resolver raises a typed
    error naming the unmet predicate fields, BEFORE any catalogue lookup."""

    catalogue = _catalogue_with_production_oracle()
    decision = _gated_decision()

    with pytest.raises(RegistryValidationError, match=r"oracle|cross-reference|applicable") as exc_info:
        resolve_cross_reference_oracle(
            cross_reference_id=decision.id,
            oracle_id=ORACLE_ID,
            catalogue=catalogue,
            environment=OracleEnvironment.PRODUCTION,
            decision=decision,
            profile_facts={"does_intracomunitario": False},
        )

    message = str(exc_info.value)
    assert decision.id in message
    assert "not applicable" in message
    assert "does_intracomunitario" in message


def test_resolver_ignores_applicability_gate_when_decision_or_profile_omitted() -> None:
    """Callers that don't thread profile facts resolve through the
    catalogue without any applicability check; the gate is opt-in."""

    catalogue = _catalogue_with_production_oracle()
    decision = _gated_decision()  # has applicability_predicates declared

    # No decision/profile_facts supplied -> gate is skipped
    resolved = resolve_cross_reference_oracle(
        cross_reference_id=decision.id,
        oracle_id=ORACLE_ID,
        catalogue=catalogue,
        environment=OracleEnvironment.PRODUCTION,
    )

    assert resolved.oracle_id == ORACLE_ID


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


def test_dual_environment_oracle_resolves_under_either_environment() -> None:
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.BOTH)

    production = resolve_cross_reference_oracle(
        cross_reference_id="xref",
        oracle_id=ORACLE_ID,
        catalogue=catalogue,
        environment=OracleEnvironment.PRODUCTION,
    )
    test_env = resolve_cross_reference_oracle(
        cross_reference_id="xref",
        oracle_id=ORACLE_ID,
        catalogue=catalogue,
        environment=OracleEnvironment.TEST_ENVIRONMENT,
    )

    assert production.oracle_id == ORACLE_ID
    assert test_env.oracle_id == ORACLE_ID
