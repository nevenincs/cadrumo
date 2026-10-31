"""Native exact-profile coverage for the six registered review-package exchange leaves."""

from __future__ import annotations

import json
import sys
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import pytest
from click.testing import Result
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.review_package_recipient_encryption import RecipientEncryptionAdapter
from cadrumo.adapters.persistence.profile.review_package_recipient_registry import (
    build_recipient_fingerprint_registry_ports,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.application.modelo.review_package_recipient_encryption import ensure_recipient_encryption_keypair
from cadrumo.application.modelo.review_package_recipient_registry import add_recipient_fingerprint
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.workflow.persistence import workflow_state_repository
from cadrumo.core.config import override_settings
from cadrumo.core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.tests import modelo_operation_test_support
from cadrumo.tests.cli_envelope import require_error_document, unwrap_cli_result
from cadrumo_runtime.host.tests.native_commands.runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    RuntimeFailureObservation,
    native_cli_profile_scope,
)

from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.tax_id": "12345678Z",
    "identity.name": "Native",
    "identity.surnames": "Review Package",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    "withholding.colegio_concertado": "false",
}


def _invoke(
    profile: NativeCliProfileFixture,
    *command: str,
    output_format: str = "json",
) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(
            (
                "--language",
                "en",
                "--format",
                output_format,
                "--profile",
                profile.label,
                "--profile-secrets-stdin",
                *command,
            ),
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    assert profile.passphrase not in result.output
    return result


def _invoke_public(*command: str) -> Result:
    return invoke_cached_cli(("--language", "en", "--format", "json", *command))


def _reauthenticate(profile: NativeCliProfileFixture, operation: PinnedAuthorityOperation) -> str:
    assert profile.label is not None
    close_active_bucket_session()
    session = authenticate_profile_for_invocation(
        name=profile.label,
        passphrase_callback=lambda: profile.passphrase,
        profile_decode_context=operation.profile_decode_context(),
    )
    return str(session.bucket_id)


def _payload(result: Result) -> dict[str, object]:
    value = unwrap_cli_result(result)
    assert isinstance(value, dict)
    return STR_KEYED_MAPPING_ADAPTER.validate_python(value)


def _register_recipient(bucket_id: str, recipient_id: str, public_key_hex: str) -> None:
    add_recipient_fingerprint(
        recipient_id=recipient_id,
        public_key_hex=public_key_hex,
        ports=build_recipient_fingerprint_registry_ports(bucket_id=bucket_id),
    )


def _own_public_key(bucket_id: str) -> str:
    objects = secure_object_repository_for_bucket(bucket_id)
    keypair = ensure_recipient_encryption_keypair(
        bucket_id=bucket_id,
        recipient_encryption=RecipientEncryptionAdapter(repository=objects, bucket_id=bucket_id),
    )
    return keypair.public_key_hex


def _write_tampered_package(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source, "r") as original, zipfile.ZipFile(destination, "w") as tampered:
        for member in original.infolist():
            data = b"TAMPERED" if member.filename == "draft.fichero-boe" else original.read(member.filename)
            tampered.writestr(member, data)


def _assert_refused(result: Result) -> None:
    assert result.exit_code != 0, result.output


@dataclass
class _Exchange:
    """The profile session and artifacts the review-package exchange steps hand to one another."""

    profile: NativeCliProfileFixture
    tmp_path: Path
    operation: PinnedAuthorityOperation
    bucket_id: str
    work_unit_id: str
    revision_id: str
    package_path: Path
    package_bytes: bytes
    own_encryption_public_key: str
    signer_public_key: str = field(init=False)
    signature_path: Path = field(init=False)
    signature_document: dict[str, object] = field(init=False)
    counter_receipt_path: Path = field(init=False)
    counter_public_key: str = field(init=False)


def _sign_and_counter_sign(ex: _Exchange) -> None:
    """Sign the package, verify the signature, counter-sign it and verify the receipt."""
    ex.signature_path = (ex.tmp_path / "signature.json").resolve()
    signed = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "sign",
        str(ex.package_path),
        "--output",
        str(ex.signature_path),
    )
    assert signed.exit_code == 0, signed.output
    signed_payload = _payload(signed)
    signer_public_key = signed_payload["signer_public_key_hex"]
    assert isinstance(signer_public_key, str) and len(signer_public_key) == 64
    ex.signer_public_key = signer_public_key
    assert signed_payload["operation"] == "modelo.review_package.sign"
    assert signed_payload["package_path"] == str(ex.package_path)
    assert signed_payload["signature_path"] == str(ex.signature_path)
    assert ex.signature_path.exists()
    ex.signature_document = json.loads(ex.signature_path.read_text(encoding="utf-8"))
    assert ex.signature_document["public_key_hex"] == ex.signer_public_key
    assert "private_key" not in signed.output
    assert "private_key" not in ex.signature_path.read_text(encoding="utf-8")

    verified_signature = _invoke_public(
        "app",
        "modelo",
        "review-package",
        "verify-signature",
        str(ex.package_path),
        str(ex.signature_path),
        "--public-key",
        ex.signer_public_key,
    )
    assert verified_signature.exit_code == 0, verified_signature.output
    assert _payload(verified_signature)["is_valid"] is True
    assert _payload(verified_signature)["package_path"] == str(ex.package_path)

    ex.counter_receipt_path = (ex.tmp_path / "counter-receipt.json").resolve()
    counter_signed = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "counter-sign",
        str(ex.package_path),
        str(ex.signature_path),
        "--output",
        str(ex.counter_receipt_path),
        "--note",
        "reviewed, no changes",
    )
    assert counter_signed.exit_code == 0, counter_signed.output
    counter_payload = _payload(counter_signed)
    counter_public_key = counter_payload["counter_signer_public_key_hex"]
    assert isinstance(counter_public_key, str) and len(counter_public_key) == 64
    ex.counter_public_key = counter_public_key
    assert counter_payload["note"] == "reviewed, no changes"
    assert counter_payload["receipt_path"] == str(ex.counter_receipt_path)
    assert ex.counter_receipt_path.exists()
    assert "private_key" not in counter_signed.output
    assert "private_key" not in ex.counter_receipt_path.read_text(encoding="utf-8")

    verified_receipt = _invoke_public(
        "app",
        "modelo",
        "review-package",
        "verify-receipt",
        str(ex.package_path),
        str(ex.counter_receipt_path),
        "--operator-public-key",
        ex.signer_public_key,
        "--counter-signer-public-key",
        ex.counter_public_key,
    )
    assert verified_receipt.exit_code == 0, verified_receipt.output
    assert _payload(verified_receipt)["is_valid"] is True


