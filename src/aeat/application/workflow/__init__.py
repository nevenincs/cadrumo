"""End-user composite workflow engine for the modelo lifecycle.

Composes the auth, filing, and submission layers into a single resumable
workflow that drives a modelo from setup through draft, verification, and
export. Run state is persisted per bucket, so an interrupted run resumes
where it left off.

Major declarations:

* :class:`WorkflowEngine` — the orchestrator that advances a run through
  its :class:`WorkflowStage` sequence.
* :class:`WorkflowState` and :class:`WorkflowResult` — the persisted run
  record and its terminal outcome.
* :func:`resume_modelo_workflow` and :func:`find_latest_run_for_period` —
  the resume entry points.
* :class:`WorkflowRunRepository` and :class:`WorkflowStateRepository` —
  the persistence boundaries.
* :class:`WorkflowError` and its subclasses (:class:`WorkflowAbortedError`,
  :class:`WorkflowComponentError`, :class:`WorkflowInputMismatchError`) — the
  failure taxonomy. The active-profile refusal :class:`NoActiveProfileError` is
  core-owned (:mod:`aeat.core.errors`); import it from there, not from this package.

The engine speaks to its dependencies through the protocols defined here
(:class:`DeadlineEngineProtocol`, :class:`ModeloDraftBuilderProtocol`,
:class:`SubmissionEngineProtocol`), so the concrete adapters stay swappable.
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
    ActiveProfileManifestStatusRepairResult,
    ActiveProfileRepairResult,
    assess_active_profile_health,
    repair_active_profile_manifest_status,
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
    "ActiveProfileManifestStatusRepairResult",
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
    "repair_active_profile_manifest_status",
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
