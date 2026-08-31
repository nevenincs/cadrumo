"""Recipient fingerprint registry: encrypted roundtrip and anti-tautology proofs.

Exercises :mod:`~application.modelo._review_package_recipient_registry`
against a REAL encrypted
:class:`~adapters.persistence.storage.SecureObjectRepository`
(:func:`~tests.secure_sql.isolated_runtime_profile` -- a genuine
``BUCKET_DEK_V1`` bucket, no mocks or fakes): add a recipient, confirm the
register roundtrips through the encrypted boundary with strict equality,
confirm the register is real ciphertext at rest, confirm duplicate/missing-id
refusal, and confirm a corrupted on-disk payload is refused at load (the
anti-tautology proof required by ``aeat-quality-gates``).

See Also:
    :class:`~application.modelo.RecipientFingerprintRegistryRepository`:
        Encrypted public-key trust register under test.
    :class:`~application.modelo.RecipientFingerprintRegister`:
        Strict register model roundtripped through the secure object store.
    :mod:`~application.modelo._review_package_recipient_encryption`:
        Consumer that encrypts review packages to registered public keys.
    :mod:`~entrypoints.cli._config._collab`:
        CLI surface that lets operators add, list, and remove recipients.
"""

from __future__ import annotations

import json as _json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from pydantic import ValidationError

from ....adapters.persistence.storage.errors import DecryptionError
from ....adapters.persistence.storage.secure_object_namespaces import (
    MODELO_REVIEW_PACKAGE_RECIPIENT_FINGERPRINT_REGISTRY_NAMESPACE as _NAMESPACE,
)
from ....adapters.persistence.storage.sql._orm import SecureObjectRow
from ....adapters.persistence.storage.sql.session import session_scope
from ....core.classification.policies import SensitivityClass
from ....tests.secure_sql import isolated_runtime_profile
from .._review_package_recipient_registry import (
    RecipientAlreadyRegisteredError,
    RecipientFingerprintRecord,
    RecipientFingerprintRegister,
    RecipientFingerprintRegistryError,
    RecipientFingerprintRegistryRepository,
    RecipientNotRegisteredError,
    public_key_hex_from_raw_bytes,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def _fresh_public_key_hex() -> str:
    return public_key_hex_from_raw_bytes(X25519PrivateKey.generate().public_key().public_bytes_raw())


# --- Known-vector, non-tautological proof of the ``sha256_hex`` delegation --
#
# ``public_key_hex`` is pattern-constrained to exactly 64 lowercase hex
# characters (32 raw bytes, the X25519 key size), so the published NIST
# "abc" worked example (a 3-byte message) cannot be used directly here. Each
# digest below is instead computed independently of this project -- via
# CPython's ``hashlib`` in a throwaway shell session
# (``python -c "import hashlib; print(hashlib.sha256(bytes(32)).hexdigest())"``)
# -- and hard-coded as a literal. The tests below drive the production
# ``fingerprint_sha256`` property with the exact input bytes and assert
# against the literal; they never call ``fingerprint_sha256`` (or
# ``sha256_hex``) to build their own expectation.
_KNOWN_VECTOR_ZERO32_PUBLIC_KEY_HEX = "00" * 32
"""32 zero bytes, hex-encoded (64 hex chars)."""
_KNOWN_VECTOR_ZERO32_SHA256 = "66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925"
"""``hashlib.sha256(bytes(32)).hexdigest()``, computed outside this codebase."""

_KNOWN_VECTOR_SEQ32_PUBLIC_KEY_HEX = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
"""32 sequential bytes ``0x00..0x1f``, hex-encoded (64 hex chars)."""
_KNOWN_VECTOR_SEQ32_SHA256 = "630dcd2966c4336691125448bbb25b4ff412a49c732db2c8abc1b8581bd710dd"
"""``hashlib.sha256(bytes(range(32))).hexdigest()``, computed outside this codebase."""


def test_load_returns_empty_register_when_absent(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="135dbe14-59b2-4418-9731-552c860fcf78") as profile:
        repository = RecipientFingerprintRegistryRepository(objects=profile.repository)
        assert repository.load() == RecipientFingerprintRegister()


def test_add_then_load_roundtrips_with_strict_equality(tmp_path: Path) -> None:
    public_key_hex = _fresh_public_key_hex()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="77a6c02c-9b4e-458b-877d-0bb8ad233ee1") as profile:
        repository = RecipientFingerprintRegistryRepository(objects=profile.repository)

        added = repository.add(
            recipient_id="my-accountant",
            public_key_hex=public_key_hex,
            label="My Accountant",
            added_at=_NOW,
        )
        reloaded = repository.load()

    assert reloaded == added
    assert len(reloaded.records) == 1
    record = reloaded.records[0]
    assert record.recipient_id == "my-accountant"
    assert record.label == "My Accountant"
    assert record.public_key_hex == public_key_hex
    assert record.added_at == _NOW
    # fingerprint_sha256 is computed, never a stored independent field --
    # confirm it is deterministically derivable from the public key alone.
    import hashlib

    assert record.fingerprint_sha256 == hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()
    # Real behaviour: the reconstructed live public-key object actually
    # matches the bytes it was minted from, not just an equal hex string.
    assert record.public_key().public_bytes_raw().hex() == public_key_hex