def _forged_proofs_verify_as_invalid(ex: _Exchange) -> None:
    """A bad signature, tampered package, wrong key and edited receipt each verify as invalid."""
    invalid_signature_path = (ex.tmp_path / "invalid-signature.json").resolve()
    invalid_signature = dict(ex.signature_document)
    invalid_signature["signature_hex"] = "0" * 128
    invalid_signature_path.write_text(json.dumps(invalid_signature), encoding="utf-8")
    invalid_signature_verification = _invoke_public(
        "app",
        "modelo",
        "review-package",
        "verify-signature",
        str(ex.package_path),
        str(invalid_signature_path),
        "--public-key",
        ex.signer_public_key,
    )
    assert invalid_signature_verification.exit_code == 0, invalid_signature_verification.output
    assert _payload(invalid_signature_verification)["is_valid"] is False
    no_verify_receipt_path = (ex.tmp_path / "counter-sign-without-verification.json").resolve()
    counter_signed_unverified = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "counter-sign",
        str(ex.package_path),
        str(invalid_signature_path),
        "--output",
        str(no_verify_receipt_path),
    )
    assert counter_signed_unverified.exit_code == 0, counter_signed_unverified.output
    unverified_receipt = _invoke_public(
        "app",
        "modelo",
        "review-package",
        "verify-receipt",
        str(ex.package_path),
        str(no_verify_receipt_path),
        "--operator-public-key",
        ex.signer_public_key,
        "--counter-signer-public-key",
        ex.counter_public_key,
    )
    assert unverified_receipt.exit_code == 0, unverified_receipt.output
    assert _payload(unverified_receipt)["is_valid"] is False

    tampered_package_path = (ex.tmp_path / "tampered-package.zip").resolve()
    _write_tampered_package(ex.package_path, tampered_package_path)
    tampered_signature = _invoke_public(
        "app",
        "modelo",
        "review-package",
        "verify-signature",
        str(tampered_package_path),
        str(ex.signature_path),
        "--public-key",
        ex.signer_public_key,
    )
    assert tampered_signature.exit_code == 0, tampered_signature.output
    assert _payload(tampered_signature)["is_valid"] is False
    wrong_key_signature = _invoke_public(
        "app",
        "modelo",
        "review-package",
        "verify-signature",
        str(ex.package_path),
        str(ex.signature_path),
        "--public-key",
        "0" * 64,
    )
    assert wrong_key_signature.exit_code == 0, wrong_key_signature.output
    assert _payload(wrong_key_signature)["is_valid"] is False

    edited_receipt_path = (ex.tmp_path / "edited-receipt.json").resolve()
    edited_receipt = json.loads(ex.counter_receipt_path.read_text(encoding="utf-8"))
    edited_receipt["note"] = "edited after signing"
    edited_receipt_path.write_text(json.dumps(edited_receipt), encoding="utf-8")
    edited_verification = _invoke_public(
        "app",
        "modelo",
        "review-package",
        "verify-receipt",
        str(ex.package_path),
        str(edited_receipt_path),
        "--operator-public-key",
        ex.signer_public_key,
        "--counter-signer-public-key",
        ex.counter_public_key,
    )
    assert edited_verification.exit_code == 0, edited_verification.output
    assert _payload(edited_verification)["is_valid"] is False


