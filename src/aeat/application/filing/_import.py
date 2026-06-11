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
import re
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from zoneinfo import ZoneInfo

from ...adapters.inbound.justificante import parse_justificante
from ...core.logging import get_logger
from ...domain.filing import CasillaSchemaProvider, ModeloBuilderError, ModeloDraft, ModeloImportError
from ...domain.justificante import Justificante
from .runtime import ModeloOperatorProfile

if TYPE_CHECKING:
    from ...domain.submission import ModeloPresentado

_logger = get_logger(__name__)

_MADRID_TZ = ZoneInfo("Europe/Madrid")

_QUARTER_RE = re.compile(r"^([1-4])T$")
_MONTH_RE = re.compile(r"^(0[1-9]|1[0-2])$")
_ANNUAL_RE = re.compile(r"^0A$")
_YEAR_RE = re.compile(r"^\d{4}$")
_CANONICAL_QUARTER_RE = re.compile(r"^\d{4}Q[1-4]$")
_CANONICAL_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_CANONICAL_ANNUAL_RE = re.compile(r"^\d{4}A$")

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
    raw_period: str,
    schema_provider: RegistryImportSchemaProvider,
) -> str:
    """Canonicalise a printed AEAT period to the project's internal form.

    Quarterly period tokens (``"1T"..."4T"``) become
    ``"YYYYQ1"..."YYYYQ4"``. Monthly tokens (``"01"..."12"``) become
    ``"YYYY-MM"``. Annual tokens (``"0A"`` or the printed
    ejercicio itself) become ``"YYYYA"``. Already canonical inputs pass
    through unchanged.

    Args:
        modelo: The modelo string, used only for error messages.
        ejercicio: Four-digit tax year; required for any non-canonical
            input.
        raw_period: The period as printed on the justificante
            (``"1T"``, ``"12"``, ``"0A"``, ``"2026Q1"``, ...).
        schema_provider: Registry-backed schema provider used to look
            up the supported period tokens for the given modelo.

    Returns:
        The canonical period string.

    Raises:
        ModeloImportError: If the pair cannot be canonicalised.
    """
    try:
        subview = schema_provider.get_subview(modelo)
    except ModeloBuilderError as exc:
        raise ModeloImportError(f"modelo {modelo!r} is not present in the calculation registry") from exc
    supported_periods = set(subview.period_selector_periods)

    if match := _CANONICAL_QUARTER_RE.match(raw_period):
        return _require_supported_period_token(
            modelo=modelo,
            canonical=raw_period,
            period_code=f"{match.group(0)[-1]}T",
            supported_periods=supported_periods,
        )
    if match := _CANONICAL_MONTH_RE.match(raw_period):
        return _require_supported_period_token(
            modelo=modelo,
            canonical=raw_period,
            period_code=match.group(1),
            supported_periods=supported_periods,
        )
    if _CANONICAL_ANNUAL_RE.match(raw_period):
        return _require_supported_period_token(
            modelo=modelo,
            canonical=raw_period,
            period_code="0A",
            supported_periods=supported_periods,
        )

    if ejercicio is None:
        raise ModeloImportError(
            f"modelo {modelo}: justificante period {raw_period!r} requires an ejercicio to canonicalise",
        )
    if not re.fullmatch(r"\d{4}", ejercicio):
        raise ModeloImportError(f"modelo {modelo}: unexpected ejercicio {ejercicio!r}; want four-digit year")

    quarter_match = _QUARTER_RE.match(raw_period)
    if quarter_match is not None:
        quarter = quarter_match.group(1)
        return _require_supported_period_token(
            modelo=modelo,
            canonical=f"{ejercicio}Q{quarter}",
            period_code=f"{quarter}T",
            supported_periods=supported_periods,
        )
    month_match = _MONTH_RE.match(raw_period)
    if month_match is not None:
        month = month_match.group(1)
        return _require_supported_period_token(
            modelo=modelo,
            canonical=f"{ejercicio}-{month}",
            period_code=month,
            supported_periods=supported_periods,
        )
    if _ANNUAL_RE.match(raw_period):
        return _require_supported_period_token(
            modelo=modelo,
            canonical=f"{ejercicio}A",
            period_code="0A",
            supported_periods=supported_periods,
        )
    if _YEAR_RE.match(raw_period) and raw_period == ejercicio:
        return _require_supported_period_token(
            modelo=modelo,
            canonical=f"{ejercicio}A",
            period_code="0A",
            supported_periods=supported_periods,
        )

    raise ModeloImportError(f"modelo {modelo}: cannot canonicalise period {raw_period!r} for ejercicio {ejercicio!r}")


def _require_supported_period_token(
    *,
    modelo: str,
    canonical: str,
    period_code: str,
    supported_periods: set[str],
) -> str:
    if period_code not in supported_periods:
        raise ModeloImportError(
            f"modelo {modelo}: period token {period_code!r} is not declared by the active registry revision",
        )
    return canonical


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
        period=str(draft.period),
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
