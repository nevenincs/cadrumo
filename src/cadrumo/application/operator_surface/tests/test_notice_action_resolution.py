"""Real joins from declared operator actions to successful notice actions."""

from __future__ import annotations

import ast
import inspect

import pytest

from ....core import (
    ActionArgumentSource,
    ActionArgumentStatus,
)
from ....core.json_contract import ResolvedActionArgument
from ...operator_actions import (
    OPERATOR_ACTION_CATALOGUE,
    ActionCatalogue,
    ActionCatalogueEntry,
    ActionReference,
)
from .. import ResolvedCatalogueAction, _action_resolution, resolve_catalogue_action, resolve_notice_action
from .._manifest import (
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    MountedFamilyInventoryRow,
    OperatorSurfaceReconciliation,
    ProfilePolicyInventoryRow,
    ReconciledOperatorLeaf,
    ResultSchemaInventoryRow,
    SurfaceExposureInventoryRow,
)
from .._manifest import ResolvedCatalogueAction as ManifestResolvedCatalogueAction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _reconciliation(*, target_command_key: str, required_input_names: tuple[str, ...]) -> OperatorSurfaceReconciliation:
    """Build the actual typed reconciliation shape for one live target."""
    return OperatorSurfaceReconciliation(
        leaves=(
            ReconciledOperatorLeaf(
                live_leaf=LiveLeafInventoryRow(
                    subject_leaf_key=target_command_key,
                    canonical_cli_path=("config", "profile", "target"),
                    provenance="real S05 command traversal projection",
                ),
                result_schema=ResultSchemaInventoryRow(
                    subject_leaf_key=target_command_key,
                    schema_name="TargetPayload",
                    provenance="COMMAND_GRAPH",
                ),
                input_schema=InputSchemaInventoryRow(
                    subject_leaf_key=target_command_key,
                    required_input_names=required_input_names,
                    provenance="S05 VerbInputSchema.required_inputs",
                ),
                mounted_family=MountedFamilyInventoryRow(
                    root="config",
                    child="profile",
                    provenance="OperatorSurfaceContract.command_families",
                ),
                profile_policy=ProfilePolicyInventoryRow(
                    subject_leaf_key=target_command_key,
                    classification="profile_bound_read",
                    should_expose_externally=True,
                    provenance="profile policy classification",
                ),
                surface_exposure=SurfaceExposureInventoryRow(
                    subject_leaf_key=target_command_key,
                    exposed=True,
                    provenance="external surface inventory",
                ),
                exclusions=(),
            ),
        ),
    )


def _profile_name_argument() -> ResolvedActionArgument:
    """One concrete producer argument using the catalogue's declared provenance."""
    return ResolvedActionArgument(
        argument_name="profile_name",
        status=ActionArgumentStatus.RESOLVED,
        value="Ada",
        source=ActionArgumentSource.VERDICT_CONTEXT,
        source_key="profile_name",
    )


def test_zero_input_catalogue_action_resolves_to_a_success_notice_action() -> None:
    action = resolve_notice_action(
        action=ActionReference(action_id="operator.overview.status"),
        argument_bindings=(),
        catalogue=OPERATOR_ACTION_CATALOGUE,
        reconciliation=_reconciliation(target_command_key="overview.status", required_input_names=()),
    )

    assert action.model_dump(mode="json") == {
        "action": {
            "action_id": "operator.overview.status",
            "target_command_key": "overview.status",
        },
        "argument_bindings": [],
    }


def test_required_catalogue_input_retains_concrete_value_and_provenance() -> None:
    action = resolve_notice_action(
        action=ActionReference(action_id="operator.profile.create"),
        argument_bindings=(_profile_name_argument(),),
        catalogue=OPERATOR_ACTION_CATALOGUE,
        reconciliation=_reconciliation(
            target_command_key="config.profile.create",
            required_input_names=("profile_name",),
        ),
    )

    (argument,) = action.argument_bindings
    assert argument.value == "Ada"
    assert argument.source is ActionArgumentSource.VERDICT_CONTEXT
    assert argument.source_key == "profile_name"


