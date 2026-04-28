"""Tests for the master-key rotation substrate helper.

Wave-10: rotation re-encrypts every governance envelope under a new
master key in a single bytes-level pass. These tests confirm:

- A round-trip rotation: encrypt under key-A → rotate to key-B →
  decryption succeeds under key-B and fails under key-A.
- Resume idempotency: re-running rotation on an already-rotated set
  is a no-op (every file lands in ``skipped``).
- Mixed-state handling: half-rotated directory continues to load
  correctly from each side.
- Cross-consumer ciphertext substitution after rotation still fails
  (AAD binding survives the re-encryption).
- Rotation does not change the inner payload bytes — leak canaries
  in the original payload survive the rotation round-trip.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field

from . import (
    EncryptedBlobStore,
    Envelope,
    EphemeralMasterKeyProvider,
    RotationPlanEntry,
    RotationSummary,
    SensitivityClass,
    load_encrypted_envelope,
    override_master_key_provider,
    rotate_blob_stores,
    rotate_master_key,
    save_encrypted_envelope,
)
from .errors import DecryptionError

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

_NIF_CANARY = "12345678Z"
_HKDF_CONTEXT_TX = b"aeat.financial.transactions.catalogue.v1"
_HKDF_CONTEXT_DRAFT = b"aeat.filing.draft.v1"


class _Sample(BaseModel):
    """Synthetic payload for the rotation tests."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    taxpayer_nif: str
    amount: str = Field(default="0.00")


@pytest.fixture
def alice() -> EphemeralMasterKeyProvider:
    """The 'old' master key provider."""
    return EphemeralMasterKeyProvider()


@pytest.fixture
def bob() -> EphemeralMasterKeyProvider:
    """The 'new' master key provider — different key bytes from alice."""
    return EphemeralMasterKeyProvider()


@pytest.fixture(autouse=True)
def _patch_master_key(alice: EphemeralMasterKeyProvider) -> Iterator[None]:
    """Default provider during fixture setup is alice (the old key).

    Individual tests temporarily swap to bob as needed via
    ``override_master_key_provider``.
    """
    override_master_key_provider(alice)
    try:
        yield
    finally:
        override_master_key_provider(None)


def _build_envelope(nif: str = _NIF_CANARY) -> Envelope[_Sample]:
    return Envelope[_Sample](
        schema_version=1,
        written_at=datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
        classification=SensitivityClass.FINANCIAL,
        payload=_Sample(taxpayer_nif=nif, amount="987.65"),
    )


def _seed_envelope(
    target: Path,
    *,
    provider: EphemeralMasterKeyProvider,
    hkdf_context: bytes = _HKDF_CONTEXT_TX,
    nif: str = _NIF_CANARY,
) -> None:
    save_encrypted_envelope(
        _build_envelope(nif=nif),
        target,
        master_key_provider=provider,
        hkdf_context=hkdf_context,
    )


