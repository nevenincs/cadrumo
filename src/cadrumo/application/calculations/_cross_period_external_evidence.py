"""External-evidence validation for cross-period filing history."""

from __future__ import annotations

from collections.abc import Mapping

from ...adapters.persistence.profile.justificante import JustificanteRepository
from ...core.aeat_csv import normalise_aeat_csv
from ...domain.justificante import Justificante
from ...domain.modelos.filing_record import (
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    is_justificante_backed_external_evidence,
    is_receipt_bound_external_evidence,
)
from .cross_period_models import CrossPeriodCleanStateBlocker
from .observations_repository import ObservationSourceKind, is_official_aeat_observation_source


def filing_external_evidence_blockers(
    filing: ModeloRecord,
    observation_source_kind: str | None,
    justificante_repository: JustificanteRepository,
    taxpayer_tax_id: str | None,
    observation_source_metadata: Mapping[str, str] | None = None,
) -> list[CrossPeriodCleanStateBlocker]:
    """Return every filing-history blocker attributable to external evidence."""
    blockers: list[CrossPeriodCleanStateBlocker] = []
    if filing.status is not ModeloRecordStatus.VIGENTE:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD)
    if not filing.aeat_accepted:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_AEAT_ACCEPTANCE)
    if filing.external_evidence is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE)
        if not is_official_aeat_observation_source(observation_source_kind or ""):
            blockers.append(CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE)
    elif filing.external_evidence.kind is ExternalEvidenceKind.AEAT_CSV_REGISTER:
        metadata_reference = _clean_metadata_value(
            (observation_source_metadata or {}).get("external_evidence_reference_id"),
        )
        metadata_filing_id = _clean_metadata_value(
            (observation_source_metadata or {}).get("filing_record_id"),
        )
        if metadata_reference is None and metadata_filing_id is None:
            blockers.append(CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD)
        elif (
            observation_source_kind != ObservationSourceKind.AEAT_CSV_REGISTER.value
            or metadata_reference != filing.external_evidence.reference_id
            or metadata_filing_id != filing.filing_record_id
        ):
            blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
    elif not is_justificante_backed_external_evidence(filing.external_evidence.kind):
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION)
    elif is_receipt_bound_external_evidence(filing.external_evidence.kind):
        justificante = justificante_repository.load(filing.external_evidence.reference_id)
        if justificante is None:
            blockers.append(CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD)
        elif not _justificante_matches_filing_apart_from_owner(filing, justificante, taxpayer_tax_id=taxpayer_tax_id):
            blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
        elif _resolved_filing_identity(filing, taxpayer_tax_id) is None:
            blockers.append(CrossPeriodCleanStateBlocker.UNRESOLVED_TAXPAYER_IDENTITY)
        else:
            blockers.extend(_justificante_observation_reference_blockers(justificante, observation_source_metadata))
    return blockers


def _justificante_observation_reference_blockers(
    justificante: Justificante,
    observation_source_metadata: Mapping[str, str] | None,
) -> list[CrossPeriodCleanStateBlocker]:
    if not observation_source_metadata:
        return []
    blockers: list[CrossPeriodCleanStateBlocker] = []
    metadata_csv = _clean_metadata_csv(
        observation_source_metadata.get("aeat_justificante_csv") or observation_source_metadata.get("justificante_csv"),
    )
    receipt_csv = normalise_aeat_csv(justificante.csv)
    if metadata_csv is not None and metadata_csv != receipt_csv:
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
    metadata_csvs = _clean_metadata_csvs(observation_source_metadata.get("aeat_justificante_csvs"))
    if metadata_csvs and receipt_csv not in metadata_csvs:
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
    metadata_expediente_id = _clean_metadata_value(observation_source_metadata.get("aeat_expediente_id"))
    presentation_id = _clean_metadata_value(justificante.presentation_id)
    if metadata_expediente_id is not None:
        has_csv_reference = metadata_csv is not None or bool(metadata_csvs)
        if (presentation_id is None and not has_csv_reference) or (
            presentation_id is not None and metadata_expediente_id.casefold() != presentation_id.casefold()
        ):
            blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
    return blockers


def _clean_metadata_value(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _clean_metadata_csv(value: str | None) -> str | None:
    return normalise_aeat_csv(value or "") or None


def _clean_metadata_csvs(value: str | None) -> tuple[str, ...]:
    return tuple(dict.fromkeys(normalise_aeat_csv(item) for item in (value or "").split(",") if item.strip()))


def _resolved_filing_identity(filing: ModeloRecord, taxpayer_tax_id: str | None) -> str | None:
    expected_tax_id = filing.member_nif or taxpayer_tax_id
    if expected_tax_id is None or not expected_tax_id.strip():
        return None
    return expected_tax_id


def _justificante_matches_filing_apart_from_owner(
    filing: ModeloRecord,
    justificante: Justificante,
    *,
    taxpayer_tax_id: str | None,
) -> bool:
    resolved = _resolved_filing_identity(filing, taxpayer_tax_id)
    expected_tax_id = resolved if resolved is not None else justificante.tax_id
    if not expected_tax_id.strip():
        return False
    return justificante.matches_filing_target(
        modelo=str(filing.modelo),
        filing_year=filing.filing_year,
        period=filing.period,
        tax_id=expected_tax_id,
    )
