"""The command each catalogue action targets, for a process that holds no command graph.

An operator is shown a recovery action by the canonical path of the command it
targets. The command graph declares that path, and the command line reads it
there. The runtime serves the same recovery actions to the terminal interface
and to MCP without the command graph, so the facts of each action's target
leaf are recorded here: its path, its result schema, its required inputs and
its write policy.

The record is derived from the command graph and checked against it for every
action in the catalogue, so a command that moves or changes its inputs fails
that check until this record follows it. Reconciling a recorded leaf runs the
same application reconciliation a leaf read from the graph runs, and the same
projection then resolves the action against it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from .contract import get_operator_surface_contract
from .manifest import (
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    MountedFamilyInventoryRow,
    OperatorSurfaceReconciliation,
    ProfilePolicyInventoryRow,
    ReconciledOperatorLeaf,
    ResultSchemaInventoryRow,
    SurfaceExposureInventoryRow,
    reconcile_operator_surface_inventory,
)
from .precondition_action import resolve_precondition_action

if TYPE_CHECKING:
    from ...core.json_contract import ResolvedPreconditionAction
    from ..operator_actions.models import PreconditionVerdict

__all__ = [
    "ACTION_TARGETS",
    "ActionTarget",
    "recorded_action_target_reconciliation",
    "resolve_recorded_precondition_action",
]

_PROVENANCE: Final = "recorded action target"
_PROFILE_BOUND_WRITE: Final = "profile_bound_write"
_NON_PROFILE_BOUND: Final = "non_profile_bound"


@dataclass(frozen=True, slots=True)
class ActionTarget:
    """The facts of one command leaf a catalogue action targets.

    Every recorded target is an exposed leaf with a mounted family, a result
    schema and an input schema, and has no alias path: an action cannot target
    a leaf the reconciliation would have to excuse.
    """

    command_key: str
    cli_path: tuple[str, ...]
    result_schema: str
    required_inputs: tuple[str, ...] = ()
    profile_bound_write: bool = False

    @classmethod
    def of_leaf(cls, leaf: ReconciledOperatorLeaf) -> ActionTarget:
        """Record the facts of one reconciled leaf.

        Raises:
            ValueError: The leaf carries something this record cannot hold.
        """
        result_schema, input_schema = leaf.result_schema, leaf.input_schema
        policy, exposure = leaf.profile_policy, leaf.surface_exposure
        if (
            result_schema is None
            or input_schema is None
            or policy is None
            or exposure is None
            or leaf.mounted_family is None
            or leaf.exclusions
            or leaf.live_leaf.alias_cli_paths
            or not exposure.exposed
            or not policy.should_expose_externally
            or policy.classification not in {_PROFILE_BOUND_WRITE, _NON_PROFILE_BOUND}
        ):
            raise ValueError(f"action target leaf cannot be recorded: {leaf.live_leaf.subject_leaf_key}")
        return cls(
            command_key=leaf.live_leaf.subject_leaf_key,
            cli_path=leaf.live_leaf.canonical_cli_path,
            result_schema=result_schema.schema_name,
            required_inputs=input_schema.required_input_names,
            profile_bound_write=policy.classification == _PROFILE_BOUND_WRITE,
        )


ACTION_TARGETS: Final[tuple[ActionTarget, ...]] = (
    ActionTarget(
        "app.live.filed.pull", ("app", "live", "filed", "pull"), "FiledCaptureResult", profile_bound_write=True
    ),
    ActionTarget(
        "app.live.filed.pull_all",
        ("app", "live", "filed", "pull-all"),
        "FiledHistoryOnboardingResult",
        profile_bound_write=True,
    ),
    ActionTarget("app.live.notifications.list", ("app", "live", "notifications", "list"), "NotificationsListResult"),
    ActionTarget(
        "config.auth.configure",
        ("config", "auth", "configure"),
        "AuthConfigurePayload",
        required_inputs=("provider",),
        profile_bound_write=True,
    ),
    ActionTarget(
        "config.auth.diagnostics.view",
        ("config", "auth", "diagnostics", "view"),
        "AuthDiagnosticsViewResult",
        required_inputs=("diagnostic_id",),
    ),
    ActionTarget("config.auth.login", ("config", "auth", "login"), "AuthLoginPayload", profile_bound_write=True),
    ActionTarget("config.login", ("config", "login"), "ConfigLoginResult"),
    ActionTarget("config.logout", ("config", "logout"), "ConfigLogoutResult"),
    ActionTarget(
        "config.profile.archive.reconcile",
        ("config", "profile", "archive", "reconcile"),
        "ProfileBundleReconcileResult",
        profile_bound_write=True,
    ),
    ActionTarget(
        "config.profile.complete_setup",
        ("config", "profile", "complete-setup"),
        "ProfileCompleteSetupResult",
        profile_bound_write=True,
    ),
    ActionTarget("config.profile.create", ("config", "profile", "create"), "ConfigProfileCreateResult"),
    ActionTarget(
        "config.profile.descendiente.list",
        ("config", "profile", "descendiente", "list"),
        "ConfigProfileDescendienteListResult",
    ),
    ActionTarget(
        "config.profile.edit", ("config", "profile", "edit"), "ConfigProfileEditResult", profile_bound_write=True
    ),
    ActionTarget("config.profile.list", ("config", "profile", "list"), "ConfigListResult"),
    ActionTarget("config.profile.status", ("config", "profile", "status"), "ConfigStatusResult"),
    ActionTarget("config.provision.browser", ("config", "provision", "browser"), "ProvisionBrowserResult"),
    ActionTarget("config.repair", ("config", "repair"), "ConfigRepairResult"),
    ActionTarget("config.repair.profile", ("config", "repair", "profile"), "RepairProfileResult"),
    ActionTarget("config.repair.quarantine", ("config", "repair", "quarantine"), "RepairQuarantineResult"),
    ActionTarget("config.repair.reset_progress", ("config", "repair", "reset-progress"), "RepairResetProgressResult"),
    ActionTarget("config.storage.init", ("config", "storage", "init"), "ConfigStorageInitResult"),
    ActionTarget(
        "ledger.actividad_asset.correct",
        ("app", "ledger", "actividad-asset", "correct"),
        "ActivityAssetHistoryPayload",
        required_inputs=("revision_json",),
        profile_bound_write=True,
    ),
    ActionTarget("ledger.classify", ("app", "ledger", "classify"), "LedgerClassifyResult", profile_bound_write=True),
    ActionTarget(
        "ledger.evidence.review.list", ("app", "ledger", "evidence", "review", "list"), "EvidenceReviewListResult"
    ),
    ActionTarget(
        "ledger.link",
        ("app", "ledger", "link"),
        "LedgerLinkResult",
        required_inputs=("transaction_id", "invoice_id"),
        profile_bound_write=True,
    ),
    ActionTarget(
        "ledger.preflight", ("app", "ledger", "preflight"), "LedgerPreflightResult", required_inputs=("period", "year")
    ),
    ActionTarget("ledger.review", ("app", "ledger", "review"), "LedgerReviewResult"),
    ActionTarget("modelo.bindings.list", ("app", "modelo", "bindings", "list"), "ModeloBindingsListResult"),
    ActionTarget("modelo.casillas", ("app", "modelo", "casillas"), "ModeloCasillasResult", required_inputs=("modelo",)),
    ActionTarget("modelo.describe", ("app", "modelo", "describe"), "ModeloDescribeResult", required_inputs=("modelo",)),
    ActionTarget("modelo.filing_record.list", ("app", "modelo", "filing-record", "list"), "ModeloRecordListResult"),
    ActionTarget(
        "modelo.verification_report.list",
        ("app", "modelo", "verification-report", "list"),
        "VerificationReportListResult",
    ),
    ActionTarget(
        "modelo.work.calculate", ("app", "modelo", "work", "calculate"), "WorkCalculateResult", profile_bound_write=True
    ),
    ActionTarget(
        "modelo.work.create",
        ("app", "modelo", "work", "create"),
        "WorkCreateResult",
        required_inputs=("modelo", "year", "period"),
        profile_bound_write=True,
    ),
    ActionTarget("modelo.work.file", ("app", "modelo", "work", "file"), "WorkFileResult", profile_bound_write=True),
    ActionTarget("modelo.work.list", ("app", "modelo", "work", "list"), "WorkListResult"),
    ActionTarget("modelo.work.revisions", ("app", "modelo", "work", "revisions"), "WorkRevisionsResult"),
    ActionTarget("modelo.work.status", ("app", "modelo", "work", "status"), "WorkStatusResult"),
    ActionTarget(
        "modelo.work.verify", ("app", "modelo", "work", "verify"), "WorkVerifyResult", profile_bound_write=True
    ),
    ActionTarget(
        "overview.explain", ("app", "overview", "explain"), "OverviewExplainResult", required_inputs=("modelo",)
    ),
    ActionTarget("overview.status", ("app", "overview", "status"), "OverviewStatusResult"),
)
"""One record for each command a catalogue action targets, ordered by command key."""


def recorded_action_target_reconciliation(command_key: str, /) -> OperatorSurfaceReconciliation:
    """Reconcile the recorded leaf that owns ``command_key``.

    Raises:
        LookupError: No catalogue action targets ``command_key``.
    """
    target = next((item for item in ACTION_TARGETS if item.command_key == command_key), None)
    if target is None:
        raise LookupError(f"unknown command schema identity: {command_key}")
    return reconcile_operator_surface_inventory(
        live_leaves=(
            LiveLeafInventoryRow(
                subject_leaf_key=command_key,
                canonical_cli_path=target.cli_path,
                alias_cli_paths=(),
                provenance=_PROVENANCE,
            ),
        ),
        result_schemas=(
            ResultSchemaInventoryRow(
                subject_leaf_key=command_key, schema_name=target.result_schema, provenance=_PROVENANCE
            ),
        ),
        input_schemas=(
            InputSchemaInventoryRow(
                subject_leaf_key=command_key, required_input_names=target.required_inputs, provenance=_PROVENANCE
            ),
        ),
        mounted_families=tuple(
            MountedFamilyInventoryRow(
                root=family.root.value, child=family.child, provenance="OperatorSurfaceContract.command_families"
            )
            for family in get_operator_surface_contract().command_families
            if (family.root.value, family.child) == target.cli_path[:2]
        ),
        profile_policies=(
            ProfilePolicyInventoryRow(
                subject_leaf_key=command_key,
                classification=_PROFILE_BOUND_WRITE if target.profile_bound_write else _NON_PROFILE_BOUND,
                should_expose_externally=True,
                provenance=_PROVENANCE,
            ),
        ),
        surface_exposures=(
            SurfaceExposureInventoryRow(subject_leaf_key=command_key, exposed=True, provenance=_PROVENANCE),
        ),
    )


def resolve_recorded_precondition_action(verdict: PreconditionVerdict, /) -> ResolvedPreconditionAction:
    """Resolve a verdict's recovery action against the recorded action targets.

    This is the resolver of a process that holds no command graph. It names
    the command the command line names for the same verdict.
    """
    return resolve_precondition_action(verdict, target_reconciliation=recorded_action_target_reconciliation)