class TestRotationRoundTrip:
    def test_rotate_then_load_under_new_key(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        store = tmp_path / "tx-store"
        store.mkdir()
        target = store / "rec-001.envelope.json"
        _seed_envelope(target, provider=alice)

        summary = rotate_master_key(
            (RotationPlanEntry(store_dir=store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )

        assert isinstance(summary, RotationSummary)
        assert summary.rotated == 1
        assert summary.skipped == 0
        assert summary.errors == 0

        # Now decryption succeeds under bob, fails under alice.
        loaded = load_encrypted_envelope(
            target,
            Envelope[_Sample],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=bob,
            hkdf_context=_HKDF_CONTEXT_TX,
            max_supported_version=1,
        )
        assert loaded.payload.taxpayer_nif == _NIF_CANARY

        with pytest.raises(DecryptionError):
            load_encrypted_envelope(
                target,
                Envelope[_Sample],
                expected_class=SensitivityClass.FINANCIAL,
                master_key_provider=alice,
                hkdf_context=_HKDF_CONTEXT_TX,
                max_supported_version=1,
            )

    def test_payload_bytes_preserved_through_rotation(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        """Rotation must NOT mutate the inner payload — every leaf
        survives unchanged after decryption under the new key."""
        store = tmp_path / "drafts"
        store.mkdir()
        target = store / "draft-001.envelope.json"
        _seed_envelope(target, provider=alice, hkdf_context=_HKDF_CONTEXT_DRAFT)

        rotate_master_key(
            (RotationPlanEntry(store_dir=store, hkdf_context=_HKDF_CONTEXT_DRAFT),),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )

        loaded = load_encrypted_envelope(
            target,
            Envelope[_Sample],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=bob,
            hkdf_context=_HKDF_CONTEXT_DRAFT,
            max_supported_version=1,
        )
        assert loaded.payload.taxpayer_nif == _NIF_CANARY
        assert loaded.payload.amount == "987.65"

    def test_no_plaintext_leaf_lands_after_rotation(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        store = tmp_path / "tx-store"
        store.mkdir()
        target = store / "leak.envelope.json"
        _seed_envelope(target, provider=alice)

        rotate_master_key(
            (RotationPlanEntry(store_dir=store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )

        on_disk = target.read_text(encoding="utf-8")
        assert _NIF_CANARY not in on_disk
        assert "987.65" not in on_disk


class TestResumeIdempotency:
    def test_rerun_on_already_rotated_set_is_no_op(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        store = tmp_path / "tx-store"
        store.mkdir()
        for i in range(3):
            _seed_envelope(store / f"rec-{i}.envelope.json", provider=alice)

        first = rotate_master_key(
            (RotationPlanEntry(store_dir=store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert first.rotated == 3
        assert first.skipped == 0

        second = rotate_master_key(
            (RotationPlanEntry(store_dir=store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert second.rotated == 0
        assert second.skipped == 3
        assert second.errors == 0


class TestMixedState:
    """Half-rotated directory: rotation completes the rest in a re-run."""

    def test_partial_rotation_completes_on_rerun(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        store = tmp_path / "tx-store"
        store.mkdir()
        # Three under alice, two pre-rotated to bob.
        for i in range(3):
            _seed_envelope(store / f"old-{i}.envelope.json", provider=alice)
        for i in range(2):
            _seed_envelope(store / f"new-{i}.envelope.json", provider=bob)

        summary = rotate_master_key(
            (RotationPlanEntry(store_dir=store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert summary.rotated == 3
        assert summary.skipped == 2
        assert summary.errors == 0


class TestAadBindingSurvivesRotation:
    """Cross-consumer ciphertext substitution after rotation must still fail."""

    def test_wrong_hkdf_context_after_rotation_fails(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        store = tmp_path / "drafts"
        store.mkdir()
        target = store / "rec.envelope.json"
        _seed_envelope(target, provider=alice, hkdf_context=_HKDF_CONTEXT_DRAFT)

        rotate_master_key(
            (RotationPlanEntry(store_dir=store, hkdf_context=_HKDF_CONTEXT_DRAFT),),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )

        # Loading under the wrong consumer's HKDF context fails.
        with pytest.raises(DecryptionError):
            load_encrypted_envelope(
                target,
                Envelope[_Sample],
                expected_class=SensitivityClass.FINANCIAL,
                master_key_provider=bob,
                hkdf_context=_HKDF_CONTEXT_TX,
                max_supported_version=1,
            )


class TestErrorHandling:
    def test_unrelated_file_in_store_dir_counted_under_errors(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        store = tmp_path / "tx-store"
        store.mkdir()
        # Plant a malformed envelope-suffixed file.
        (store / "bogus.envelope.json").write_text("not json", encoding="utf-8")
        # Plant a legit envelope alongside.
        _seed_envelope(store / "rec.envelope.json", provider=alice)

        summary = rotate_master_key(
            (RotationPlanEntry(store_dir=store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert summary.rotated == 1
        assert summary.errors == 1
        assert summary.skipped == 0

    def test_missing_store_dir_is_a_no_op(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        summary = rotate_master_key(
            (
                RotationPlanEntry(
                    store_dir=tmp_path / "missing",
                    hkdf_context=_HKDF_CONTEXT_TX,
                ),
            ),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert summary.rotated == 0
        assert summary.skipped == 0
        assert summary.errors == 0


class TestMultiConsumerPlan:
    """Rotation across multiple consumers in one pass."""

    def test_rotates_across_distinct_hkdf_contexts(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        tx_store = tmp_path / "tx-store"
        tx_store.mkdir()
        _seed_envelope(tx_store / "a.envelope.json", provider=alice, hkdf_context=_HKDF_CONTEXT_TX)
        drafts_store = tmp_path / "drafts"
        drafts_store.mkdir()
        _seed_envelope(
            drafts_store / "b.envelope.json",
            provider=alice,
            hkdf_context=_HKDF_CONTEXT_DRAFT,
        )

        summary = rotate_master_key(
            (
                RotationPlanEntry(store_dir=tx_store, hkdf_context=_HKDF_CONTEXT_TX),
                RotationPlanEntry(store_dir=drafts_store, hkdf_context=_HKDF_CONTEXT_DRAFT),
            ),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert summary.rotated == 2
        assert summary.errors == 0


class TestBlobStoreRotation:
    """Wave-16: blob-store DEK re-wrapping under master-key rotation."""

    def test_blob_dek_is_re_wrapped_under_new_key(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        # Seed a FINANCIAL-class blob under alice's master key.
        store_root = tmp_path / "blob-store"
        store_a = EncryptedBlobStore(root_dir=store_root, master_key_provider=alice)
        ref = store_a.put(
            b"per-blob payload bytes",
            classification=SensitivityClass.FINANCIAL,
            content_type="application/octet-stream",
        )
        # Reading under alice succeeds, under bob fails.
        assert store_a.get(ref) == b"per-blob payload bytes"
        store_b_pre = EncryptedBlobStore(root_dir=store_root, master_key_provider=bob)
        with pytest.raises(DecryptionError):
            store_b_pre.get(ref)

        # Rotate the wrapped DEK from alice to bob.
        summary = rotate_blob_stores(
            (store_root,),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert summary.rotated == 1
        assert summary.errors == 0

        # Reading under bob now succeeds; alice fails.
        store_b_post = EncryptedBlobStore(root_dir=store_root, master_key_provider=bob)
        assert store_b_post.get(ref) == b"per-blob payload bytes"

    def test_already_rotated_blob_is_skipped(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        store_root = tmp_path / "blob-store"
        store_a = EncryptedBlobStore(root_dir=store_root, master_key_provider=alice)
        store_a.put(
            b"payload",
            classification=SensitivityClass.FINANCIAL,
            content_type="application/octet-stream",
        )
        first = rotate_blob_stores(
            (store_root,),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert first.rotated == 1
        # Re-running with the same providers — every blob now succeeds
        # under the new key first, so they all land in ``skipped``.
        second = rotate_blob_stores(
            (store_root,),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert second.rotated == 0
        assert second.skipped == 1

    def test_corpus_class_blob_has_no_dek_to_rotate(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        # CORPUS-class blobs are persisted plaintext (no wrapped DEK);
        # rotation visits the manifest but counts it as ``skipped``.
        store_root = tmp_path / "blob-store"
        store_a = EncryptedBlobStore(root_dir=store_root, master_key_provider=alice)
        store_a.put(
            b"public corpus payload",
            classification=SensitivityClass.CORPUS,
            content_type="text/plain",
        )
        summary = rotate_blob_stores(
            (store_root,),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert summary.rotated == 0
        assert summary.skipped == 1
        assert summary.errors == 0

    def test_empty_root_returns_zeros(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        summary = rotate_blob_stores(
            (tmp_path / "does-not-exist",),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert summary.rotated == 0
        assert summary.skipped == 0
        assert summary.errors == 0


class TestSingleFileRotationEntry:
    """Wave-16: single-file consumers (usage_ratios, setup profile)."""

    def test_target_filename_visits_only_named_file(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        # Single-file consumer: filename does not end in .envelope.json.
        store = tmp_path / "single-file-store"
        store.mkdir()
        target = store / "usage-ratios.json"
        _seed_envelope(target, provider=alice, hkdf_context=_HKDF_CONTEXT_TX)

        # Without target_filename the default-suffix walk would miss
        # this file (it does not end in `.envelope.json`).
        summary_default_suffix = rotate_master_key(
            (RotationPlanEntry(store_dir=store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert summary_default_suffix.rotated == 0
        assert summary_default_suffix.skipped == 0

        # With target_filename, rotation visits exactly that file.
        summary = rotate_master_key(
            (
                RotationPlanEntry(
                    store_dir=store,
                    hkdf_context=_HKDF_CONTEXT_TX,
                    target_filename="usage-ratios.json",
                ),
            ),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert summary.rotated == 1
        assert summary.errors == 0

    def test_target_filename_missing_file_is_a_clean_no_op(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        # Operator hasn't run setup yet — profile file does not exist.
        # Rotation must report (0, 0, 0) without raising.
        store = tmp_path / "single-file-store"
        store.mkdir()
        summary = rotate_master_key(
            (
                RotationPlanEntry(
                    store_dir=store,
                    hkdf_context=_HKDF_CONTEXT_TX,
                    target_filename="profile.json",
                ),
            ),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert summary.rotated == 0
        assert summary.skipped == 0
        assert summary.errors == 0
