"""Real encrypted-custody regression for ordinary Modelo 390 applicability evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cadrumo.application.modelo.action_errors import M303Exonerado390AttestationUnadmissibleError
from cadrumo.application.modelo.m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationRequest,
    admit_m303_exonerado_390_applicability_attestation,
    m303_exonerado_390_filing_evidence_reference,
    resolve_m303_exonerado_390_not_applicable_attestation,
)
from cadrumo.domain.attachments.enums import AttachmentKind, AttachmentSource
from cadrumo.domain.attachments.errors import AttachmentValidationError
from cadrumo.domain.attachments.m303_filing_evidence import (
    M303Exonerado390ApplicabilityAssertion,
    M303Exonerado390ApplicabilityAttestation,
    M303Exonerado390ApplicabilityProfileWitness,
)
from cadrumo.domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.user_profile.values import UserProfileFact

from .....core.period import Period
from ..attachment import AttachmentStore
from .profile_capsule_runtime import bound_test_profile_record, seed_modelo_ready_profile_record
from .secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "3a1f0b2c-4d5e-4f60-8a71-92b3c4d5e6f7"
_CAPTURED_AT = datetime(2025, 4, 1, 10, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")


def _request(
    value: M303Exonerado390ApplicabilityAssertion = M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
) -> M303Exonerado390ApplicabilityAttestationRequest:
    return M303Exonerado390ApplicabilityAttestationRequest(
        filing_year=2025,
        period=_PERIOD,
        asserted_value=value,
        observed_at=datetime(2025, 3, 31, 12, tzinfo=UTC),
    )


def test_admission_and_resolution_are_profile_witnessed_and_custody_verified(
    tmp_path: Path,
    operation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CAPTURED_AT)
        with bound_test_profile_record(_BUCKET_ID):
            store = AttachmentStore()
            admission = admit_m303_exonerado_390_applicability_attestation(
                bucket_id=_BUCKET_ID,
                request=_request(),
                actor="operator:test",
                operation=operation,
                store=store,
                clock=lambda: _CAPTURED_AT,
            )

            reference = admission.filing_evidence_reference()
            resolved = resolve_m303_exonerado_390_not_applicable_attestation(
                bucket_id=_BUCKET_ID,
                filing_year=2025,
                period=_PERIOD,
                evidence_reference=reference,
                operation=operation,
                store=store,
                clock=lambda: _CAPTURED_AT,
            )

            attachment = store.load_manifest(admission.attachment_id)
            assert resolved == reference
            assert admission.attachment_id == admission.sha256
            assert attachment.kind is AttachmentKind.M303_EXONERADO_390_APPLICABILITY_ATTESTATION
            assert attachment.metadata == {}
            assert attachment.bucket_id == _BUCKET_ID


def test_applicable_assertion_refuses_before_custody_mutation(tmp_path: Path, operation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CAPTURED_AT)
        with bound_test_profile_record(_BUCKET_ID):
            store = AttachmentStore()

            with pytest.raises(AttachmentValidationError, match="not supported"):
                admit_m303_exonerado_390_applicability_attestation(
                    bucket_id=_BUCKET_ID,
                    request=_request(M303Exonerado390ApplicabilityAssertion.APPLICABLE),
                    actor="operator:test",
                    operation=operation,
                    store=store,
                    clock=lambda: _CAPTURED_AT,
                )

            assert tuple(store.iter_manifests()) == ()


def test_split_attachment_identifiers_refuse_malformed_or_conflicting_values() -> None:
    with pytest.raises(M303Exonerado390AttestationUnadmissibleError):
        m303_exonerado_390_filing_evidence_reference(attachment_id="not-a-digest", sha256="a" * 64)
    with pytest.raises(M303Exonerado390AttestationUnadmissibleError):
        m303_exonerado_390_filing_evidence_reference(attachment_id="a" * 64, sha256="b" * 64)


def test_resolution_refuses_a_conflicting_typed_assertion_in_the_same_coordinate(
    tmp_path: Path,
    operation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CAPTURED_AT)
        with bound_test_profile_record(_BUCKET_ID) as profiles:
            store = AttachmentStore()
            admission = admit_m303_exonerado_390_applicability_attestation(
                bucket_id=_BUCKET_ID,
                request=_request(),
                actor="operator:test",
                operation=operation,
                store=store,
                clock=lambda: _CAPTURED_AT,
            )
            reference = admission.filing_evidence_reference()
            conflicting = M303Exonerado390ApplicabilityAttestation(
                schema_version=1,
                role="m303_exonerado_390_applicability",
                asserted_value=M303Exonerado390ApplicabilityAssertion.APPLICABLE,
                filing_year=2025,
                period=_PERIOD,
                observed_at=datetime(2025, 3, 31, 12, tzinfo=UTC),
                profile_witness=M303Exonerado390ApplicabilityProfileWitness.from_profile_record(
                    profiles.load(_BUCKET_ID)
                ),
            )
            add_attachment(
                store,
                content=AttachmentBytesContent(data=conflicting.canonical_json_bytes()),
                request=AttachmentIngestionRequest(
                    kind=AttachmentKind.M303_EXONERADO_390_APPLICABILITY_ATTESTATION,
                    source=AttachmentSource.INLINE,
                    source_reference="m303-exonerado-390-applicability:2025:1T",
                    mime_type="application/vnd.cadrumo.m303-exonerado-390-applicability+json",
                    captured_at=_CAPTURED_AT,
                    bucket_id=_BUCKET_ID,
                    captured_by="operator:test",
                    source_command="test:conflicting-typed-attestation",
                ),
            )

            with pytest.raises(AttachmentValidationError, match="conflicting"):
                resolve_m303_exonerado_390_not_applicable_attestation(
                    bucket_id=_BUCKET_ID,
                    filing_year=2025,
                    period=_PERIOD,
                    evidence_reference=reference,
                    operation=operation,
                    store=store,
                    clock=lambda: _CAPTURED_AT,
                )


def test_resolution_refuses_an_attestation_stale_against_the_current_profile_witness(
    tmp_path: Path,
    operation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile_record(_BUCKET_ID, clock=_CAPTURED_AT)
        with bound_test_profile_record(_BUCKET_ID) as profiles:
            store = AttachmentStore()
            admission = admit_m303_exonerado_390_applicability_attestation(
                bucket_id=_BUCKET_ID,
                request=_request(),
                actor="operator:test",
                operation=operation,
                store=store,
                clock=lambda: _CAPTURED_AT,
            )
            reference = admission.filing_evidence_reference()
            current = profiles.load(_BUCKET_ID)
            updated_at = current.updated_at + timedelta(minutes=1)
            profiles.apply_fact_changes(
                _BUCKET_ID,
                facts=tuple(
                    UserProfileFact(path=fact.path, value="Ana Maria") if fact.path == "identity.name" else fact
                    for fact in current.facts
                ),
                expected_revision=current.record_revision,
                expected_content_digest=current.content_digest,
                event_type=BucketEventType.PROFILE_VALUES_UPDATED,
                event_payload={},
                now=updated_at,
            )

            with pytest.raises(AttachmentValidationError, match="does not match"):
                resolve_m303_exonerado_390_not_applicable_attestation(
                    bucket_id=_BUCKET_ID,
                    filing_year=2025,
                    period=_PERIOD,
                    evidence_reference=reference,
                    operation=operation,
                    store=store,
                    clock=lambda: updated_at,
                )
