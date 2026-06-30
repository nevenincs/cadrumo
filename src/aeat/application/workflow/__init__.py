"""Public facade for workflow runs and profile-bucket discovery.

The workflow engine surface composes auth, filing, draft-building, and
submission collaborators into resumable modelo runs. A
:class:`~aeat.application.workflow.WorkflowEngine` advances
:class:`~aeat.application.workflow.WorkflowStage` values and persists
:class:`~aeat.application.workflow.WorkflowResult` records through
:class:`~aeat.application.workflow.WorkflowRunRepository`. The companion
:class:`~aeat.application.workflow.WorkflowState` envelope carries progress
pointers, auth readiness, review annotations, and bucket events; it does not
store profile facts or profile-value maps.

The profile-discovery surface is manifest-backed and intentionally cheap.
:func:`~aeat.application.workflow.list_profile_buckets`,
:func:`~aeat.application.workflow.read_profile_bucket`,
:func:`~aeat.application.workflow.read_profile_bucket_by_id`, and
:func:`~aeat.application.workflow.resolve_profile_bucket` scan plaintext
bucket manifests and return
:class:`~aeat.application.workflow.ProfileBucketPointer` records without
opening an encrypted database. Active-profile status and repair use the
redacted :class:`~aeat.application.workflow.ActiveProfileHealth` projection;
sensitive profile records are loaded only through the active bucket and the
user-profile orchestration layer.

This initializer is only the public re-export boundary. Manifest parsing stays
in :mod:`aeat.application.workflow._profile_bucket_scan`; health projection and
pointer repair stay in :mod:`aeat.application.workflow._profile_health`;
encrypted state and run storage stay behind
:class:`~aeat.application.workflow.WorkflowStateRepository` and
:class:`~aeat.application.workflow.WorkflowRunRepository`; and engine
orchestration stays in :mod:`aeat.application.workflow._engine`. Callers must
not duplicate pointer parsing, manifest resolution, secure-repository opening,
SQL routing, or master-key handling here. The active-profile refusal
``NoActiveProfileError`` remains core-owned and is imported from
:mod:`aeat.core.errors`.

See Also:
    :class:`aeat.application.workflow.WorkflowState`: Encrypted progress,
        readiness, review, and event state for the active bucket.
    :class:`aeat.application.workflow.WorkflowResult`: Persisted terminal
        result for one modelo workflow run.
    :func:`aeat.application.workflow.resume_modelo_workflow`: Build the
        resume context for a persisted aborted workflow run.
    :func:`aeat.application.workflow.resolve_modelo_workflow_resume_target`:
        Resolve exact run ids, exact work-unit ids, calculation revisions, or
        visible modelo selectors to one resumable workflow run target.
    :func:`aeat.application.workflow.list_profile_buckets`: Enumerate live
        manifest-backed profile buckets without opening secure storage.
    :func:`aeat.application.workflow.assess_active_profile_health`: Produce
        the redacted active-profile status used by CLI status surfaces.
    :class:`aeat.application.workflow.DeadlineEngineProtocol`: Protocol
        boundary for pluggable deadline calculation collaborators.
"""

from __future__ import annotations

# ---- adapters & engine (pull in auth / filing layers) -----------------------
from ._adapters import (
    DeadlineEngineAdapter,
    ModeloDraftBuilderAdapter,
    SubmissionEngineAdapter,
    default_engine,
)
from ._engine import WorkflowEngine

# ---- errors (no application deps) -------------------------------------------
from ._errors import (
    ProfileLabelAmbiguousError,
    WorkflowAbortedError,
    WorkflowComponentError,
    WorkflowError,
    WorkflowInputMismatchError,
)

# ---- core models first (no application-layer deps) -------------------------
# These MUST be imported before _adapters, _engine, _persistence so that
# when auth._actions / profile._actions / review._actions import
# WorkflowState / utc_now from this package during their own module load,
# those names are already present in the partially-initialised module.
from ._models import (
    DeclaracionPointer,
    ProfileBucketPointer,
    SiteHealthAlert,
    WorkflowAbortReason,
    WorkflowEvent,
    WorkflowPurpose,
    WorkflowResult,
    WorkflowStage,
    WorkflowState,
    WorkflowStep,
    active_transaction_catalogue_repository,
    compute_run_id,
    declaration_key,
    update_declaration_pointer,
    utc_now,
)

# ---- persistence (depends on _models only) ----------------------------------
from ._persistence import (
    WorkflowRunRepository,
    WorkflowStateRepository,
    WorkflowStateResetFingerprint,
    fingerprint_workflow_state,
    list_runs,
    load_run,
    reset_workflow_state,
    save_run,
    workflow_state_repository,
)

# ---- profile-bucket scan (depends on _models only) --------------------------
from ._profile_bucket_scan import (
    list_profile_buckets,
    read_profile_bucket,
    read_profile_bucket_by_id,
    resolve_profile_bucket,
)
from ._profile_health import (
    ActiveProfileHealth,
    ActiveProfileRepairResult,
    assess_active_profile_health,
    repair_active_profile_pointer,
)

# ---- protocols (no application deps) ----------------------------------------
from ._protocols import (
    CertificateBundleProtocol,
    DeadlineEngineProtocol,
    ModeloDraftBuilderProtocol,
    ModeloInputs,
    ModeloInputScalar,
    ModeloInputsProviderProtocol,
    ModeloInputValue,
    RegistryModeloDraftProtocol,
    SubmissionEngineProtocol,
)

# ---- resume action (depends on _models + _persistence) ----------------------
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

__all__ = [
    "ActiveProfileHealth",
    "ActiveProfileRepairResult",
    "CertificateBundleProtocol",
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
    "ProfileLabelAmbiguousError",
    "RegistryModeloDraftProtocol",
    "SiteHealthAlert",
    "SubmissionEngineAdapter",
    "SubmissionEngineProtocol",
    "WorkflowAbortReason",
    "WorkflowAbortedError",
    "WorkflowComponentError",
    "WorkflowEngine",
    "WorkflowError",
    "WorkflowEvent",
    "WorkflowInputMismatchError",
    "WorkflowPurpose",
    "WorkflowResult",
    "WorkflowResumeContext",
    "WorkflowResumeRefusedError",
    "WorkflowResumeRunAmbiguousError",
    "WorkflowResumeRunCandidate",
    "WorkflowResumeTargetResolution",
    "WorkflowRunRepository",
    "WorkflowStage",
    "WorkflowState",
    "WorkflowStateRepository",
    "WorkflowStateResetFingerprint",
    "WorkflowStep",
    "active_transaction_catalogue_repository",
    "assess_active_profile_health",
    "compute_run_id",
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
    "resolve_modelo_exact_workflow_run_for_resume",
    "resolve_modelo_visible_workflow_run_for_resume",
    "resolve_modelo_workflow_resume_target",
    "resolve_modelo_workflow_run_for_resume",
    "resolve_profile_bucket",
    "resume_modelo_workflow",
    "save_run",
    "update_declaration_pointer",
    "utc_now",
    "workflow_resume_candidate_lines",
    "workflow_state_repository",
]
