"""Persistence-bound proofs for the review-package signing adapter."""

from __future__ import annotations

import contextvars
import functools
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select

from cadrumo.adapters.persistence.profile.review_package_signing import (
    ReviewPackageSigningKeypairAdapter,
    build_review_package_signing_keypair_reader,
)
from cadrumo.adapters.persistence.profile.tests._review_package_bytes_support import (
    build_package_path,
    review_package_revision,
    review_package_work_unit,
)
from cadrumo.adapters.persistence.storage.secure_object_namespaces import (
    MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE,
)
from cadrumo.adapters.persistence.storage.sql.orm import SecureObjectRow
from cadrumo.adapters.persistence.storage.sql.session import session_scope
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.review_package_signing import (
    ReviewPackageSigningError,
    ReviewPackageSigningKeypair,
    sign_review_package,
    verify_review_package_signature,
)
from cadrumo.core.classification.policies import SensitivityClass

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
_DRAFT_BYTES = b"FICHERO-BOE-BYTES-FOR-REVIEW-PACKAGE-SIGNING-ADAPTER-TEST"
_OWNER_BUCKET_ID = "2e510000-0000-4000-8000-000000000001"
_FOREIGN_BUCKET_ID = "2e510000-0000-4000-8000-000000000002"
_CONCURRENT_BUCKET_ID = "2e510000-0000-4000-8000-000000000003"


_build_package = functools.partial(
    build_package_path,
    work_unit_factory=review_package_work_unit,
    revision_factory=review_package_revision,
    draft_bytes=_DRAFT_BYTES,
)


def test_ensure_keypair_mints_then_persists_and_is_idempotent(tmp_path: Path) -> None:
    """A second adapter call returns the same bucket singleton without rotation."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f1671beb-ff26-411d-b81c-76ccfb3af59c") as profile:
        capability = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id=profile.bucket_id,
        )
        first = capability.ensure_keypair(bucket_id=profile.bucket_id)
        second = capability.ensure_keypair(bucket_id=profile.bucket_id)

    assert first.bucket_id == profile.bucket_id
    assert first.private_key_hex == second.private_key_hex
    assert first.public_key_hex == second.public_key_hex
    assert first.created_at == second.created_at
    message = b"adapter-anti-tautology-probe"
    signature = first.private_key().sign(message)
    second.public_key().verify(signature, message)


def test_load_keypair_absence_never_creates_a_secure_object(tmp_path: Path) -> None:
    """Reading an unused signing namespace leaves it empty."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OWNER_BUCKET_ID) as profile:
        reader = build_review_package_signing_keypair_reader(bucket_id=profile.bucket_id)
        assert reader.load_keypair(bucket_id=profile.bucket_id) is None
        assert reader.load_keypair(bucket_id=profile.bucket_id) is None
        with session_scope(profile.repository._engine) as session:
            assert (
                session.execute(
                    select(SecureObjectRow).where(
                        SecureObjectRow.namespace == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
                    ),
                ).first()
                is None
            )


def test_load_keypair_retains_the_existing_secure_object_revision(tmp_path: Path) -> None:
    """Read-only access returns the existing key without rewriting its object."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OWNER_BUCKET_ID) as profile:
        capability = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id=profile.bucket_id,
        )
        original = capability.ensure_keypair(bucket_id=profile.bucket_id, generated_at=_NOW)
        object_key = MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.object_key_grammar.format(
            bucket_id=profile.bucket_id,
        )
        before = profile.repository.load(
            MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            object_key,
            expected_class=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity,
            max_supported_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
        )
        loaded = capability.load_keypair(bucket_id=f" {profile.bucket_id} ")
        after = profile.repository.load(
            MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            object_key,
            expected_class=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity,
            max_supported_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
        )
        assert loaded == original
        assert before is not None
        assert after == before


def test_load_keypair_refuses_a_foreign_requested_bucket(tmp_path: Path) -> None:
    """A reader cannot be retargeted to another profile by its call argument."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OWNER_BUCKET_ID) as profile:
        reader = build_review_package_signing_keypair_reader(bucket_id=profile.bucket_id)
        with pytest.raises(ReviewPackageSigningError, match="different bucket"):
            reader.load_keypair(bucket_id=_FOREIGN_BUCKET_ID)


