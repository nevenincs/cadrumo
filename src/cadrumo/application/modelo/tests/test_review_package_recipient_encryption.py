"""X25519 encrypt-for-recipient roundtrip and anti-tautology proofs.

Exercises :mod:`~application.modelo._review_package_recipient_encryption`
end to end: a real X25519 keypair, a real review package built via
:func:`~application.modelo.build_review_package`, real ECDH + HKDF +
AES-256-GCM (no mocks, no hand-rolled crypto) -- encrypt for the recipient,
confirm the recipient's own key decrypts it byte-for-byte, and confirm a
wrong key / tampered ciphertext / mismatched recipient key all fail closed.

Also proves composition with the recipient fingerprint registry: a public
key registered via
:mod:`~application.modelo._review_package_recipient_registry` is the
same public key this module's encryption targets.

Also exercises the expiry, review-only, and replay-defence follow-up slice:
a package presented past its ``valid_until`` deadline refuses, a
``review_only`` envelope decrypts but is flagged non-filing-grade, and the
envelope's replay nonce composes with
:class:`~adapters.persistence.profile.recipient_replay_guard.RecipientReplayGuardRepository` to refuse a
second presentation of the same package.

See Also:
    :func:`~application.modelo.encrypt_review_package_for_recipient`:
        X25519 ECIES encryption primitive under test.
    :func:`~application.modelo.decrypt_review_package_for_recipient`:
        Expiry-aware decrypt primitive that returns typed recovered bytes.
    :class:`~application.modelo.RecipientFingerprintRegistryRepository`:
        Trusted-recipient public-key registry used by the composition tests.
    :func:`~entrypoints.cli._modelo_review_package_cli.review_package_decrypt`:
        CLI call site that composes decryption with replay-guard consumption.
"""

from __future__ import annotations

import contextvars
import functools
import threading
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from pydantic import ValidationError

from ....adapters.persistence.profile.recipient_replay_guard import (
    RecipientPackageReplayedError,
    RecipientReplayGuardRepository,
)
from ....adapters.persistence.storage import (
    MODELO_REVIEW_PACKAGE_RECIPIENT_ENCRYPTION_KEY_NAMESPACE as _ENCRYPTION_KEY_NAMESPACE,
)
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....adapters.persistence.storage.sql.session import session_scope
from ....core import Period, validated_casilla_id
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.modelos import ModeloCode, WorkUnit, WorkUnitState, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._review_package_recipient_encryption import (
    RecipientDecryptionError,
    RecipientEncryptionError,
    RecipientEncryptionKeypair,
    RecipientPackageExpiredError,
    _recipient_encryption_key_object_key,
    decrypt_review_package_for_recipient,
    encrypt_review_package_for_recipient,
    ensure_recipient_encryption_keypair,
    load_recipient_encryption_keypair,
    recipient_encryption_public_key,
)
from .._review_package_recipient_registry import (
    RecipientFingerprintRegistryRepository,
    public_key_hex_from_raw_bytes,
)
from ._review_package_bytes_support import build_package_bytes

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
        filing_instance_evidence=None,
        source_provenance=(),
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
        filing_instance_evidence=None,
        source_provenance=(),
    )


_build_package_bytes = functools.partial(
    build_package_bytes,
    work_unit_factory=_work_unit,
    revision_factory=_revision,
    draft_bytes=_DRAFT_BYTES,
)


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
    assert recovered.package_bytes == package_bytes
    assert recovered.review_only is False


