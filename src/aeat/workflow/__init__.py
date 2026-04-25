"""End-user composite workflow engine (issue #59).

The :mod:`aeat.workflow` subpackage owns the project's first
*composite* end-user command: a single entry point that orchestrates
the deadline engine (#38), the self-healing sync runner (#11), the
filing draft engine (#39), the submission engine (#42), and the
in-flight status / inbox / certificate surfaces into one ordered
pipeline. The workflow is **dry-run by default**; the live path
requires an explicit ``dry_run=False`` call at the API level, after
which the submission engine owns the live-write gates verbatim.

Public API discipline: callers outside this subpackage must import
only from :mod:`aeat.workflow`. The underscored modules are
implementation detail.

See [[2026-04-12-workflow-engine-research]],
[[2026-04-12-workflow-engine-adr]], and
[[2026-04-12-workflow-engine-plan]] for the full context.
"""

from __future__ import annotations

# Resolve the ``WorkflowStep.site_health_alert`` forward reference once
# ``aeat.browser._site_health.SiteHealthAlert`` is importable. Importing
# at this layer breaks the cycle: ``aeat.workflow._models`` must not
# import from ``aeat.browser._site_health`` at module load time, but the
# public subpackage boundary is a safe rebuild site.
from ..browser import _site_health as _site_health_module
from ..browser._site_health import SiteHealthAlert as _SiteHealthAlert
from . import _models as _workflow_models
from ._adapters import (
    DeadlineEngineAdapter,
    FilingDraftBuilderAdapter,
    JsonFileInputsProvider,
    SubmissionEngineAdapter,
    SyncRunnerAdapter,
    default_engine,
)
from ._engine import WorkflowEngine
from ._errors import (
    WorkflowAbortedError,
    WorkflowComponentError,
    WorkflowError,
)
from ._models import (
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
    SubmissionEngineProtocol,
    SubmittedFilingLike,
    SyncRunnerProtocol,
    SyncRunSummary,
)

_workflow_models.SiteHealthAlert = _SiteHealthAlert  # type: ignore[attr-defined]
_site_health_module.WorkflowStage = WorkflowStage  # type: ignore[attr-defined]
_SiteHealthAlert.model_rebuild()
WorkflowStep.model_rebuild()

__all__ = [
    "CertificateBundleProtocol",
    "DeadlineEngineAdapter",
    "DeadlineEngineProtocol",
    "FilingDraftBuilderAdapter",
    "FilingDraftBuilderProtocol",
    "FilingInputsProviderProtocol",
    "JsonFileInputsProvider",
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
