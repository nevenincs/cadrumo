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
  :class:`WorkflowComponentError`, :class:`WorkflowInputMismatchError`) plus the
  core-owned :class:`NoActiveProfileError` re-export — the failure taxonomy.

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
    list_runs,
    load_run,
    save_run,
    workflow_state_repository,
)

# ---- profile-bucket scan (depends on _models only) --------------------------
from ._profile_bucket_scan import (
    list_profile_buckets,
    read_profile_bucket,
    read_profile_bucket_by_id,
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
    find_latest_run_for_period,
    resume_modelo_workflow,
)

__all__ = [
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
    "WorkflowRunRepository",
    "WorkflowStage",
    "WorkflowState",
    "WorkflowStateRepository",
    "WorkflowStep",
    "active_transaction_catalogue_repository",
    "compute_run_id",
    "declaration_key",
    "default_engine",
    "find_latest_run_for_period",
    "list_profile_buckets",
    "list_runs",
    "load_run",
    "read_profile_bucket",
    "read_profile_bucket_by_id",
    "resume_modelo_workflow",
    "save_run",
    "update_declaration_pointer",
    "utc_now",
    "workflow_state_repository",
]