def _seal_decrypt_and_refuse_a_replay(ex: _Exchange) -> None:
    """Seal for the recipient, refuse a corrupt or replayed envelope and a wrong recipient."""
    sealed_path = (ex.tmp_path / "sealed.json").resolve()
    sealed = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "encrypt-for-recipient",
        str(ex.package_path),
        "--recipient",
        "native-self",
        "--output",
        str(sealed_path),
    )
    assert sealed.exit_code == 0, sealed.output
    sealed_payload = _payload(sealed)
    assert sealed_payload["operation"] == "modelo.review_package.encrypt_for_recipient"
    assert sealed_payload["recipient_id"] == "native-self"
    assert sealed_payload["recipient_public_key_hex"] == ex.own_encryption_public_key
    assert sealed_payload["review_only"] is False
    assert sealed_payload["valid_until"] is None
    envelope_text = sealed_path.read_text(encoding="utf-8")
    assert ex.package_bytes not in envelope_text.encode("latin-1", errors="ignore")
    assert "private_key" not in envelope_text

    corrupted_envelope_path = (ex.tmp_path / "corrupted-envelope.json").resolve()
    corrupted_envelope = json.loads(envelope_text)
    ciphertext = corrupted_envelope["ciphertext"]
    assert isinstance(ciphertext, str) and ciphertext
    corrupted_envelope["ciphertext"] = ciphertext[:-1] + ("0" if ciphertext[-1] != "0" else "1")
    corrupted_envelope_path.write_text(json.dumps(corrupted_envelope), encoding="utf-8")
    corrupted_decryption_output = ex.tmp_path / "corrupted-envelope-output.zip"
    corrupted_decryption = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "decrypt",
        str(corrupted_envelope_path),
        "--output",
        str(corrupted_decryption_output),
    )
    _assert_refused(corrupted_decryption)
    assert not corrupted_decryption_output.exists()

    plaintext_path = (ex.tmp_path / "recovered.zip").resolve()
    decrypted = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "decrypt",
        str(sealed_path),
        "--output",
        str(plaintext_path),
    )
    assert decrypted.exit_code == 0, decrypted.output
    decrypted_payload = _payload(decrypted)
    assert decrypted_payload["bucket_id"] == ex.bucket_id
    assert decrypted_payload["review_only"] is False
    assert plaintext_path.read_bytes() == ex.package_bytes
    with zipfile.ZipFile(plaintext_path, "r") as recovered_archive:
        assert "draft.fichero-boe" in set(recovered_archive.namelist())
    replay = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "decrypt",
        str(sealed_path),
        "--output",
        str(ex.tmp_path / "replay.zip"),
    )
    _assert_refused(replay)
    assert not (ex.tmp_path / "replay.zip").exists()

    review_only_path = (ex.tmp_path / "review-only.json").resolve()
    review_only = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "encrypt-for-recipient",
        str(ex.package_path),
        "--recipient",
        "native-self",
        "--output",
        str(review_only_path),
        "--review-only",
        "--valid-for-days",
        "30",
    )
    assert review_only.exit_code == 0, review_only.output
    review_only_payload = _payload(review_only)
    assert review_only_payload["review_only"] is True
    assert review_only_payload["valid_until"] is not None
    reviewed_package_path = (ex.tmp_path / "review-only-recovered.zip").resolve()
    reviewed = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "decrypt",
        str(review_only_path),
        "--output",
        str(reviewed_package_path),
        output_format="text",
    )
    assert reviewed.exit_code == 0, reviewed.output
    assert "modelo.review_package.decrypt" in reviewed.output
    assert "review_only" in reviewed.output
    assert reviewed_package_path.read_bytes() == ex.package_bytes

    mismatch_path = (ex.tmp_path / "recipient-mismatch.json").resolve()
    mismatch_encryption = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "encrypt-for-recipient",
        str(ex.package_path),
        "--recipient",
        "native-outsider",
        "--output",
        str(mismatch_path),
    )
    assert mismatch_encryption.exit_code == 0, mismatch_encryption.output
    mismatch_plaintext = ex.tmp_path / "must-not-decrypt.zip"
    mismatch_decryption = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "decrypt",
        str(mismatch_path),
        "--output",
        str(mismatch_plaintext),
    )
    _assert_refused(mismatch_decryption)
    assert not mismatch_plaintext.exists()


