"""Adapter classes wiring concrete components to the workflow protocols.

Each adapter is a thin translation layer: no domain decisions live here,
only the minimal surface normalisation required by the narrow Protocols
in :mod:`aeat.application.workflow._protocols`. The
:func:`default_engine` factory composes the adapters into a
:class:`aeat.application.workflow.WorkflowEngine` and is the entry point
production call sites (notably the CLI) use to obtain a fully-wired
workflow engine.

The session and certificate-bundle slots remain ``None`` by default:
:class:`aeat.application.workflow.WorkflowEngine` tolerates ``None`` for
each and records the skipped stages as "not wired" diagnostics rather
than failing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import cast

from ...adapters.outbound.aeat.auth import AeatSession
from ...core.config import Settings, load_settings
from ...core.logging import get_logger
from ...domain.deadlines import (
    AutonomoProfile,
    DeadlineEngine,
    Schedule,
)
from ...domain.submission import SubmissionEngine, SubmissionPreflightError
from ..filing import (
    CasillaSchemaProvider,
    FilingDraft,
    FilingProfile,
    build_draft,
)
from ._engine import WorkflowEngine
from ._errors import WorkflowError
from ._protocols import (
    CertificateBundleProtocol,
    DeadlineEngineProtocol,
    FilingDraftBuilderProtocol,
    FilingInputsProviderProtocol,
    RegistryFilingDraftProtocol,
    SubmissionEngineProtocol,
)

_logger = get_logger(__name__)


class DeadlineEngineAdapter:
    """Wrap :class:`aeat.domain.deadlines.DeadlineEngine` as a workflow Protocol."""

    def __init__(self, engine: DeadlineEngine) -> None:
        """Store the wrapped :class:`DeadlineEngine`."""
        self._engine = engine

    def compute(
        self,
        profile: AutonomoProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        """Delegate to :meth:`DeadlineEngine.compute`."""
        return self._engine.compute(profile, year, today=today)


class FilingDraftBuilderAdapter:
    """Wrap :func:`aeat.application.filing.build_draft` as a workflow Protocol.

    A schema provider is stored on construction so the narrow
    Protocol method does not leak the provider argument into the
    workflow engine's signature.
    """

    def __init__(self, *, schema_provider: object) -> None:
        """Store the schema provider used for every subsequent build."""
        self._schema_provider = schema_provider

    def build(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
        inputs: Mapping[str, object],
        fail_on_warning: bool = False,
    ) -> RegistryFilingDraftProtocol:
        """Delegate to :func:`build_draft`.

        ``cast`` is used for the filing-engine cross-module types because
        :class:`AutonomoProfile` and :class:`aeat.application.filing.FilingProfile`
        are structurally similar but not declared as the same Protocol
        — the real adapter hooks in on the call site when the profile
        loader lands.
        """
        draft: FilingDraft = build_draft(
            modelo=modelo,
            period=period,
            profile=cast("FilingProfile", profile),
            inputs=inputs,
            schema_provider=cast("CasillaSchemaProvider", self._schema_provider),
            fail_on_warning=fail_on_warning,
        )
        return cast("RegistryFilingDraftProtocol", draft)


class SubmissionEngineAdapter:
    """Wrap :class:`aeat.adapters.outbound.aeat.export.SubmissionEngine` as a workflow Protocol.

    The adapter uses the engine's public preflight method so the
    workflow's ``RUNNING_PREFLIGHT`` stage can execute the gate without
    exposing any AEAT write operation.
    """

    def __init__(self, engine: SubmissionEngine) -> None:
        """Store the wrapped :class:`SubmissionEngine`."""
        self._engine = engine

    def preflight(self, draft: RegistryFilingDraftProtocol, *, today: date) -> None:
        """Delegate to the engine's public preflight method."""
        self._engine.preflight(draft, today=today)