def test_two_encryptions_of_same_bytes_use_distinct_ephemeral_keys_nonces_and_ciphertext(
    tmp_path: Path,
) -> None:
    """Real behaviour: each call mints a fresh ephemeral keypair and replay nonce (never reused)."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-b")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    first = encrypt_review_package_for_recipient(package_bytes, recipient_public_key_hex=recipient_public_key_hex)
    second = encrypt_review_package_for_recipient(package_bytes, recipient_public_key_hex=recipient_public_key_hex)

    assert first.ephemeral_public_key_hex != second.ephemeral_public_key_hex
    assert first.ciphertext != second.ciphertext
    assert first.envelope_nonce_hex != second.envelope_nonce_hex
    # Both still decrypt correctly under the same recipient key.
    assert (
        decrypt_review_package_for_recipient(first, recipient_private_key=recipient_private_key).package_bytes
        == package_bytes
    )
    assert (
        decrypt_review_package_for_recipient(second, recipient_private_key=recipient_private_key).package_bytes
        == package_bytes
    )


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

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f47793db-b91f-4d35-95fd-5e68ce6fcbac") as profile:
        repository = RecipientFingerprintRegistryRepository(objects=profile.repository)
        repository.add(recipient_id="my-accountant", public_key_hex=recipient_public_key_hex, added_at=_NOW)
        registered = repository.get("my-accountant")

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=registered.public_key_hex,
    )
    recovered = decrypt_review_package_for_recipient(envelope, recipient_private_key=recipient_private_key)
    assert recovered.package_bytes == package_bytes


def test_encrypt_with_no_valid_for_never_expires(tmp_path: Path) -> None:
    """No ``valid_for`` -> ``valid_until`` is ``None`` -> decrypt succeeds arbitrarily far in the future."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-h")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
        issued_at=_NOW,
    )
    assert envelope.valid_until is None

    far_future = _NOW + timedelta(days=3650)
    recovered = decrypt_review_package_for_recipient(
        envelope,
        recipient_private_key=recipient_private_key,
        now=far_future,
    )
    assert recovered.package_bytes == package_bytes


def test_decrypt_succeeds_inside_the_validity_window(tmp_path: Path) -> None:
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-i")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
        valid_for=timedelta(days=7),
        issued_at=_NOW,
    )
    assert envelope.valid_until == _NOW + timedelta(days=7)

    recovered = decrypt_review_package_for_recipient(
        envelope,
        recipient_private_key=recipient_private_key,
        now=_NOW + timedelta(days=6),
    )
    assert recovered.package_bytes == package_bytes


def test_decrypt_refuses_a_package_presented_past_its_expiry(tmp_path: Path) -> None:
    """Real behaviour: an expired envelope is refused before AEAD decryption is attempted."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-j")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
        valid_for=timedelta(days=7),
        issued_at=_NOW,
    )

    with pytest.raises(RecipientPackageExpiredError):
        decrypt_review_package_for_recipient(
            envelope,
            recipient_private_key=recipient_private_key,
            now=_NOW + timedelta(days=7, seconds=1),
        )


def test_decrypt_refuses_a_package_presented_exactly_at_its_expiry(tmp_path: Path) -> None:
    """Boundary proof: the deadline itself is refused (``now >= valid_until``), not only strictly-after."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-k")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
        valid_for=timedelta(days=7),
        issued_at=_NOW,
    )

    with pytest.raises(RecipientPackageExpiredError):
        decrypt_review_package_for_recipient(
            envelope,
            recipient_private_key=recipient_private_key,
            now=envelope.valid_until,
        )


def test_expired_check_precedes_cryptographic_work_even_with_tampered_ciphertext(tmp_path: Path) -> None:
    """The expiry refusal fires even when the ciphertext is also tampered.

    Anti-tautology proof for the ordering claim in the docstring: if the
    expiry check were skipped or performed after decryption, tampering the
    ciphertext would surface as ``RecipientDecryptionError`` instead of the
    more specific ``RecipientPackageExpiredError``.
    """
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-l")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
        valid_for=timedelta(days=1),
        issued_at=_NOW,
    )
    tampered_ciphertext = envelope.ciphertext[:-1] + bytes([envelope.ciphertext[-1] ^ 0xFF])
    tampered_and_expired = envelope.model_copy(update={"ciphertext": tampered_ciphertext})

    with pytest.raises(RecipientPackageExpiredError):
        decrypt_review_package_for_recipient(
            tampered_and_expired,
            recipient_private_key=recipient_private_key,
            now=_NOW + timedelta(days=2),
        )


def test_encrypt_refuses_non_positive_valid_for(tmp_path: Path) -> None:
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-m")
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        X25519PrivateKey.generate().public_key().public_bytes_raw(),
    )

    with pytest.raises(RecipientEncryptionError):
        encrypt_review_package_for_recipient(
            package_bytes,
            recipient_public_key_hex=recipient_public_key_hex,
            valid_for=timedelta(0),
        )


