"""Six-route canonical exchange, exact human policy and concrete writer settlement.

Real disposable ZIP/signature files prove canonical signing. Inward encryption
and persistence doubles isolate delegation and effect authority; installed/native
acceptance remains with the existing outward and runtime suites.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessAllowed, AccessDenied, Availability, DisclosureCategory
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import review_package_exchange_operation as module
from .. import review_package_signing as signing_module
from ..recipient_encryption import RecipientEncryptedPackage
from ..review_package_counter_sign import CounterSignedReceipt, verify_counter_signed_receipt
from ..review_package_feedback import build_feedback_package, encrypt_feedback_package_for_originator
from ..review_package_signing import SignedReviewPackage, verify_review_package_signature
from .m036_operation_support import INSTANT, PROFILE_ID, policy_decision
from .review_package_exchange_operation_support import Subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


@pytest.fixture
def subject(authority_operation: PinnedAuthorityOperation, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Subject:
    monkeypatch.setattr(module, "require_active_bucket_id", lambda: str(PROFILE_ID))
    return Subject(authority_operation, tmp_path)


def _request(identifier: str, payload: BaseModel) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=identifier, subject_ref=profile_operation_subject(str(PROFILE_ID)), payload=payload
    )


def _registry(subject: Subject) -> OperationRegistry:
    definitions = module.build_review_package_exchange_operation_definitions(subject.compose)
    return OperationRegistry(
        definitions=definitions,
        public_registrations=module.build_review_package_exchange_operation_registrations(definitions),
    )


async def _execute(subject: Subject, identifier: str, payload: BaseModel) -> module.ReviewPackageExchangeProjection:
    request = _request(identifier, payload)
    await module.ReviewPackageExchangeExecutor(subject.compose).execute(request, subject.context(identifier))
    return cast(module.ReviewPackageExchangeExecutionResult, subject.operands.values[-1]).projection


def test_real_registry_compiles_complete_human_family_and_closed_metadata_schemas(subject: Subject) -> None:
    registry = _registry(subject)
    definitions = module.build_review_package_exchange_operation_definitions(subject.compose)
    assert len(definitions) == 6
    for definition in definitions:
        contract = registry.lookup_public_contract(definition.definition_id)
        assert contract.request_schema.schema_id == definition.definition_id + ".request"
        assert (
            contract.result_schema is not None
            and contract.result_schema.schema_id == definition.definition_id + ".result"
        )
        assert definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
        assert {
            OperationEffect.NONE,
            OperationEffect.UPDATED,
            OperationEffect.PARTIAL,
            OperationEffect.UNKNOWN,
        } <= definition.capabilities.permitted_effects
    for projection in (
        module.ModeloReviewPackageSignProjection,
        module.ModeloReviewPackageCounterSignProjection,
        module.ModeloReviewPackageEncryptForRecipientProjection,
        module.ModeloReviewPackageDecryptProjection,
        module.ModeloReviewPackageEncryptFeedbackProjection,
        module.ModeloReviewPackageImportFeedbackProjection,
    ):
        assert not {"private_key_hex", "ciphertext", "package_bytes", "signature_hex"} & projection.model_fields.keys()


@pytest.mark.asyncio
async def test_complete_canonical_human_roundtrip_retains_signatures_disposition_feedback_and_write_order(
    subject: Subject, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def extra_authority() -> None:
        raise AssertionError("signing must use the existing worker pin")

    monkeypatch.setattr(signing_module, "bundled_indexed_authority", extra_authority)
    signature = tmp_path / "signature.json"
    receipt_path = tmp_path / "receipt.json"
    envelope_path = tmp_path / "envelope.json"
    recovered_path = tmp_path / "recovered.zip"
    feedback_path = tmp_path / "feedback.json"
    sign = await _execute(
        subject,
        module.MODELO_REVIEW_PACKAGE_SIGN_OPERATION_DEFINITION_ID,
        module.ModeloReviewPackageSignRequest(profile_id=PROFILE_ID, package=subject.package, output=signature),
    )
    assert isinstance(sign, module.ModeloReviewPackageSignProjection)
    signed = SignedReviewPackage.model_validate_json(signature.read_bytes())
    assert verify_review_package_signature(subject.package, signed, public_key_hex=sign.signer_public_key_hex)
    assert (
        sign.manifest_sha256 == signed.manifest_sha256
        and sign.calculation_revision_id == signed.calculation_revision_id
    )
    counter = await _execute(
        subject,
        module.MODELO_REVIEW_PACKAGE_COUNTER_SIGN_OPERATION_DEFINITION_ID,
        module.ModeloReviewPackageCounterSignRequest(
            profile_id=PROFILE_ID,
            package=subject.package,
            signature=signature,
            output=receipt_path,
            note="synthetic human approval",
        ),
    )
    assert isinstance(counter, module.ModeloReviewPackageCounterSignProjection)
    receipt = CounterSignedReceipt.model_validate_json(receipt_path.read_bytes())
    assert verify_counter_signed_receipt(
        subject.package,
        receipt,
        operator_public_key_hex=sign.signer_public_key_hex,
        counter_signer_public_key_hex=counter.counter_signer_public_key_hex,
    )
    encrypted = await _execute(
        subject,
        module.MODELO_REVIEW_PACKAGE_ENCRYPT_FOR_RECIPIENT_OPERATION_DEFINITION_ID,
        module.ModeloReviewPackageEncryptForRecipientRequest(
            profile_id=PROFILE_ID,
            package=subject.package,
            recipient_id=str(PROFILE_ID),
            output=envelope_path,
            review_only=True,
            valid_for_days=2,
        ),
    )
    assert isinstance(encrypted, module.ModeloReviewPackageEncryptForRecipientProjection)
    assert encrypted.review_only and encrypted.valid_until is not None
    assert (encrypted.valid_until - encrypted.issued_at).days == 2
    decrypted = await _execute(
        subject,
        module.MODELO_REVIEW_PACKAGE_DECRYPT_OPERATION_DEFINITION_ID,
        module.ModeloReviewPackageDecryptRequest(
            profile_id=PROFILE_ID, envelope_path=envelope_path, output=recovered_path
        ),
    )
    assert isinstance(decrypted, module.ModeloReviewPackageDecryptProjection) and decrypted.review_only
    assert recovered_path.read_bytes() == subject.package.read_bytes()
    envelope = RecipientEncryptedPackage.model_validate_json(envelope_path.read_bytes())
    assert envelope.envelope_nonce_hex in subject.replay.consumed
    feedback = await _execute(
        subject,
        module.MODELO_REVIEW_PACKAGE_ENCRYPT_FEEDBACK_OPERATION_DEFINITION_ID,
        module.ModeloReviewPackageEncryptFeedbackRequest(
            profile_id=PROFILE_ID,
            originator_id=str(PROFILE_ID),
            work_unit_id="a" * 64,
            calculation_revision_id=signed.calculation_revision_id,
            submitted_by="synthetic reviewer",
            output=feedback_path,
            note="synthetic returned verdict",
            receipt=receipt_path,
        ),
    )
    assert isinstance(feedback, module.ModeloReviewPackageEncryptFeedbackProjection) and feedback.has_counter_sign
    imported = await _execute(
        subject,
        module.MODELO_REVIEW_PACKAGE_IMPORT_FEEDBACK_OPERATION_DEFINITION_ID,
        module.ModeloReviewPackageImportFeedbackRequest(
            profile_id=PROFILE_ID,
            envelope_path=feedback_path,
            package=subject.package,
            operator_public_key_hex=sign.signer_public_key_hex,
            counter_signer_public_key_hex=counter.counter_signer_public_key_hex,
        ),
    )
    assert isinstance(imported, module.ModeloReviewPackageImportFeedbackProjection)
    assert imported.counter_signature_verified is True and imported.attached_to_journal
    assert imported.note == "synthetic returned verdict" and imported.submitted_by == "synthetic reviewer"
    assert imported.work_unit_id == "a" * 64 and imported.calculation_revision_id == signed.calculation_revision_id
    assert subject.fence.entries == 12 and not subject.fence.active
    assert subject.encryption.encrypt_calls == subject.encryption.decrypt_calls == 2
    assert all(
        value.profile_id == PROFILE_ID and value.effect is OperationEffect.UPDATED
        for value in (sign, counter, encrypted, decrypted, feedback, imported)
    )
    assert subject.signing.keypair is not None
    journal = " ".join(subject.events.phases)
    assert "synthetic returned verdict" not in journal and str(tmp_path) not in journal
    assert (
        subject.signing.keypair.private_key_hex not in journal
        and subject.encryption.prepared.private_key_hex not in journal
    )


@pytest.mark.asyncio
async def test_counter_sign_preserves_existing_no_package_verification_contract(
    subject: Subject, tmp_path: Path
) -> None:
    signature = tmp_path / "signature.json"
    signed = SignedReviewPackage(
        bucket_id=str(PROFILE_ID),
        calculation_revision_id="b" * 64,
        manifest_sha256="c" * 64,
        signature_hex="d" * 128,
        public_key_hex="e" * 64,
        signed_at=INSTANT,
    )
    signature.write_text(signed.model_dump_json(), encoding="utf-8")
    absent_package = tmp_path / "never-read-package.zip"
    output = tmp_path / "receipt.json"
    result = await _execute(
        subject,
        module.MODELO_REVIEW_PACKAGE_COUNTER_SIGN_OPERATION_DEFINITION_ID,
        module.ModeloReviewPackageCounterSignRequest(
            profile_id=PROFILE_ID, package=absent_package, signature=signature, output=output
        ),
    )
    assert isinstance(result, module.ModeloReviewPackageCounterSignProjection) and result.package_path == str(
        absent_package
    )
    assert CounterSignedReceipt.model_validate_json(output.read_bytes()).original_signature == signed
    assert subject.fence.entries == 3 and not absent_package.exists()


@pytest.mark.asyncio
async def test_replayed_decrypt_retains_existing_audit_before_refusal_and_never_overwrites_plaintext(
    subject: Subject, tmp_path: Path
) -> None:
    envelope = subject.encryption.encrypt(
        b"synthetic confidential package", recipient_public_key_hex=subject.encryption.prepared.public_key_hex
    )
    subject.encryption.keypair = subject.encryption.prepared
    subject.replay.consumed.add(envelope.envelope_nonce_hex)
    path = tmp_path / "envelope.json"
    path.write_text(envelope.model_dump_json(), encoding="utf-8")
    output = tmp_path / "untouched.zip"
    request = _request(
        module.MODELO_REVIEW_PACKAGE_DECRYPT_OPERATION_DEFINITION_ID,
        module.ModeloReviewPackageDecryptRequest(profile_id=PROFILE_ID, envelope_path=path, output=output),
    )
    with pytest.raises(ValueError, match="already-consumed"):
        await module.ReviewPackageExchangeExecutor(subject.compose).execute(
            request, subject.context(request.definition_id)
        )
    assert len(subject.history.catalogue.events) == 1 and not output.exists()
    assert subject.events.effects[-1] is OperationEffect.PARTIAL
    assert subject.fence.entries == 1 and not subject.operands.values


@pytest.mark.asyncio
@pytest.mark.parametrize("mint", [False, True])
async def test_unstructured_feedback_keeps_no_attachment_and_truthful_optional_key_mint_effect(
    subject: Subject, tmp_path: Path, mint: bool
) -> None:
    subject.encryption.keypair = None if mint else subject.encryption.prepared
    feedback = build_feedback_package(
        bucket_id=str(PROFILE_ID),
        work_unit_id="a" * 64,
        calculation_revision_id="b" * 64,
        submitted_by="synthetic reviewer",
        note="unstructured verdict",
    )
    envelope = encrypt_feedback_package_for_originator(
        feedback,
        originator_public_key_hex=subject.encryption.prepared.public_key_hex,
        recipient_encryption=subject.encryption,
    )
    path = tmp_path / "feedback.json"
    path.write_text(envelope.model_dump_json(), encoding="utf-8")
    result = await _execute(
        subject,
        module.MODELO_REVIEW_PACKAGE_IMPORT_FEEDBACK_OPERATION_DEFINITION_ID,
        module.ModeloReviewPackageImportFeedbackRequest(
            profile_id=PROFILE_ID, envelope_path=path, package=subject.package, operator_public_key_hex="c" * 64
        ),
    )
    assert isinstance(result, module.ModeloReviewPackageImportFeedbackProjection)
    assert result.counter_signature_verified is None and not result.attached_to_journal
    assert result.note == feedback.note and not subject.history.catalogue.events
    assert result.effect is (OperationEffect.UPDATED if mint else OperationEffect.NONE)
    assert subject.fence.entries == int(mint)
    retained = cast(module.ReviewPackageExchangeExecutionResult, subject.operands.values[-1])
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="c" * 64,
            definition_id=module.MODELO_REVIEW_PACKAGE_IMPORT_FEEDBACK_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
        ),
        revision=1,
        settled_at=INSTANT,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=result.effect,
        result_ref="d" * 64,
    )
    assert module.project_review_package_exchange_operation_result(retained, receipt) == result
    unproved = retained.model_copy(update={"projection": result.model_copy(update={"attached_to_journal": True})})
    with pytest.raises(ValueError):
        module.project_review_package_exchange_operation_result(unproved, receipt)


@pytest.mark.asyncio
@pytest.mark.parametrize("deny", [True, False])
async def test_revoked_writer_and_actual_written_file_failure_have_distinct_no_write_unknown_receipts(
    subject: Subject, tmp_path: Path, deny: bool
) -> None:
    subject.fence.deny = deny
    subject.files.fail_after_write = not deny
    output = tmp_path / "encrypted.json"
    request = _request(
        module.MODELO_REVIEW_PACKAGE_ENCRYPT_FOR_RECIPIENT_OPERATION_DEFINITION_ID,
        module.ModeloReviewPackageEncryptForRecipientRequest(
            profile_id=PROFILE_ID, package=subject.package, recipient_id=str(PROFILE_ID), output=output
        ),
    )
    with pytest.raises((ProfileAccessRefusedError, OSError)):
        await module.ReviewPackageExchangeExecutor(subject.compose).execute(
            request, subject.context(request.definition_id)
        )
    assert output.exists() is not deny
    assert subject.events.effects[-1] is (OperationEffect.NONE if deny else OperationEffect.UNKNOWN)
    assert not subject.operands.values and not subject.fence.active


@pytest.mark.asyncio
async def test_key_mint_before_invalid_sign_input_retains_confirmed_partial_receipt(
    subject: Subject, tmp_path: Path
) -> None:
    request = _request(
        module.MODELO_REVIEW_PACKAGE_SIGN_OPERATION_DEFINITION_ID,
        module.ModeloReviewPackageSignRequest(
            profile_id=PROFILE_ID, package=tmp_path / "absent.zip", output=tmp_path / "uncreated.json"
        ),
    )
    with pytest.raises(FileNotFoundError):
        await module.ReviewPackageExchangeExecutor(subject.compose).execute(
            request, subject.context(request.definition_id)
        )
    assert subject.signing.keypair is not None and subject.fence.entries == 1
    assert subject.events.effects[-1] is OperationEffect.PARTIAL and not subject.operands.values


@pytest.mark.asyncio
async def test_wrong_profile_and_wrong_family_request_refuse_before_private_access(
    subject: Subject, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = module.ModeloReviewPackageSignRequest(
        profile_id=PROFILE_ID, package=subject.package, output=tmp_path / "signature.json"
    )
    request = _request(module.MODELO_REVIEW_PACKAGE_DECRYPT_OPERATION_DEFINITION_ID, payload)
    with pytest.raises(ProfileAccessRefusedError):
        await module.ReviewPackageExchangeExecutor(subject.compose).execute(
            request, subject.context(request.definition_id)
        )
    request = _request(module.MODELO_REVIEW_PACKAGE_SIGN_OPERATION_DEFINITION_ID, payload)
    monkeypatch.setattr(module, "require_active_bucket_id", lambda: str(uuid4()))
    with pytest.raises(ProfileAccessRefusedError):
        await module.ReviewPackageExchangeExecutor(subject.compose).execute(
            request, subject.context(request.definition_id)
        )
    assert subject.fence.entries == 0 and subject.signing.keypair is None and not subject.operands.values


@pytest.mark.parametrize("missing", [DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES, None])
def test_actual_policy_requires_complete_human_destination_consent_all_periods_and_exact_action(
    subject: Subject, tmp_path: Path, missing: DisclosureCategory | None
) -> None:
    registry = _registry(subject)
    request = _request(
        module.MODELO_REVIEW_PACKAGE_SIGN_OPERATION_DEFINITION_ID,
        module.ModeloReviewPackageSignRequest(
            profile_id=PROFILE_ID, package=subject.package, output=tmp_path / "signature.json"
        ),
    )
    context = OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registry.lookup_public_contract(request.definition_id),
        published_authority=Availability.AVAILABLE,
        authority_operation=subject.operation,
    )
    resolved = module.resolve_review_package_exchange_operation_access(request, context)
    disclosures = frozenset(row for row in resolved.policy.disclosures if row.category is not missing)
    decision = policy_decision(resolved, registry, disclosures=disclosures, human=True)
    assert isinstance(decision, AccessAllowed if missing is None else AccessDenied)
    if missing is None:
        assert isinstance(policy_decision(resolved, registry, disclosures=disclosures), AccessDenied)
        assert isinstance(
            policy_decision(resolved, registry, disclosures=disclosures, human=True, all_periods=False), AccessDenied
        )
        assert isinstance(
            policy_decision(
                resolved,
                registry,
                disclosures=disclosures,
                human=True,
                operations=frozenset({module.MODELO_REVIEW_PACKAGE_DECRYPT_OPERATION_DEFINITION_ID}),
            ),
            AccessDenied,
        )
        wrong = frozenset(row.model_copy(update={"destination_id": uuid4()}) for row in disclosures)
        assert isinstance(policy_decision(resolved, registry, disclosures=wrong, human=True), AccessDenied)
    with pytest.raises(ProfileAccessRefusedError):
        module.resolve_review_package_exchange_operation_access(
            request, replace(context, frontend=OperationFrontendProjection.MCP)
        )
    observed = module.resolve_review_package_exchange_operation_access(
        request, replace(context, action=AccessAction.OBSERVE)
    )
    assert {row.category for row in observed.policy.disclosures} == {DisclosureCategory.OPERATION_METADATA}


@pytest.mark.asyncio
async def test_result_projector_refuses_foreign_purpose_effect_and_profile(subject: Subject, tmp_path: Path) -> None:
    identifier = module.MODELO_REVIEW_PACKAGE_COUNTER_SIGN_OPERATION_DEFINITION_ID
    signature = tmp_path / "signature.json"
    signed = SignedReviewPackage(
        bucket_id=str(PROFILE_ID),
        calculation_revision_id="b" * 64,
        manifest_sha256="c" * 64,
        signature_hex="d" * 128,
        public_key_hex="e" * 64,
        signed_at=INSTANT,
    )
    signature.write_text(signed.model_dump_json(), encoding="utf-8")
    await _execute(
        subject,
        identifier,
        module.ModeloReviewPackageCounterSignRequest(
            profile_id=PROFILE_ID,
            package=subject.package,
            signature=signature,
            output=tmp_path / "receipt.json",
            note="synthetic protected note",
        ),
    )
    result = cast(module.ReviewPackageExchangeExecutionResult, subject.operands.values[-1])
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="b" * 64, definition_id=identifier, subject_ref=profile_operation_subject(str(PROFILE_ID))
        ),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        result_ref="d" * 64,
        revision=1,
        settled_at=INSTANT,
    )
    assert module.project_review_package_exchange_operation_result(result, receipt) == result.projection
    for wrong in (
        receipt.model_copy(update={"effect": OperationEffect.NONE}),
        receipt.model_copy(
            update={
                "identity": receipt.identity.model_copy(
                    update={"definition_id": module.MODELO_REVIEW_PACKAGE_SIGN_OPERATION_DEFINITION_ID}
                )
            }
        ),
        receipt.model_copy(
            update={
                "identity": receipt.identity.model_copy(update={"subject_ref": profile_operation_subject(str(uuid4()))})
            }
        ),
    ):
        with pytest.raises(ValueError):
            module.project_review_package_exchange_operation_result(result, wrong)
