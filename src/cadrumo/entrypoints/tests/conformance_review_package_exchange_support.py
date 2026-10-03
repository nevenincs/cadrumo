"""Registered-executor conformance scenarios for the review-package exchange family.

Every artefact a step consumes is produced by the production builders and
crypto: the package is built from a verified revision, signatures and
counter-signatures use Ed25519 through the review-package signing routines,
and envelopes are sealed through the profile's stored recipient-encryption
capability. The profile's own signing and recipient keypairs are minted in
the encrypted store before submission, so each expectation can name the
exact public key the executor must use. A second, unstored Ed25519 keypair
stands in for the other party of the exchange.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.recipient_replay_guard import RecipientReplayGuardRepository
from ...adapters.persistence.profile.review_package_recipient_encryption import build_recipient_encryption_capability
from ...adapters.persistence.profile.review_package_recipient_registry import (
    build_recipient_fingerprint_registry_ports,
)
from ...adapters.persistence.profile.review_package_signing import build_review_package_signing_keypair_capability
from ...application.modelo.recipient_encryption import RecipientEncryptedPackage, RecipientEncryptionKeypair
from ...application.modelo.review_package import build_review_package
from ...application.modelo.review_package_counter_sign import (
    CounterSignedReceipt,
    counter_sign_review_package,
    verify_counter_signed_receipt,
)
from ...application.modelo.review_package_exchange_operation import (
    MODELO_REVIEW_PACKAGE_COUNTER_SIGN_OPERATION_DEFINITION_ID,
    MODELO_REVIEW_PACKAGE_DECRYPT_OPERATION_DEFINITION_ID,
    MODELO_REVIEW_PACKAGE_ENCRYPT_FEEDBACK_OPERATION_DEFINITION_ID,
    MODELO_REVIEW_PACKAGE_ENCRYPT_FOR_RECIPIENT_OPERATION_DEFINITION_ID,
    MODELO_REVIEW_PACKAGE_IMPORT_FEEDBACK_OPERATION_DEFINITION_ID,
    MODELO_REVIEW_PACKAGE_SIGN_OPERATION_DEFINITION_ID,
    ModeloReviewPackageCounterSignProjection,
    ModeloReviewPackageCounterSignRequest,
    ModeloReviewPackageDecryptProjection,
    ModeloReviewPackageDecryptRequest,
    ModeloReviewPackageEncryptFeedbackProjection,
    ModeloReviewPackageEncryptFeedbackRequest,
    ModeloReviewPackageEncryptForRecipientProjection,
    ModeloReviewPackageEncryptForRecipientRequest,
    ModeloReviewPackageImportFeedbackProjection,
    ModeloReviewPackageImportFeedbackRequest,
    ModeloReviewPackageSignProjection,
    ModeloReviewPackageSignRequest,
)
from ...application.modelo.review_package_feedback import (
    build_feedback_package,
    decrypt_feedback_package_from_originator_envelope,
    encrypt_feedback_package_for_originator,
)
from ...application.modelo.review_package_recipient_encryption import (
    decrypt_review_package_for_recipient,
    encrypt_review_package_for_recipient,
    ensure_recipient_encryption_keypair,
)
from ...application.modelo.review_package_recipient_registry import add_recipient_fingerprint
from ...application.modelo.review_package_signing import (
    ReviewPackageSigningKeypair,
    SignedReviewPackage,
    ensure_review_package_signing_keypair,
    sign_review_package,
    verify_review_package_signature,
)
from ...core.corpus_manifest.manifest import verify_corpus_bundle
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.buckets.event import BucketEvent, BucketEventType
from . import modelo_operation_test_support
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_DRAFT_BYTES = b"synthetic conformance fichero-boe draft"
_RECIPIENT_ID = "conformance-recipient"
_ORIGINATOR_ID = "conformance-originator"
_REVIEWER = "conformance-reviewer"
_COUNTER_SIGN_NOTE = "synthetic conformance counter-sign note"
_FEEDBACK_NOTE = "synthetic conformance feedback note"
_VALID_FOR_DAYS = 7


@dataclass(frozen=True, slots=True)
class _SeededPackage:
    path: Path
    work_unit_id: str
    calculation_revision_id: str


def _seed_package(context: ConformanceFamilyContext) -> _SeededPackage:
    """Build a real review package from a verified revision of this profile."""
    revision_id, _report_id = modelo_operation_test_support.seeded_modelo_verification_report(
        context.profile_id, operation=context.operation
    )
    revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
    assert revision is not None
    work_unit = WorkUnitCatalogueRepository().load().get(revision.work_unit_id)
    assert work_unit is not None
    path = context.input_root / "review-package.zip"
    build_review_package(
        revision=revision,
        work_unit=work_unit,
        draft_bytes=_DRAFT_BYTES,
        output_path=path,
        built_by=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        operation=context.operation,
    )
    return _SeededPackage(
        path=path, work_unit_id=work_unit.work_unit_id, calculation_revision_id=revision.calculation_revision_id
    )


def _profile_signing_keypair(profile_id: UUID) -> ReviewPackageSigningKeypair:
    bucket_id = str(profile_id)
    return ensure_review_package_signing_keypair(
        bucket_id=bucket_id, signing_keypair=build_review_package_signing_keypair_capability(bucket_id=bucket_id)
    )


def _profile_recipient_keypair(profile_id: UUID) -> RecipientEncryptionKeypair:
    bucket_id = str(profile_id)
    return ensure_recipient_encryption_keypair(
        bucket_id=bucket_id, recipient_encryption=build_recipient_encryption_capability(bucket_id=bucket_id)
    )


def _counterparty_signing_keypair() -> ReviewPackageSigningKeypair:
    """The other party's Ed25519 keypair, never stored in this profile."""
    private_key = Ed25519PrivateKey.generate()
    return ReviewPackageSigningKeypair(
        bucket_id="conformance-counterparty",
        private_key_hex=private_key.private_bytes_raw().hex(),
        public_key_hex=private_key.public_key().public_bytes_raw().hex(),
        created_at=datetime.now(UTC),
    )


