"""Reconstruct a :class:`ModeloDraft` from an AEAT justificante PDF.

The operator keeps the justificante PDF of a past filing on disk. This
module parses the PDF via :mod:`aeat.adapters.inbound.justificante`,
materialises an empty draft scaffold (every casilla ``EMPTY``) via the
registered builder for the modelo, and co-produces a ``ModeloPresentado``
record so the import is usable as the baseline for amendment flows.

No AEAT certificate authentication or network call is involved — the
command is a pure offline transform from (PDF bytes) → (draft, submission,
warnings).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from zoneinfo import ZoneInfo

from ...adapters.inbound.justificante import parse_justificante
from ...core import Period, PeriodError
from ...core.logging import get_logger
from ...domain.filing import CasillaSchemaProvider, ModeloBuilderError, ModeloDraft, ModeloImportError
from ...domain.justificante import Justificante
from .runtime import ModeloOperatorProfile

if TYPE_CHECKING:
    from ...domain.submission import ModeloPresentado

_logger = get_logger(__name__)

_MADRID_TZ = ZoneInfo("Europe/Madrid")

_EMPTY_CASILLA_WARNING: str = "filing.import.empty_casilla_warning"


class _RegistryPeriodSubview(Protocol):
    period_selector_periods: tuple[str, ...]


class RegistryImportSchemaProvider(CasillaSchemaProvider, Protocol):
    """Combined casilla schema and period-subview provider used by the import path.

    Implementations must satisfy both the :class:`aeat.domain.filing.CasillaSchemaProvider`
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
    ``aeat.adapters.outbound.aeat.export`` package itself imports :mod:`aeat.application.filing`, so
    pulling ``ModeloPresentado`` in at module scope would cycle).

    Attributes:
        draft: The freshly built scaffold with every casilla empty.
        submission: The companion :class:`aeat.domain.submission.ModeloPresentado`
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

    # Deferred import: `aeat.application.filing` imports this module, so top-level
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
        raise ModeloImportError(f"cannot import modelo {justificante.modelo!r}: {exc}") from exc

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
    year-only annual receipts to :class:`aeat.core.Period` before this
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
        raise ModeloImportError(f"modelo {modelo!r} is not present in the calculation registry") from exc
    supported_periods = set(subview.period_selector_periods)

    if ejercicio is not None and (len(ejercicio) != 4 or not ejercicio.isdigit()):
        raise ModeloImportError(f"modelo {modelo}: unexpected ejercicio {ejercicio!r}; want four-digit year")
    if ejercicio is not None and raw_period.filing_year != int(ejercicio):
        raise ModeloImportError(
            f"modelo {modelo}: cannot canonicalise period {raw_period!s} for ejercicio {ejercicio!r}",
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
            f"modelo {modelo}: period token {period_code!r} is not declared by the active registry revision",
        )
    try:
        return Period.from_year_and_code(filing_year, period_code)
    except PeriodError as exc:
        raise ModeloImportError(
            f"modelo {modelo}: period token {period_code!r} cannot be represented as a core Period",
        ) from exc


def _build_submission_record(
    *,
    justificante: Justificante,
    draft: ModeloDraft,
) -> ModeloPresentado:
    """Build the companion :class:`ModeloPresentado` for an import.

    The ``submission_id`` hashes the CSV and the draft id together so it
    stays stable across re-imports of the same PDF and remains distinct
    from locally-created attempt ids.
    """
    from ...domain.submission import ModeloPresentado, SubmissionAttempt, SubmissionStatus

    submitted_at = justificante.presented_at.replace(tzinfo=_MADRID_TZ).astimezone(UTC)
    submission_id = hashlib.sha256(f"{justificante.csv}:{draft.draft_id}".encode()).hexdigest()[:16]
    attempt = SubmissionAttempt(
        attempt_id=f"{submission_id}.1",
        started_at=submitted_at,
        ended_at=submitted_at,
        status=SubmissionStatus.PRESENTADA,
    )
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id=draft.draft_id,
        modelo=draft.modelo,
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