def test_private_key_is_never_stored_as_plaintext(tmp_path: Path) -> None:
    """The adapter persists the signing private key only as ciphertext."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="225abfcd-a133-4652-8f32-18f7494de580") as profile:
        capability = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id=profile.bucket_id,
        )
        keypair = capability.ensure_keypair(bucket_id=profile.bucket_id)

        raw_record = profile.repository.load(
            MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.object_key_grammar.format(
                bucket_id=profile.bucket_id,
            ),
            expected_class=SensitivityClass.SECRET,
            max_supported_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
        )
        assert raw_record is not None
        assert keypair.private_key_hex.encode("utf-8") in raw_record.payload

        with session_scope(profile.repository._engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(
                    SecureObjectRow.namespace == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
                ),
            ).scalar_one()
            ciphertext_bytes = bytes(row.payload)

        assert keypair.private_key_hex.encode("utf-8") not in ciphertext_bytes
        assert bytes.fromhex(keypair.private_key_hex) not in ciphertext_bytes


def test_two_buckets_mint_independent_keypairs(tmp_path: Path) -> None:
    """Two adapter bindings keep their bucket keypairs independent."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="6e572448-849d-487e-adcb-de9c2f6fb3b3") as profile_one:
        first = ReviewPackageSigningKeypairAdapter(
            repository=profile_one.repository,
            bucket_id=profile_one.bucket_id,
        ).ensure_keypair(bucket_id=profile_one.bucket_id)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="83a9a3da-d37f-4e1e-a338-9c5bdd5601ec") as profile_two:
        second = ReviewPackageSigningKeypairAdapter(
            repository=profile_two.repository,
            bucket_id=profile_two.bucket_id,
        ).ensure_keypair(bucket_id=profile_two.bucket_id)

    assert first.public_key_hex != second.public_key_hex
    assert first.private_key_hex != second.private_key_hex


@pytest.mark.parametrize("stored_bucket_id", (pytest.param(_FOREIGN_BUCKET_ID, id="foreign"),))
def test_signing_keypair_refuses_foreign_payload_bucket(tmp_path: Path, stored_bucket_id: str) -> None:
    """A stored keypair claiming another bucket is rejected by the adapter."""
    private_key = Ed25519PrivateKey.generate()
    misplaced = ReviewPackageSigningKeypair(
        bucket_id=stored_bucket_id,
        private_key_hex=private_key.private_bytes_raw().hex(),
        public_key_hex=private_key.public_key().public_bytes_raw().hex(),
        created_at=_NOW,
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OWNER_BUCKET_ID) as profile:
        object_key = MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.object_key_grammar.format(
            bucket_id=_OWNER_BUCKET_ID,
        )
        misplaced_payload = misplaced.model_dump_json().encode("utf-8")
        profile.repository.save(
            namespace=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            object_key=object_key,
            classification=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity,
            schema_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=misplaced_payload,
            write_provenance="test.review_package_signing_adapter.foreign_payload",
        )

        capability = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id=_OWNER_BUCKET_ID,
        )
        with pytest.raises(ReviewPackageSigningError, match="does not belong"):
            capability.ensure_keypair(bucket_id=_OWNER_BUCKET_ID)
        with pytest.raises(ReviewPackageSigningError, match="does not belong"):
            capability.load_keypair(bucket_id=_OWNER_BUCKET_ID)

        unchanged = profile.repository.load(
            MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            object_key,
            expected_class=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity,
            max_supported_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
        )
        assert unchanged is not None
        assert unchanged.payload == misplaced_payload