def _register_recipient(profile_id: UUID, recipient_id: str, public_key_hex: str) -> None:
    add_recipient_fingerprint(
        recipient_id=recipient_id,
        public_key_hex=public_key_hex,
        ports=build_recipient_fingerprint_registry_ports(bucket_id=str(profile_id)),
    )


def _seal_for_profile(profile_id: UUID, payload: bytes, *, review_only: bool) -> RecipientEncryptedPackage:
    return encrypt_review_package_for_recipient(
        payload,
        recipient_public_key_hex=_profile_recipient_keypair(profile_id).public_key_hex,
        recipient_encryption=build_recipient_encryption_capability(bucket_id=str(profile_id)),
        review_only=review_only,
    )


def _open_as_profile(profile_id: UUID, envelope: RecipientEncryptedPackage) -> bytes:
    return decrypt_review_package_for_recipient(
        envelope,
        recipient_private_key_hex=_profile_recipient_keypair(profile_id).private_key_hex,
        recipient_encryption=build_recipient_encryption_capability(bucket_id=str(profile_id)),
    ).package_bytes


def _events(event_type: BucketEventType) -> tuple[BucketEvent, ...]:
    return tuple(
        event for event in BucketEventHistoryRepository().load().events.values() if event.event_type is event_type
    )


def _new_events(event_type: BucketEventType, before: tuple[BucketEvent, ...]) -> tuple[BucketEvent, ...]:
    seen = {event.event_id for event in before}
    return tuple(event for event in _events(event_type) if event.event_id not in seen)


def _write_json(path: Path, document: str) -> Path:
    path.write_text(document, encoding="utf-8", newline="\n")
    return path


def _prepare_sign(context: ConformanceFamilyContext) -> ConformancePreparation:
    package = _seed_package(context)
    signer = _profile_signing_keypair(context.profile_id)
    output = context.input_root / "signature.json"
    request = ModeloReviewPackageSignRequest(profile_id=context.profile_id, package=package.path, output=output)

    def verify(outcome: ConformanceOutcome) -> None:
        actual = outcome.resolve_result(ModeloReviewPackageSignProjection)
        written = SignedReviewPackage.model_validate_json(output.read_text(encoding="utf-8"))
        # The receipt mirrors the written envelope; only its signing instant is
        # unknowable before submission, so it is taken from that envelope.
        assert actual == ModeloReviewPackageSignProjection(
            profile_id=context.profile_id,
            effect=OperationEffect.UPDATED,
            package_path=str(package.path),
            signature_path=str(output),
            bucket_id=str(context.profile_id),
            calculation_revision_id=package.calculation_revision_id,
            manifest_sha256=verify_corpus_bundle(package.path).manifest.manifest_sha256,
            signer_public_key_hex=signer.public_key_hex,
            signed_at=written.signed_at,
        )
        assert written.public_key_hex == signer.public_key_hex
        assert written.bucket_id == str(context.profile_id)
        assert verify_review_package_signature(package.path, written, public_key_hex=signer.public_key_hex)
        assert "private_key" not in output.read_text(encoding="utf-8")

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)), request=request, verify=verify
    )


