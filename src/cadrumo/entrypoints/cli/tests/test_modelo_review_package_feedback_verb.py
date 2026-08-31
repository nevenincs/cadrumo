"""CLI surface tests for ``aeat app modelo review-package encrypt-feedback/import-feedback``.

Exercises the recipient feedback round trip end to end against a genuine
encrypted profile bucket (no mocks): build a review package, sign it,
counter-sign it, seal the recipient's feedback (note + counter-signed receipt)
back to the originator via ``encrypt-feedback``, then ``import-feedback`` on the
originator side -- which decrypts, re-verifies BOTH signature layers against
the locally-held package, and attaches the verified countersignature to the
originator's bucket-event journal. Because the single-profile harness runs the
originator and the reviewer on the same active bucket, the operator and
counter-signer keys are identical here; the round trip still exercises the full
encrypt -> import -> verify -> journal-attach chain independently. Also proves
the feedback envelope on disk never carries a private key, and that a feedback
package with no counter-signed receipt imports as unstructured feedback with no
journal attach.

See Also:
    :func:`~application.modelo.import_feedback_package`
        Application import primitive that decrypts and verifies feedback envelopes.
    :func:`~application.modelo.encrypt_feedback_package_for_originator`
        Application primitive behind the CLI ``encrypt-feedback`` verb.
    :func:`~application.modelo.emit_collab_feedback_countersign_attached_event`
        Journal hook asserted after verified countersignature import.
    :class:`~application.modelo.RecipientFingerprintRegistryRepository`
        Encrypted recipient public-key registry used to address the originator.
    :func:`~entrypoints.cli._modelo_review_package_cli.review_package_encrypt_feedback`
        CLI verb that seals feedback for the originator.
    :func:`~entrypoints.cli._modelo_review_package_cli.review_package_import_feedback`
        CLI verb that opens feedback and attaches verified countersignatures.
    :class:`~domain.buckets.BucketEventType`
        Bucket-event enum whose collaboration event is asserted here.
    :class:`CasillaId`
        Typed casilla ids used to seed the exportable Modelo 111 revision.
    :class:`Period`
        Typed filing period used to resolve the review-package work target.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....application.modelo.review_package_recipient_encryption import (
    ensure_recipient_encryption_keypair,
    recipient_encryption_public_key,
)
from ....application.modelo.review_package_recipient_registry import RecipientFingerprintRegistryRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....domain.buckets.event import BucketEventType
from ....domain.user_profile.values import UserProfileFact
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session, set_active_test_profile_facts
from ._modelo_review_package_support import build_review_package_via_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"

_isolated_backend = active_profile_isolated_backend_fixture(bucket_id=_BUCKET_ID, dispose_engine_around=True)


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _payload_string(output: str, key: str) -> str:
    value = STR_KEYED_MAPPING_ADAPTER.validate_python(_payload(output))[key]
    assert isinstance(value, str)
    return value


def _set_export_profile_name() -> None:
    set_active_test_profile_facts(
        (
            UserProfileFact(path="identity.name", value="Ana"),
            UserProfileFact(path="identity.surnames", value="Feedback Round Trip Test"),
            UserProfileFact(path="activities.description", value="Consulting"),
        ),
    )


_M111_CASILLAS: dict[CasillaId, str] = {
    validated_casilla_id("03", surface="modelo 111 feedback test casilla"): "180.25",
    validated_casilla_id("06", surface="modelo 111 feedback test casilla"): "12.10",
    validated_casilla_id("09", surface="modelo 111 feedback test casilla"): "300.00",
    validated_casilla_id("12", surface="modelo 111 feedback test casilla"): "14.40",
    validated_casilla_id("15", surface="modelo 111 feedback test casilla"): "25.00",
    validated_casilla_id("18", surface="modelo 111 feedback test casilla"): "0.50",
    validated_casilla_id("21", surface="modelo 111 feedback test casilla"): "7.00",
    validated_casilla_id("24", surface="modelo 111 feedback test casilla"): "8.00",
    validated_casilla_id("27", surface="modelo 111 feedback test casilla"): "9.00",
    validated_casilla_id("29", surface="modelo 111 feedback test casilla"): "40.00",
}


def _build_package(tmp_path: Path, *, name: str = "review-package.zip") -> tuple[Path, str, str]:
    _set_export_profile_name()
    return build_review_package_via_cli(tmp_path, invoke=_invoke, input_values_by_casilla_id=_M111_CASILLAS, name=name)


def _register_originator(recipient_id: str) -> str:
    """Register the active bucket's own encryption public key as an 'originator', return the hex."""
    from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    repository = secure_object_repository_for_bucket(_BUCKET_ID)
    keypair = ensure_recipient_encryption_keypair(bucket_id=_BUCKET_ID, repository=repository)
    public_key = recipient_encryption_public_key(keypair)
    registry = RecipientFingerprintRegistryRepository(bucket_id=_BUCKET_ID)
    registry.add(recipient_id=recipient_id, public_key_hex=public_key.public_key_hex)
    return public_key.public_key_hex


def _sign(tmp_path: Path, package_path: Path) -> tuple[Path, str]:
    signature_path = tmp_path / "signature.json"
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "sign",
            str(package_path),
            "--output",
            str(signature_path),
        ],
    )
    assert result.exit_code == 0, result.output
    return signature_path, _payload_string(result.output, "signer_public_key_hex")