class JsonFileInputsProvider:
    """Read casilla inputs from the settings-configured JSON file.

    The JSON file must hold ``modelo -> period -> inputs``. The workflow
    refuses root-level casilla payloads so a caller cannot bypass the
    explicit modelo/period registry selection performed by the filing
    draft builder.
    """

    def __init__(self, path: Path | None) -> None:
        """Store the configured inputs file path."""
        self._path = path

    def load_inputs(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
    ) -> Mapping[str, object]:
        """Read and return the JSON inputs for ``(modelo, period)``."""
        del profile  # intentionally unused; profile is read by the builder directly
        if self._path is None:
            raise WorkflowError("AEAT_WORKFLOW_DRAFT_INPUTS_PATH is unset; cannot build a draft")
        if not self._path.exists():
            raise WorkflowError(f"workflow draft inputs file not found: {self._path}")
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            _logger.error("workflow draft inputs file %s is malformed JSON", self._path, exc_info=True)
            raise WorkflowError(f"workflow draft inputs file {self._path} is not valid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise WorkflowError(f"workflow draft inputs file {self._path} must be a JSON object")
        modelo_section = raw.get(modelo)
        if not isinstance(modelo_section, dict):
            raise WorkflowError(f"workflow draft inputs file {self._path} must contain object for modelo {modelo!r}")
        period_section = modelo_section.get(period)
        if not isinstance(period_section, dict):
            raise WorkflowError(
                f"workflow draft inputs file {self._path} must contain object for modelo {modelo!r} period {period!r}"
            )
        return period_section


def default_engine(
    *,
    submission_engine: SubmissionEngineProtocol,
    deadline_engine: DeadlineEngineProtocol | None = None,
    filing_draft_builder: FilingDraftBuilderProtocol | None = None,
    session: AeatSession | None = None,
    certificate_bundle: CertificateBundleProtocol | None = None,
    inputs_provider: FilingInputsProviderProtocol | None = None,
    settings: Settings | None = None,
) -> WorkflowEngine:
    """Build a :class:`WorkflowEngine` wired to the production components.

    Args:
        submission_engine: Required submission Protocol. The caller
            must build the real :class:`SubmissionEngine` themselves
            (the composition is complex and owned by the CLI root
            command wiring) and pass it wrapped or pre-adapted.
        deadline_engine: Optional deadline Protocol. ``None`` triggers
            a :class:`WorkflowError`; deadlines are mandatory for the
            workflow to have any obligation to work on.
        filing_draft_builder: Optional draft-builder Protocol.
            ``None`` triggers a :class:`WorkflowError`.
        session: Optional authenticated :class:`aeat.adapters.outbound.aeat.auth.AeatSession`.
            ``None`` skips both the inbox probe and the already-filed
            probe (both stages record a "not wired" diagnostic).
        certificate_bundle: Optional certificate Protocol.
        inputs_provider: Optional inputs Protocol; defaults to a
            :class:`JsonFileInputsProvider` backed by
            ``settings.aeat_workflow_draft_inputs_path``.
        settings: Optional :class:`Settings` override.

    Returns:
        A fully wired :class:`WorkflowEngine`.

    Raises:
        WorkflowError: If any of the required mandatory adapters
            cannot be constructed.
    """
    cfg = settings or load_settings()
    if deadline_engine is None:
        raise WorkflowError("default_engine requires a deadline_engine adapter")
    if filing_draft_builder is None:
        raise WorkflowError("default_engine requires a filing_draft_builder adapter")
    provider = inputs_provider or JsonFileInputsProvider(cfg.aeat_workflow_draft_inputs_path)
    return WorkflowEngine(
        deadline_engine=deadline_engine,
        filing_draft_builder=filing_draft_builder,
        submission_engine=submission_engine,
        session=session,
        certificate_bundle=certificate_bundle,
        inputs_provider=provider,
        settings=cfg,
    )


# Re-exported so importing :mod:`aeat.application.workflow` surfaces the primary
# preflight-exception type without callers having to dig into
# :mod:`aeat.adapters.outbound.aeat.export` for an isinstance check.
__all__ = [
    "DeadlineEngineAdapter",
    "FilingDraftBuilderAdapter",
    "JsonFileInputsProvider",
    "SubmissionEngineAdapter",
    "SubmissionPreflightError",
    "default_engine",
]