def test_signing_keypair_accepts_a_whitespace_wrapped_spelling_as_the_same_bucket(tmp_path: Path) -> None:
    """The public namespace key contract normalizes one padded bucket spelling."""
    padded = f" {_OWNER_BUCKET_ID} "
    private_key = Ed25519PrivateKey.generate()
    stored = ReviewPackageSigningKeypair(
        bucket_id=padded,
        private_key_hex=private_key.private_bytes_raw().hex(),
        public_key_hex=private_key.public_key().public_bytes_raw().hex(),
        created_at=_NOW,
    )

    assert stored.bucket_id == _OWNER_BUCKET_ID

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_OWNER_BUCKET_ID) as profile:
        profile.repository.save(
            namespace=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
            object_key=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.object_key_grammar.format(
                bucket_id=_OWNER_BUCKET_ID,
            ),
            classification=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity,
            schema_version=MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=stored.model_dump_json().encode("utf-8"),
            write_provenance="test.review_package_signing_adapter.whitespace_payload",
        )
        loaded = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id=_OWNER_BUCKET_ID,
        ).ensure_keypair(bucket_id=_OWNER_BUCKET_ID)

    assert loaded.bucket_id == _OWNER_BUCKET_ID
    assert loaded.public_key_hex == stored.public_key_hex


def test_concurrent_signing_keypair_mint_reuses_one_encrypted_key_and_signs_package(tmp_path: Path) -> None:
    """Concurrent first use returns one persisted adapter keypair."""
    worker_count = 12
    gate = threading.Barrier(worker_count)
    result_lock = threading.Lock()
    minted: list[ReviewPackageSigningKeypair] = []
    errors: list[str] = []

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_CONCURRENT_BUCKET_ID) as profile:
        capability = ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id=_CONCURRENT_BUCKET_ID,
        )

        def worker() -> None:
            try:
                gate.wait(timeout=60)
                keypair = capability.ensure_keypair(bucket_id=_CONCURRENT_BUCKET_ID, generated_at=_NOW)
                with result_lock:
                    minted.append(keypair)
            except Exception as exc:  # surface a real worker failure below
                with result_lock:
                    errors.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=contextvars.copy_context().run, args=(worker,)) for _ in range(worker_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not [thread for thread in threads if thread.is_alive()]
        assert errors == []
        assert len(minted) == worker_count

        loaded = capability.ensure_keypair(bucket_id=_CONCURRENT_BUCKET_ID)
        assert {keypair.private_key_hex for keypair in minted} == {loaded.private_key_hex}
        assert {keypair.public_key_hex for keypair in minted} == {loaded.public_key_hex}

        from sqlalchemy import func, select

        with session_scope(profile.repository._engine) as session:
            persisted_count = session.execute(
                select(func.count())
                .select_from(SecureObjectRow)
                .where(SecureObjectRow.namespace == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace),
            ).scalar_one()
        assert persisted_count == 1

        package_path = _build_package(tmp_path, bucket_id=_CONCURRENT_BUCKET_ID)
        signed = sign_review_package(package_path, keypair=loaded, signed_at=_NOW)
        assert verify_review_package_signature(package_path, signed, public_key_hex=loaded.public_key_hex) is True


def test_counter_signer_keys_never_stored_as_plaintext(tmp_path: Path) -> None:
    """The adapter's accountant keypair is persisted only as ciphertext."""
    from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_two_bucket_runtime

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime, runtime.switch_to_secondary():
        accountant_keypair = ReviewPackageSigningKeypairAdapter(
            repository=runtime.secondary.repository,
            bucket_id=runtime.secondary.bucket_id,
        ).ensure_keypair(bucket_id=runtime.secondary.bucket_id)

        from sqlalchemy import select

        with session_scope(runtime.secondary.repository._engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(
                    SecureObjectRow.namespace == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace,
                ),
            ).scalar_one()
            ciphertext_bytes = bytes(row.payload)

    assert accountant_keypair.private_key_hex.encode("utf-8") not in ciphertext_bytes
    assert bytes.fromhex(accountant_keypair.private_key_hex) not in ciphertext_bytes


__all__: list[str] = []