def _prepare_counter_sign(context: ConformanceFamilyContext) -> ConformancePreparation:
    package = _seed_package(context)
    originator = _counterparty_signing_keypair()
    counter_signer = _profile_signing_keypair(context.profile_id)
    signature = _write_json(
        context.input_root / "originator-signature.json",
        sign_review_package(package.path, keypair=originator, operation=context.operation).model_dump_json(indent=2),
    )
    output = context.input_root / "counter-signed-receipt.json"
    before = _events(BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED)
    request = ModeloReviewPackageCounterSignRequest(
        profile_id=context.profile_id,
        package=package.path,
        signature=signature,
        output=output,
        note=_COUNTER_SIGN_NOTE,
    )

    def verify(outcome: ConformanceOutcome) -> None:
        actual = outcome.resolve_result(ModeloReviewPackageCounterSignProjection)
        receipt = CounterSignedReceipt.model_validate_json(output.read_text(encoding="utf-8"))
        assert actual == ModeloReviewPackageCounterSignProjection(
            profile_id=context.profile_id,
            effect=OperationEffect.UPDATED,
            package_path=str(package.path),
            signature_path=str(signature),
            receipt_path=str(output),
            bucket_id=str(context.profile_id),
            note=_COUNTER_SIGN_NOTE,
            counter_signer_public_key_hex=counter_signer.public_key_hex,
            counter_signed_at=receipt.counter_signed_at,
        )
        assert verify_counter_signed_receipt(
            package.path,
            receipt,
            operator_public_key_hex=originator.public_key_hex,
            counter_signer_public_key_hex=counter_signer.public_key_hex,
        )
        # review_package_exchange_operation.py emits one counter-signed event on the signer's journal.
        recorded = _new_events(BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED, before)
        assert [event.object_id for event in recorded] == [counter_signer.public_key_hex]

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)), request=request, verify=verify
    )


def _prepare_encrypt_for_recipient(context: ConformanceFamilyContext) -> ConformancePreparation:
    package = _seed_package(context)
    recipient = _profile_recipient_keypair(context.profile_id)
    _register_recipient(context.profile_id, _RECIPIENT_ID, recipient.public_key_hex)
    output = context.input_root / "recipient-envelope.json"
    before = _events(BucketEventType.COLLAB_PACKAGE_ENCRYPTED_FOR_RECIPIENT)
    request = ModeloReviewPackageEncryptForRecipientRequest(
        profile_id=context.profile_id,
        package=package.path,
        recipient_id=_RECIPIENT_ID,
        output=output,
        review_only=True,
        valid_for_days=_VALID_FOR_DAYS,
    )

    def verify(outcome: ConformanceOutcome) -> None:
        actual = outcome.resolve_result(ModeloReviewPackageEncryptForRecipientProjection)
        envelope = RecipientEncryptedPackage.model_validate_json(output.read_text(encoding="utf-8"))
        assert actual == ModeloReviewPackageEncryptForRecipientProjection(
            profile_id=context.profile_id,
            effect=OperationEffect.UPDATED,
            package_path=str(package.path),
            output_path=str(output),
            recipient_id=_RECIPIENT_ID,
            recipient_public_key_hex=recipient.public_key_hex,
            review_only=True,
            issued_at=envelope.issued_at,
            valid_until=envelope.issued_at + timedelta(days=_VALID_FOR_DAYS),
        )
        assert envelope.recipient_public_key_hex == recipient.public_key_hex
        assert _open_as_profile(context.profile_id, envelope) == package.path.read_bytes()
        recorded = _new_events(BucketEventType.COLLAB_PACKAGE_ENCRYPTED_FOR_RECIPIENT, before)
        assert [event.payload["envelope_nonce_hex"] for event in recorded] == [envelope.envelope_nonce_hex]

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)), request=request, verify=verify
    )


