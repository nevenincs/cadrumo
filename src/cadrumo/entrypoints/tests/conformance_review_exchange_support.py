"""Registered review exchange with real verified filings, signatures and ciphertext."""

from __future__ import annotations

from pydantic import BaseModel

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...application.modelo.export import ModeloExportCommand, export_modelo_revision
from ...application.modelo.operation_definitions import resolve_active_workflow_profile
from ...application.modelo.recipient_encryption import RecipientEncryptedPackage
from ...application.modelo.review_package import build_review_package
from ...application.modelo.review_package_counter_sign import (
    CounterSignedReceipt,
    counter_sign_review_package,
    verify_counter_signed_receipt,
)
from ...application.modelo.review_package_exchange_operation import (
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
    SignedReviewPackage,
    ensure_review_package_signing_keypair,
    sign_review_package,
    verify_review_package_signature,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..adapter_composition import build_modelo_export_ports
from ..review_package_exchange_operation_composition import build_review_package_exchange_operation_ports
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)
from .modelo_operation_test_support import seeded_modelo_verification_report


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    revision_id, _ = seeded_modelo_verification_report(context.profile_id, operation=context.operation)
    revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
    assert revision is not None
    unit = WorkUnitCatalogueRepository().load().get(revision.work_unit_id)
    assert unit is not None
    workflow = resolve_active_workflow_profile(context.operation)
    draft = context.input_root / "draft.fichero-boe"
    export_modelo_revision(
        ModeloExportCommand(
            calculation_revision_id=revision.calculation_revision_id, output_path=draft, actor="conformance"
        ),
        workflow_profile=workflow,
        export_ports=build_modelo_export_ports(
            bucket_id=profile, m303_rectificativa_taxpayer_tax_id=workflow.tax_id, operation=context.operation
        ),
        operation=context.operation,
    )
    package = context.input_root / "review.zip"
    build_review_package(
        revision=revision,
        work_unit=unit,
        draft_bytes=draft.read_bytes(),
        output_path=package,
        built_by="conformance",
        operation=context.operation,
    )
    payload = package.read_bytes()
    ports = build_review_package_exchange_operation_ports(
        profile_id=context.profile_id, operation=context.operation, write=lambda callback: callback()
    )
    signing = ensure_review_package_signing_keypair(bucket_id=profile, signing_keypair=ports.signing)
    encryption = ensure_recipient_encryption_keypair(bucket_id=profile, recipient_encryption=ports.encryption)
    add_recipient_fingerprint(recipient_id="self", public_key_hex=encryption.public_key_hex, ports=ports.recipients)
    signed = sign_review_package(package, keypair=signing, operation=context.operation)
    signature = context.input_root / "original-signature.json"
    signature.write_text(signed.model_dump_json(), encoding="utf-8")
    receipt = counter_sign_review_package(signed, counter_signer_keypair=signing, note="reviewed by conformance")
    receipt_path = context.input_root / "original-receipt.json"
    receipt_path.write_text(receipt.model_dump_json(), encoding="utf-8")
    output = context.input_root / "result.json"
    verb = context.definition.definition_id.rsplit(".", 1)[1]
    request: BaseModel
    if verb == "sign":
        request = ModeloReviewPackageSignRequest(profile_id=context.profile_id, package=package, output=output)
    elif verb == "counter_sign":
        request = ModeloReviewPackageCounterSignRequest(
            profile_id=context.profile_id,
            package=package,
            signature=signature,
            output=output,
            note="registered review approval",
        )
    elif verb == "encrypt_for_recipient":
        request = ModeloReviewPackageEncryptForRecipientRequest(
            profile_id=context.profile_id,
            package=package,
            recipient_id="self",
            output=output,
            review_only=True,
            valid_for_days=2,
        )
    elif verb == "decrypt":
        envelope = encrypt_review_package_for_recipient(
            payload,
            recipient_public_key_hex=encryption.public_key_hex,
            recipient_encryption=ports.encryption,
            review_only=True,
        )
        source = context.input_root / "incoming.json"
        source.write_text(envelope.model_dump_json(), encoding="utf-8")
        request = ModeloReviewPackageDecryptRequest(profile_id=context.profile_id, envelope_path=source, output=output)
    elif verb == "encrypt_feedback":
        request = ModeloReviewPackageEncryptFeedbackRequest(
            profile_id=context.profile_id,
            originator_id="self",
            work_unit_id=unit.work_unit_id,
            calculation_revision_id=revision.calculation_revision_id,
            submitted_by="conformance",
            output=output,
            note="review completed",
            receipt=receipt_path,
        )
    else:
        feedback = build_feedback_package(
            bucket_id=profile,
            work_unit_id=unit.work_unit_id,
            calculation_revision_id=revision.calculation_revision_id,
            note="review completed",
            counter_signed_receipt=receipt,
            submitted_by="conformance",
        )
        envelope = encrypt_feedback_package_for_originator(
            feedback, originator_public_key_hex=encryption.public_key_hex, recipient_encryption=ports.encryption
        )
        source = context.input_root / "incoming-feedback.json"
        source.write_text(envelope.model_dump_json(), encoding="utf-8")
        request = ModeloReviewPackageImportFeedbackRequest(
            profile_id=context.profile_id,
            envelope_path=source,
            package=package,
            operator_public_key_hex=signing.public_key_hex,
            counter_signer_public_key_hex=signing.public_key_hex,
        )
    history_before = ports.history.load()

    def verify(outcome: ConformanceOutcome) -> None:
        if verb == "sign":
            result = outcome.resolve_result(ModeloReviewPackageSignProjection)
            actual = SignedReviewPackage.model_validate_json(output.read_bytes())
            assert result.signer_public_key_hex == signing.public_key_hex == actual.public_key_hex
            assert result.calculation_revision_id == revision.calculation_revision_id
            assert verify_review_package_signature(package, actual, public_key_hex=signing.public_key_hex)
            assert not verify_review_package_signature(
                package, actual.model_copy(update={"signature_hex": "0" * 128}), public_key_hex=signing.public_key_hex
            )
        elif verb == "counter_sign":
            result = outcome.resolve_result(ModeloReviewPackageCounterSignProjection)
            actual = CounterSignedReceipt.model_validate_json(output.read_bytes())
            assert result.note == actual.note == "registered review approval"
            assert verify_counter_signed_receipt(
                package,
                actual,
                operator_public_key_hex=signing.public_key_hex,
                counter_signer_public_key_hex=signing.public_key_hex,
            )
            assert not verify_counter_signed_receipt(
                package,
                actual.model_copy(update={"note": "tampered"}),
                operator_public_key_hex=signing.public_key_hex,
                counter_signer_public_key_hex=signing.public_key_hex,
            )
        elif verb == "encrypt_for_recipient":
            result = outcome.resolve_result(ModeloReviewPackageEncryptForRecipientProjection)
            actual = RecipientEncryptedPackage.model_validate_json(output.read_bytes())
            clear = decrypt_review_package_for_recipient(
                actual, recipient_private_key_hex=encryption.private_key_hex, recipient_encryption=ports.encryption
            )
            assert clear.package_bytes == payload and clear.review_only and result.review_only
            assert result.recipient_public_key_hex == encryption.public_key_hex and result.valid_until is not None
            assert (result.valid_until - result.issued_at).days == 2
        elif verb == "decrypt":
            result = outcome.resolve_result(ModeloReviewPackageDecryptProjection)
            assert output.read_bytes() == payload and result.review_only and result.bucket_id == profile
        elif verb == "encrypt_feedback":
            result = outcome.resolve_result(ModeloReviewPackageEncryptFeedbackProjection)
            actual = RecipientEncryptedPackage.model_validate_json(output.read_bytes())
            clear_feedback = decrypt_feedback_package_from_originator_envelope(
                actual, originator_private_key_hex=encryption.private_key_hex, recipient_encryption=ports.encryption
            )
            assert result.has_counter_sign and clear_feedback.counter_signed_receipt == receipt
            assert clear_feedback.note == "review completed" and clear_feedback.work_unit_id == unit.work_unit_id
            assert clear_feedback.calculation_revision_id == revision.calculation_revision_id
        else:
            result = outcome.resolve_result(ModeloReviewPackageImportFeedbackProjection)
            assert result.counter_signature_verified is True and result.attached_to_journal
            assert result.note == "review completed" and result.submitted_by == "conformance"
            assert (
                result.work_unit_id == unit.work_unit_id
                and result.calculation_revision_id == revision.calculation_revision_id
            )
        assert package.read_bytes() == payload
        if verb in {"counter_sign", "encrypt_for_recipient", "decrypt", "import_feedback"}:
            assert len(ports.history.load().events) == len(history_before.events) + 1

    return ConformancePreparation(profile_operation_subject(profile), request, verify=verify)


REVIEW_EXCHANGE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=tuple(
        RegisteredExecutorConformanceCase(
            f"modelo.review_package.{verb}",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (f"modelo.review_package.{verb}",),
        )
        for verb in ("sign", "counter_sign", "encrypt_for_recipient", "decrypt", "encrypt_feedback", "import_feedback")
    ),
    prepare=_prepare,
)
