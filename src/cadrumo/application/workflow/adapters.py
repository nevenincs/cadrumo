"""Adapter classes wiring concrete components to the workflow protocols.

Each adapter is a thin translation layer: no domain decisions live here,
only the minimal surface normalisation required by the narrow Protocols
in :mod:`application.workflow.protocols`. The
:func:`default_engine` factory composes the adapters into a
:class:`~application.workflow.WorkflowEngine` and is the entry point
production call sites (notably the CLI) use to obtain a fully-wired
workflow engine. The deadline adapter wraps a :class:`Schedule`-producing engine; the
filing adapter constructs a :class:`ModeloDraft` via ``build_draft``
from the filing surface.

The session and certificate-bundle slots remain ``None`` by default:
:class:`~application.workflow.WorkflowEngine` tolerates ``None`` for
each and records the skipped stages as "not wired" diagnostics rather
than failing.

See Also:
    :mod:`application.workflow.protocols`
        Declares the narrow contracts each adapter satisfies.
    :class:`~application.workflow.WorkflowEngine`
        Consumes the adapted deadline, draft-building, submission, and live
        read collaborators.
    :class:`~domain.submission.SubmissionEngine`
        Read-only domain preflight engine wrapped by
        :class:`SubmissionEngineAdapter`.
    :mod:`application.modelo._workflow_gate`
        Builds revision-scoped workflow engines with the same adapter
        boundaries for verification and local mark-as-filed paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...core.config import Settings, load_settings
from ...core.identity import SubjectTaxId
from ...core.logging import get_logger
from ...core.period import Period
from ...domain.deadlines.engine import DeadlineEngine
from ...domain.deadlines.models import Schedule, TaxpayerProfile
from ...domain.filing.protocols import CasillaSchemaProvider
from ...domain.filing.schema import ModeloDraft
from ...domain.submission._engine import SubmissionEngine
from ..filing._draft_construction import build_draft
from .engine import WorkflowEngine
from .errors import WorkflowError
from .protocols import (
    CertificateBundleProtocol,
    DeadlineEngineProtocol,
    ExpedientesSource,
    ModeloDraftBuilderProtocol,
    ModeloInputs,
    ModeloInputsProviderProtocol,
    RegistryModeloDraftProtocol,
    SubmissionEngineProtocol,
)

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _TaxpayerProfileBridge:
    """Minimal :class:`~domain.filing.ModeloProfile`-compatible wrapper.

    :class:`~domain.deadlines.TaxpayerProfile` does not declare
    ``display_name``, which the :class:`~domain.filing.ModeloProfile`
    Protocol requires. This thin bridge adds a default empty ``display_name``
    so the structural protocol check passes without modifying either model.

    The bridge is intentionally private: no production code outside
    :class:`ModeloDraftBuilderAdapter` should depend on it.
    """

    tax_id: SubjectTaxId
    display_name: str = ""


class DeadlineEngineAdapter:
    """Wrap :class:`~domain.deadlines.DeadlineEngine` as a workflow Protocol."""

    def __init__(self, engine: DeadlineEngine) -> None:
        """Store the wrapped :class:`DeadlineEngine`."""
        self._engine = engine

    def compute(
        self,
        profile: TaxpayerProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        """Delegate to :meth:`DeadlineEngine.compute` for the given :class:`TaxpayerProfile`.

        Returns a :class:`Schedule`.
        """
        return self._engine.compute(profile, year, today=today)


class ModeloDraftBuilderAdapter:
    """Wrap :func:`application.filing.build_draft` as a workflow Protocol.

    A schema provider is stored on construction so the narrow
    Protocol method does not leak the provider argument into the
    workflow engine's signature.
    """

    def __init__(
        self,
        *,
        schema_provider: CasillaSchemaProvider,
    ) -> None:
        """Store the registry-backed schema provider."""
        self._schema_provider: CasillaSchemaProvider = schema_provider

    def build(
        self,
        *,
        modelo: str,
        period: Period,
        profile: TaxpayerProfile,
        inputs: ModeloInputs,
        fail_on_warning: bool = False,
    ) -> RegistryModeloDraftProtocol:
        """Delegate to :func:`build_draft` and return a :class:`RegistryModeloDraftProtocol`.

        :class:`TaxpayerProfile` lacks ``display_name`` required by the
        :class:`~domain.filing.ModeloProfile` Protocol.
        :class:`_TaxpayerProfileBridge` bridges the gap without modifying
        either domain model.
        """
        bridged_profile = _TaxpayerProfileBridge(tax_id=profile.tax_id)
        draft: ModeloDraft = build_draft(
            modelo=modelo,
            period=period,
            profile=bridged_profile,
            inputs=inputs,
            schema_provider=self._schema_provider,
            fail_on_warning=fail_on_warning,
        )
        return draft


class SubmissionEngineAdapter:
    """Wrap :class:`~domain.submission.SubmissionEngine` as a workflow Protocol.

    The adapter uses the engine's public preflight method so the
    workflow's ``RUNNING_PREFLIGHT`` stage can execute the gate without
    exposing any AEAT write operation.
    """

    def __init__(self, engine: SubmissionEngine) -> None:
        """Store the wrapped :class:`SubmissionEngine`."""
        self._engine = engine

    def preflight(
        self,
        draft: RegistryModeloDraftProtocol,
        *,
        today: date,
        skip_deadline_window: bool = False,
        skip_auth_readiness: bool = False,
    ) -> None:
        """Delegate to the engine's public preflight method."""
        self._engine.preflight(
            draft,
            today=today,
            skip_deadline_window=skip_deadline_window,
            skip_auth_readiness=skip_auth_readiness,
        )