def test_encrypted_registry_load_refuses_duplicate_persisted_recipient_id(tmp_path: Path) -> None:
    """A valid multi-recipient register roundtrips; a duplicate persisted id does not.

    The duplicate is injected through the real encrypted secure-object repository
    after confirming its two distinct trusted recipients reload normally. This
    proves the register invariant is re-applied at the persisted-state load
    boundary, where a pre-existing bad row must never select a trusted key by
    tuple order.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="19c86bf5-83c1-4901-a9ed-ebbab0460c1a") as profile:
        repository = RecipientFingerprintRegistryRepository(objects=profile.repository)
        repository.add(recipient_id="acct", public_key_hex=_fresh_public_key_hex(), added_at=_NOW)
        expected = repository.add(recipient_id="gestor", public_key_hex=_fresh_public_key_hex(), added_at=_NOW)

        assert repository.load() == expected

        persisted = profile.repository.load(
            _NAMESPACE.namespace,
            _NAMESPACE.require_default_object_key(),
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_NAMESPACE.schema_version,
        )
        assert persisted is not None
        document = _json.loads(persisted.payload.decode("utf-8"))
        records = document["records"]
        assert [record["recipient_id"] for record in records] == ["acct", "gestor"]

        records[1]["recipient_id"] = records[0]["recipient_id"]
        profile.repository.save(
            namespace=_NAMESPACE.namespace,
            object_key=_NAMESPACE.require_default_object_key(),
            classification=persisted.classification,
            schema_version=persisted.schema_version,
            written_at=persisted.written_at,
            payload=_json.dumps(document).encode("utf-8"),
        )

        with pytest.raises(ValidationError, match="recipient_id must be unique"):
            repository.load()


def test_register_is_never_stored_as_plaintext(tmp_path: Path) -> None:
    public_key_hex = _fresh_public_key_hex()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f5a353fa-361e-4bf2-abc3-83675e2ef80e") as profile:
        repository = RecipientFingerprintRegistryRepository(objects=profile.repository)
        repository.add(recipient_id="my-accountant", public_key_hex=public_key_hex, added_at=_NOW)

        raw_record = profile.repository.load(
            _NAMESPACE.namespace,
            _NAMESPACE.require_default_object_key(),
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_NAMESPACE.schema_version,
        )
        assert raw_record is not None
        assert public_key_hex.encode("utf-8") in raw_record.payload

        from sqlalchemy import select

        with session_scope(profile.repository._engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(SecureObjectRow.namespace == _NAMESPACE.namespace),
            ).scalar_one()
            ciphertext_bytes = bytes(row.payload)

    assert public_key_hex.encode("utf-8") not in ciphertext_bytes
    assert b"my-accountant" not in ciphertext_bytes


def test_add_refuses_duplicate_recipient_id(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cdfb8758-b634-4a3a-a773-5d8a82b2ed31") as profile:
        repository = RecipientFingerprintRegistryRepository(objects=profile.repository)
        repository.add(recipient_id="my-accountant", public_key_hex=_fresh_public_key_hex(), added_at=_NOW)

        with pytest.raises(RecipientAlreadyRegisteredError):
            repository.add(recipient_id="my-accountant", public_key_hex=_fresh_public_key_hex(), added_at=_NOW)


def test_remove_refuses_missing_recipient_id(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="149809a3-c4de-40c0-8181-36858b8d0162") as profile,
        pytest.raises(RecipientNotRegisteredError),
    ):
        RecipientFingerprintRegistryRepository(objects=profile.repository).remove("nobody")


def test_get_refuses_missing_recipient_id(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cf272ad2-1286-4663-84fe-326afa95dda5") as profile,
        pytest.raises(RecipientNotRegisteredError),
    ):
        RecipientFingerprintRegistryRepository(objects=profile.repository).get("nobody")


def test_add_then_remove_then_list_reflects_removal(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="dcffda71-679b-4381-8aa9-25fe689e8f55") as profile:
        repository = RecipientFingerprintRegistryRepository(objects=profile.repository)
        repository.add(recipient_id="a", public_key_hex=_fresh_public_key_hex(), added_at=_NOW)
        repository.add(recipient_id="b", public_key_hex=_fresh_public_key_hex(), added_at=_NOW)

        repository.remove("a")
        remaining = repository.list()

    assert [record.recipient_id for record in remaining] == ["b"]


def test_two_buckets_maintain_independent_registers(tmp_path: Path) -> None:
    """Two profiles' recipient registries never collide -- per-bucket scoping."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="7e263462-fbaf-4c50-8b20-c4b5c84a7e15") as profile_one:
        RecipientFingerprintRegistryRepository(objects=profile_one.repository).add(
            recipient_id="only-in-one",
            public_key_hex=_fresh_public_key_hex(),
            added_at=_NOW,
        )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="3e2c956e-7ade-4471-ae5e-1a4573f5d4a7") as profile_two:
        register_two = RecipientFingerprintRegistryRepository(objects=profile_two.repository).load()

    assert register_two.records == ()


