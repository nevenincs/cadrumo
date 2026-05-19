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

from collections.abc import Mapping
from datetime import date
from typing import TYPE_CHECKING, cast

from ...core.config import Settings, load_settings

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth import AeatSession
from ...core.logging import get_logger
from ...domain.deadlines import (
    AutonomoProfile,
    DeadlineEngine,
    Schedule,
)
from ...domain.submission import SubmissionEngine, SubmissionPreflightError
from ..filing import (
    CasillaSchemaProvider,
    ModeloDraft,
    ModeloProfile,
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

    def __init__(self, *, schema_provider: CasillaSchemaProvider) -> None:
        """Store the schema provider used for every subsequent build."""
        self._schema_provider: CasillaSchemaProvider = schema_provider

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

        ``cast`` is used for ``profile`` because :class:`AutonomoProfile`
        and :class:`aeat.application.filing.ModeloProfile` are structurally
        compatible (both expose ``tax_id``) but ``AutonomoProfile`` does not
        declare ``display_name`` and therefore does not satisfy the Protocol
        statically. At this adapter boundary the structural bridging is
        intentional.
        """
        draft: ModeloDraft = build_draft(
            modelo=modelo,
            period=period,
            profile=cast(ModeloProfile, profile),
            inputs=inputs,
            schema_provider=self._schema_provider,
            fail_on_warning=fail_on_warning,
        )
        return cast(RegistryFilingDraftProtocol, draft)


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
        inputs_provider: Required inputs Protocol. Sensitive draft
            inputs come from bucket-backed application services, not
            JSON files.
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
    if inputs_provider is None:
        raise WorkflowError("default_engine requires a bucket-backed filing inputs provider")
    return WorkflowEngine(
        deadline_engine=deadline_engine,
        filing_draft_builder=filing_draft_builder,
        submission_engine=submission_engine,
        session=session,
        certificate_bundle=certificate_bundle,
        inputs_provider=inputs_provider,
        settings=cfg,
    )


# Re-exported so importing :mod:`aeat.application.workflow` surfaces the primary
# preflight-exception type without callers having to dig into
# :mod:`aeat.adapters.outbound.aeat.export` for an isinstance check.
__all__ = [
    "DeadlineEngineAdapter",
    "FilingDraftBuilderAdapter",
    "SubmissionEngineAdapter",
    "SubmissionPreflightError",
    "default_engine",
]