def _refuse_unusable_inputs(ex: _Exchange) -> None:
    """Unknown recipients, missing files and wrong-profile requests are refused without output."""
    unknown_recipient = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "encrypt-for-recipient",
        str(ex.package_path),
        "--recipient",
        "not-registered",
        "--output",
        str(ex.tmp_path / "unknown-recipient.json"),
    )
    _assert_refused(unknown_recipient)
    missing_encrypt_package = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "encrypt-for-recipient",
        str(ex.tmp_path / "missing-package.zip"),
        "--recipient",
        "native-self",
        "--output",
        str(ex.tmp_path / "missing-package-envelope.json"),
    )
    _assert_refused(missing_encrypt_package)
    invalid_expiry = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "encrypt-for-recipient",
        str(ex.package_path),
        "--recipient",
        "native-self",
        "--output",
        str(ex.tmp_path / "invalid-expiry.json"),
        "--valid-for-days",
        "0",
    )
    _assert_refused(invalid_expiry)

    wrong_bucket_output = (ex.tmp_path / "wrong-profile-signature.json").resolve()
    wrong_profile = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "sign",
        str(ex.package_path),
        "--output",
        str(wrong_bucket_output),
        "--bucket-id",
        "22222222-2222-4222-8222-222222222222",
    )
    _assert_refused(wrong_profile)
    assert not wrong_bucket_output.exists()

    missing_sign = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "sign",
        str(ex.tmp_path / "missing-package.zip"),
        "--output",
        str(ex.tmp_path / "missing-signature.json"),
    )
    _assert_refused(missing_sign)
    missing_counter_signature = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "counter-sign",
        str(ex.package_path),
        str(ex.tmp_path / "missing-signature.json"),
        "--output",
        str(ex.tmp_path / "missing-receipt.json"),
    )
    _assert_refused(missing_counter_signature)
    missing_envelope = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "decrypt",
        str(ex.tmp_path / "missing-envelope.json"),
        "--output",
        str(ex.tmp_path / "missing-plaintext.zip"),
    )
    _assert_refused(missing_envelope)
    malformed_envelope_path = (ex.tmp_path / "malformed-envelope.json").resolve()
    malformed_envelope_path.write_text("not json", encoding="utf-8")
    malformed_envelope = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "decrypt",
        str(malformed_envelope_path),
        "--output",
        str(ex.tmp_path / "malformed-plaintext.zip"),
    )
    _assert_refused(malformed_envelope)
    assert not (ex.tmp_path / "malformed-plaintext.zip").exists()