@pytest.mark.parametrize(
    "issued_at",
    (
        pytest.param(datetime(2026, 7, 3, 12, 0), id="naive"),
        pytest.param(datetime(2026, 7, 3, 14, 0, tzinfo=timezone(timedelta(hours=2))), id="non-utc"),
    ),
)
def test_encrypt_refuses_a_naive_or_non_utc_issued_at(tmp_path: Path, issued_at: datetime) -> None:
    """An encrypted envelope must carry one explicit UTC ``issued_at`` instant."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-time")
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        X25519PrivateKey.generate().public_key().public_bytes_raw(),
    )

    with pytest.raises(ValidationError, match="datetime must be"):
        encrypt_review_package_for_recipient(
            package_bytes,
            recipient_public_key_hex=recipient_public_key_hex,
            issued_at=issued_at,
        )


def test_review_only_envelope_decrypts_but_carries_the_flag(tmp_path: Path) -> None:
    """A review-only package decrypts to real bytes, flagged non-filing-grade."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-n")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
        review_only=True,
        issued_at=_NOW,
    )
    assert envelope.review_only is True

    recovered = decrypt_review_package_for_recipient(
        envelope,
        recipient_private_key=recipient_private_key,
        now=_NOW,
    )
    assert recovered.package_bytes == package_bytes
    assert recovered.review_only is True


def test_default_envelope_is_not_review_only(tmp_path: Path) -> None:
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-o")
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        X25519PrivateKey.generate().public_key().public_bytes_raw(),
    )

    envelope = encrypt_review_package_for_recipient(package_bytes, recipient_public_key_hex=recipient_public_key_hex)
    assert envelope.review_only is False


def test_replay_guard_refuses_a_second_presentation_of_the_same_envelope_nonce(tmp_path: Path) -> None:
    """Composition proof: the envelope nonce feeds the replay-guard ledger to refuse a repeat decrypt."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-p")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
        issued_at=_NOW,
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="1d9c0483-98fe-4896-9eb2-1ccb660f2983") as profile:
        guard = RecipientReplayGuardRepository(objects=profile.repository)

        # First presentation: decrypts and the nonce is recorded consumed.
        first_pass = decrypt_review_package_for_recipient(
            envelope,
            recipient_private_key=recipient_private_key,
            now=_NOW,
        )
        guard.mark_consumed(envelope.envelope_nonce_hex, consumed_at=_NOW)
        assert first_pass.package_bytes == package_bytes

        # Second presentation of the SAME envelope: decryption itself still
        # succeeds (it is a pure cryptographic primitive with no ledger
        # dependency), but the composed replay check refuses it.
        second_pass = decrypt_review_package_for_recipient(
            envelope,
            recipient_private_key=recipient_private_key,
            now=_NOW,
        )
        assert second_pass.package_bytes == package_bytes
        assert guard.is_consumed(envelope.envelope_nonce_hex) is True

        with pytest.raises(RecipientPackageReplayedError):
            guard.mark_consumed(envelope.envelope_nonce_hex, consumed_at=_NOW)


def test_envelope_nonce_is_independent_across_two_encryptions_of_identical_inputs(tmp_path: Path) -> None:
    """Anti-tautology proof: the replay nonce is a real per-call random token, not derived from the plaintext."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-q")
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        X25519PrivateKey.generate().public_key().public_bytes_raw(),
    )

    first = encrypt_review_package_for_recipient(package_bytes, recipient_public_key_hex=recipient_public_key_hex)
    second = encrypt_review_package_for_recipient(package_bytes, recipient_public_key_hex=recipient_public_key_hex)

    assert first.envelope_nonce_hex != second.envelope_nonce_hex


def test_envelope_rejects_valid_until_at_or_before_issued_at() -> None:
    """Model-level guard: a self-contradictory envelope never validates."""
    from .._review_package_recipient_encryption import RecipientEncryptedPackage

    with pytest.raises(ValueError, match="valid_until"):
        RecipientEncryptedPackage(
            ephemeral_public_key_hex="ab" * 32,
            recipient_public_key_hex="cd" * 32,
            ciphertext=b"not-empty",
            envelope_nonce_hex="ef" * 32,
            issued_at=_NOW,
            valid_until=_NOW,
        )


def test_envelope_json_round_trip_preserves_ciphertext_bytes(tmp_path: Path) -> None:
    """Anti-regression: ``model_dump_json`` must not raise on arbitrary AEAD bytes.

    A bare ``bytes`` field's default pydantic JSON encoding assumes valid
    UTF-8, which AEAD ciphertext is not (it is uniformly-random bytes). This
    proves the hex-on-JSON-boundary serializer round-trips real ciphertext
    -- including non-UTF-8 byte sequences -- through a genuine
    ``model_dump_json`` / ``model_validate_json`` cycle, the exact path the
    CLI ``encrypt-for-recipient`` / ``decrypt`` verbs exercise when they
    write and read the envelope as a JSON file on disk.
    """
    package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-json-roundtrip")
    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )

    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
    )

    # AEAD ciphertext is high-entropy bytes; assert it genuinely is not valid
    # UTF-8 so this test cannot pass vacuously on a lucky all-ASCII draw.
    with pytest.raises(UnicodeDecodeError):
        envelope.ciphertext.decode("utf-8")

    envelope_json = envelope.model_dump_json()
    reloaded = envelope.model_validate_json(envelope_json)
    assert reloaded.ciphertext == envelope.ciphertext
    assert reloaded == envelope

    recovered = decrypt_review_package_for_recipient(reloaded, recipient_private_key=recipient_private_key)
    assert recovered.package_bytes == package_bytes