def test_one_argument_can_use_exactly_one_of_its_declared_source_strategies() -> None:
    reconciliation = _reconciliation(
        target_command_key="modelo.work.calculate",
        required_input_names=("work_unit_id",),
    )
    evidence_argument = ResolvedActionArgument(
        argument_name="work_unit_id",
        status=ActionArgumentStatus.RESOLVED,
        value="work-1",
        source=ActionArgumentSource.CONDITION_EVIDENCE,
        source_key="work_unit_id",
        source_evidence_id="workflow.work_unit.addressing",
    )
    verdict_argument = ResolvedActionArgument(
        argument_name="work_unit_id",
        status=ActionArgumentStatus.RESOLVED,
        value="work-2",
        source=ActionArgumentSource.VERDICT_CONTEXT,
        source_key="work_unit_id",
    )

    for argument in (evidence_argument, verdict_argument):
        action = resolve_notice_action(
            action=ActionReference(action_id="operator.modelo.work.calculate"),
            argument_bindings=(argument,),
            catalogue=OPERATOR_ACTION_CATALOGUE,
            reconciliation=reconciliation,
        )
        assert action.argument_bindings == (argument,)

    wrong_source = ResolvedActionArgument(
        argument_name="work_unit_id",
        status=ActionArgumentStatus.RESOLVED,
        value="work-3",
        source=ActionArgumentSource.REQUEST_CONTEXT,
        source_key="work_unit_id",
    )
    with pytest.raises(ValueError, match="provenance does not match"):
        resolve_notice_action(
            action=ActionReference(action_id="operator.modelo.work.calculate"),
            argument_bindings=(wrong_source,),
            catalogue=OPERATOR_ACTION_CATALOGUE,
            reconciliation=reconciliation,
        )


def test_required_or_unresolved_producer_arguments_refuse_success_notice_actions() -> None:
    reconciliation = _reconciliation(
        target_command_key="config.profile.create",
        required_input_names=("profile_name",),
    )

    with pytest.raises(ValueError, match="missing required input bindings"):
        resolve_notice_action(
            action=ActionReference(action_id="operator.profile.create"),
            argument_bindings=(),
            catalogue=OPERATOR_ACTION_CATALOGUE,
            reconciliation=reconciliation,
        )

    with pytest.raises(ValueError, match="cannot carry unresolved"):
        resolve_notice_action(
            action=ActionReference(action_id="operator.profile.create"),
            argument_bindings=(
                ResolvedActionArgument(
                    argument_name="profile_name",
                    status=ActionArgumentStatus.MISSING,
                ),
            ),
            catalogue=OPERATOR_ACTION_CATALOGUE,
            reconciliation=reconciliation,
        )


def test_catalogue_and_producer_argument_declarations_fail_closed() -> None:
    reconciliation = _reconciliation(
        target_command_key="config.profile.create",
        required_input_names=("profile_name",),
    )
    incomplete_catalogue = ActionCatalogue(
        entries=(
            ActionCatalogueEntry(
                action_id="operator.profile.custom_create",
                target_command_key="config.profile.create",
                canonical_cli_path=("config", "profile", "create"),
            ),
        ),
    )
    with pytest.raises(ValueError, match="insufficient action argument specifications"):
        resolve_catalogue_action(
            action=ActionReference(action_id="operator.profile.custom_create"),
            catalogue=incomplete_catalogue,
            reconciliation=reconciliation,
        )

    with pytest.raises(ValueError, match="not declared by the catalogue"):
        resolve_notice_action(
            action=ActionReference(action_id="operator.profile.create"),
            argument_bindings=(
                _profile_name_argument(),
                ResolvedActionArgument(
                    argument_name="display_name",
                    status=ActionArgumentStatus.RESOLVED,
                    value="Ada",
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="profile_name",
                ),
            ),
            catalogue=OPERATOR_ACTION_CATALOGUE,
            reconciliation=reconciliation,
        )


def test_notice_resolution_uses_the_manifest_owned_catalogue_action_record() -> None:
    """The notice bridge consumes the manifest record rather than a parallel DTO."""
    assert ResolvedCatalogueAction is ManifestResolvedCatalogueAction
    resolution_module = ast.parse(inspect.getsource(_action_resolution))
    assert not any(
        isinstance(node, ast.ClassDef) and node.name == ManifestResolvedCatalogueAction.__name__
        for node in ast.walk(resolution_module)
    )

    resolution = resolve_catalogue_action(
        action=ActionReference(action_id="operator.profile.create"),
        catalogue=OPERATOR_ACTION_CATALOGUE,
        reconciliation=_reconciliation(
            target_command_key="config.profile.create",
            required_input_names=("profile_name",),
        ),
    )

    assert type(resolution) is ManifestResolvedCatalogueAction
