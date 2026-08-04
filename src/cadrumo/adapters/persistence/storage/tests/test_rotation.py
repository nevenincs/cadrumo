"""Tests for the master-key rotation substrate helper.

rotation re-encrypts every governance envelope under a new
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

import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field

from .....core.config import override_settings
from .....core.external_constants import UTF_8_ENCODING
from .....tests.master_key import EphemeralMasterKeyProvider
from .. import (
    CipherEnvelope,
    EncryptedBlobStore,
    Envelope,
    RotationPlanEntry,
    RotationSummary,
    SensitivityClass,
    load_encrypted_envelope,
    rotate_blob_stores,
    rotate_master_key,
    save_encrypted_envelope,
)
from ..errors import DecryptionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NIF_CANARY = "12345678Z"
_HKDF_CONTEXT_TX = b"cadrumo.domain.transactions.catalogue.v1"
_HKDF_CONTEXT_DRAFT = b"cadrumo.application.filing.draft.v1"


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
def _use_alice_master_key(alice: EphemeralMasterKeyProvider) -> Iterator[None]:
    """Default provider during fixture setup is alice (the old key).

    Individual tests temporarily swap to bob as needed by entering
    the provider as a context manager.
    """
    with alice:
        yield


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

        on_disk = target.read_text(encoding=UTF_8_ENCODING)
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
        (store / "bogus.envelope.json").write_text("not json", encoding=UTF_8_ENCODING)
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

    def test_malformed_envelope_warning_uses_path_marker(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        alice: EphemeralMasterKeyProvider,
        bob: EphemeralMasterKeyProvider,
    ) -> None:
        private_root_segment = "private-profile-root-client-alpha"
        store = tmp_path / private_root_segment / "tx-store"
        store.mkdir(parents=True)
        target = store / "bogus.envelope.json"
        target.write_text("not json", encoding=UTF_8_ENCODING)
        caplog.set_level(logging.WARNING, logger="cadrumo.adapters.persistence.storage._rotation")

        summary = rotate_master_key(
            (RotationPlanEntry(store_dir=store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )

        assert summary.errors == 1
        assert "path_marker=<path:" in caplog.text
        assert str(target) not in caplog.text
        assert private_root_segment not in caplog.text

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
    """blob-store DEK re-wrapping under master-key rotation."""

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
    """single-file consumers such as usage ratios."""

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
        # Single-file target does not exist. Rotation must report
        # (0, 0, 0) without raising.
        store = tmp_path / "single-file-store"
        store.mkdir()
        summary = rotate_master_key(
            (
                RotationPlanEntry(
                    store_dir=store,
                    hkdf_context=_HKDF_CONTEXT_TX,
                    target_filename="single-file.json",
                ),
            ),
            old_master_key_provider=alice,
            new_master_key_provider=bob,
        )
        assert summary.rotated == 0
        assert summary.skipped == 0
        assert summary.errors == 0


class TestDefaultBlobStoreRoots:
    """`default_blob_store_roots` must return ``EncryptedBlobStore.root_dir``'s own contract.

    ``root_dir`` is documented as the directory *containing* the ``blobs/``
    subtree -- the PARENT of ``blobs/``, not ``blobs/`` itself, because the
    store appends its own ``blobs`` segment internally. Every test in this
    class drives that real contract rather than asserting a settings field
    equals itself: a prior version of this class asserted
    ``cadrumo_blob_store_dir in roots`` (``cadrumo_blob_store_dir`` is
    already ``<root>/blobs``, the CHILD), which enshrined the doubled-path
    bug the fix below closes rather than catching it.
    """

    def test_returns_the_storage_root_and_a_real_blob_round_trips_through_it(self, tmp_path: Path) -> None:
        """A blob written at the declared grammar path is found by walking the returned root."""
        from .. import default_blob_store_roots

        storage_root = tmp_path / "storage"
        provider = EphemeralMasterKeyProvider()
        writer = EncryptedBlobStore(root_dir=storage_root, master_key_provider=provider)
        reference = writer.put(b"real-blob-payload", classification=SensitivityClass.SECRET)

        with override_settings(cadrumo_local_storage_root=storage_root) as settings:
            roots = default_blob_store_roots(settings)

        assert roots == (storage_root,), f"expected exactly the storage root; got {roots!r}"
        reader = EncryptedBlobStore(root_dir=roots[0], master_key_provider=provider)
        assert reader.get(reference) == b"real-blob-payload"

    def test_skips_missing_directories(self, tmp_path: Path) -> None:
        # Pre-provision installations have no storage root yet — the
        # helper must omit a non-existent root so the rotation reports a
        # clean (0, 0, 0) instead of an OS-level error.
        from .. import default_blob_store_roots

        with override_settings(cadrumo_local_storage_root=tmp_path / "never-provisioned") as settings:
            roots = default_blob_store_roots(settings)
        assert roots == ()

    def test_the_child_blobs_directory_would_have_silently_no_opped_rotation_positive_control(
        self,
        tmp_path: Path,
    ) -> None:
        """Positive control: the pre-fix root makes rotation report a clean no-op on a real, un-rotated blob.

        Master-key rotation exists to re-wrap every blob's DEK before the
        old key is retired; a blob whose DEK is not re-wrapped becomes
        unrecoverable the moment the old key is gone. Walking the wrong
        (child) root finds zero manifests and reports success -- worse than
        an error, because nothing signals that the real blob was skipped.
        """
        from .. import default_blob_store_roots

        storage_root = tmp_path / "storage"
        old_key = EphemeralMasterKeyProvider()
        new_key = EphemeralMasterKeyProvider()
        writer = EncryptedBlobStore(root_dir=storage_root, master_key_provider=old_key)
        writer.put(b"needs-rotation", classification=SensitivityClass.SECRET)

        with override_settings(cadrumo_local_storage_root=storage_root) as settings:
            # The pre-fix contract: what ``cadrumo_blob_store_dir`` resolves
            # to, already ``<storage_root>/blobs`` -- the CHILD
            # ``EncryptedBlobStore`` appends its own ``blobs`` segment onto.
            buggy_roots = (storage_root / "blobs",)
            buggy_summary = rotate_blob_stores(
                buggy_roots,
                old_master_key_provider=old_key,
                new_master_key_provider=new_key,
            )
            assert buggy_summary == RotationSummary(rotated=0, skipped=0, errors=0), (
                "fixture assumption: the buggy child root must silently find nothing to rotate"
            )

            fixed_roots = default_blob_store_roots(settings)
            fixed_summary = rotate_blob_stores(
                fixed_roots,
                old_master_key_provider=old_key,
                new_master_key_provider=new_key,
            )
        assert fixed_summary == RotationSummary(rotated=1, skipped=0, errors=0), (
            "the corrected root must actually rotate the real blob the buggy root silently missed"
        )


class TestRotationLockTargetAlignment:
    """Rotation lock-target must match the writer's lock-target."""

    def test_rotation_lock_path_conventions(self) -> None:
        cases = (
            (
                "multi-file-envelope-writer-convention",
                RotationPlanEntry(
                    store_dir=Path("/store"),
                    hkdf_context=_HKDF_CONTEXT_DRAFT,
                ),
                Path("/store/draft-abc123.envelope.json"),
                Path("/store/draft-abc123.lock"),
            ),
            (
                "single-file-with-suffix-convention",
                RotationPlanEntry(
                    store_dir=Path("/store"),
                    hkdf_context=b"cadrumo.domain.usage_ratios.profile.v1",
                    target_filename="usage-ratios.json",
                ),
                Path("/store/usage-ratios.json"),
                Path("/store/usage-ratios.lock"),
            ),
            (
                "fallback-to-stem-when-suffix-missing",
                RotationPlanEntry(
                    store_dir=Path("/store"),
                    hkdf_context=_HKDF_CONTEXT_TX,
                    envelope_suffix=".envelope.json",
                ),
                Path("/store/oddly-named-file.json"),
                Path("/store/oddly-named-file.lock"),
            ),
        )

        for case_id, entry, envelope_path, expected_lock_path in cases:
            assert entry.lock_path_for(envelope_path) == expected_lock_path, case_id

    def test_rotation_blocks_on_writer_held_lock(
        self,
        tmp_path: Path,
        alice: EphemeralMasterKeyProvider,
    ) -> None:
        # ``ModeloDraftRepository`` locks
        # ``<store>/<draft_id>.lock`` (passed to exclusive_file_lock,
        # which appends another ``.lock`` to make the actual lock-
        # byte target ``<draft_id>.lock.lock``). The rotation must
        # contend on the SAME ``<draft_id>.lock.lock`` so concurrent
        # writers cannot stomp the rotation mid-run.
        from .....core import exclusive_file_lock
        from .. import LockAcquisitionError

        store = tmp_path / "drafts"
        store.mkdir()
        draft_id = "abc123"
        envelope_path = store / f"{draft_id}.envelope.json"
        _seed_envelope(envelope_path, provider=alice)

        writer_lock_target = store / f"{draft_id}.lock"
        with exclusive_file_lock(writer_lock_target):
            entry = RotationPlanEntry(
                store_dir=store,
                hkdf_context=_HKDF_CONTEXT_TX,
            )
            rotation_lock_target = entry.lock_path_for(envelope_path)
            assert rotation_lock_target == writer_lock_target, (
                f"rotation lock target {rotation_lock_target!r} must equal writer lock target {writer_lock_target!r}"
            )
            with (
                pytest.raises(LockAcquisitionError),
                exclusive_file_lock(rotation_lock_target, timeout=0.0),
            ):
                pass

    def test_rotation_lock_target_for_usage_ratios_matches_writer(
        self,
        tmp_path: Path,
    ) -> None:
        # The usage-ratios writer locks
        # ``target.with_suffix('.lock')`` for ``target = usage-ratios.json``.
        # The rotation plan entry for the usage-ratios profile must
        # produce the same lock target. "probe-store" is a fictional
        # directory: RotationPlanEntry takes store_dir as a parameter, so the
        # directory name is arbitrary and the test's subject is lock-target
        # agreement, not any real taxonomy location.
        from .....core import exclusive_file_lock

        store = tmp_path / "probe-store"
        store.mkdir()
        envelope_path = store / "usage-ratios.json"
        envelope_path.write_text("{}", encoding=UTF_8_ENCODING)

        writer_lock_target = envelope_path.with_suffix(".lock")
        entry = RotationPlanEntry(
            store_dir=store,
            hkdf_context=b"cadrumo.domain.usage_ratios.profile.v1",
            target_filename="usage-ratios.json",
        )
        rotation_lock_target = entry.lock_path_for(envelope_path)
        assert rotation_lock_target == writer_lock_target

        with exclusive_file_lock(rotation_lock_target):
            pass


