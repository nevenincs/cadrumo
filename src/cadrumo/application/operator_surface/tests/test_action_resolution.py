"""Contract tests for canonical action-to-live-schema resolution."""

from __future__ import annotations

import pytest

from ....core import (
    ActionArgumentSource,
    NoRecoveryOutcome,
)
from ...operator_actions import (
    ActionArgumentBindingSpecification,
    ActionCatalogue,
    ActionCatalogueEntry,
    ActionReference,
)
from .. import ManifestActionProfile
from .._errors import OperatorSurfaceContractError
from .._manifest import (
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    OperatorSurfaceReconciliation,
    ReconciledOperatorLeaf,
    ResultSchemaInventoryRow,
    resolve_manifest_action_profiles,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _leaf(
    subject_leaf_key: str,
    *,
    required_inputs: tuple[str, ...] = (),
    cli_path: tuple[str, ...] | None = None,
    result_schema_key: str | None = None,
    input_schema_key: str | None = None,
    has_result_schema: bool = True,
    has_input_schema: bool = True,
) -> ReconciledOperatorLeaf:
    path = cli_path if cli_path is not None else tuple(subject_leaf_key.split("."))
    return ReconciledOperatorLeaf(
        live_leaf=LiveLeafInventoryRow(
            subject_leaf_key=subject_leaf_key,
            canonical_cli_path=path,
            provenance="resolved production command identity",
        ),
        result_schema=(
            ResultSchemaInventoryRow(
                subject_leaf_key=result_schema_key or subject_leaf_key,
                schema_name="ActionResolutionPayload",
                provenance="registered result schema",
            )
            if has_result_schema
            else None
        ),
        input_schema=(
            InputSchemaInventoryRow(
                subject_leaf_key=input_schema_key or subject_leaf_key,
                required_input_names=required_inputs,
                provenance="live required input schema",
            )
            if has_input_schema
            else None
        ),
        mounted_family=None,
        profile_policy=None,
        surface_exposure=None,
        exclusions=(),
    )


def _catalogue_entry(
    *,
    action_id: str = "operator.recovery.run",
    target_command_key: str = "app.recovery.run",
    inputs: tuple[str, ...] = ("subject_id",),
) -> ActionCatalogueEntry:
    return ActionCatalogueEntry(
        action_id=action_id,
        target_command_key=target_command_key,
        argument_specifications=tuple(
            ActionArgumentBindingSpecification(
                argument_name=input_name,
                source=ActionArgumentSource.REQUEST_CONTEXT,
                source_key=input_name,
            )
            for input_name in inputs
        ),
    )


def _reconciliation(*leaves: ReconciledOperatorLeaf) -> OperatorSurfaceReconciliation:
    return OperatorSurfaceReconciliation(leaves=leaves)


def test_profiles_resolve_exact_actions_and_preserve_typed_no_recovery() -> None:
    subject = _leaf("app.guard.run")
    target = _leaf("app.recovery.run", required_inputs=("subject_id",))
    catalogue = ActionCatalogue(entries=(_catalogue_entry(inputs=("subject_id", "optional_detail")),))
    actionable = ManifestActionProfile(
        subject_leaf_key="app.guard.run",
        condition_id="guard.subject.missing",
        scenario_id="scenario.subject.absent",
        action=ActionReference(action_id="operator.recovery.run"),
    )
    closed = ManifestActionProfile(
        subject_leaf_key="app.guard.run",
        condition_id="guard.operation.forbidden",
        scenario_id="scenario.safety.boundary",
        no_recovery_outcome=NoRecoveryOutcome.SAFETY,
    )

    resolution = resolve_manifest_action_profiles(
        profiles=(actionable, closed),
        catalogue=catalogue,
        reconciliation=_reconciliation(subject, target),
    )

    actionable_resolution = next(
        profile for profile in resolution.profiles if profile.declaration.identity == actionable.identity
    )
    assert actionable_resolution.subject_leaf is subject
    assert actionable_resolution.resolved_action is not None
    assert actionable_resolution.resolved_action.action_id == "operator.recovery.run"
    assert actionable_resolution.resolved_action.target_leaf is target
    assert resolution.action_for("operator.recovery.run") is actionable_resolution.resolved_action

    closed_resolution = next(
        profile for profile in resolution.profiles if profile.declaration.identity == closed.identity
    )
    assert closed_resolution.declaration.no_recovery_outcome is NoRecoveryOutcome.SAFETY
    assert closed_resolution.resolved_action is None


def test_every_catalogue_target_is_live_even_when_no_profile_references_it() -> None:
    live_entry = _catalogue_entry()
    dead_entry = _catalogue_entry(
        action_id="operator.recovery.ghost",
        target_command_key="app.recovery.ghost",
    )
    profile = ManifestActionProfile(
        subject_leaf_key="app.guard.run",
        condition_id="guard.subject.missing",
        scenario_id="scenario.subject.absent",
        action=ActionReference(action_id=live_entry.action_id),
    )

    with pytest.raises(OperatorSurfaceContractError, match="orphan action target command identity") as exc_info:
        resolve_manifest_action_profiles(
            profiles=(profile,),
            catalogue=ActionCatalogue(entries=(live_entry, dead_entry)),
            reconciliation=_reconciliation(
                _leaf("app.guard.run"),
                _leaf("app.recovery.run", required_inputs=("subject_id",)),
            ),
        )

    assert dead_entry.action_id in str(exc_info.value)
    assert dead_entry.target_command_key in str(exc_info.value)


def test_action_resolution_rejects_insufficient_required_input_sources() -> None:
    catalogue = ActionCatalogue(entries=(_catalogue_entry(inputs=("subject_id",)),))

    with pytest.raises(ValueError, match="insufficient action argument specifications") as exc_info:
        resolve_manifest_action_profiles(
            profiles=(),
            catalogue=catalogue,
            reconciliation=_reconciliation(
                _leaf("app.recovery.run", required_inputs=("subject_id", "confirmation")),
            ),
        )

    assert "confirmation" in str(exc_info.value)


@pytest.mark.parametrize(
    ("has_result_schema", "has_input_schema", "expected_surface"),
    [
        (False, True, "result"),
        (True, False, "input"),
    ],
)
def test_action_resolution_rejects_missing_target_schema_accounting(
    has_result_schema: bool,
    has_input_schema: bool,
    expected_surface: str,
) -> None:
    with pytest.raises(ValueError, match=rf"action target lacks {expected_surface} schema accounting"):
        resolve_manifest_action_profiles(
            profiles=(),
            catalogue=ActionCatalogue(entries=(_catalogue_entry(),)),
            reconciliation=_reconciliation(
                _leaf(
                    "app.recovery.run",
                    required_inputs=("subject_id",),
                    has_result_schema=has_result_schema,
                    has_input_schema=has_input_schema,
                ),
            ),
        )


def test_action_resolution_rejects_unknown_action_and_orphan_subject_identities() -> None:
    catalogue = ActionCatalogue(entries=(_catalogue_entry(),))
    reconciliation = _reconciliation(
        _leaf("app.guard.run"),
        _leaf("app.recovery.run", required_inputs=("subject_id",)),
    )
    unknown_action = ManifestActionProfile(
        subject_leaf_key="app.guard.run",
        condition_id="guard.subject.missing",
        scenario_id="scenario.subject.absent",
        action=ActionReference(action_id="operator.recovery.unknown"),
    )
    with pytest.raises(OperatorSurfaceContractError, match="unknown manifest action-profile action identity"):
        resolve_manifest_action_profiles(
            profiles=(unknown_action,),
            catalogue=catalogue,
            reconciliation=reconciliation,
        )

    orphan_subject = ManifestActionProfile(
        subject_leaf_key="app.guard.ghost",
        condition_id="guard.subject.missing",
        scenario_id="scenario.subject.absent",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    )
    with pytest.raises(OperatorSurfaceContractError, match="orphan manifest action-profile subject identity"):
        resolve_manifest_action_profiles(
            profiles=(orphan_subject,),
            catalogue=catalogue,
            reconciliation=reconciliation,
        )


def test_action_resolution_rejects_duplicate_profile_and_ambiguous_live_identities() -> None:
    catalogue = ActionCatalogue(entries=(_catalogue_entry(),))
    profile = ManifestActionProfile(
        subject_leaf_key="app.guard.run",
        condition_id="guard.subject.missing",
        scenario_id="scenario.subject.absent",
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
    reconciliation = _reconciliation(
        _leaf("app.guard.run"),
        _leaf("app.recovery.run", required_inputs=("subject_id",)),
    )
    with pytest.raises(OperatorSurfaceContractError, match="duplicate manifest action-profile identity"):
        resolve_manifest_action_profiles(
            profiles=(profile, profile),
            catalogue=catalogue,
            reconciliation=reconciliation,
        )

    with pytest.raises(OperatorSurfaceContractError, match="ambiguous reconciled CLI path"):
        resolve_manifest_action_profiles(
            profiles=(),
            catalogue=catalogue,
            reconciliation=_reconciliation(
                _leaf("app.guard.run", cli_path=("app", "shared")),
                _leaf(
                    "app.recovery.run",
                    cli_path=("app", "shared"),
                    required_inputs=("subject_id",),
                ),
            ),
        )


@pytest.mark.parametrize(
    ("result_schema_key", "input_schema_key", "expected_surface"),
    [
        ("app.recovery.other", None, "result_schema"),
        (None, "app.recovery.other", "input_schema"),
    ],
)
def test_action_resolution_rejects_internally_misaligned_schema_identity(
    result_schema_key: str | None,
    input_schema_key: str | None,
    expected_surface: str,
) -> None:
    with pytest.raises(OperatorSurfaceContractError, match=rf"reconciled {expected_surface} identity mismatch"):
        resolve_manifest_action_profiles(
            profiles=(),
            catalogue=ActionCatalogue(entries=(_catalogue_entry(),)),
            reconciliation=_reconciliation(
                _leaf(
                    "app.recovery.run",
                    required_inputs=("subject_id",),
                    result_schema_key=result_schema_key,
                    input_schema_key=input_schema_key,
                ),
            ),
        )