def test_ensure_recipient_encryption_keypair_mints_once_and_reuses(tmp_path: Path) -> None:
    """``ensure_recipient_encryption_keypair`` mirrors the signing keypair's idempotent-reuse contract."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cec6b9b7-f07d-45c0-a1ee-46064972a1df") as profile:
        minted = ensure_recipient_encryption_keypair(
            bucket_id="cec6b9b7-f07d-45c0-a1ee-46064972a1df", repository=profile.repository
        )
        reused = ensure_recipient_encryption_keypair(
            bucket_id="cec6b9b7-f07d-45c0-a1ee-46064972a1df", repository=profile.repository
        )
        assert reused.private_key_hex == minted.private_key_hex
        assert reused.public_key_hex == minted.public_key_hex

        loaded = load_recipient_encryption_keypair(
            bucket_id="cec6b9b7-f07d-45c0-a1ee-46064972a1df",
            repository=profile.repository,
        )
        assert loaded.private_key_hex == minted.private_key_hex

        public = recipient_encryption_public_key(minted)
        assert public.public_key_hex == minted.public_key_hex
        # The public projection never carries the private key.
        assert not hasattr(public, "private_key_hex")


@pytest.mark.parametrize(
    "generated_at",
    (
        pytest.param(datetime(2026, 7, 3, 12, 0), id="naive"),
        pytest.param(datetime(2026, 7, 3, 14, 0, tzinfo=timezone(timedelta(hours=2))), id="non-utc"),
    ),
)
def test_ensure_recipient_encryption_keypair_refuses_a_naive_or_non_utc_generated_at(
    tmp_path: Path,
    generated_at: datetime,
) -> None:
    """The minted keypair's ``created_at`` must carry one explicit UTC instant."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="ff063716-086e-4576-9d53-3f44ab646d21") as profile,
        pytest.raises(ValidationError, match="datetime must be"),
    ):
        ensure_recipient_encryption_keypair(
            bucket_id="ff063716-086e-4576-9d53-3f44ab646d21",
            repository=profile.repository,
            generated_at=generated_at,
        )


def test_load_recipient_encryption_keypair_refuses_before_mint(tmp_path: Path) -> None:
    from .._review_package_recipient_encryption import RecipientEncryptionKeyNotFoundError

    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="df232797-fe0c-4e0f-9f80-c608b60391e7") as profile,
        pytest.raises(RecipientEncryptionKeyNotFoundError),
    ):
        load_recipient_encryption_keypair(
            bucket_id="df232797-fe0c-4e0f-9f80-c608b60391e7",
            repository=profile.repository,
        )