def _prepare_decrypt(context: ConformanceFamilyContext) -> ConformancePreparation:
    package = _seed_package(context)
    package_bytes = package.path.read_bytes()
    envelope = _seal_for_profile(context.profile_id, package_bytes, review_only=True)
    envelope_path = _write_json(context.input_root / "recipient-envelope.json", envelope.model_dump_json(indent=2))
    output = context.input_root / "recovered-package.zip"
    before = _events(BucketEventType.COLLAB_PACKAGE_DECRYPTED)
    request = ModeloReviewPackageDecryptRequest(
        profile_id=context.profile_id, envelope_path=envelope_path, output=output
    )

    def verify(_outcome: ConformanceOutcome) -> None:
        assert output.read_bytes() == package_bytes
        consumed = {record.nonce_hex for record in RecipientReplayGuardRepository().load().records}
        assert envelope.envelope_nonce_hex in consumed
        recorded = _new_events(BucketEventType.COLLAB_PACKAGE_DECRYPTED, before)
        assert [event.payload["envelope_nonce_hex"] for event in recorded] == [envelope.envelope_nonce_hex]

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=request,
        expected_result=ModeloReviewPackageDecryptProjection(
            profile_id=context.profile_id,
            effect=OperationEffect.UPDATED,
            envelope_path=str(envelope_path),
            output_path=str(output),
            bucket_id=str(context.profile_id),
            review_only=True,
        ),
        verify=verify,
    )


def _prepare_encrypt_feedback(context: ConformanceFamilyContext) -> ConformancePreparation:
    package = _seed_package(context)
    originator_recipient = _profile_recipient_keypair(context.profile_id)
    _register_recipient(context.profile_id, _ORIGINATOR_ID, originator_recipient.public_key_hex)
    signed = sign_review_package(package.path, keypair=_counterparty_signing_keypair(), operation=context.operation)
    receipt = counter_sign_review_package(
        signed, counter_signer_keypair=_profile_signing_keypair(context.profile_id), note=_COUNTER_SIGN_NOTE
    )
    receipt_path = _write_json(context.input_root / "counter-signed-receipt.json", receipt.model_dump_json(indent=2))
    output = context.input_root / "feedback-envelope.json"
    request = ModeloReviewPackageEncryptFeedbackRequest(
        profile_id=context.profile_id,
        originator_id=_ORIGINATOR_ID,
        work_unit_id=package.work_unit_id,
        calculation_revision_id=package.calculation_revision_id,
        submitted_by=_REVIEWER,
        output=output,
        note=_FEEDBACK_NOTE,
        receipt=receipt_path,
    )

    def verify(outcome: ConformanceOutcome) -> None:
        actual = outcome.resolve_result(ModeloReviewPackageEncryptFeedbackProjection)
        envelope = RecipientEncryptedPackage.model_validate_json(output.read_text(encoding="utf-8"))
        # The feedback envelope is sealed without an expiry.
        assert actual == ModeloReviewPackageEncryptFeedbackProjection(
            profile_id=context.profile_id,
            effect=OperationEffect.UPDATED,
            output_path=str(output),
            originator_id=_ORIGINATOR_ID,
            originator_public_key_hex=originator_recipient.public_key_hex,
            work_unit_id=package.work_unit_id,
            calculation_revision_id=package.calculation_revision_id,
            has_counter_sign=True,
            issued_at=envelope.issued_at,
            valid_until=None,
        )
        assert _FEEDBACK_NOTE not in output.read_text(encoding="utf-8")
        feedback = decrypt_feedback_package_from_originator_envelope(
            envelope,
            originator_private_key_hex=originator_recipient.private_key_hex,
            recipient_encryption=build_recipient_encryption_capability(bucket_id=str(context.profile_id)),
        )
        # The executor addresses feedback to the trusted originator's registered id.
        assert feedback.bucket_id == _ORIGINATOR_ID
        assert feedback.work_unit_id == package.work_unit_id
        assert feedback.calculation_revision_id == package.calculation_revision_id
        assert feedback.note == _FEEDBACK_NOTE
        assert feedback.submitted_by == _REVIEWER
        assert feedback.counter_signed_receipt == receipt

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)), request=request, verify=verify
    )


