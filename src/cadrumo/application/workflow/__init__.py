"""Public facade for workflow runs and profile-bucket discovery.

The workflow engine surface composes auth, filing, draft-building, and
submission collaborators into resumable modelo runs. A
:class:`WorkflowEngine` advances
:class:`WorkflowStage` values and persists
:class:`WorkflowResult` records through
:class:`WorkflowRunRepository`. The companion
:class:`WorkflowState` envelope carries progress
pointers, auth readiness, review annotations, and bucket events; it does not
store profile facts or profile-value maps.

Persisted authentication records are part of this public workflow boundary.
Their definitions live in the internal shared leaf
:mod:`application._workflow_auth_models`, while callers import them from this
facade.

The profile-discovery surface is the one anchored committed-capsule projection.
:func:`list_profile_buckets`,
:func:`read_profile_bucket`,
:func:`read_profile_bucket_by_id`, and
:func:`resolve_profile_bucket` enumerate current committed capsules and return
:class:`ProfileBucketPointer` records without
opening profile facts. The projection exposes immutable bucket UUIDs and
non-authoritative operator labels. Retired-layout detection and malformed
current commit markers propagate as typed custody outcomes; workflow never
scans arbitrary bucket directories or parses former metadata files.
Active-profile status and repair use the redacted
:class:`ActiveProfileHealth` projection;
sensitive profile records are loaded only through the active bucket and the
user-profile orchestration layer.

Workflow persistence is likewise bucket-scoped.
:func:`~cadrumo.application.workflow._persistence.workflow_state_repository` binds the
state envelope to the currently resolved active bucket via the storage
runtime's secure-object repository. A cold root with no active pointer is the
only bootstrap exception, so recovery and status probes can observe an absent
state without manufacturing a profile bucket. Reset helpers
:func:`fingerprint_workflow_state` and
:func:`reset_workflow_state` operate on the
workflow-state row only: they emit a plaintext-free
:class:`WorkflowStateResetFingerprint` and append
the ``workflow_state.reset`` bucket event before deleting the encrypted row.

This initializer is only the public re-export boundary. Committed-capsule
projection stays in :mod:`_profile_bucket_scan`; health projection and
pointer repair stay in :mod:`_profile_health`;
encrypted state and run storage stay behind
:class:`WorkflowStateRepository` and
:class:`WorkflowRunRepository`; and engine
orchestration stays in :mod:`_engine`. Callers must
not duplicate pointer parsing, capsule discovery, secure-repository opening,
SQL routing, or master-key handling here. The active-profile refusal
``NoActiveProfileError`` remains core-owned and is imported from
:mod:`core.errors`.

See Also:
    :class:`WorkflowState`: Encrypted progress,
        readiness, review, and event state for the active bucket.
    :class:`WorkflowResult`: Persisted terminal
        result for one modelo workflow run.
    :func:`resume_modelo_workflow`: Build the
        resume context for a persisted aborted workflow run.
    :func:`resolve_modelo_workflow_resume_target`:
        Resolve exact run ids, exact work-unit ids, calculation revisions, or
        visible modelo selectors to one resumable workflow run target.
    :func:`list_profile_buckets`: Enumerate current committed profile
        projections without opening profile facts.
    :func:`assess_active_profile_health`: Produce
        the redacted active-profile status used by CLI status surfaces.
    :func:`~cadrumo.application.workflow._persistence.workflow_state_repository`: Resolve the
        active-bucket secure-object repository for encrypted workflow state.
    :class:`WorkflowStateResetFingerprint`: Redacted
        reset audit record produced before workflow-state deletion.
    :class:`DeadlineEngineProtocol`: Protocol
        boundary for pluggable deadline calculation collaborators.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...domain.filing import ModeloInputs, ModeloInputScalar, ModeloInputValue
    from .._workflow_auth_models import (
        AuthCleanupCertificateSource,
        AuthCleanupIntent,
        AuthCleanupOperationKind,
        AuthState,
        CertificateSecretMutationEventKind,
        CertificateSecretMutationIntent,
        CertificateSourceName,
        CertificateSourceRecord,
    )
    from .._workflow_review_models import WorkflowEvent
    from ._adapters import DeadlineEngineAdapter, ModeloDraftBuilderAdapter, SubmissionEngineAdapter, default_engine
    from ._engine import WorkflowEngine
    from ._errors import (
        ProfileLabelAmbiguousError,
        WorkflowAbortedError,
        WorkflowComponentError,
        WorkflowError,
        WorkflowInputMismatchError,
    )
    from ._events import WorkflowStateResetFingerprint
    from ._persistence import (
        WorkflowRunRepository,
        WorkflowStateRepository,
        current_operation_instant,
        fingerprint_workflow_state,
        list_runs,
        load_run,
        reset_workflow_state,
        save_run,
        workflow_state_repository,
    )
    from ._profile_bucket_models import ProfileBucketPointer
    from ._profile_bucket_scan import (
        list_profile_buckets,
        read_profile_bucket,
        read_profile_bucket_by_id,
        resolve_profile_bucket,
    )
    from ._profile_health import (
        ActiveProfileHealth,
        ActiveProfileRepairResult,
        ProfileHealthStatus,
        ProfileSource,
        assess_active_profile_health,
        repair_active_profile_pointer,
        unavailable_profile_record_verdict,
    )
    from ._protocols import (
        CertificateBundleProtocol,
        DeadlineEngineProtocol,
        ModeloDraftBuilderProtocol,
        ModeloInputsProviderProtocol,
        RegistryModeloDraftProtocol,
        SubmissionEngineProtocol,
    )
    from ._resume import (
        WorkflowResumeContext,
        WorkflowResumeRefusedError,
        WorkflowResumeRunAmbiguousError,
        WorkflowResumeRunCandidate,
        WorkflowResumeTargetResolution,
        find_latest_run_for_period,
        find_unique_run_for_period,
        resolve_modelo_exact_workflow_run_for_resume,
        resolve_modelo_visible_workflow_run_for_resume,
        resolve_modelo_workflow_resume_target,
        resolve_modelo_workflow_run_for_resume,
        resume_modelo_workflow,
        workflow_resume_candidate_lines,
    )
    from ._run_models import (
        SiteHealthAlert,
        WorkflowAlreadyFiledDetails,
        WorkflowAuthCheckDetails,
        WorkflowDeadlineContextDetails,
        WorkflowDeadlineRecoveryFacts,
        WorkflowDiagnosticSkipReason,
        WorkflowDraftBuiltDetails,
        WorkflowDraftMismatchDetails,
        WorkflowDraftNotReadyDetails,
        WorkflowFailureDetails,
        WorkflowInboxBlockedDetails,
        WorkflowInboxSkippedDetails,
        WorkflowObligationFacts,
        WorkflowPreflightFailedDetails,
        WorkflowPurpose,
        WorkflowResult,
        WorkflowSiteHealthFacts,
        WorkflowStage,
        WorkflowStep,
        WorkflowStepDetails,
        WorkflowValidationFailedDetails,
        compute_run_id,
    )
    from ._state_models import (
        ActiveProfileRecordResolution,
        DeclaracionPointer,
        WorkflowState,
        active_transaction_catalogue_repository,
        declaration_key,
        resolve_active_profile_record,
        update_declaration_pointer,
        utc_now,
    )
    from ._workflow_abort import WorkflowAbortReason


_LAZY_EXPORTS: dict[str, str] = {
    **dict.fromkeys(
        (
            "AuthCleanupCertificateSource",
            "AuthCleanupIntent",
            "AuthCleanupOperationKind",
            "AuthState",
            "CertificateSecretMutationEventKind",
            "CertificateSecretMutationIntent",
            "CertificateSourceName",
            "CertificateSourceRecord",
        ),
        ".._workflow_auth_models",
    ),
    **dict.fromkeys(
        ("DeadlineEngineAdapter", "ModeloDraftBuilderAdapter", "SubmissionEngineAdapter", "default_engine"),
        "._adapters",
    ),
    "WorkflowEngine": "._engine",
    **dict.fromkeys(
        (
            "ProfileLabelAmbiguousError",
            "WorkflowAbortedError",
            "WorkflowComponentError",
            "WorkflowError",
            "WorkflowInputMismatchError",
        ),
        "._errors",
    ),
    **dict.fromkeys(
        (
            "ActiveProfileRecordResolution",
            "DeclaracionPointer",
            "WorkflowState",
            "active_transaction_catalogue_repository",
            "declaration_key",
            "resolve_active_profile_record",
            "update_declaration_pointer",
            "utc_now",
        ),
        "._state_models",
    ),
    "ProfileBucketPointer": "._profile_bucket_models",
    "WorkflowEvent": ".._workflow_review_models",
    **dict.fromkeys(
        (
            "SiteHealthAlert",
            "WorkflowAlreadyFiledDetails",
            "WorkflowAuthCheckDetails",
            "WorkflowDeadlineContextDetails",
            "WorkflowDeadlineRecoveryFacts",
            "WorkflowDiagnosticSkipReason",
            "WorkflowDraftBuiltDetails",
            "WorkflowDraftMismatchDetails",
            "WorkflowDraftNotReadyDetails",
            "WorkflowFailureDetails",
            "WorkflowInboxBlockedDetails",
            "WorkflowInboxSkippedDetails",
            "WorkflowObligationFacts",
            "WorkflowPreflightFailedDetails",
            "WorkflowPurpose",
            "WorkflowResult",
            "WorkflowSiteHealthFacts",
            "WorkflowStage",
            "WorkflowStep",
            "WorkflowStepDetails",
            "WorkflowValidationFailedDetails",
            "compute_run_id",
        ),
        "._run_models",
    ),
    "WorkflowAbortReason": "._workflow_abort",
    **dict.fromkeys(
        (
            "WorkflowRunRepository",
            "WorkflowStateRepository",
            "current_operation_instant",
            "fingerprint_workflow_state",
            "list_runs",
            "load_run",
            "reset_workflow_state",
            "save_run",
            "workflow_state_repository",
        ),
        "._persistence",
    ),
    "WorkflowStateResetFingerprint": "._events",
    **dict.fromkeys(
        ("list_profile_buckets", "read_profile_bucket", "read_profile_bucket_by_id", "resolve_profile_bucket"),
        "._profile_bucket_scan",
    ),
    **dict.fromkeys(
        (
            "ActiveProfileHealth",
            "ActiveProfileRepairResult",
            "ProfileHealthStatus",
            "ProfileSource",
            "assess_active_profile_health",
            "repair_active_profile_pointer",
            "unavailable_profile_record_verdict",
        ),
        "._profile_health",
    ),
    **dict.fromkeys(
        (
            "CertificateBundleProtocol",
            "DeadlineEngineProtocol",
            "ModeloDraftBuilderProtocol",
            "ModeloInputsProviderProtocol",
            "RegistryModeloDraftProtocol",
            "SubmissionEngineProtocol",
        ),
        "._protocols",
    ),
    **dict.fromkeys(
        ("ModeloInputs", "ModeloInputScalar", "ModeloInputValue"),
        "cadrumo.domain.filing",
    ),
    **dict.fromkeys(
        (
            "WorkflowResumeContext",
            "WorkflowResumeRefusedError",
            "WorkflowResumeRunAmbiguousError",
            "WorkflowResumeRunCandidate",
            "WorkflowResumeTargetResolution",
            "find_latest_run_for_period",
            "find_unique_run_for_period",
            "resolve_modelo_exact_workflow_run_for_resume",
            "resolve_modelo_visible_workflow_run_for_resume",
            "resolve_modelo_workflow_resume_target",
            "resolve_modelo_workflow_run_for_resume",
            "resume_modelo_workflow",
            "workflow_resume_candidate_lines",
        ),
        "._resume",
    ),
}

_LAZY_MODULE_LOADERS: dict[str, Callable[[], ModuleType]] = {
    module_path: partial(import_module, module_path, __name__) for module_path in frozenset(_LAZY_EXPORTS.values())
}


def __getattr__(name: str) -> object:
    """Resolve a public name without loading unrelated workflow capabilities."""
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    loader = _LAZY_MODULE_LOADERS.get(module_path)
    if loader is None:
        raise RuntimeError(f"missing lazy loader for {module_path!r}")
    value = getattr(loader(), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Report the complete public surface before its owners are imported."""
    return sorted(set(__all__) | set(globals()))


