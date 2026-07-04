"""X25519 encrypt-for-recipient roundtrip and anti-tautology proofs.

Exercises :mod:`aeat.application.modelo._review_package_recipient_encryption`
end to end: a real X25519 keypair, a real review package built via
:func:`~aeat.application.modelo.build_review_package`, real ECDH + HKDF +
AES-256-GCM (no mocks, no hand-rolled crypto) -- encrypt for the recipient,
confirm the recipient's own key decrypts it byte-for-byte, and confirm a
wrong key / tampered ciphertext / mismatched recipient key all fail closed.

Also proves composition with the recipient fingerprint registry: a public
key registered via
:mod:`aeat.application.modelo._review_package_recipient_registry` is the
same public key this module's encryption targets.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from ....core import Period
from ....domain.calculations.registry import CasillaObservation, validated_casilla_id
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    WorkUnit,
    WorkUnitState,
    derive_calculation_revision_id,
    derive_work_unit_id,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._review_package import build_review_package
from .._review_package_recipient_encryption import (
    RecipientDecryptionError,
    RecipientEncryptionError,
    decrypt_review_package_for_recipient,
    encrypt_review_package_for_recipient,
)
from .._review_package_recipient_registry import (
    RecipientFingerprintRegistryRepository,
    public_key_hex_from_raw_bytes,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
_BASE_CASILLA = validated_casilla_id("base", surface="test_review_package_recipient_encryption")
_CUOTA_CASILLA = validated_casilla_id("cuota", surface="test_review_package_recipient_encryption")
_DRAFT_BYTES = b"FICHERO-BOE-BYTES-FOR-RECIPIENT-ENCRYPTION-TEST"


def _work_unit(*, bucket_id: str) -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="recipient-encryption-revision",
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id="recipient-encryption-revision",
        name="303-2026-1T",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
    )


def _revision(work_unit: WorkUnit) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        binding_overrides={},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        source_transaction_ids=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        observations=(
            CasillaObservation(
                casilla_id=_CUOTA_CASILLA,
                value=Decimal("21.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("test-review-package-recipient-encryption",),
            ),
        ),
        ledger_filing_evidence=None,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filed_at=None,
        filed_by=None,
        superseded_at=None,
    )


def _build_package_bytes(tmp_path: Path, *, bucket_id: str) -> bytes:
    work_unit = _work_unit(bucket_id=bucket_id)
    revision = _revision(work_unit)
    output_path = tmp_path / "review-package.zip"
    build_review_package(
        revision=revision,
        work_unit=work_unit,
        draft_bytes=_DRAFT_BYTES,
        output_path=output_path,
        built_by="operator",
    )
    return output_path.read_bytes()


def test_encrypt_then_decrypt_with_matching_key_recovers_original_bytes(tmp_path: Path) -> None:
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-a")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
    )

    assert envelope.recipient_public_key_hex == recipient_public_key_hex
    # The ciphertext never contains the plaintext package bytes.
    assert _DRAFT_BYTES not in envelope.ciphertext
    # Ephemeral sender key is fresh per call -- not the recipient's own key.
    assert envelope.ephemeral_public_key_hex != recipient_public_key_hex

    recovered = decrypt_review_package_for_recipient(envelope, recipient_private_key=recipient_private_key)
    assert recovered == package_bytes


def test_two_encryptions_of_same_bytes_use_distinct_ephemeral_keys_and_ciphertext(tmp_path: Path) -> None:
    """Real behaviour: each call mints a fresh ephemeral keypair (never reused)."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-b")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    first = encrypt_review_package_for_recipient(package_bytes, recipient_public_key_hex=recipient_public_key_hex)
    second = encrypt_review_package_for_recipient(package_bytes, recipient_public_key_hex=recipient_public_key_hex)

    assert first.ephemeral_public_key_hex != second.ephemeral_public_key_hex
    assert first.ciphertext != second.ciphertext
    # Both still decrypt correctly under the same recipient key.
    assert decrypt_review_package_for_recipient(first, recipient_private_key=recipient_private_key) == package_bytes
    assert decrypt_review_package_for_recipient(second, recipient_private_key=recipient_private_key) == package_bytes


def test_decrypt_fails_with_wrong_recipient_private_key(tmp_path: Path) -> None:
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-c")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )
    wrong_private_key = X25519PrivateKey.generate()

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
    )

    with pytest.raises(RecipientDecryptionError):
        decrypt_review_package_for_recipient(envelope, recipient_private_key=wrong_private_key)


def test_decrypt_fails_when_ciphertext_is_tampered(tmp_path: Path) -> None:
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-d")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
    )
    tampered_ciphertext = envelope.ciphertext[:-1] + bytes([envelope.ciphertext[-1] ^ 0xFF])
    tampered = envelope.model_copy(update={"ciphertext": tampered_ciphertext})

    with pytest.raises(RecipientDecryptionError):
        decrypt_review_package_for_recipient(tampered, recipient_private_key=recipient_private_key)


def test_decrypt_fails_when_ephemeral_public_key_is_swapped(tmp_path: Path) -> None:
    """A ciphertext re-targeted at a different ephemeral key must fail AEAD auth."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-e")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    first = encrypt_review_package_for_recipient(package_bytes, recipient_public_key_hex=recipient_public_key_hex)
    second = encrypt_review_package_for_recipient(package_bytes, recipient_public_key_hex=recipient_public_key_hex)
    swapped = first.model_copy(update={"ephemeral_public_key_hex": second.ephemeral_public_key_hex})

    with pytest.raises(RecipientDecryptionError):
        decrypt_review_package_for_recipient(swapped, recipient_private_key=recipient_private_key)


def test_encrypt_refuses_malformed_recipient_public_key(tmp_path: Path) -> None:
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-f")

    with pytest.raises(RecipientEncryptionError):
        encrypt_review_package_for_recipient(package_bytes, recipient_public_key_hex="not-hex-at-all")


def test_registered_recipient_public_key_is_the_encryption_target(tmp_path: Path) -> None:
    """Composition proof: a fingerprint-registry entry's key is what encryption targets."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-g")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="recip-enc-g-registry") as profile:
        repository = RecipientFingerprintRegistryRepository(objects=profile.repository)
        repository.add(recipient_id="kents-accountant", public_key_hex=recipient_public_key_hex, added_at=_NOW)
        registered = repository.get("kents-accountant")

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=registered.public_key_hex,
    )
    recovered = decrypt_review_package_for_recipient(envelope, recipient_private_key=recipient_private_key)
    assert recovered == package_bytes


__all__: list[str] = []
