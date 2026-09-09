"""Source-specific reconciliation for calendar filing evidence.

These adapters project already-loaded local, filed-declaration, calculation,
and justificante-capture observations.  The calendar evidence facade owns
precedence, merging, and event enrichment; this module owns source-shape
validation and evidence-row construction.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ...core.aeat_csv import normalise_aeat_csv
from ...core.identity import same_tax_identifier
from ...core.period import Period as _Period
from ...domain.modelos.filing_record import is_justificante_backed_external_evidence
from ..calculations.observations_repository import (
    ObservationSourceKind,
    is_official_aeat_observation_source,
)
from .calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCalendarFilingEvidence,
    OverviewLocalFilingState,
)

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.sede.schema import FiledDeclaracionObservation
    from ...domain.justificante import Justificante
    from ...domain.modelos.filing_record import ModeloRecord
    from ..calculations.observations_repository import ObservationEnvelopePayload
    from ..live.justificante import JustificanteCaptureSnapshot


@dataclass(frozen=True, slots=True)
class _CalculationObservationEvidenceInput:
    """Validated coordinates needed to project one calculation observation."""

    source_kind: ObservationSourceKind
    source_metadata: Mapping[str, object]
    modelo: str
    filing_year: int
    period: _Period
    aeat_reference_id: str


def _justificantes_by_csv(justificantes: tuple[Justificante, ...]) -> dict[str, tuple[Justificante, ...]]:
    """Index loaded justificante metadata by CSV/reference identifier."""
    grouped: dict[str, list[Justificante]] = {}
    for justificante in justificantes:
        csv = justificante.csv.strip()
        if csv:
            grouped.setdefault(_justificante_csv_key(csv), []).append(justificante)
    return {key: tuple(values) for key, values in grouped.items()}


def _justificante_csv_key(csv: str) -> str:
    """Return the canonical lookup key for AEAT CSV identifiers.

    Delegates to the one comparison form rather than restating it. This site
    previously casefolded, which produced a lowercase key that the canonical
    uppercase contract refuses -- so one identifier had two keys depending on
    which surface built it.
    """
    return normalise_aeat_csv(csv)


def _filing_evidence_from_modelo_record(
    record: ModeloRecord,
    *,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> OverviewCalendarFilingEvidence | None:
    """Project one local Modelo filing record into calendar evidence."""
    if record.status.value.lower() != "vigente":
        return None
    return _filing_axes_from_modelo_record(
        record,
        justificantes_by_csv=justificantes_by_csv,
        expected_tax_id=expected_tax_id,
    )


def _filing_axes_from_modelo_record(
    record: ModeloRecord,
    *,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> OverviewCalendarFilingEvidence:
    """Return the local and AEAT filing axes for one Modelo filing record."""
    modelo = str(record.modelo)
    filing_year = int(record.filing_year)
    period = record.period
    external_evidence = record.external_evidence
    local_state = _local_filing_state_from_modelo_record(record)
    aeat_state = OverviewAeatSubmissionState.NOT_OBSERVED
    aeat_evidence_kind = None
    aeat_reference_id = None
    aeat_submitted_at = None
    justificante_verified = False
    verified_justificante_csv = None
    aeat_accepted = record.aeat_accepted
    if aeat_accepted and external_evidence is not None:
        aeat_state = OverviewAeatSubmissionState.ACCEPTED
    if external_evidence is not None:
        kind = getattr(external_evidence, "kind", None)
        aeat_evidence_kind = str(getattr(kind, "value", kind))
        aeat_reference_id = str(external_evidence.reference_id)
        if aeat_accepted and is_justificante_backed_external_evidence(external_evidence.kind):
            verified_justificante = _modelo_record_verified_justificante(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                reference_id=aeat_reference_id,
                justificantes_by_csv=justificantes_by_csv,
                expected_tax_id=expected_tax_id,
            )
            if verified_justificante is not None:
                aeat_state = OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
                aeat_submitted_at = verified_justificante.presented_at
                justificante_verified = True
                verified_justificante_csv = verified_justificante.csv
        elif aeat_accepted and aeat_state is OverviewAeatSubmissionState.NOT_OBSERVED:
            aeat_state = OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    return OverviewCalendarFilingEvidence(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        local_filing_state=local_state,
        local_filing_record_id=str(record.filing_record_id),
        local_calculation_revision_id=str(record.calculation_revision_id),
        local_filed_at=record.filed_at,
        aeat_submission_state=aeat_state,
        aeat_submitted_at=aeat_submitted_at,
        aeat_reference_id=aeat_reference_id,
        aeat_evidence_kind=aeat_evidence_kind,
        verified_justificante_csv=verified_justificante_csv,
        justificante_verified=justificante_verified,
        evidence_source="modelo_filing_record",
    )


def _modelo_record_verified_justificante(
    *,
    modelo: str,
    filing_year: int,
    period: _Period,
    reference_id: str,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> Justificante | None:
    """Return matching justificante metadata for a Modelo record external reference."""
    expected = (expected_tax_id or "").strip()
    if not expected:
        return None
    candidates = justificantes_by_csv.get(_justificante_csv_key(reference_id), ())
    matching = tuple(
        justificante
        for justificante in candidates
        if _justificante_matches_calendar_target(
            justificante,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            expected_tax_id=expected,
        )
    )
    if not matching or len(matching) != len(candidates):
        return None
    return matching[0]


def _justificante_matches_calendar_target(
    justificante: Justificante,
    *,
    modelo: str,
    filing_year: int,
    period: _Period,
    expected_tax_id: str,
) -> bool:
    return justificante.matches_filing_target(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        tax_id=expected_tax_id,
    )


def _local_filing_state_from_modelo_record(record: ModeloRecord) -> OverviewLocalFilingState:
    """Return the local-app axis for one current Modelo record.

    ``external_evidence`` is the AEAT axis and must not erase the local
    meaning of a filing record. A normal local filing that later receives live
    AEAT evidence remains ``ready_to_file``; only records created through the
    external baseline import command use the imported-baseline state.
    """
    filed_by = record.filed_by.strip().lower()
    if filed_by == "aeat-import" or filed_by.startswith("aeat-import:"):
        return OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED
    return OverviewLocalFilingState.READY_TO_FILE


def _filing_evidence_from_observed_event(
    event: OverviewCalendarEvent,
    *,
    expected_tax_id: str | None,
) -> OverviewCalendarFilingEvidence | None:
    """Project an active filing event into AEAT-side obligation evidence."""
    if event.event_type is not OverviewCalendarEventType.FILING:
        return None
    if event.modelo is None or event.filing_year is None or event.period is None:
        return None
    if event.status is not None and not _is_active_aeat_filing_status(event.status):
        return None
    state = event.aeat_submission_state
    if state is None:
        return None
    if not _authenticated_identity_matches_expected(event.authenticated_identity, expected_tax_id):
        return None
    return OverviewCalendarFilingEvidence(
        modelo=event.modelo,
        filing_year=event.filing_year,
        period=event.period,
        aeat_submission_state=state,
        aeat_submitted_at=event.aeat_submitted_at
        or datetime.combine(event.event_date, datetime.min.time(), tzinfo=UTC),
        aeat_reference_id=event.reference_id,
        aeat_snapshot_id=event.snapshot_id,
        verified_justificante_csv=event.verified_justificante_csv,
        justificante_verified=bool(event.justificante_verified),
        evidence_source=event.source,
    )


def _authenticated_identity_matches_expected(
    authenticated_identity: str | None,
    expected_tax_id: str | None,
) -> bool:
    if not expected_tax_id:
        return True
    return same_tax_identifier(authenticated_identity, expected_tax_id)


def _filing_evidence_from_filed_declaration_observation(
    observation: FiledDeclaracionObservation,
    *,
    expected_tax_id: str | None,
    verified_artefact_refs: frozenset[str],
    verified_artefact_csv_by_ref: Mapping[str, str],
) -> OverviewCalendarFilingEvidence | None:
    """Project one captured filed-declaration observation into evidence.

    The observation must belong to the expected authenticated identity and must
    be an active ``ALTA`` register row. Justificante verification is granted
    only when the storage layer has already verified and supplied the encrypted
    justificante artefact reference and CSV.
    """
    if expected_tax_id and not same_tax_identifier(observation.authenticated_identity, expected_tax_id):
        return None
    if not _is_active_aeat_filing_status(observation.status):
        return None
    verified_csv = _filed_declaration_verified_csv(
        observation,
        verified_artefact_refs=verified_artefact_refs,
        verified_artefact_csv_by_ref=verified_artefact_csv_by_ref,
    )
    verified = verified_csv is not None
    return OverviewCalendarFilingEvidence(
        modelo=observation.modelo,
        filing_year=observation.ejercicio,
        period=observation.period,
        aeat_submission_state=(
            OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
            if verified
            else OverviewAeatSubmissionState.SUBMITTED_OBSERVED
        ),
        aeat_submitted_at=observation.presented_at,
        aeat_reference_id=observation.expediente_id,
        aeat_evidence_kind="aeat_justificante_pdf" if verified else "filed_declaration_observation",
        verified_justificante_csv=verified_csv if verified else None,
        justificante_verified=verified,
        evidence_source="filed_declaration_observation",
    )


def _filed_declaration_verified_csv(
    observation: FiledDeclaracionObservation,
    *,
    verified_artefact_refs: frozenset[str],
    verified_artefact_csv_by_ref: Mapping[str, str],
) -> str | None:
    """Return the first storage-verified justificante CSV, if its CSV is known."""
    artefact = next(
        (item for item in observation.artefacts if _is_verified_justificante_artefact(item, verified_artefact_refs)),
        None,
    )
    if artefact is None or artefact.storage_ref is None:
        return None
    return verified_artefact_csv_by_ref.get(artefact.storage_ref) or None


def _is_verified_justificante_artefact(
    artefact: object,
    verified_artefact_refs: frozenset[str],
) -> bool:
    """Whether one observation artefact is a storage-verified justificante PDF."""
    kind = getattr(artefact, "kind", None)
    storage_ref = getattr(artefact, "storage_ref", None)
    return kind == "justificante_pdf" and storage_ref is not None and storage_ref in verified_artefact_refs


def _is_active_aeat_filing_status(status: str | None) -> bool:
    """Return whether an AEAT register row represents the current accepted filing."""
    return (status or "").strip().upper() == "ALTA"


def _filing_evidence_from_calculation_observation(
    payload: ObservationEnvelopePayload,
    *,
    expected_tax_id: str | None,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
) -> OverviewCalendarFilingEvidence | None:
    """Project official calculation observations into AEAT-submitted evidence.

    Only official AEAT source kinds with active register metadata are accepted.
    A matching loaded :class:`~cadrumo.domain.justificante.Justificante` upgrades
    the row to :attr:`OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED`;
    otherwise the row remains submitted-observed evidence.
    """
    target = _calculation_observation_evidence_input(payload, expected_tax_id=expected_tax_id)
    if target is None:
        return None
    verified_justificante = _calculation_observation_verified_justificante(
        modelo=target.modelo,
        filing_year=target.filing_year,
        period=target.period,
        source_metadata=target.source_metadata,
        justificantes_by_csv=justificantes_by_csv,
        expected_tax_id=expected_tax_id,
    )
    verified = verified_justificante is not None
    return OverviewCalendarFilingEvidence(
        modelo=target.modelo,
        filing_year=target.filing_year,
        period=target.period,
        aeat_submission_state=(
            OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
            if verified
            else OverviewAeatSubmissionState.SUBMITTED_OBSERVED
        ),
        aeat_submitted_at=verified_justificante.presented_at
        if verified_justificante is not None
        else payload.captured_at,
        aeat_reference_id=target.aeat_reference_id,
        aeat_evidence_kind=target.source_kind.value,
        verified_justificante_csv=verified_justificante.csv if verified_justificante is not None else None,
        justificante_verified=verified,
        evidence_source=target.source_kind.value,
    )


def _calculation_observation_evidence_input(
    payload: ObservationEnvelopePayload,
    *,
    expected_tax_id: str | None,
) -> _CalculationObservationEvidenceInput | None:
    """Validate official register metadata and resolve the observation period."""
    source_kind = payload.source_kind
    source_metadata = payload.source_metadata
    if not is_official_aeat_observation_source(source_kind) or not source_metadata:
        return None
    if not _is_active_aeat_filing_status(str(source_metadata.get("aeat_register_status", "")).strip()):
        return None
    aeat_reference_id = str(source_metadata.get("aeat_expediente_id") or "").strip()
    if not aeat_reference_id:
        return None
    authenticated_identity = str(source_metadata.get("authenticated_identity", ""))
    if expected_tax_id and not same_tax_identifier(authenticated_identity, expected_tax_id):
        return None
    observation = payload.observation
    period = _calculation_observation_period(observation.filing_year, observation.period, observation.filing_period)
    if period is None:
        return None
    return _CalculationObservationEvidenceInput(
        source_kind=source_kind,
        source_metadata=source_metadata,
        modelo=str(observation.modelo),
        filing_year=observation.filing_year,
        period=period,
        aeat_reference_id=aeat_reference_id,
    )


def _calculation_observation_period(
    filing_year: int,
    registry_token: str,
    filing_period: _Period | None,
) -> _Period | None:
    """Return a consistent observation period, deriving it for administrative rows."""
    if filing_period is not None:
        return filing_period if filing_period.filing_year == filing_year else None
    # filing_period is derived at construction from filing_year and period,
    # so it is absent only when a caller passed None explicitly. The model
    # permits that, so the fallback stays live rather than being deleted as
    # unreachable.
    try:
        return _period_from_registry_token(filing_year, registry_token)
    except ValueError:
        return None


def _calculation_observation_verified_justificante(
    *,
    modelo: str,
    filing_year: int,
    period: _Period,
    source_metadata: Mapping[str, object],
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> Justificante | None:
    """Resolve filed-history observation metadata to matching persisted justificante metadata."""
    expected = str(expected_tax_id or source_metadata.get("authenticated_identity") or "").strip()
    if not expected:
        return None
    for csv in _metadata_justificante_csv_candidates(source_metadata):
        candidates = justificantes_by_csv.get(_justificante_csv_key(csv), ())
        matching = tuple(
            justificante
            for justificante in candidates
            if _justificante_matches_calendar_target(
                justificante,
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                expected_tax_id=expected,
            )
        )
        if not matching or len(matching) != len(candidates):
            continue
        return matching[0]
    return None


def _filing_evidence_from_justificante_capture_snapshot(
    snapshot: JustificanteCaptureSnapshot,
    *,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> OverviewCalendarFilingEvidence | None:
    """Project one verified live justificante capture into AEAT-side evidence.

    The persisted snapshot is accepted only when it is active, carries a typed
    :class:`~cadrumo.core.Period`, and resolves to loaded
    :class:`~cadrumo.domain.justificante.Justificante` metadata for the same filing
    target.
    """
    if not _capture_snapshot_is_active(snapshot):
        return None
    if snapshot.period.filing_year != snapshot.filing_year:
        return None
    verified_justificante = _capture_snapshot_verified_justificante(
        snapshot,
        justificantes_by_csv=justificantes_by_csv,
        expected_tax_id=expected_tax_id,
    )
    if verified_justificante is None:
        return None
    source_kind = str(getattr(snapshot, "source_kind", "aeat_sede_live_capture") or "aeat_sede_live_capture")
    return OverviewCalendarFilingEvidence(
        modelo=snapshot.modelo,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
        aeat_submission_state=OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED,
        aeat_submitted_at=verified_justificante.presented_at,
        aeat_reference_id=snapshot.expediente_id,
        aeat_snapshot_id=snapshot.snapshot_id,
        aeat_evidence_kind=source_kind,
        verified_justificante_csv=verified_justificante.csv,
        justificante_verified=True,
        evidence_source=source_kind,
    )


def _capture_snapshot_is_active(snapshot: JustificanteCaptureSnapshot) -> bool:
    state = getattr(snapshot, "state", None)
    return str(getattr(state, "value", state)).strip().lower() == "active"


def _capture_snapshot_verified_justificante(
    snapshot: JustificanteCaptureSnapshot,
    *,
    justificantes_by_csv: Mapping[str, tuple[Justificante, ...]],
    expected_tax_id: str | None,
) -> Justificante | None:
    expected = (expected_tax_id or "").strip()
    candidates = justificantes_by_csv.get(_justificante_csv_key(snapshot.csv), ())
    matching = tuple(
        justificante
        for justificante in candidates
        if _justificante_matches_calendar_target(
            justificante,
            modelo=snapshot.modelo,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
            expected_tax_id=expected or justificante.tax_id,
        )
    )
    if not matching or len(matching) != len(candidates):
        return None
    return matching[0]


def _metadata_justificante_csv_candidates(source_metadata: Mapping[str, object]) -> tuple[str, ...]:
    """Return normalized single/plural justificante CSV metadata candidates."""
    csvs: list[str] = []
    for key in ("aeat_justificante_csv", "justificante_csv"):
        value = source_metadata.get(key)
        cleaned = str(value or "").strip()
        if cleaned:
            csvs.append(cleaned)
    plural = str(source_metadata.get("aeat_justificante_csvs") or "").strip()
    if plural:
        csvs.extend(item.strip() for item in plural.split(",") if item.strip())
    return tuple(dict.fromkeys(csvs))


def _period_from_registry_token(filing_year: int, registry_token: str) -> _Period:
    return _Period.from_year_and_code(filing_year, registry_token)


authenticated_identity_matches_expected = _authenticated_identity_matches_expected
filing_axes_from_modelo_record = _filing_axes_from_modelo_record
filing_evidence_from_calculation_observation = _filing_evidence_from_calculation_observation
filing_evidence_from_filed_declaration_observation = _filing_evidence_from_filed_declaration_observation
filing_evidence_from_justificante_capture_snapshot = _filing_evidence_from_justificante_capture_snapshot
filing_evidence_from_modelo_record = _filing_evidence_from_modelo_record
filing_evidence_from_observed_event = _filing_evidence_from_observed_event
is_active_aeat_filing_status = _is_active_aeat_filing_status
justificante_csv_key = _justificante_csv_key
justificantes_by_csv = _justificantes_by_csv

__all__ = [
    "authenticated_identity_matches_expected",
    "filing_axes_from_modelo_record",
    "filing_evidence_from_calculation_observation",
    "filing_evidence_from_filed_declaration_observation",
    "filing_evidence_from_justificante_capture_snapshot",
    "filing_evidence_from_modelo_record",
    "filing_evidence_from_observed_event",
    "is_active_aeat_filing_status",
    "justificante_csv_key",
    "justificantes_by_csv",
]
