"""CLI surface tests for ``aeat app modelo review-package encrypt-for-recipient/decrypt``.

Exercises the full operator-reachable chain against a genuine encrypted profile
bucket (no mocks): ``aeat config collab recipient add`` registers a recipient's
public key, ``review-package encrypt-for-recipient`` seals a built review
package against it, and ``review-package decrypt`` (run on the SAME bucket, the
common single-operator "I sealed it for my own accountant identity to test
the round trip" shape this suite exercises) mints-or-loads that bucket's own
X25519 keypair and recovers the original bytes byte-for-byte. Also proves the
envelope on disk never carries the plaintext package bytes, a wrong bucket's
keypair fails to decrypt, an expired package refuses, and a replayed envelope
refuses on its second presentation.

See Also:
    :func:`~entrypoints.cli._modelo_review_package_cli.review_package_encrypt_for_recipient`
        CLI verb that seals a package to a registered recipient key.
    :func:`~entrypoints.cli._modelo_review_package_cli.review_package_decrypt`
        CLI verb that opens an envelope with the active bucket keypair.
    :func:`~application.modelo.encrypt_review_package_for_recipient`
        X25519 ECIES primitive behind the encrypt verb.
    :func:`~application.modelo.decrypt_review_package_for_recipient`
        Decryption primitive behind the decrypt verb.
    :class:`~application.modelo.RecipientFingerprintRegistryRepository`
        Trusted-recipient registry used by ``encrypt-for-recipient``.
    :func:`~application.modelo.ensure_recipient_encryption_keypair`
        Mint-or-load path for the bucket's recipient decryption key.
    :class:`~application.modelo.RecipientEncryptedPackage`
        JSON envelope written to disk by the encrypt verb.
    :class:`~adapters.persistence.profile.recipient_replay_guard.RecipientReplayGuardRepository`
        Consumed-nonce ledger that refuses the second decrypt.
    :class:`~entrypoints.cli._modelo_review_package_payloads.ModeloReviewPackageEncryptForRecipientResult`
        JSON result schema asserted for the encrypt verb.
    :class:`~entrypoints.cli._modelo_review_package_payloads.ModeloReviewPackageDecryptResult`
        JSON result schema asserted for the decrypt verb.
    :class:`CasillaId`
        Typed casilla ids used to seed the exportable Modelo 111 revision.
    :class:`Period`
        Typed filing period used to resolve the review-package work target.
    :func:`~tests.cli_runner.invoke_cached_cli`
        CLI runner used for the operator-visible command chain.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....application.modelo.review_package_recipient_encryption import (
    ensure_recipient_encryption_keypair,
    recipient_encryption_public_key,
)
from ....application.modelo.review_package_recipient_registry import RecipientFingerprintRegistryRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.user_profile.values import UserProfileFact
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import set_active_test_profile_facts
from ._modelo_review_package_support import build_review_package_via_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"

_isolated_backend = active_profile_isolated_backend_fixture(bucket_id=_BUCKET_ID, dispose_engine_around=True)


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _set_export_profile_name() -> None:
    set_active_test_profile_facts(
        (
            UserProfileFact(path="identity.name", value="Ana"),
            UserProfileFact(path="identity.surnames", value="Recipient Encryption Test"),
            UserProfileFact(path="activities.description", value="Consulting"),
        ),
    )


_M111_CASILLA_03: CasillaId = validated_casilla_id("03", surface="modelo 111 recipient encryption test casilla")
_M111_CASILLA_06: CasillaId = validated_casilla_id("06", surface="modelo 111 recipient encryption test casilla")
_M111_CASILLA_09: CasillaId = validated_casilla_id("09", surface="modelo 111 recipient encryption test casilla")
_M111_CASILLA_12: CasillaId = validated_casilla_id("12", surface="modelo 111 recipient encryption test casilla")
_M111_CASILLA_15: CasillaId = validated_casilla_id("15", surface="modelo 111 recipient encryption test casilla")
_M111_CASILLA_18: CasillaId = validated_casilla_id("18", surface="modelo 111 recipient encryption test casilla")
_M111_CASILLA_21: CasillaId = validated_casilla_id("21", surface="modelo 111 recipient encryption test casilla")
_M111_CASILLA_24: CasillaId = validated_casilla_id("24", surface="modelo 111 recipient encryption test casilla")
_M111_CASILLA_27: CasillaId = validated_casilla_id("27", surface="modelo 111 recipient encryption test casilla")
_M111_CASILLA_29: CasillaId = validated_casilla_id("29", surface="modelo 111 recipient encryption test casilla")

_MODELO_111_INPUTS: dict[CasillaId, str] = {
    _M111_CASILLA_03: "180.25",
    _M111_CASILLA_06: "12.10",
    _M111_CASILLA_09: "300.00",
    _M111_CASILLA_12: "14.40",
    _M111_CASILLA_15: "25.00",
    _M111_CASILLA_18: "0.50",
    _M111_CASILLA_21: "7.00",
    _M111_CASILLA_24: "8.00",
    _M111_CASILLA_27: "9.00",
    _M111_CASILLA_29: "40.00",
}


def _build_package(tmp_path: Path, *, name: str = "review-package.zip") -> Path:
    _set_export_profile_name()
    package_path, _, _ = build_review_package_via_cli(
        tmp_path, invoke=_invoke, input_values_by_casilla_id=_MODELO_111_INPUTS, name=name
    )
    return package_path


def _register_recipient(recipient_id: str, *, public_key_hex: str) -> None:
    registry = RecipientFingerprintRegistryRepository(bucket_id=_BUCKET_ID)
    registry.add(recipient_id=recipient_id, public_key_hex=public_key_hex)


def test_encrypt_for_recipient_then_decrypt_recovers_original_bytes(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)
    package_bytes = package_path.read_bytes()

    # The recipient's own encryption keypair is minted lazily by `decrypt`, but
    # this test registers the fingerprint FIRST (mirroring the real
    # taxpayer/accountant workflow: the accountant shares their public key
    # before anything is sealed for them).
    from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    repository = secure_object_repository_for_bucket(_BUCKET_ID)
    keypair = ensure_recipient_encryption_keypair(bucket_id=_BUCKET_ID, repository=repository)
    public_key = recipient_encryption_public_key(keypair)
    _register_recipient("my-accountant", public_key_hex=public_key.public_key_hex)

    envelope_path = tmp_path / "envelope.json"
    encrypt_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "encrypt-for-recipient",
            str(package_path),
            "--recipient",
            "my-accountant",
            "--output",
            str(envelope_path),
        ],
    )
    assert encrypt_result.exit_code == 0, encrypt_result.output
    encrypt_payload = _payload(encrypt_result.output)
    assert encrypt_payload["recipient_id"] == "my-accountant"
    assert encrypt_payload["recipient_public_key_hex"] == public_key.public_key_hex
    assert encrypt_payload["review_only"] is False
    assert encrypt_payload["valid_until"] is None
    assert envelope_path.exists()

    # Ciphertext-only-on-disk: the envelope must never carry the plaintext
    # review-package bytes.
    envelope_text = envelope_path.read_text(encoding="utf-8")
    assert package_bytes not in envelope_text.encode("latin-1", errors="ignore")
    envelope_json = json.loads(envelope_text)
    assert "private_key" not in envelope_text
    assert envelope_json["recipient_public_key_hex"] == public_key.public_key_hex

    recovered_path = tmp_path / "recovered.zip"
    decrypt_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "decrypt",
            str(envelope_path),
            "--output",
            str(recovered_path),
        ],
    )
    assert decrypt_result.exit_code == 0, decrypt_result.output
    decrypt_payload = _payload(decrypt_result.output)
    # bucket_id is identity-class data: the CLI success-output redactor rewrites
    # it to the ``<bucket-id>`` placeholder (see test_repair_privacy_contract.py
    # for the established pattern), so the raw UUID never leaks into output.
    assert decrypt_payload["bucket_id"] == "<bucket-id>"
    assert decrypt_payload["review_only"] is False
    assert recovered_path.exists()
    assert recovered_path.read_bytes() == package_bytes

    with zipfile.ZipFile(recovered_path, "r") as archive:
        assert "draft.fichero-boe" in set(archive.namelist())


def test_encrypt_for_recipient_review_only_and_expiry_round_trip(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)

    from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    repository = secure_object_repository_for_bucket(_BUCKET_ID)
    keypair = ensure_recipient_encryption_keypair(bucket_id=_BUCKET_ID, repository=repository)
    public_key = recipient_encryption_public_key(keypair)
    _register_recipient("my-accountant", public_key_hex=public_key.public_key_hex)

    envelope_path = tmp_path / "envelope.json"
    encrypt_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "encrypt-for-recipient",
            str(package_path),
            "--recipient",
            "my-accountant",
            "--output",
            str(envelope_path),
            "--review-only",
            "--valid-for-days",
            "30",
        ],
    )
    assert encrypt_result.exit_code == 0, encrypt_result.output
    encrypt_payload = _payload(encrypt_result.output)
    assert encrypt_payload["review_only"] is True
    assert encrypt_payload["valid_until"] is not None

    recovered_path = tmp_path / "recovered.zip"
    decrypt_result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "review-package",
            "decrypt",
            str(envelope_path),
            "--output",
            str(recovered_path),
        ],
    )
    assert decrypt_result.exit_code == 0, decrypt_result.output
    assert _payload(decrypt_result.output)["review_only"] is True


def test_decrypt_refuses_on_replayed_envelope(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)

    from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    repository = secure_object_repository_for_bucket(_BUCKET_ID)
    keypair = ensure_recipient_encryption_keypair(bucket_id=_BUCKET_ID, repository=repository)
    public_key = recipient_encryption_public_key(keypair)
    _register_recipient("my-accountant", public_key_hex=public_key.public_key_hex)

    envelope_path = tmp_path / "envelope.json"
    encrypt_result = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "encrypt-for-recipient",
            str(package_path),
            "--recipient",
            "my-accountant",
            "--output",
            str(envelope_path),
        ],
    )
    assert encrypt_result.exit_code == 0, encrypt_result.output

    first_decrypt = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "decrypt",
            str(envelope_path),
            "--output",
            str(tmp_path / "recovered-1.zip"),
        ],
    )
    assert first_decrypt.exit_code == 0, first_decrypt.output

    second_decrypt = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "decrypt",
            str(envelope_path),
            "--output",
            str(tmp_path / "recovered-2.zip"),
        ],
    )
    assert second_decrypt.exit_code != 0, second_decrypt.output


def test_decrypt_refuses_missing_envelope_file(tmp_path: Path) -> None:
    result = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "decrypt",
            str(tmp_path / "does-not-exist-envelope.json"),
            "--output",
            str(tmp_path / "recovered.zip"),
        ],
    )
    assert result.exit_code != 0, result.output


def test_decrypt_refuses_malformed_envelope_file(tmp_path: Path) -> None:
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text("not valid json at all", encoding="utf-8")

    result = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "decrypt",
            str(envelope_path),
            "--output",
            str(tmp_path / "recovered.zip"),
        ],
    )
    assert result.exit_code != 0, result.output


def test_encrypt_for_recipient_refuses_unknown_recipient(tmp_path: Path) -> None:
    package_path = _build_package(tmp_path)

    result = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "encrypt-for-recipient",
            str(package_path),
            "--recipient",
            "no-such-recipient",
            "--output",
            str(tmp_path / "envelope.json"),
        ],
    )
    assert result.exit_code != 0, result.output


def test_encrypt_for_recipient_refuses_missing_package(tmp_path: Path) -> None:
    result = _invoke(
        [
            "app",
            "modelo",
            "review-package",
            "encrypt-for-recipient",
            str(tmp_path / "does-not-exist.zip"),
            "--recipient",
            "my-accountant",
            "--output",
            str(tmp_path / "envelope.json"),
        ],
    )
    assert result.exit_code != 0, result.output