# Fields rotation OWNS: it re-encrypts under a new key, so the ciphertext
# metadata and the write timestamp are its output. Every other CipherEnvelope
# field is state rotation must carry across from the envelope on disk.
_ROTATION_OWNED_CIPHER_FIELDS: frozenset[str] = frozenset({"written_at", "encryption"})

#: A value no model default can supply, so a dropped carry is observable.
#: Without it the carry test is vacuous while default == current.
_NON_DEFAULT_CIPHER_VERSION = 7


def test_rotation_carries_every_cipher_envelope_field_it_does_not_own(
    tmp_path: Path,
    alice: EphemeralMasterKeyProvider,
    bob: EphemeralMasterKeyProvider,
) -> None:
    """Rotation reconstructs the cipher envelope, so an omitted field resets silently.

    ``rotate_master_key`` rebuilds :class:`CipherEnvelope` field by field rather
    than copy-updating it. A field left out of that constructor does not fail --
    it takes the model default, which is the same shape that silently reset the
    absolute session expiry on every profile save.

    The seeded envelope is stamped to a NON-DEFAULT ``cipher_schema_version``
    first, and that is what makes this test an instrument rather than a
    decoration. Written at its default the test cannot fail: today the default
    equals the current value, so dropping the carry resets 1 to 1 and before and
    after compare equal. That was verified empirically -- with the carry removed
    from the reconstruction the naive form of this test still passed, which is
    the same "a field at its default cannot distinguish carried from reset" trap
    that hid the profile-save defect.

    Stamping the value on disk is a synthetic input to a mechanism, not a
    fabricated persisted shape being tolerated: nothing reads it back as a
    legacy format, and no migration branch is invented for it.

    The carried set is DERIVED from the model, so a field added to
    :class:`CipherEnvelope` later reddens this until someone classifies it as
    rotation-owned or carried.
    """
    store = tmp_path / "drafts"
    store.mkdir()
    target = store / "draft-carry.envelope.json"
    _seed_envelope(target, provider=alice, hkdf_context=_HKDF_CONTEXT_DRAFT)

    carried = set(CipherEnvelope.model_fields) - _ROTATION_OWNED_CIPHER_FIELDS
    assert carried, "rotation claims to own every cipher-envelope field; nothing left to carry"

    seeded = CipherEnvelope.model_validate_json(target.read_text(encoding=UTF_8_ENCODING)).model_copy(
        update={"cipher_schema_version": _NON_DEFAULT_CIPHER_VERSION},
    )
    target.write_text(seeded.model_dump_json(), encoding=UTF_8_ENCODING)
    before = CipherEnvelope.model_validate_json(target.read_text(encoding=UTF_8_ENCODING))
    for field in carried:
        assert getattr(before, field) != CipherEnvelope.model_fields[field].default, (
            f"carried field {field!r} was seeded at its model default, so this test cannot "
            "distinguish 'carried' from 'silently reset' -- seed it to a non-default value"
        )

    rotate_master_key(
        (RotationPlanEntry(store_dir=store, hkdf_context=_HKDF_CONTEXT_DRAFT),),
        old_master_key_provider=alice,
        new_master_key_provider=bob,
    )

    after = CipherEnvelope.model_validate_json(target.read_text(encoding=UTF_8_ENCODING))
    dropped = {
        field: (getattr(before, field), getattr(after, field))
        for field in carried
        if getattr(after, field) != getattr(before, field)
    }
    assert dropped == {}, (
        "rotation changed cipher-envelope field(s) outside its declared projection "
        f"{sorted(_ROTATION_OWNED_CIPHER_FIELDS)}, shown as field: (before, after) -> {dropped}; "
        "every field rotation does not derive from the re-encryption must be carried across"
    )