def _exchange_feedback(ex: _Exchange) -> None:
    """Encrypt and import reviewer feedback with and without a counter-sign receipt."""
    feedback_path = (ex.tmp_path / "feedback.json").resolve()
    encrypted_feedback = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "encrypt-feedback",
        "--originator",
        "native-self",
        "--work-unit-id",
        ex.work_unit_id,
        "--calculation-revision-id",
        ex.revision_id,
        "--by",
        "native-reviewer",
        "--note",
        "all clear",
        "--receipt",
        str(ex.counter_receipt_path),
        "--output",
        str(feedback_path),
    )
    assert encrypted_feedback.exit_code == 0, encrypted_feedback.output
    feedback_payload = _payload(encrypted_feedback)
    assert feedback_payload["has_counter_sign"] is True
    assert feedback_payload["originator_public_key_hex"] == ex.own_encryption_public_key
    feedback_text = feedback_path.read_text(encoding="utf-8")
    assert "all clear" not in feedback_text
    assert "private_key" not in feedback_text
    imported_feedback = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "import-feedback",
        str(feedback_path),
        str(ex.package_path),
        "--operator-public-key",
        ex.signer_public_key,
        "--counter-signer-public-key",
        ex.counter_public_key,
    )
    assert imported_feedback.exit_code == 0, imported_feedback.output
    imported_payload = _payload(imported_feedback)
    assert imported_payload["bucket_id"] == ex.bucket_id
    assert imported_payload["counter_signature_verified"] is True
    assert imported_payload["attached_to_journal"] is True
    assert imported_payload["note"] == "all clear"
    assert imported_payload["submitted_by"] == "native-reviewer"
    assert "private_key" not in imported_feedback.output

    ex.bucket_id = _reauthenticate(ex.profile, ex.operation)
    before_unstructured_import = BucketEventHistoryRepository().load()
    attached_before = {
        event.event_id
        for event in before_unstructured_import.events.values()
        if event.bucket_id == ex.bucket_id and event.event_type is BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED
    }

    no_receipt_feedback_path = (ex.tmp_path / "unstructured-feedback.json").resolve()
    no_receipt_feedback = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "encrypt-feedback",
        "--originator",
        "native-self",
        "--work-unit-id",
        ex.work_unit_id,
        "--calculation-revision-id",
        ex.revision_id,
        "--by",
        "native-reviewer",
        "--note",
        "informal review",
        "--output",
        str(no_receipt_feedback_path),
    )
    assert no_receipt_feedback.exit_code == 0, no_receipt_feedback.output
    assert _payload(no_receipt_feedback)["has_counter_sign"] is False
    unstructured_import = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "import-feedback",
        str(no_receipt_feedback_path),
        str(ex.package_path),
        "--operator-public-key",
        ex.signer_public_key,
    )
    assert unstructured_import.exit_code == 0, unstructured_import.output
    unstructured_payload = _payload(unstructured_import)
    assert unstructured_payload["counter_signature_verified"] is None
    assert unstructured_payload["attached_to_journal"] is False
    assert unstructured_payload["note"] == "informal review"
    ex.bucket_id = _reauthenticate(ex.profile, ex.operation)
    after_unstructured_import = BucketEventHistoryRepository().load()
    attached_after = {
        event.event_id
        for event in after_unstructured_import.events.values()
        if event.bucket_id == ex.bucket_id and event.event_type is BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED
    }
    assert attached_after == attached_before

    corrupted_feedback_path = (ex.tmp_path / "corrupted-feedback.json").resolve()
    corrupted_feedback = json.loads(no_receipt_feedback_path.read_text(encoding="utf-8"))
    ciphertext = corrupted_feedback["ciphertext"]
    assert isinstance(ciphertext, str) and ciphertext
    corrupted_feedback["ciphertext"] = ciphertext[:-1] + ("0" if ciphertext[-1] != "0" else "1")
    corrupted_feedback_path.write_text(json.dumps(corrupted_feedback), encoding="utf-8")
    rejected_feedback = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "import-feedback",
        str(corrupted_feedback_path),
        str(ex.package_path),
        "--operator-public-key",
        ex.signer_public_key,
    )
    _assert_refused(rejected_feedback)
    missing_feedback_receipt = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "encrypt-feedback",
        "--originator",
        "native-self",
        "--work-unit-id",
        ex.work_unit_id,
        "--calculation-revision-id",
        ex.revision_id,
        "--by",
        "native-reviewer",
        "--receipt",
        str(ex.tmp_path / "missing-feedback-receipt.json"),
        "--output",
        str(ex.tmp_path / "missing-feedback-output.json"),
    )
    _assert_refused(missing_feedback_receipt)
    missing_feedback_envelope = _invoke(
        ex.profile,
        "app",
        "modelo",
        "review-package",
        "import-feedback",
        str(ex.tmp_path / "missing-feedback-envelope.json"),
        str(ex.package_path),
        "--operator-public-key",
        ex.signer_public_key,
    )
    _assert_refused(missing_feedback_envelope)