def default_engine(
    *,
    submission_engine: SubmissionEngineProtocol | None = None,
    deadline_engine: DeadlineEngineProtocol | None = None,
    filing_draft_builder: ModeloDraftBuilderProtocol | None = None,
    session: object | None = None,
    expedientes_source: ExpedientesSource | None = None,
    certificate_bundle: CertificateBundleProtocol | None = None,
    inputs_provider: ModeloInputsProviderProtocol | None = None,
    settings: Settings | None = None,
) -> WorkflowEngine:
    """Build a :class:`WorkflowEngine` wired to the production components.

    Args:
        submission_engine: Required :class:`SubmissionEngineProtocol`. ``None`` triggers
            a :class:`WorkflowError`. The caller
            must build the real :class:`SubmissionEngine` themselves
            (the composition is complex and owned by the CLI root
            command wiring) and pass it wrapped or pre-adapted.
        deadline_engine: Required :class:`DeadlineEngineProtocol`. ``None`` triggers
            a :class:`WorkflowError`; deadlines are mandatory for the
            workflow to have any obligation to work on.
        filing_draft_builder: Required :class:`ModeloDraftBuilderProtocol`.
            ``None`` triggers a :class:`WorkflowError`.
        session: Optional authenticated session handle supplied by the composition root.
            ``None`` skips both the inbox probe and the already-filed
            probe (both stages record a "not wired" diagnostic).
        expedientes_source: Optional outward-composed live expediente reader.
        certificate_bundle: Optional :class:`CertificateBundleProtocol`.
        inputs_provider: Required :class:`ModeloInputsProviderProtocol`. Sensitive draft
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
    if submission_engine is None:
        raise WorkflowError(
            translated_message="application.workflow.errors.adapter_missing_submission_engine",
        )
    if deadline_engine is None:
        raise WorkflowError(
            translated_message="application.workflow.errors.adapter_missing_deadline_engine",
        )
    if filing_draft_builder is None:
        raise WorkflowError(
            translated_message="application.workflow.errors.adapter_missing_filing_draft_builder",
        )
    if inputs_provider is None:
        raise WorkflowError(
            translated_message="application.workflow.errors.adapter_missing_inputs_provider",
        )
    return WorkflowEngine(
        deadline_engine=deadline_engine,
        filing_draft_builder=filing_draft_builder,
        submission_engine=submission_engine,
        session=session,
        certificate_bundle=certificate_bundle,
        inputs_provider=inputs_provider,
        settings=cfg,
        expedientes_source=expedientes_source,
        # A workflow has no active-bucket input. Do not bypass the canonical
        # bucket-scoped capture_notifications application facade merely to
        # populate this transient preflight; the inbox stage remains NOT_WIRED.
        notifications_source=None,
    )


__all__ = [
    "DeadlineEngineAdapter",
    "ModeloDraftBuilderAdapter",
    "SubmissionEngineAdapter",
    "default_engine",
]
