"""Run a source-owned filing export and persist its validated payload in custody."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from cadrumo.application.calculations.revision_carry_gate import revision_carry_outcome
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.export_verification import (
    FilingExportConsumedResult,
    FilingExportPayloadConsumer,
    FilingExportValidatedPayload,
)
from cadrumo.application.filing.runtime import (
    RegistrySchemaAccessor,
)
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)

from .filing_export_proof_contracts import (
    FilingExportProofCoordinate,
    FilingExportProofToken,
    FilingExportSecureCustodyRecord,
    FilingExportSecureReplayEvidence,
    FilingExportSecureReplayReceipt,
)
from .filing_export_writer import _dictionary_mapping


class FilingExportSecureReplayRequest(BaseModel):
    """Development request that cannot carry caller-supplied filing inputs."""

    model_config = STRICT_FROZEN_CONFIG

    coordinate: FilingExportProofCoordinate
    source_authority_id: FilingExportProofToken
    custody_authority_id: FilingExportProofToken


@runtime_checkable
class FilingExportSecureReplaySourceAuthority(Protocol):
    """Resolve approved draft inputs only from the source-owned workflow."""

    @property
    def authority_id(self) -> str:
        """Return the source authority's stable identity."""
        ...

    def resolve_secure_replay(self, request: FilingExportSecureReplayRequest) -> FilingExportSecureReplayEvidence:
        """Resolve source-owned evidence for the requested secure replay."""
        ...

    def schema_provider_for_secure_replay(self, evidence: FilingExportSecureReplayEvidence) -> RegistrySchemaAccessor:
        """Provide canonical registry schema access for source evidence."""
        ...


@runtime_checkable
class FilingExportSecureReplayCustody(Protocol):
    """Persist replay acceptance only in encrypted operator custody."""

    @property
    def authority_id(self) -> str:
        """Return the custody authority's stable identity."""
        ...

    def persist_secure_replay(
        self,
        *,
        request: FilingExportSecureReplayRequest,
        evidence: FilingExportSecureReplayEvidence,
        payload: FilingExportValidatedPayload,
    ) -> FilingExportSecureCustodyRecord:
        """Persist the validated export payload and return its custody record."""
        ...


def prove_secure_export_replay(
    request: FilingExportSecureReplayRequest,
    *,
    source_authority: FilingExportSecureReplaySourceAuthority,
    custody: FilingExportSecureReplayCustody,
) -> FilingExportSecureReplayReceipt:
    """Resolve development source evidence, export it, and seal it in custody."""
    if request.source_authority_id != source_authority.authority_id:
        raise ValueError("secure replay request names another source authority")
    if request.custody_authority_id != custody.authority_id:
        raise ValueError("secure replay request names another custody authority")
    evidence = source_authority.resolve_secure_replay(request)
    _require_source_evidence(request, evidence)
    schema_provider = source_authority.schema_provider_for_secure_replay(evidence)
    consumer = _SecureReplayConsumer(request=request, evidence=evidence, custody=custody)
    result = _export_to_consumer(evidence, payload_consumer=consumer, schema_provider=schema_provider)
    record = consumer.record
    if record is None:
        raise ValueError("secure replay custody did not persist the canonical writer payload")
    with bundled_indexed_authority().operation() as operation:
        _require_custody_record(request, evidence, result, record, operation=operation)
    return FilingExportSecureReplayReceipt(
        receipt_id=record.receipt_id,
        coordinate=request.coordinate,
        provenance=evidence.provenance,
        source_authority_id=request.source_authority_id,
        custody_authority_id=request.custody_authority_id,
        attested_at=record.attested_at,
        valid_until=record.valid_until,
    )


class _SecureReplayConsumer:
    def __init__(
        self,
        *,
        request: FilingExportSecureReplayRequest,
        evidence: FilingExportSecureReplayEvidence,
        custody: FilingExportSecureReplayCustody,
    ) -> None:
        self._request = request
        self._evidence = evidence
        self._custody = custody
        self.record: FilingExportSecureCustodyRecord | None = None

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        if self.record is not None:
            raise ValueError("secure replay custody consumer accepts exactly one payload")
        self.record = self._custody.persist_secure_replay(
            request=self._request,
            evidence=self._evidence,
            payload=payload,
        )


def _export_to_consumer(
    proof_input: FilingExportSecureReplayEvidence,
    *,
    payload_consumer: FilingExportPayloadConsumer,
    schema_provider: RegistrySchemaAccessor,
) -> FilingExportConsumedResult:
    return export_draft(
        proof_input.draft,
        payload_consumer=payload_consumer,
        producer_snapshot=proof_input.producer_snapshot,
        dictionary_values=_dictionary_mapping(proof_input.dictionary_values),
        prior_domiciliation_election=proof_input.prior_domiciliation_election,
        product_software_identity=proof_input.product_software_identity,
        schema_provider=schema_provider,
    )


def _require_source_evidence(
    request: FilingExportSecureReplayRequest,
    evidence: FilingExportSecureReplayEvidence,
) -> None:
    if evidence.coordinate != request.coordinate or evidence.source_authority_id != request.source_authority_id:
        raise ValueError("secure replay source authority returned evidence for another request")


def _require_custody_record(
    request: FilingExportSecureReplayRequest,
    evidence: FilingExportSecureReplayEvidence,
    result: FilingExportConsumedResult,
    record: FilingExportSecureCustodyRecord,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    outcome = revision_carry_outcome(record.coordinate.snapshot_ref, operation=operation)
    if outcome.refused:
        raise ValueError(f"custody registry coordinate cannot be re-confirmed: {outcome.detail}")
    expected = (
        request.coordinate,
        request.source_authority_id,
        request.custody_authority_id,
        evidence.evidence_id,
        evidence.calculation_revision_id,
        evidence.draft.draft_id,
    )
    actual = (
        record.coordinate,
        record.source_authority_id,
        record.custody_authority_id,
        record.evidence_id,
        record.calculation_revision_id,
        record.draft_id,
    )
    if actual != expected:
        raise ValueError("secure replay custody record conflicts with its source-owned evidence")
    if record.payload_sha256 != result.file_sha256:
        raise ValueError("secure replay custody digest does not bind the canonical writer payload")
    if record.emitted_bytes != result.byte_size:
        raise ValueError("secure replay custody extent does not bind the canonical writer payload")
