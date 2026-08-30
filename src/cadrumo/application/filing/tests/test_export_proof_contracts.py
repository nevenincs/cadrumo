"""Strict contract tests for the two-channel filing export proof port."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core import Period
from ....core.hashing import sha256_hex
from ....core.time import now
from ....domain.filing.errors import FilingExportValidationError
from .. import (
    DeclaracionExportResult,
    FilingExportConformanceRequest,
    FilingExportConformanceVectorEvidence,
    FilingExportConsumedResult,
    FilingExportGeneratedOutput,
    FilingExportOfficialProbe,
    FilingExportProofAssessment,
    FilingExportProofChannel,
    FilingExportProofCoordinate,
    FilingExportProofRefusal,
    FilingExportProofRefusalReason,
    FilingExportPublicProvenance,
    FilingExportSecureReplayReceipt,
    FilingExportSecureReplayRequest,
    FilingExportValidatedPayload,
    export_draft,
)
from ._export_support import (
    _approved_modelo_111_registry_draft,
    _schema_provider,
    _typed_producer_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIGEST = "a" * 64


def _coordinate() -> FilingExportProofCoordinate:
    draft = _approved_modelo_111_registry_draft()
    return FilingExportProofCoordinate(
        modelo="111",
        revision=draft.snapshot_ref.revision_id,
        layout_ids=("m111-2025-fichero-boe",),
    )


def _provenance() -> FilingExportPublicProvenance:
    return FilingExportPublicProvenance(
        official_source_ref="aeat.modelo-111.record-design.2025",
        official_source_sha256=_DIGEST,
        design_epoch="2025",
        generation_manifest_sha256=_DIGEST,
        semantic_map_sha256=_DIGEST,
        render_profile_sha256=_DIGEST,
        loader_semantic_sha256=_DIGEST,
        generated_outputs=(FilingExportGeneratedOutput(relative_path="export/layout.toml", sha256=_DIGEST),),
        probes=(FilingExportOfficialProbe(record_id="record-1", field_id="modelo", emitted_offset=0, length=3),),
    )


class _MemoryPayloadConsumer:
    """Real one-shot in-memory destination used to observe the production writer."""

    def __init__(self) -> None:
        self.payload: FilingExportValidatedPayload | None = None

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        if self.payload is not None:
            raise AssertionError("writer delivered more than one payload")
        self.payload = payload


def test_canonical_writer_can_deliver_validated_bytes_without_plaintext_path() -> None:
    consumer = _MemoryPayloadConsumer()
    result = export_draft(
        _approved_modelo_111_registry_draft(),
        payload_consumer=consumer,
        producer_snapshot=_typed_producer_snapshot(),
        schema_provider=_schema_provider(modelos=("111",)),
    )

    assert isinstance(result, FilingExportConsumedResult)
    assert consumer.payload is not None
    assert result.byte_size == len(consumer.payload.payload)
    assert result.file_sha256 == sha256_hex(consumer.payload.payload)
    assert "output_path" not in type(result).model_fields


def _call_export_draft_unguarded(
    fn: Callable[..., DeclaracionExportResult | FilingExportConsumedResult],
    /,
    **kwargs: object,
) -> DeclaracionExportResult | FilingExportConsumedResult:
    """Invoke ``export_draft`` through its erased implementation signature.

    Deliberately bypasses the two-overload "exactly one destination" static
    contract so this test can prove the SAME invariant is also enforced at
    runtime -- a caller reaching the implementation any other way (e.g. via
    dynamic dispatch) must still be refused, not merely discouraged statically.
    """
    return fn(**kwargs)


def test_canonical_writer_refuses_zero_or_two_payload_destinations(tmp_path) -> None:
    consumer = _MemoryPayloadConsumer()
    kwargs = {
        "producer_snapshot": _typed_producer_snapshot(),
        "schema_provider": _schema_provider(modelos=("111",)),
    }
    with pytest.raises(FilingExportValidationError, match="exactly one payload destination"):
        _call_export_draft_unguarded(export_draft, draft=_approved_modelo_111_registry_draft(), **kwargs)
    with pytest.raises(FilingExportValidationError, match="exactly one payload destination"):
        _call_export_draft_unguarded(
            export_draft,
            draft=_approved_modelo_111_registry_draft(),
            output_path=tmp_path / "must-not-exist.txt",
            payload_consumer=consumer,
            **kwargs,
        )
    assert not (tmp_path / "must-not-exist.txt").exists()


def test_secure_request_cannot_carry_caller_supplied_secret_inputs() -> None:
    request = FilingExportSecureReplayRequest(
        coordinate=_coordinate(),
        source_authority_id="calculation-revision-source",
        custody_authority_id="secure-object-custody",
    )

    assert "draft" not in type(request).model_fields
    assert "producer_snapshot" not in type(request).model_fields
    assert "source_pinned_probe_expectations" not in type(request).model_fields
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FilingExportSecureReplayRequest.model_validate(
            {**request.model_dump(), "draft": _approved_modelo_111_registry_draft()},
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FilingExportSecureReplayRequest.model_validate(
            {**request.model_dump(), "source_pinned_probe_expectations": ()},
        )


def test_conformance_request_cannot_carry_caller_supplied_filing_inputs() -> None:
    request = FilingExportConformanceRequest(coordinate=_coordinate())

    assert "draft" not in type(request).model_fields
    assert "producer_snapshot" not in type(request).model_fields
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FilingExportConformanceRequest.model_validate(
            {**request.model_dump(), "draft": _approved_modelo_111_registry_draft()},
        )
    assert not {
        "draft",
        "producer_snapshot",
        "dictionary_values",
        "prior_domiciliation_election",
        "product_software_identity",
    }.intersection(FilingExportConformanceVectorEvidence.model_fields)


def test_layoutless_coordinate_can_report_refusal_but_not_conformance_success() -> None:
    """A total-corpus refusal may name a layoutless revision, never a vector."""
    coordinate = FilingExportProofCoordinate(modelo="111", revision="layout-unavailable")
    request = FilingExportConformanceRequest(coordinate=coordinate)

    assert request.coordinate.layout_ids == ()
    with pytest.raises(ValidationError, match="requires one selected filing layout"):
        FilingExportConformanceVectorEvidence(
            authority_id="test.conformance",
            coordinate=coordinate,
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            mechanism_source_ref="test/provenance",
            mechanism_source_sha256=_DIGEST,
            provenance=_provenance(),
        )


def test_public_replay_receipt_excludes_secret_payload_facts() -> None:
    attested_at = now()
    receipt = FilingExportSecureReplayReceipt(
        receipt_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        coordinate=_coordinate(),
        provenance=_provenance(),
        source_authority_id="calculation-revision-source",
        custody_authority_id="secure-object-custody",
        attested_at=attested_at,
        valid_until=attested_at + timedelta(hours=1),
    )

    public_fields = receipt.model_dump()
    assert receipt.replay_passed
    assert receipt.approved_calculation_revision
    assert receipt.source_owned_draft
    assert receipt.matching_producer_snapshot
    assert receipt.value_arrival
    assert receipt.applicability
    assert receipt.repeated_record_order
    assert receipt.emitted_extent
    assert receipt.source_pinned_probes
    assert public_fields["receipt_id"] == UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    assert not {"draft", "producer_snapshot", "payload", "payload_sha256", "output_path", "emitted_bytes"}.intersection(
        public_fields,
    )


def test_composite_assessment_requires_complete_proof_xor_explicit_channel_refusals() -> None:
    coordinate = _coordinate()
    refusal = FilingExportProofRefusal(
        coordinate=coordinate,
        channel=FilingExportProofChannel.SECURE_REPLAY,
        reason=FilingExportProofRefusalReason.EVIDENCE_MISSING,
        authority_id="secure-object-custody",
    )
    assessment = FilingExportProofAssessment(coordinate=coordinate, refusals=(refusal,))
    assert assessment.proof is None
    assert assessment.refusals == (refusal,)

    with pytest.raises(ValidationError, match="proof xor refusals"):
        FilingExportProofAssessment(coordinate=coordinate)
    with pytest.raises(ValidationError, match="at most one refusal per channel"):
        FilingExportProofAssessment(coordinate=coordinate, refusals=(refusal, refusal))
