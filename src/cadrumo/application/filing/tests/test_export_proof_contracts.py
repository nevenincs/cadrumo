"""Strict contract tests for the two-channel filing export proof port."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core import sha256_hex
from ....core.time import now
from ....domain.filing import FilingExportValidationError
from .. import (
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


def test_canonical_writer_refuses_zero_or_two_payload_destinations(tmp_path) -> None:
    consumer = _MemoryPayloadConsumer()
    kwargs = {
        "producer_snapshot": _typed_producer_snapshot(),
        "schema_provider": _schema_provider(modelos=("111",)),
    }
    with pytest.raises(FilingExportValidationError, match="exactly one payload destination"):
        export_draft(_approved_modelo_111_registry_draft(), **kwargs)
    with pytest.raises(FilingExportValidationError, match="exactly one payload destination"):
        export_draft(
            _approved_modelo_111_registry_draft(),
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
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FilingExportSecureReplayRequest.model_validate(
            {**request.model_dump(), "draft": _approved_modelo_111_registry_draft()},
        )


def test_public_replay_receipt_excludes_secret_payload_facts() -> None:
    receipt = FilingExportSecureReplayReceipt(
        coordinate=_coordinate(),
        provenance=_provenance(),
        source_authority_id="calculation-revision-source",
        custody_authority_id="secure-object-custody",
        attested_at=now(),
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
