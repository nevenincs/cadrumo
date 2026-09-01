"""Modelo 145 local communication payload schemas.

Strict :class:`~core.json_contract.OutputSchema` projections for the
``aeat app modelo m145`` commands. The payloads translate application DTOs into
stable JSON envelopes while preserving registry legal/source references and
local communication state.

See Also:
    CommandSpec schema authority
        Each operation's CommandSpec owns its lazy public OutputSchema target.
    :mod:`~entrypoints.cli._modelo_m145_cli`
        Behavior handlers that emit these payloads.
    :mod:`~entrypoints.cli._modelo_m145_rendering`
        Renderer that converts application results into these payload classes.
    :class:`~application.modelo.M145CommunicationRecord`
        Persisted record projected by :class:`M145CommunicationRecordPayload`.
    :class:`~application.modelo.M145CommunicationValidationResult`
        Backend validation result represented by
        :class:`M145CommunicationValidationResultPayload`.
    :class:`~application.modelo.M145CommunicationExportResult`
        Backend export result represented by
        :class:`M145CommunicationExportResultPayload`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...core.identity import BucketId
from ...core.json_contract import OutputSchema
from ...domain.calculations.registry.ids import LegalRefId, RevisionId, SourceRefId

if TYPE_CHECKING:
    from ...application.modelo.m145_communication_records import (
        M145CommunicationExportResult,
        M145CommunicationRecord,
        M145CommunicationValidationIssue,
        M145CommunicationValidationResult,
    )


class M145CommunicationRecordPayload(OutputSchema):
    """JSON projection of one persisted Modelo 145 local communication record."""

    communication_record_id: str
    bucket_id: BucketId
    service_owner: str
    modelo: str
    communication_year: int
    period_token: str
    revision_id: RevisionId
    state: str
    field_values: dict[CasillaId, str]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    created_at: str
    delivered_to_payer_at: str | None = None
    locally_completed_at: str | None = None
    note: str | None = None

    @classmethod
    def from_record(cls, record: M145CommunicationRecord) -> M145CommunicationRecordPayload:
        return cls(
            communication_record_id=record.communication_record_id,
            bucket_id=record.bucket_id,
            service_owner=record.service_owner,
            modelo=record.modelo,
            communication_year=record.communication_year,
            period_token=record.period_token.value,
            revision_id=record.revision_id,
            state=record.state.value,
            field_values={key: str(value) for key, value in sorted(record.field_values.items())},
            legal_refs=tuple(record.legal_refs),
            source_refs=tuple(record.source_refs),
            created_at=record.created_at.isoformat(),
            delivered_to_payer_at=record.delivered_to_payer_at.isoformat()
            if record.delivered_to_payer_at is not None
            else None,
            locally_completed_at=record.locally_completed_at.isoformat()
            if record.locally_completed_at is not None
            else None,
            note=record.note,
        )


class M145CommunicationRecordResult(OutputSchema):
    """Envelope payload for Modelo 145 local communication record mutations."""

    operation: str
    record: M145CommunicationRecordPayload


class M145CommunicationValidationIssuePayload(OutputSchema):
    """One registry-backed issue returned by Modelo 145 communication validation."""

    kind: str
    casilla_id: CasillaId | None = None
    data_type: str | None = None
    message: str
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]

    @classmethod
    def from_issue(cls, issue: M145CommunicationValidationIssue) -> M145CommunicationValidationIssuePayload:
        return cls(
            kind=issue.kind.value,
            casilla_id=issue.casilla_id,
            data_type=issue.data_type,
            message=issue.message,
            legal_refs=tuple(issue.legal_refs),
            source_refs=tuple(issue.source_refs),
        )


class M145CommunicationValidationResultPayload(OutputSchema):
    """Envelope payload for Modelo 145 local communication validation."""

    operation: str = "modelo.m145.validate"
    communication_record_id: str
    bucket_id: BucketId
    service_owner: str
    modelo: str
    communication_year: int
    period_token: str
    revision_id: RevisionId
    valid: bool
    issue_count: int
    issues: tuple[M145CommunicationValidationIssuePayload, ...]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]

    @classmethod
    def from_result(cls, result: M145CommunicationValidationResult) -> M145CommunicationValidationResultPayload:
        return cls(
            communication_record_id=result.communication_record_id,
            bucket_id=result.bucket_id,
            service_owner=result.service_owner,
            modelo=result.modelo,
            communication_year=result.communication_year,
            period_token=result.period_token.value,
            revision_id=result.revision_id,
            valid=result.valid,
            issue_count=result.issue_count,
            issues=tuple(M145CommunicationValidationIssuePayload.from_issue(issue) for issue in result.issues),
            legal_refs=tuple(result.legal_refs),
            source_refs=tuple(result.source_refs),
        )


class M145CommunicationExportResultPayload(OutputSchema):
    """Envelope payload for Modelo 145 local communication export."""

    operation: str = "modelo.m145.export"
    communication_record_id: str
    bucket_id: BucketId
    service_owner: str
    modelo: str
    communication_year: int
    period_token: str
    revision_id: RevisionId
    export_layout_id: str
    encoding: str
    record_count: int
    byte_length: int
    payload_sha256: str
    payload_text: str
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]

    @classmethod
    def from_result(cls, result: M145CommunicationExportResult) -> M145CommunicationExportResultPayload:
        return cls(
            communication_record_id=result.communication_record_id,
            bucket_id=result.bucket_id,
            service_owner=result.service_owner,
            modelo=result.modelo,
            communication_year=result.communication_year,
            period_token=result.period_token.value,
            revision_id=result.revision_id,
            export_layout_id=result.export_layout_id,
            encoding=result.encoding,
            record_count=result.record_count,
            byte_length=result.byte_length,
            payload_sha256=result.payload_sha256,
            payload_text=result.payload.decode(result.encoding),
            legal_refs=tuple(result.legal_refs),
            source_refs=tuple(result.source_refs),
        )


__all__ = [
    "M145CommunicationExportResultPayload",
    "M145CommunicationRecordPayload",
    "M145CommunicationRecordResult",
    "M145CommunicationValidationIssuePayload",
    "M145CommunicationValidationResultPayload",
]
