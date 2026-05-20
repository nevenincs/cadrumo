"""End-user composite workflow engine."""

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
    NoActiveProfileError,
    WorkflowAbortedError,
    WorkflowComponentError,
    WorkflowError,
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
    WorkflowResult,
    WorkflowStage,
    WorkflowState,
    WorkflowStep,
    active_bucket_id_or_raise,
    active_transaction_catalogue_repository,
    compute_run_id,
    declaration_key,
    update_declaration_pointer,
    utc_now,
)

# ---- persistence (depends on _models only) ----------------------------------
from ._persistence import (
    WorkflowStateRepository,
    list_runs,
    load_run,
    save_run,
    workflow_state_repository,
)

# ---- protocols (no application deps) ----------------------------------------
from ._protocols import (
    CertificateBundleProtocol,
    DeadlineEngineProtocol,
    ModeloDraftBuilderProtocol,
    ModeloInputsProviderProtocol,
    RegistryModeloDraftProtocol,
    SubmissionEngineProtocol,
)

# ---- resume action (depends on _models + _persistence) ----------------------
from ._resume import (
    WorkflowResumeContext,
    WorkflowResumeRefusedError,
    resume_modelo_workflow,
)

__all__ = [
    "CertificateBundleProtocol",
    "DeadlineEngineAdapter",
    "DeadlineEngineProtocol",
    "DeclaracionPointer",
    "ModeloDraftBuilderAdapter",
    "ModeloDraftBuilderProtocol",
    "ModeloInputsProviderProtocol",
    "NoActiveProfileError",
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
    "WorkflowResult",
    "WorkflowResumeContext",
    "WorkflowResumeRefusedError",
    "WorkflowStage",
    "WorkflowState",
    "WorkflowStateRepository",
    "WorkflowStep",
    "active_bucket_id_or_raise",
    "active_transaction_catalogue_repository",
    "compute_run_id",
    "declaration_key",
    "default_engine",
    "list_runs",
    "load_run",
    "resume_modelo_workflow",
    "save_run",
    "update_declaration_pointer",
    "utc_now",
    "workflow_state_repository",
]