def _prepare_import_feedback(context: ConformanceFamilyContext) -> ConformancePreparation:
    package = _seed_package(context)
    operator = _profile_signing_keypair(context.profile_id)
    reviewer = _counterparty_signing_keypair()
    signed = sign_review_package(package.path, keypair=operator, operation=context.operation)
    receipt = counter_sign_review_package(signed, counter_signer_keypair=reviewer, note=_COUNTER_SIGN_NOTE)
    feedback = build_feedback_package(
        bucket_id=str(context.profile_id),
        work_unit_id=package.work_unit_id,
        calculation_revision_id=package.calculation_revision_id,
        note=_FEEDBACK_NOTE,
        counter_signed_receipt=receipt,
        submitted_by=_REVIEWER,
    )
    envelope = encrypt_feedback_package_for_originator(
        feedback,
        originator_public_key_hex=_profile_recipient_keypair(context.profile_id).public_key_hex,
        recipient_encryption=build_recipient_encryption_capability(bucket_id=str(context.profile_id)),
    )
    envelope_path = _write_json(context.input_root / "feedback-envelope.json", envelope.model_dump_json(indent=2))
    before = _events(BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED)
    request = ModeloReviewPackageImportFeedbackRequest(
        profile_id=context.profile_id,
        envelope_path=envelope_path,
        package=package.path,
        operator_public_key_hex=operator.public_key_hex,
        counter_signer_public_key_hex=reviewer.public_key_hex,
    )

    def verify(_outcome: ConformanceOutcome) -> None:
        # A verified receipt is attached to the originator's own journal.
        recorded = _new_events(BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED, before)
        assert len(recorded) == 1
        assert recorded[0].bucket_id == str(context.profile_id)

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=request,
        # The journal attachment is the confirmed write, so the import settles UPDATED.
        expected_result=ModeloReviewPackageImportFeedbackProjection(
            profile_id=context.profile_id,
            effect=OperationEffect.UPDATED,
            envelope_path=str(envelope_path),
            bucket_id=str(context.profile_id),
            work_unit_id=package.work_unit_id,
            calculation_revision_id=package.calculation_revision_id,
            note=_FEEDBACK_NOTE,
            submitted_by=_REVIEWER,
            counter_signature_verified=True,
            attached_to_journal=True,
        ),
        verify=verify,
    )


_PREPARERS: dict[str, Callable[[ConformanceFamilyContext], ConformancePreparation]] = {
    MODELO_REVIEW_PACKAGE_SIGN_OPERATION_DEFINITION_ID: _prepare_sign,
    MODELO_REVIEW_PACKAGE_COUNTER_SIGN_OPERATION_DEFINITION_ID: _prepare_counter_sign,
    MODELO_REVIEW_PACKAGE_ENCRYPT_FOR_RECIPIENT_OPERATION_DEFINITION_ID: _prepare_encrypt_for_recipient,
    MODELO_REVIEW_PACKAGE_DECRYPT_OPERATION_DEFINITION_ID: _prepare_decrypt,
    MODELO_REVIEW_PACKAGE_ENCRYPT_FEEDBACK_OPERATION_DEFINITION_ID: _prepare_encrypt_feedback,
    MODELO_REVIEW_PACKAGE_IMPORT_FEEDBACK_OPERATION_DEFINITION_ID: _prepare_import_feedback,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    preparer = _PREPARERS.get(context.definition.definition_id)
    if preparer is None:
        raise AssertionError(f"no review-package exchange conformance scenario for {context.definition.definition_id}")
    return preparer(context)


def _succeeded_updated(definition_id: str) -> RegisteredExecutorConformanceCase:
    # build_single_phase_definition publishes the definition id as the only phase,
    # and every seeded route ends in a confirmed writer receipt.
    return RegisteredExecutorConformanceCase(
        definition_id, OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, (definition_id,)
    )


REVIEW_PACKAGE_EXCHANGE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=tuple(_succeeded_updated(definition_id) for definition_id in _PREPARERS),
    prepare=_prepare,
)