def _counter_sign(tmp_path: Path, package_path: Path, signature_path: Path) -> tuple[Path, str]:
    receipt_path = tmp_path / "receipt.json"
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "counter-sign",
            str(package_path),
            str(signature_path),
            "--output",
            str(receipt_path),
            "--note",
            "reviewed, no changes",
        ],
    )
    assert result.exit_code == 0, result.output
    return receipt_path, _payload_string(result.output, "counter_signer_public_key_hex")


def test_encrypt_feedback_then_import_feedback_attaches_countersign_to_journal(tmp_path: Path) -> None:
    package_path, work_unit_id, calculation_revision_id = _build_package(tmp_path)
    originator_public_key_hex = _register_originator("my-client")
    signature_path, operator_public_key_hex = _sign(tmp_path, package_path)
    receipt_path, counter_signer_public_key_hex = _counter_sign(tmp_path, package_path, signature_path)

    feedback_envelope_path = tmp_path / "feedback-envelope.json"
    encrypt_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "encrypt-feedback",
            "--originator",
            "my-client",
            "--work-unit-id",
            work_unit_id,
            "--calculation-revision-id",
            calculation_revision_id,
            "--by",
            "my-accountant",
            "--note",
            "all clear",
            "--receipt",
            str(receipt_path),
            "--output",
            str(feedback_envelope_path),
        ],
    )
    assert encrypt_result.exit_code == 0, encrypt_result.output
    encrypt_payload = _payload(encrypt_result.output)
    assert encrypt_payload["has_counter_sign"] is True
    assert encrypt_payload["originator_public_key_hex"] == originator_public_key_hex
    assert feedback_envelope_path.exists()

    # Ciphertext-only-on-disk: never a private key in the sealed envelope.
    envelope_text = feedback_envelope_path.read_text(encoding="utf-8")
    assert "private_key" not in envelope_text

    import_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "import-feedback",
            str(feedback_envelope_path),
            "--package",
            str(package_path),
            "--operator-public-key",
            operator_public_key_hex,
            "--counter-signer-public-key",
            counter_signer_public_key_hex,
        ],
    )
    assert import_result.exit_code == 0, import_result.output
    import_payload = _payload(import_result.output)
    assert import_payload["counter_signature_verified"] is True
    assert import_payload["attached_to_journal"] is True
    assert import_payload["note"] == "all clear"
    assert import_payload["submitted_by"] == "my-accountant"
    assert "private_key" not in import_result.output

    # Countersign-attach-to-journal: the originator's own bucket-event history
    # now carries the COLLAB_PACKAGE_COUNTER_SIGNED attach event.
    with open_test_profile_session(_BUCKET_ID):
        catalogue = BucketEventHistoryRepository().load()
    attach_events = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED
    ]
    assert attach_events, [event.event_type for event in catalogue.events.values()]


def test_import_feedback_without_receipt_is_unstructured_no_journal_attach(tmp_path: Path) -> None:
    package_path, work_unit_id, calculation_revision_id = _build_package(tmp_path)
    _register_originator("my-client")
    _signature_path, operator_public_key_hex = _sign(tmp_path, package_path)

    feedback_envelope_path = tmp_path / "feedback-envelope.json"
    encrypt_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "encrypt-feedback",
            "--originator",
            "my-client",
            "--work-unit-id",
            work_unit_id,
            "--calculation-revision-id",
            calculation_revision_id,
            "--by",
            "my-accountant",
            "--note",
            "see attached corrections, no formal sign-off yet",
            "--output",
            str(feedback_envelope_path),
        ],
    )
    assert encrypt_result.exit_code == 0, encrypt_result.output
    assert _payload(encrypt_result.output)["has_counter_sign"] is False

    import_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "import-feedback",
            str(feedback_envelope_path),
            "--package",
            str(package_path),
            "--operator-public-key",
            operator_public_key_hex,
        ],
    )
    assert import_result.exit_code == 0, import_result.output
    import_payload = _payload(import_result.output)
    assert import_payload["counter_signature_verified"] is None
    assert import_payload["attached_to_journal"] is False
    assert import_payload["note"] == "see attached corrections, no formal sign-off yet"


def test_import_feedback_refuses_tampered_feedback_envelope(tmp_path: Path) -> None:
    package_path, work_unit_id, calculation_revision_id = _build_package(tmp_path)
    _register_originator("my-client")
    _signature_path, operator_public_key_hex = _sign(tmp_path, package_path)

    feedback_envelope_path = tmp_path / "feedback-envelope.json"
    encrypt_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "encrypt-feedback",
            "--originator",
            "my-client",
            "--work-unit-id",
            work_unit_id,
            "--calculation-revision-id",
            calculation_revision_id,
            "--by",
            "my-accountant",
            "--note",
            "all clear",
            "--output",
            str(feedback_envelope_path),
        ],
    )
    assert encrypt_result.exit_code == 0, encrypt_result.output

    # Corrupt the ciphertext hex in the envelope on disk.
    envelope_json = json.loads(feedback_envelope_path.read_text(encoding="utf-8"))
    ciphertext_hex = envelope_json["ciphertext"]
    flipped = "0" if ciphertext_hex[-1] != "0" else "1"
    envelope_json["ciphertext"] = ciphertext_hex[:-1] + flipped
    feedback_envelope_path.write_text(json.dumps(envelope_json), encoding="utf-8")

    import_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "import-feedback",
            str(feedback_envelope_path),
            "--package",
            str(package_path),
            "--operator-public-key",
            operator_public_key_hex,
        ],
    )
    assert import_result.exit_code != 0


__all__: list[str] = []