def test_public_key_hex_from_raw_bytes_refuses_wrong_length() -> None:
    with pytest.raises(RecipientFingerprintRegistryError):
        public_key_hex_from_raw_bytes(b"too-short")


def test_load_raises_on_corrupted_ciphertext(tmp_path: Path) -> None:
    """Anti-tautology proof: a corrupted on-disk payload must not silently deserialise.

    Directly mutates the raw stored ciphertext bytes (bypassing the
    repository's encrypt path) and confirms ``load`` refuses rather than
    returning a plausible-looking register -- the failure mode this
    roundtrip-discipline proof exists to catch.
    """
    public_key_hex = _fresh_public_key_hex()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="0b47fb30-9219-487d-82fa-7c1fd796ceac") as profile:
        repository = RecipientFingerprintRegistryRepository(objects=profile.repository)
        repository.add(recipient_id="my-accountant", public_key_hex=public_key_hex, added_at=_NOW)

        from sqlalchemy import select, update

        with session_scope(profile.repository._engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(SecureObjectRow.namespace == _NAMESPACE.namespace),
            ).scalar_one()
            corrupted_payload = bytes(row.payload)[:-1] + bytes([bytes(row.payload)[-1] ^ 0xFF])
            session.execute(
                update(SecureObjectRow)
                .where(SecureObjectRow.namespace == _NAMESPACE.namespace)
                .values(payload=corrupted_payload),
            )

        with pytest.raises(DecryptionError):
            repository.load()


