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
    blockers = _filing_record_blockers(filing)
    if filing.external_evidence is None:
        return blockers + _missing_external_evidence_blockers(observation_source_kind)
    return blockers + _external_evidence_reference_blockers(
        filing,
        observation_source_kind,
        justificante_repository,
        taxpayer_tax_id,
        observation_source_metadata,
    )


def _filing_record_blockers(filing: ModeloRecord) -> list[CrossPeriodCleanStateBlocker]:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    if filing.status is not ModeloRecordStatus.VIGENTE:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD)
    if not filing.aeat_accepted:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_AEAT_ACCEPTANCE)
    return blockers


def _missing_external_evidence_blockers(
    observation_source_kind: str | None,
) -> list[CrossPeriodCleanStateBlocker]:
    blockers = [CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE]
    if not is_official_aeat_observation_source(observation_source_kind or ""):
        blockers.append(CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE)
    return blockers


def _external_evidence_reference_blockers(
    filing: ModeloRecord,
    observation_source_kind: str | None,
    justificante_repository: JustificanteRepository,
    taxpayer_tax_id: str | None,
    observation_source_metadata: Mapping[str, str] | None,
) -> list[CrossPeriodCleanStateBlocker]:
    evidence = filing.external_evidence
    if evidence is None:
        return []
    if evidence.kind is ExternalEvidenceKind.AEAT_CSV_REGISTER:
        return _csv_register_reference_blockers(filing, observation_source_kind, observation_source_metadata)
    if not is_justificante_backed_external_evidence(evidence.kind):
        return [CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION]
    if not is_receipt_bound_external_evidence(evidence.kind):
        return []
    return _receipt_reference_blockers(
        filing,
        justificante_repository,
        taxpayer_tax_id,
        observation_source_metadata,
    )


def _csv_register_reference_blockers(
    filing: ModeloRecord,
    observation_source_kind: str | None,
    observation_source_metadata: Mapping[str, str] | None,
) -> list[CrossPeriodCleanStateBlocker]:
    metadata = observation_source_metadata or {}
    metadata_reference = _clean_metadata_value(metadata.get("external_evidence_reference_id"))
    metadata_filing_id = _clean_metadata_value(metadata.get("filing_record_id"))
    if metadata_reference is None and metadata_filing_id is None:
        return [CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD]
    evidence = filing.external_evidence
    if evidence is None:
        return []
    if (
        observation_source_kind != ObservationSourceKind.AEAT_CSV_REGISTER.value
        or metadata_reference != evidence.reference_id
        or metadata_filing_id != filing.filing_record_id
    ):
        return [CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD]
    return []


def _receipt_reference_blockers(
    filing: ModeloRecord,
    justificante_repository: JustificanteRepository,
    taxpayer_tax_id: str | None,
    observation_source_metadata: Mapping[str, str] | None,
) -> list[CrossPeriodCleanStateBlocker]:
    evidence = filing.external_evidence
    if evidence is None:
        return []
    justificante = justificante_repository.load(evidence.reference_id)
    if justificante is None:
        return [CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD]
    if not _justificante_matches_filing_apart_from_owner(filing, justificante, taxpayer_tax_id=taxpayer_tax_id):
        return [CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD]
    if _resolved_filing_identity(filing, taxpayer_tax_id) is None:
        return [CrossPeriodCleanStateBlocker.UNRESOLVED_TAXPAYER_IDENTITY]
    return _justificante_observation_reference_blockers(justificante, observation_source_metadata)


def _justificante_observation_reference_blockers(
    justificante: Justificante,
    observation_source_metadata: Mapping[str, str] | None,
) -> list[CrossPeriodCleanStateBlocker]:
    if not observation_source_metadata:
        return []
    return [
        *_justificante_csv_reference_blockers(justificante, observation_source_metadata),
        *_justificante_expediente_reference_blockers(justificante, observation_source_metadata),
    ]


def _justificante_csv_reference_blockers(
    justificante: Justificante,
    observation_source_metadata: Mapping[str, str],
) -> list[CrossPeriodCleanStateBlocker]:
    metadata_csv = _clean_metadata_csv(
        observation_source_metadata.get("aeat_justificante_csv") or observation_source_metadata.get("justificante_csv"),
    )
    receipt_csv = normalise_aeat_csv(justificante.csv)
    blockers: list[CrossPeriodCleanStateBlocker] = []
    if metadata_csv is not None and metadata_csv != receipt_csv:
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
    metadata_csvs = _clean_metadata_csvs(observation_source_metadata.get("aeat_justificante_csvs"))
    if metadata_csvs and receipt_csv not in metadata_csvs:
        blockers.append(CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD)
    return blockers


def _justificante_expediente_reference_blockers(
    justificante: Justificante,
    observation_source_metadata: Mapping[str, str],
) -> list[CrossPeriodCleanStateBlocker]:
    metadata_expediente_id = _clean_metadata_value(observation_source_metadata.get("aeat_expediente_id"))
    if metadata_expediente_id is None:
        return []
    metadata_csv = _clean_metadata_csv(
        observation_source_metadata.get("aeat_justificante_csv") or observation_source_metadata.get("justificante_csv"),
    )
    metadata_csvs = _clean_metadata_csvs(observation_source_metadata.get("aeat_justificante_csvs"))
    has_csv_reference = metadata_csv is not None or bool(metadata_csvs)
    presentation_id = _clean_metadata_value(justificante.presentation_id)
    if (presentation_id is None and not has_csv_reference) or (
        presentation_id is not None and metadata_expediente_id.casefold() != presentation_id.casefold()
    ):
        return [CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD]
    return []


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