def test_native_review_package_exchange_round_trip_and_refusals(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Run the full sign/seal/return path through one authenticated profile worker."""
    with native_cli_profile_scope(tmp_path) as profile:
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(label="native-review-package", facts=_PROFILE_FACTS)
        bucket_id = _reauthenticate(profile, operation)
        assert workflow_state_repository().load().active_profile_bucket_id() == bucket_id
        revision_id, report_id = modelo_operation_test_support.seeded_modelo_verification_report(
            UUID(bucket_id), operation=operation
        )
        revision = (
            CalculationRevisionCatalogueRepository(bucket_id=bucket_id).load(operation=operation).get(revision_id)
        )
        assert revision is not None and revision.verified_at is not None and report_id
        work_unit_id = revision.work_unit_id

        def build_invoke(arguments: Sequence[str]) -> Result:
            result = _invoke(profile, *arguments)
            if result.exit_code != 0:
                error = require_error_document(result.output)["error"]
                diagnostics = {
                    "code": error["code"],
                    "submitted_definitions": [
                        row.definition_id
                        for row in failures
                        if row.stage == "profile_operation_entered" and row.definition_id is not None
                    ],
                    "failures": [
                        {
                            "stage": row.stage,
                            "type": row.exception_type,
                            "phase": row.phase,
                            "action": row.action,
                            "reason": row.reason,
                            "locations": row.traceback_locations,
                        }
                        for row in failures
                        if row.exception_type is not None
                    ],
                }
                pytest.fail(json.dumps(diagnostics), pytrace=False)
            return result

        package_path = (tmp_path / "review-package.zip").resolve()
        build_invoke(("app", "modelo", "review-package", "build", work_unit_id, "--output", str(package_path)))
        package_bytes = package_path.read_bytes()

        bucket_id = _reauthenticate(profile, operation)
        own_encryption_public_key = _own_public_key(bucket_id)
        _register_recipient(bucket_id, "native-self", own_encryption_public_key)
        outsider_private_key = X25519PrivateKey.generate()
        outsider_public_key = (
            outsider_private_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            .hex()
        )
        _register_recipient(bucket_id, "native-outsider", outsider_public_key)

        ex = _Exchange(
            profile=profile,
            tmp_path=tmp_path,
            operation=operation,
            bucket_id=bucket_id,
            work_unit_id=work_unit_id,
            revision_id=revision_id,
            package_path=package_path,
            package_bytes=package_bytes,
            own_encryption_public_key=own_encryption_public_key,
        )
        _sign_and_counter_sign(ex)
        _forged_proofs_verify_as_invalid(ex)
        _seal_decrypt_and_refuse_a_replay(ex)
        _refuse_unusable_inputs(ex)
        _exchange_feedback(ex)

        bucket_id = _reauthenticate(profile, operation)
        history = BucketEventHistoryRepository().load()
        event_types = [event.event_type for event in history.events.values() if event.bucket_id == bucket_id]
        assert BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED in event_types
        assert BucketEventType.COLLAB_PACKAGE_ENCRYPTED_FOR_RECIPIENT in event_types
        assert BucketEventType.COLLAB_PACKAGE_DECRYPTED in event_types


__all__: list[str] = []