__all__ = [
    "ActiveProfileHealth",
    "ActiveProfileRecordResolution",
    "ActiveProfileRepairResult",
    "AuthCleanupCertificateSource",
    "AuthCleanupIntent",
    "AuthCleanupOperationKind",
    "AuthState",
    "CertificateBundleProtocol",
    "CertificateSecretMutationEventKind",
    "CertificateSecretMutationIntent",
    "CertificateSourceName",
    "CertificateSourceRecord",
    "DeadlineEngineAdapter",
    "DeadlineEngineProtocol",
    "DeclaracionPointer",
    "ModeloDraftBuilderAdapter",
    "ModeloDraftBuilderProtocol",
    "ModeloInputScalar",
    "ModeloInputValue",
    "ModeloInputs",
    "ModeloInputsProviderProtocol",
    "ProfileBucketPointer",
    "ProfileHealthStatus",
    "ProfileLabelAmbiguousError",
    "ProfileSource",
    "RegistryModeloDraftProtocol",
    "SiteHealthAlert",
    "SubmissionEngineAdapter",
    "SubmissionEngineProtocol",
    "WorkflowAbortReason",
    "WorkflowAbortedError",
    "WorkflowAlreadyFiledDetails",
    "WorkflowAuthCheckDetails",
    "WorkflowComponentError",
    "WorkflowDeadlineContextDetails",
    "WorkflowDeadlineRecoveryFacts",
    "WorkflowDiagnosticSkipReason",
    "WorkflowDraftBuiltDetails",
    "WorkflowDraftMismatchDetails",
    "WorkflowDraftNotReadyDetails",
    "WorkflowEngine",
    "WorkflowError",
    "WorkflowEvent",
    "WorkflowFailureDetails",
    "WorkflowInboxBlockedDetails",
    "WorkflowInboxSkippedDetails",
    "WorkflowInputMismatchError",
    "WorkflowObligationFacts",
    "WorkflowPreflightFailedDetails",
    "WorkflowPurpose",
    "WorkflowResult",
    "WorkflowResumeContext",
    "WorkflowResumeRefusedError",
    "WorkflowResumeRunAmbiguousError",
    "WorkflowResumeRunCandidate",
    "WorkflowResumeTargetResolution",
    "WorkflowRunRepository",
    "WorkflowSiteHealthFacts",
    "WorkflowStage",
    "WorkflowState",
    "WorkflowStateRepository",
    "WorkflowStateResetFingerprint",
    "WorkflowStep",
    "WorkflowStepDetails",
    "WorkflowValidationFailedDetails",
    "active_transaction_catalogue_repository",
    "assess_active_profile_health",
    "compute_run_id",
    "current_operation_instant",
    "declaration_key",
    "default_engine",
    "find_latest_run_for_period",
    "find_unique_run_for_period",
    "fingerprint_workflow_state",
    "list_profile_buckets",
    "list_runs",
    "load_run",
    "read_profile_bucket",
    "read_profile_bucket_by_id",
    "repair_active_profile_pointer",
    "reset_workflow_state",
    "resolve_active_profile_record",
    "resolve_modelo_exact_workflow_run_for_resume",
    "resolve_modelo_visible_workflow_run_for_resume",
    "resolve_modelo_workflow_resume_target",
    "resolve_modelo_workflow_run_for_resume",
    "resolve_profile_bucket",
    "resume_modelo_workflow",
    "save_run",
    "unavailable_profile_record_verdict",
    "update_declaration_pointer",
    "utc_now",
    "workflow_resume_candidate_lines",
    "workflow_state_repository",
]