@pytest.mark.parametrize(
    ("public_key_hex", "expected_sha256"),
    [
        pytest.param(_KNOWN_VECTOR_ZERO32_PUBLIC_KEY_HEX, _KNOWN_VECTOR_ZERO32_SHA256, id="zero32"),
        pytest.param(_KNOWN_VECTOR_SEQ32_PUBLIC_KEY_HEX, _KNOWN_VECTOR_SEQ32_SHA256, id="sequential32"),
    ],
)
def test_fingerprint_sha256_matches_a_known_sha256_vector(public_key_hex: str, expected_sha256: str) -> None:
    """``fingerprint_sha256`` reproduces an independently-computed SHA-256 digest.

    Non-tautological proof of the ``core.hashing.sha256_hex`` delegation this
    property carries: ``expected_sha256`` is a literal computed with CPython's
    ``hashlib`` outside this codebase, never by calling ``fingerprint_sha256``
    (or the project's own ``sha256_hex`` helper) to build its own expectation.
    """
    record = RecipientFingerprintRecord(
        recipient_id="known-vector",
        public_key_hex=public_key_hex,
        added_at=_NOW,
    )

    assert record.fingerprint_sha256 == expected_sha256


def test_known_vector_fingerprint_survives_the_encrypted_registry_roundtrip(tmp_path: Path) -> None:
    """A known-vector fingerprint is byte-identical after the encrypted roundtrip.

    Combines the known-vector proof above with the real
    ``RecipientFingerprintRegistryRepository`` persistence boundary (a genuine
    ``BUCKET_DEK_V1`` bucket, no mocks or fakes): adds a record carrying the
    zero32 known-vector public key, reloads it through the encrypted store,
    and confirms the reloaded record's ``fingerprint_sha256`` still equals the
    literal computed independently via ``hashlib`` -- proving the
    ``sha256_hex`` delegation is byte-identical across the persistence
    boundary, not just in memory.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="4c8742c7-1471-433a-9e6b-3d420f0c13f5") as profile:
        repository = RecipientFingerprintRegistryRepository(objects=profile.repository)
        repository.add(
            recipient_id="known-vector",
            public_key_hex=_KNOWN_VECTOR_ZERO32_PUBLIC_KEY_HEX,
            added_at=_NOW,
        )
        reloaded = repository.load()

    assert len(reloaded.records) == 1
    record = reloaded.records[0]
    assert record.public_key_hex == _KNOWN_VECTOR_ZERO32_PUBLIC_KEY_HEX
    assert record.fingerprint_sha256 == _KNOWN_VECTOR_ZERO32_SHA256


__all__: list[str] = []


def test_register_refuses_two_records_under_one_recipient_id() -> None:
    """A register carrying a duplicated recipient_id is not a valid register.

    ``add`` refuses a duplicate against the register it just loaded, which guards
    only the write path. A persisted register with two records for one id was
    accepted on load and ``get`` silently returned whichever came first, making
    recipient encryption depend on row order rather than on one canonical
    trusted key.
    """
    first = RecipientFingerprintRecord(
        recipient_id="acct",
        label="first key",
        public_key_hex=_fresh_public_key_hex(),
        added_at=_NOW,
    )
    second = first.model_copy(
        update={
            "label": "second key",
            "public_key_hex": _fresh_public_key_hex(),
        },
    )
    assert first.public_key_hex != second.public_key_hex

    with pytest.raises(ValidationError, match="recipient_id must be unique"):
        RecipientFingerprintRegister(records=(first, second))


def test_register_accepts_distinct_recipient_ids() -> None:
    """Positive control: two genuinely different recipients still register.

    Without it the refusal above could hold because the register refuses every
    multi-record value, which would break the real multi-recipient case.
    """
    first = RecipientFingerprintRecord(
        recipient_id="acct",
        public_key_hex=_fresh_public_key_hex(),
        added_at=_NOW,
    )
    second = RecipientFingerprintRecord(
        recipient_id="gestor",
        public_key_hex=_fresh_public_key_hex(),
        added_at=_NOW,
    )

    register = RecipientFingerprintRegister(records=(first, second))

    assert {record.recipient_id for record in register.records} == {"acct", "gestor"}
