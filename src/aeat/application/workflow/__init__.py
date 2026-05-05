"""End-user composite workflow engine.

The :mod:`aeat.application.workflow` subpackage owns the project's first
*composite* end-user command: a single entry point that orchestrates
the deadline engine, the filing draft builder, the submission engine,
and the in-flight status / inbox / certificate surfaces into one
ordered pipeline. The workflow is
**read-only**: live AEAT submission is permanently forbidden, so the
pipeline stops after preflight and never executes a real filing.

Public API discipline: callers outside this subpackage must import only
from :mod:`aeat.application.workflow`. The underscored modules are
implementation detail and may change without notice.

Examples:
    >>> from aeat.application.workflow import default_engine
    >>> engine = default_engine(submission_engine=..., deadline_engine=...)
"""

from __future__ import annotations

from ._adapters import (
    DeadlineEngineAdapter,
    FilingDraftBuilderAdapter,
    JsonFileInputsProvider,
    SubmissionEngineAdapter,
    default_engine,
)
from ._engine import WorkflowEngine
from ._errors import (
    WorkflowAbortedError,
    WorkflowComponentError,
    WorkflowError,
)
from ._models import (
    SiteHealthAlert,
    WorkflowAbortReason,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    compute_run_id,
)
from ._persistence import list_runs, load_run, save_run
from ._protocols import (
    CertificateBundleProtocol,
    DeadlineEngineProtocol,
    FilingDraftBuilderProtocol,
    FilingInputsProviderProtocol,
    RegistryFilingDraftProtocol,
    SubmissionEngineProtocol,
)

__all__ = [
    "CertificateBundleProtocol",
    "DeadlineEngineAdapter",
    "DeadlineEngineProtocol",
    "FilingDraftBuilderAdapter",
    "FilingDraftBuilderProtocol",
    "FilingInputsProviderProtocol",
    "JsonFileInputsProvider",
    "RegistryFilingDraftProtocol",
    "SiteHealthAlert",
    "SubmissionEngineAdapter",
    "SubmissionEngineProtocol",
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