def test_recipient_encryption_key_is_stored_only_as_ciphertext_at_rest(tmp_path: Path) -> None:
    """The minted private key never appears as a plaintext substring at rest.

    Mirrors :func:`test_private_key_is_never_stored_as_plaintext` in
    ``test_review_package_signing.py`` exactly: read the raw SQL row
    ciphertext directly (bypassing the repository's decrypt step) and confirm
    the plaintext private-key hex does NOT appear in it.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="54a0e9b6-44e3-45ac-999e-b8ca8e21da09") as profile:
        keypair = ensure_recipient_encryption_keypair(
            bucket_id="54a0e9b6-44e3-45ac-999e-b8ca8e21da09",
            repository=profile.repository,
        )

        from sqlalchemy import select

        with session_scope(profile.repository._engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(SecureObjectRow.namespace == _ENCRYPTION_KEY_NAMESPACE.namespace),
            ).scalar_one()
            ciphertext_bytes = bytes(row.payload)

        assert keypair.private_key_hex.encode("utf-8") not in ciphertext_bytes
        assert bytes.fromhex(keypair.private_key_hex) not in ciphertext_bytes


@pytest.mark.parametrize(
    "stored_bucket_id",
    (
        pytest.param("recip-enc-keypair-foreign", id="foreign"),
        pytest.param(" recip-enc-keypair-owner ", id="whitespace"),
    ),
)
def test_recipient_encryption_keypair_refuses_foreign_or_whitespace_payload_bucket(
    tmp_path: Path,
    stored_bucket_id: str,
) -> None:
    """A real encrypted row cannot claim a different or ambiguous bucket identity."""
    target_bucket_id = "1f6b0000-0000-4000-8000-00000000e0e0"
    private_key = X25519PrivateKey.generate()
    misplaced = RecipientEncryptionKeypair(
        bucket_id=stored_bucket_id,
        private_key_hex=private_key.private_bytes_raw().hex(),
        public_key_hex=private_key.public_key().public_bytes_raw().hex(),
        created_at=_NOW,
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=target_bucket_id) as profile:
        object_key = _recipient_encryption_key_object_key(target_bucket_id)
        misplaced_payload = misplaced.model_dump_json().encode("utf-8")
        profile.repository.save(
            namespace=_ENCRYPTION_KEY_NAMESPACE.namespace,
            object_key=object_key,
            classification=_ENCRYPTION_KEY_NAMESPACE.sensitivity,
            schema_version=_ENCRYPTION_KEY_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=misplaced_payload,
            write_provenance="test.review_package_recipient_encryption.foreign_payload",
        )

        with pytest.raises(RecipientEncryptionError, match="does not belong"):
            load_recipient_encryption_keypair(bucket_id=target_bucket_id, repository=profile.repository)
        with pytest.raises(RecipientEncryptionError, match="does not belong"):
            ensure_recipient_encryption_keypair(bucket_id=target_bucket_id, repository=profile.repository)

        unchanged = profile.repository.load(
            _ENCRYPTION_KEY_NAMESPACE.namespace,
            object_key,
            expected_class=_ENCRYPTION_KEY_NAMESPACE.sensitivity,
            max_supported_version=_ENCRYPTION_KEY_NAMESPACE.schema_version,
        )
        assert unchanged is not None
        assert unchanged.payload == misplaced_payload


def test_concurrent_recipient_encryption_keypair_mint_reuses_one_encrypted_key_and_round_trips(
    tmp_path: Path,
) -> None:
    """Concurrent first use returns one persisted X25519 keypair, which decrypts a real package."""
    bucket_id = "1f6b0000-0000-4000-8000-00000000c0c0"
    worker_count = 12
    gate = threading.Barrier(worker_count)
    result_lock = threading.Lock()
    minted: list[RecipientEncryptionKeypair] = []
    errors: list[str] = []

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:

        def worker() -> None:
            try:
                gate.wait(timeout=60)
                keypair = ensure_recipient_encryption_keypair(
                    bucket_id=bucket_id,
                    repository=profile.repository,
                    generated_at=_NOW,
                )
                with result_lock:
                    minted.append(keypair)
            except Exception as exc:  # surface a real worker failure to the assertion below
                with result_lock:
                    errors.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=contextvars.copy_context().run, args=(worker,)) for _ in range(worker_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        assert not [thread for thread in threads if thread.is_alive()], "keypair mint workers deadlocked"
        assert errors == [], f"concurrent keypair mint failures: {errors}"
        assert len(minted) == worker_count

        loaded = load_recipient_encryption_keypair(bucket_id=bucket_id, repository=profile.repository)
        assert {keypair.private_key_hex for keypair in minted} == {loaded.private_key_hex}
        assert {keypair.public_key_hex for keypair in minted} == {loaded.public_key_hex}

        from sqlalchemy import func, select

        with session_scope(profile.repository._engine) as session:
            persisted_count = session.execute(
                select(func.count())
                .select_from(SecureObjectRow)
                .where(SecureObjectRow.namespace == _ENCRYPTION_KEY_NAMESPACE.namespace),
            ).scalar_one()
        assert persisted_count == 1

        package_bytes = _build_package_bytes(tmp_path, bucket_id="recip-enc-keypair-concurrent-package")
        envelope = encrypt_review_package_for_recipient(
            package_bytes,
            recipient_public_key_hex=loaded.public_key_hex,
            issued_at=_NOW,
        )
        recovered = decrypt_review_package_for_recipient(
            envelope,
            recipient_private_key=loaded.private_key(),
            now=_NOW,
        )
        assert recovered.package_bytes == package_bytes


__all__: list[str] = []
