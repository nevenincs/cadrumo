"""Code-only closure gate for live authored and operator-action coverage.

This gate composes the production authorities for authored actions, live
precondition observations, and CLI action-census closure.  It intentionally reads
neither process-history artefacts nor human planning records: all inputs are the
current source tree, the canonical action catalogue, the resolved live operator
surface, and the checked-in disposition ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from cadrumo.application.modelo._preconditions import (
    MODELO_PRECONDITION_PROFILES,
    build_modelo_precondition_failure_for_scenario,
)
from cadrumo.application.operator_actions import OPERATOR_ACTION_CATALOGUE, ActionCatalogue
from cadrumo.application.operator_surface import (
    ManifestActionResolution,
    OperatorSurfaceContractError,
    resolve_manifest_action_profiles,
)
from cadrumo.core import ActionEvidenceProvenance
from cadrumo.entrypoints.cli import current_operator_surface_reconciliation

from ..agent_eval._action_coverage import LeafConditionScenario, leaf_condition_scenario_matrix
from ..agent_eval._models import ObservedProductionActionAssertion, observe_production_action
from ..quality.cli_action_census import (
    AuthoredErrorMessageJoin,
    authored_error_message_join,
    current_action_alias_discoveries,
    current_census,
)
from ..quality.cli_action_census_dispositions import (
    DEFAULT_DISPOSITIONS_PATH,
    AuthoredMessageExclusion,
    CandidateDisposition,
    DispositionValidationError,
    load_authored_message_exclusions,
    load_dispositions,
    validate_authored_error_message_join,
    validate_dispositions,
    validate_exception_override_owners,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True, slots=True)
class _LiveClosureInputs:
    """The source-derived inputs consumed by the closure assertion."""

    dispositions: tuple[CandidateDisposition, ...]
    authored_join: AuthoredErrorMessageJoin
    authored_exclusions: tuple[AuthoredMessageExclusion, ...]
    resolution: ManifestActionResolution
    observations: tuple[ObservedProductionActionAssertion, ...]


def _live_resolution() -> ManifestActionResolution:
    """Resolve the sole production profile catalogue against the live CLI surface."""
    return resolve_manifest_action_profiles(
        profiles=MODELO_PRECONDITION_PROFILES,
        catalogue=OPERATOR_ACTION_CATALOGUE,
        reconciliation=current_operator_surface_reconciliation(),
    )


def _observe_live_profile(coverage: LeafConditionScenario) -> ObservedProductionActionAssertion:
    """Build and observe one application verdict without scenario-owned action data."""
    resolved_action = coverage.profile.resolved_action
    action_argument_values = (
        None
        if resolved_action is None
        else {
            specification.argument_name: f"s47-observation-{specification.argument_name}"
            for specification in resolved_action.declaration.argument_specifications
        }
    )
    verdict = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=coverage.subject_leaf_key,
        scenario_id=coverage.scenario_id,
        evidence_id="action_coverage_closure.production_observation",
        evidence_values={"scenario": coverage.scenario_id},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        action_argument_values=action_argument_values,
    ).verdict
    return observe_production_action(coverage, verdict)


def _assert_resolved_actions(resolution: ManifestActionResolution) -> None:
    """Require every catalogue target and every profile outcome to stay resolvable."""
    assert resolution.catalogue_actions, "the canonical operator action catalogue resolved no live actions"
    assert resolution.profiles, "the production precondition profile set resolved no live outcomes"

    for action in resolution.catalogue_actions:
        target = action.target_leaf
        assert target.result_schema is not None, f"{action.action_id} lacks a live result-schema proof"
        assert target.input_schema is not None, f"{action.action_id} lacks a live input-schema proof"
        required_inputs = frozenset(target.input_schema.required_input_names)
        declared_inputs = frozenset(
            specification.argument_name for specification in action.declaration.argument_specifications
        )
        assert required_inputs <= declared_inputs, (
            f"{action.action_id} has insufficient catalogue bindings for {action.target_command_key}: "
            f"missing {sorted(required_inputs - declared_inputs)}"
        )

    for profile in resolution.profiles:
        declaration = profile.declaration
        if declaration.action is None:
            assert declaration.no_recovery_outcome is not None, (
                f"{declaration.identity} has neither an action nor an explicit no-recovery outcome"
            )
            assert profile.resolved_action is None, f"{declaration.identity} resolved an undeclared action"
            continue
        assert profile.resolved_action is not None, f"{declaration.identity} has an unresolved action"
        assert profile.resolved_action.action_id == declaration.action.action_id, (
            f"{declaration.identity} resolved {profile.resolved_action.action_id}, not {declaration.action.action_id}"
        )


def _assert_complete_observation_proofs(
    matrix: tuple[LeafConditionScenario, ...],
    observations: tuple[ObservedProductionActionAssertion, ...],
) -> None:
    """Require exactly one successful observation per live declaration."""
    declared = tuple(coverage.identity for coverage in matrix)
    observed = tuple(assertion.leaf_condition_scenario for assertion in observations)

    assert len(declared) == len(set(declared)), "resolved production matrix contains duplicate identities"
    assert len(observed) == len(set(observed)), "production observation proofs contain duplicate identities"
    assert set(observed) == set(declared), (
        f"production observation proof mismatch: missing={sorted(set(declared) - set(observed))}; "
        f"undeclared={sorted(set(observed) - set(declared))}"
    )
    assert all(assertion.passed for assertion in observations), "a production observation contradicts its live profile"


def _assert_code_only_closure(inputs: _LiveClosureInputs) -> None:
    """Reject unclassified sites, unresolved actions, weak bindings, and unproven observations."""
    candidates = current_census()
    assert validate_dispositions(candidates, inputs.dispositions) == inputs.dispositions
    assert validate_exception_override_owners(inputs.dispositions) == ()
    assert current_action_alias_discoveries(aliases=frozenset({"next_action"})) == ()

    partition = validate_authored_error_message_join(inputs.authored_join, inputs.authored_exclusions)
    assert len(partition.clean_codes) + len(partition.owned_sites) + len(partition.excluded_sites) > 0

    _assert_resolved_actions(inputs.resolution)
    matrix = leaf_condition_scenario_matrix(inputs.resolution).rows
    _assert_complete_observation_proofs(matrix, inputs.observations)


@pytest.fixture(scope="module")
def live_closure_inputs() -> _LiveClosureInputs:
    """Materialise the live closure denominator once without an alternate fixture authority."""
    resolution = _live_resolution()
    matrix = leaf_condition_scenario_matrix(resolution).rows
    return _LiveClosureInputs(
        dispositions=load_dispositions(DEFAULT_DISPOSITIONS_PATH),
        authored_join=authored_error_message_join(),
        authored_exclusions=load_authored_message_exclusions(DEFAULT_DISPOSITIONS_PATH),
        resolution=resolution,
        observations=tuple(_observe_live_profile(coverage) for coverage in matrix),
    )


def test_action_coverage_closure_is_complete_against_live_code(
    live_closure_inputs: _LiveClosureInputs,
) -> None:
    """The current source tree has no unclassified authored or operator-action residue."""
    _assert_code_only_closure(live_closure_inputs)


def test_action_coverage_closure_rejects_unclassified_or_ungrounded_action_sites(
    live_closure_inputs: _LiveClosureInputs,
) -> None:
    """Mutating either ledger arm proves no action site can bypass review grounding."""
    with pytest.raises(DispositionValidationError, match="missing disposition for current census candidate"):
        validate_dispositions(current_census(), live_closure_inputs.dispositions[1:])

    excluded = next(row for row in live_closure_inputs.dispositions if row.exclusion is not None)
    ungrounded = replace(excluded, reason="", exclusion=None)
    rows = tuple(ungrounded if row == excluded else row for row in live_closure_inputs.dispositions)
    with pytest.raises(DispositionValidationError, match="requires symbol and enclosing_function grounding"):
        validate_dispositions(current_census(), rows)


def test_action_coverage_closure_rejects_unclassified_authored_site(
    live_closure_inputs: _LiveClosureInputs,
) -> None:
    """Removing a registered owner cannot be hidden by the broad authored-message scan."""
    owned = next(site for site in live_closure_inputs.authored_join.sites if site.owner_qualnames)
    orphaned = replace(owned, owner_qualnames=())
    mutated_join = replace(
        live_closure_inputs.authored_join,
        sites=tuple(orphaned if site == owned else site for site in live_closure_inputs.authored_join.sites),
    )

    with pytest.raises(DispositionValidationError, match="exclusions instead of one"):
        validate_authored_error_message_join(mutated_join, live_closure_inputs.authored_exclusions)


def test_action_coverage_closure_rejects_unresolved_action_and_insufficient_bindings(
    live_closure_inputs: _LiveClosureInputs,
) -> None:
    """The live resolver refuses a dead target and a required input with no catalogue source."""
    resolved = next(
        action
        for action in live_closure_inputs.resolution.catalogue_actions
        if action.target_leaf.input_schema is not None
        and action.target_leaf.input_schema.required_input_names
        and action.declaration.argument_specifications
    )
    insufficient = resolved.declaration.model_copy(update={"argument_specifications": ()})
    unresolved = resolved.declaration.model_copy(update={"target_command_key": "operator.unresolved.action"})

    insufficient_catalogue = ActionCatalogue(
        entries=tuple(
            insufficient if entry == resolved.declaration else entry for entry in OPERATOR_ACTION_CATALOGUE.entries
        ),
    )
    unresolved_catalogue = ActionCatalogue(
        entries=tuple(
            unresolved if entry == resolved.declaration else entry for entry in OPERATOR_ACTION_CATALOGUE.entries
        ),
    )
    reconciliation = current_operator_surface_reconciliation()

    with pytest.raises(ValueError, match="insufficient action argument specifications"):
        resolve_manifest_action_profiles(
            profiles=MODELO_PRECONDITION_PROFILES,
            catalogue=insufficient_catalogue,
            reconciliation=reconciliation,
        )
    with pytest.raises(OperatorSurfaceContractError, match="orphan action target command identity"):
        resolve_manifest_action_profiles(
            profiles=MODELO_PRECONDITION_PROFILES,
            catalogue=unresolved_catalogue,
            reconciliation=reconciliation,
        )


def test_action_coverage_closure_rejects_a_missing_production_observation_proof(
    live_closure_inputs: _LiveClosureInputs,
) -> None:
    """The bijection fails if any resolved production profile lacks an observation."""
    matrix = leaf_condition_scenario_matrix(live_closure_inputs.resolution).rows

    with pytest.raises(AssertionError, match="production observation proof mismatch"):
        _assert_complete_observation_proofs(matrix, live_closure_inputs.observations[1:])
