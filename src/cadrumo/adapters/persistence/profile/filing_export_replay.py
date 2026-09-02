"""Encrypted custody adapter for source-owned filing export replay proof."""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar, override
from uuid import uuid4

from ....application.filing.export_proof import (
    FilingExportSecureCustodyRecord,
    FilingExportSecureReplayEvidence,
    FilingExportSecureReplayRequest,
    FilingExportSourcePinnedProbeExpectation,
)
from ....application.filing.export_verification import FilingExportValidatedPayload
from ....core.classification.policies import SensitivityClass
from ....core.config import Settings
from ....core.hashing import sha256_hex
from ....core.time.clock import now
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.secure_object_namespaces import FILING_EXPORT_REPLAY_PROOFS_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository


class FilingExportReplayCustodyRepository(SecureBoundRepository[FilingExportSecureCustodyRecord]):
    """Persist replay evidence only through the profile's encrypted substrate."""

    namespace: ClassVar[str] = FILING_EXPORT_REPLAY_PROOFS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = FILING_EXPORT_REPLAY_PROOFS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = FILING_EXPORT_REPLAY_PROOFS_NAMESPACE.schema_version
    authority_id: ClassVar[str] = "cadrumo.persistence.filing-export-replay-custody"

    def __init__(
        self,
        *,
        valid_for: timedelta,
        bucket_id: str | None = None,
        objects: SecureObjectRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Bind encrypted storage and an explicit operator receipt lifetime."""
        if valid_for <= timedelta(0):
            raise ValueError("secure replay receipt lifetime must be positive")
        self._valid_for = valid_for
        super().__init__(bucket_id=bucket_id, objects=objects, settings=settings)

    @override
    @classmethod
    def payload_model(cls) -> type[FilingExportSecureCustodyRecord]:
        """Return the encrypted internal replay-record model."""
        return FilingExportSecureCustodyRecord

    @override
    def extract_identifier(self, payload: FilingExportSecureCustodyRecord) -> str:
        """Use the opaque receipt UUID as the secure-object natural key."""
        return str(payload.receipt_id)

    def persist_secure_replay(
        self,
        *,
        request: FilingExportSecureReplayRequest,
        evidence: FilingExportSecureReplayEvidence,
        payload: FilingExportValidatedPayload,
    ) -> FilingExportSecureCustodyRecord:
        """Validate canonical output, encrypt it as evidence, and re-read it."""
        if (
            evidence.coordinate != request.coordinate
            or payload.modelo != request.coordinate.modelo
            or payload.draft_id != evidence.draft.draft_id
            or payload.period != evidence.draft.period
        ):
            raise ValueError("secure replay payload conflicts with source-owned evidence")
        _require_source_pinned_probe_bytes(
            expectations=evidence.source_pinned_probe_expectations,
            payload=payload.payload,
        )
        attested_at = now()
        record = FilingExportSecureCustodyRecord(
            receipt_id=uuid4(),
            coordinate=request.coordinate,
            source_authority_id=request.source_authority_id,
            custody_authority_id=self.authority_id,
            evidence_id=evidence.evidence_id,
            calculation_revision_id=evidence.calculation_revision_id,
            draft_id=evidence.draft.draft_id,
            payload_sha256=sha256_hex(payload.payload),
            emitted_bytes=len(payload.payload),
            attested_at=attested_at,
            valid_until=attested_at + self._valid_for,
            encrypted_at_rest=True,
            approved_calculation_revision=True,
            source_owned_draft=True,
            matching_producer_snapshot=True,
            value_arrival=True,
            applicability=True,
            repeated_record_order=True,
            emitted_extent=True,
            source_pinned_probes_passed=True,
        )
        self.save(record)
        reloaded = self.load(str(record.receipt_id))
        if reloaded != record:
            raise ValueError("encrypted replay custody did not round-trip its exact internal receipt")
        return record


def _require_source_pinned_probe_bytes(
    *,
    expectations: tuple[FilingExportSourcePinnedProbeExpectation, ...],
    payload: bytes,
) -> None:
    """Refuse any replay whose bytes differ from source-owned expectations."""
    for expectation in expectations:
        probe = expectation.probe
        end = probe.emitted_offset + probe.length
        if end > len(payload):
            raise ValueError("secure replay source-pinned probe falls outside emitted bytes")
        if payload[probe.emitted_offset : end] != expectation.expected_bytes:
            raise ValueError("secure replay payload disagrees with source-pinned expected bytes")


__all__ = ["FilingExportReplayCustodyRepository"]
