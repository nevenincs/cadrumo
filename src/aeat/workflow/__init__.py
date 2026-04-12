"""End-user composite workflow engine (issue #59).

The :mod:`aeat.workflow` subpackage owns the project's first
*composite* end-user command: a single entry point that orchestrates
the deadline engine (#38), the self-healing sync runner (#11), the
filing draft engine (#39), the submission engine (#42), and the
in-flight status / inbox / certificate surfaces into one ordered
pipeline. The workflow is **dry-run by default**; the live path
requires both ``dry_run=False`` and ``override_confirmation=True`` at
the API level, mirroring the submission engine's gate verbatim.

Public API discipline: callers outside this subpackage must import
only from :mod:`aeat.workflow`. The underscored modules are
implementation detail.

See [[2026-04-12-workflow-engine-research]],
[[2026-04-12-workflow-engine-adr]], and
[[2026-04-12-workflow-engine-plan]] for the full context.
"""

from __future__ import annotations

from aeat.workflow._adapters import (
    DeadlineEngineAdapter,
    FilingDraftBuilderAdapter,
    JsonFileInputsProvider,
    SubmissionEngineAdapter,
    SyncRunnerAdapter,
    default_engine,
)
from aeat.workflow._engine import WorkflowEngine
from aeat.workflow._errors import (
    WorkflowAbortedError,
    WorkflowComponentError,
    WorkflowError,
)
from aeat.workflow._models import (
    WorkflowAbortReason,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    compute_run_id,
)
from aeat.workflow._persistence import list_runs, load_run, save_run
from aeat.workflow._protocols import (
    CertificateBundleProtocol,
    DeadlineEngineProtocol,
    ExpedienteLike,
    FilingDraftBuilderProtocol,
    FilingInputsProviderProtocol,
    InboxProtocol,
    RequerimientoLike,
    StatusReaderProtocol,
    SubmissionEngineProtocol,
    SubmittedFilingLike,
    SyncRunnerProtocol,
    SyncRunSummary,
)

__all__ = [
    "CertificateBundleProtocol",
    "DeadlineEngineAdapter",
    "DeadlineEngineProtocol",
    "ExpedienteLike",
    "FilingDraftBuilderAdapter",
    "FilingDraftBuilderProtocol",
    "FilingInputsProviderProtocol",
    "InboxProtocol",
    "JsonFileInputsProvider",
    "RequerimientoLike",
    "StatusReaderProtocol",
    "SubmissionEngineAdapter",
    "SubmissionEngineProtocol",
    "SubmittedFilingLike",
    "SyncRunSummary",
    "SyncRunnerAdapter",
    "SyncRunnerProtocol",
    "WorkflowAbortReason",
    "WorkflowAbortedError",
    "WorkflowComponentError",
    "WorkflowEngine",
    "WorkflowError",
    "WorkflowResult",
    "WorkflowStage",
    "WorkflowStep",
    "compute_run_id",
    "default_engine",
    "list_runs",
    "load_run",
    "save_run",
]
