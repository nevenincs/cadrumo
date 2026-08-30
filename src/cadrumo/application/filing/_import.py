"""Reconstruct a :class:`~domain.filing.ModeloDraft` from an AEAT justificante PDF.

The operator keeps the justificante PDF of a past filing on disk. This
module parses the PDF into a :class:`~domain.justificante.Justificante`
via :func:`adapters.inbound.justificante.parse_justificante`, validates
the printed period against the active registry subview, asks
:func:`application.filing.build_draft` to materialise an empty draft
scaffold, and co-produces a companion
:class:`~domain.submission.ModeloPresentado` record so the import can be
used as an amendment baseline.

The justificante is receipt metadata, not a full casilla-value source. When
the active registry requires inputs or binding values that the receipt cannot
provide, import fails with :class:`~domain.filing.ModeloImportError`
instead of fabricating tax values.

No AEAT certificate authentication or network call is involved — the
command is a pure offline transform from (PDF bytes) → (draft, submission,
warnings).

This is not the production external-evidence import path for current filing
records. It does not create a :class:`~ModeloRecord`, attach
:class:`~ExternalEvidence`, or infer missing casilla values
from receipt metadata.

See Also:
    :mod:`adapters.inbound.justificante`
        Local PDF parser that extracts the typed receipt record.
    :func:`application.filing.build_runtime_schema_provider`
        Registry-backed schema provider used to validate supported periods
        and build the draft scaffold.
    :func:`application.filing.build_complementaria`
        Amendment flow that can consume the imported submission baseline.
    :func:`application.modelo.import_external_filing_evidence`
        External-evidence import path that builds the current
        :class:`~ModeloRecord` baseline consumed by
        work-unit amendments.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ...adapters.inbound.justificante.parser import parse_justificante
from ...core import Modelo
from ...core.period import Period, PeriodError
from ...core.logging import get_logger
from ...core.time import MADRID_TZ
from ...domain.filing.errors import ModeloBuilderError
from ...domain.filing.protocols import CasillaSchemaProvider
from ...domain.filing.schema import ModeloDraft
from ...domain.justificante import Justificante
from .errors import ModeloApplicationError as ModeloImportError
from .runtime import ModeloOperatorProfile

if TYPE_CHECKING:
    from ...domain.submission import ModeloPresentado

_logger = get_logger(__name__)

_EMPTY_CASILLA_WARNING: str = "filing.import.empty_casilla_warning"


class _RegistryPeriodSubview(Protocol):
    period_selector_periods: tuple[str, ...]


class RegistryImportSchemaProvider(CasillaSchemaProvider, Protocol):
    """Combined casilla schema and period-subview provider used by the import path.

    Implementations must satisfy both the :class:`domain.filing.CasillaSchemaProvider`
    contract (for draft construction) and expose ``get_subview`` so
    :func:`import_filing_from_justificante` can look up the supported
    period tokens for a given modelo during period canonicalisation.
    The production implementation is ``build_runtime_schema_provider()``.
    """

    def get_subview(self, modelo: str) -> _RegistryPeriodSubview: ...


@dataclass(frozen=True, slots=True)
class JustificanteImportResult:
    """Outcome of a :func:`import_filing_from_justificante` call.

    The container is deliberately a frozen dataclass rather than a
    pydantic model because it wraps two already-validated pydantic
    records and defers the ``ModeloPresentado`` type to runtime (the
    ``cadrumo.adapters.outbound.aeat.export`` package itself imports :mod:`application.filing`, so
    pulling ``ModeloPresentado`` in at module scope would cycle).

    Attributes:
        draft: The freshly built :class:`~domain.filing.ModeloDraft` scaffold.
        submission: The companion :class:`~domain.submission.ModeloPresentado`
            that lets the amendment engine treat the imported draft as a
            baseline.
        warnings: Multilingual advisory messages. The CLI renders these so
            the operator knows which fields still need input.
    """

    draft: ModeloDraft
    submission: ModeloPresentado
    warnings: tuple[str, ...]


def import_filing_from_justificante(
    pdf_path: Path,
    *,
    schema_provider: RegistryImportSchemaProvider,
) -> JustificanteImportResult:
    """Reconstruct a draft + submission record from a justificante PDF.

    Args:
        pdf_path: Path to the justificante PDF on disk. Must exist.
        schema_provider: Casilla schema provider used by the filing
            builder. Callers typically pass
            ``build_runtime_schema_provider()``.

    Returns:
        A :class:`JustificanteImportResult` with ``draft``, companion
        ``submission``, and any advisory warnings.

    Raises:
        ModeloImportError: If the modelo has no registered builder or
            the printed period cannot be canonicalised.
    """
    justificante = parse_justificante(pdf_path)
    period = _normalise_period(
        modelo=justificante.modelo,
        ejercicio=justificante.ejercicio,
        raw_period=justificante.period,
        schema_provider=schema_provider,
    )
    profile = ModeloOperatorProfile(
        tax_id=justificante.tax_id,
        display_name=f"Imported filing {justificante.csv}",
    )

    # Deferred import: `cadrumo.application.filing` imports this module, so top-level
    # resolution of ``build_draft`` would form a cycle.
    from . import build_draft

    try:
        draft = build_draft(
            modelo=justificante.modelo,
            period=period,
            profile=profile,
            inputs={},
            schema_provider=schema_provider,
        )
    except ModeloBuilderError as exc:
        raise ModeloImportError(
            translated_message="application.filing.errors.import_failed",
            context={"modelo": repr(justificante.modelo), "detail": str(exc)},
        ) from exc

    submission = _build_submission_record(justificante=justificante, draft=draft)
    warnings: tuple[str, ...] = (_EMPTY_CASILLA_WARNING,)
    _logger.debug(
        "imported justificante csv=%s modelo=%s period=%s → draft_id=%s submission_id=%s",
        justificante.csv,
        justificante.modelo,
        period,
        draft.draft_id,
        submission.submission_id,
    )
    return JustificanteImportResult(draft=draft, submission=submission, warnings=warnings)


def _normalise_period(
    *,
    modelo: str,
    ejercicio: str | None,
    raw_period: Period,
    schema_provider: RegistryImportSchemaProvider,
) -> Period:
    """Validate a parsed justificante period against the active registry.

    The inbound justificante parser resolves printed AEAT tokens and
    year-only annual receipts to :class:`core.Period` before this
    import service builds filing records. This helper only confirms that
    the typed period matches the printed ``ejercicio`` and is declared by
    the active registry revision.

    Args:
        modelo: The modelo string, used only for error messages.
        ejercicio: Four-digit tax year printed on the justificante, when
            present.
        raw_period: Typed filing period parsed from the justificante.
        schema_provider: Registry-backed schema provider used to look
            up the supported period tokens for the given modelo.

    Returns:
        The typed filing period.

    Raises:
        ModeloImportError: If the pair cannot be canonicalised.
    """
    try:
        subview = schema_provider.get_subview(modelo)
    except ModeloBuilderError as exc:
        raise ModeloImportError(
            translated_message="application.filing.errors.modelo_not_in_registry",
            context={"modelo": repr(modelo)},
        ) from exc
    supported_periods = set(subview.period_selector_periods)

    if ejercicio is not None and (len(ejercicio) != 4 or not ejercicio.isdigit()):
        raise ModeloImportError(
            translated_message="application.filing.errors.unexpected_ejercicio",
            context={"modelo": modelo, "ejercicio": repr(ejercicio)},
        )
    if ejercicio is not None and raw_period.filing_year != int(ejercicio):
        raise ModeloImportError(
            translated_message="application.filing.errors.period_ejercicio_mismatch",
            context={"modelo": modelo, "period": str(raw_period), "ejercicio": repr(ejercicio)},
        )

    return _require_supported_period_token(
        modelo=modelo,
        filing_year=raw_period.filing_year,
        period_code=raw_period.registry_token,
        supported_periods=supported_periods,
    )


def _require_supported_period_token(
    *,
    modelo: str,
    filing_year: int,
    period_code: str,
    supported_periods: set[str],
) -> Period:
    if period_code not in supported_periods:
        raise ModeloImportError(
            translated_message="application.filing.import.errors.period_token_undeclared",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period_code": period_code,
                "supported_period_count": len(supported_periods),
            },
        )
    try:
        return Period.from_year_and_code(filing_year, period_code)
    except PeriodError as exc:
        raise ModeloImportError(
            translated_message="application.filing.import.errors.period_token_unrepresentable",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period_code": period_code,
            },
        ) from exc


def _build_submission_record(
    *,
    justificante: Justificante,
    draft: ModeloDraft,
) -> ModeloPresentado:
    """Build the companion :class:`~domain.submission.ModeloPresentado` for an import.

    The imported receipt is the first attempt for its draft, so identity comes
    from the submission domain's canonical ``(draft_id, attempt_ordinal)``
    coordinate. Naive receipt times retain the importer contract of Madrid
    civil time; aware receipt times retain their supplied instant.
    """
    from ...domain.submission import ModeloPresentado, SubmissionAttempt, SubmissionStatus, make_submission_id

    presented_at = justificante.presented_at
    if presented_at.utcoffset() is None:
        presented_at = presented_at.replace(tzinfo=MADRID_TZ)
    submitted_at = presented_at.astimezone(UTC)
    attempt_ordinal = 1
    submission_id = make_submission_id(draft.draft_id, attempt_ordinal)
    attempt = SubmissionAttempt(
        attempt_id=f"{submission_id}.{attempt_ordinal}",
        started_at=submitted_at,
        ended_at=submitted_at,
        status=SubmissionStatus.PRESENTADA,
    )
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id=draft.draft_id,
        modelo=Modelo(draft.modelo),
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        status=SubmissionStatus.PRESENTADA,
        justificante_csv=justificante.csv,
        justificante_pdf_path=justificante.source_pdf_path,
        submitted_at=submitted_at,
        acknowledged_at=None,
        attempts=(attempt,),
    )


__all__ = [
    "JustificanteImportResult",
    "import_filing_from_justificante",
]
