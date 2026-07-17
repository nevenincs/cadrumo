"""Crash-injection tests for the mixed-key master-key rotation window.

This is the highest-value crash window in the D11 multi-store matrix: a
master-key rotation touches three independent stores - the ``*.envelope.json``
file consumers (rotated by ``rotate_master_key``), the blob-manifest wrapped
DEKs (rotated by ``rotate_blob_stores``), and the keystore bucket DEK
(``bucket.dek.json``, re-wrapped value-preservingly under the sanctioned
``wrap_dek`` / ``unwrap_dek`` helpers). There is no single orchestrator wiring
the three together, so a crash BETWEEN two of them leaves a mixed-key ground
state: some ciphertext under the new key, some still under the old.

The recovery contract is per-store probe-skip idempotency: each store first
attempts decryption / unwrap under the NEW key and skips when it succeeds, so
re-running the whole rotation after a crash completes exactly the un-rotated
remainder and is a clean no-op once every store has converged.

The interruption is simulated by driving the real rotation primitives store by
store and stopping after the first - no storage primitive is patched or mocked,
and the anti-tautology proof reads every store under a new-key-only view to
confirm the mixed state genuinely fails before the recovery re-run makes it
pass.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from .....tests.master_key import EphemeralMasterKeyProvider
from .. import (
    BlobReference,
    EncryptedBlobStore,
    Envelope,
    RotationPlanEntry,
    SensitivityClass,
    load_encrypted_envelope,
    rotate_blob_stores,
    rotate_master_key,
    save_encrypted_envelope,
)
from ..errors import DecryptionError
from ..master_key import (
    WrappedDek,
    read_wrapped_bucket_dek,
    unwrap_dek,
    wrap_dek,
    write_wrapped_bucket_dek,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_HKDF_CONTEXT_TX = b"cadrumo.domain.transactions.catalogue.v1"
_ENVELOPE_CANARY = "12345678Z"
_BLOB_PAYLOAD = b"per-blob financial payload bytes"
_KEYSTORE_BUCKET_ID = "44444444-4444-4444-8444-444444444444"


class _Sample(BaseModel):
    """Synthetic envelope payload for the rotation crash-window tests."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    taxpayer_nif: str


@pytest.fixture
def old_key() -> EphemeralMasterKeyProvider:
    """The pre-rotation master key ('old')."""
    return EphemeralMasterKeyProvider()


@pytest.fixture
def new_key() -> EphemeralMasterKeyProvider:
    """The post-rotation master key ('new'); distinct bytes from ``old_key``."""
    return EphemeralMasterKeyProvider()


def _seed_envelope(target: Path, *, provider: EphemeralMasterKeyProvider) -> None:
    save_encrypted_envelope(
        Envelope[_Sample](
            schema_version=1,
            written_at=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
            classification=SensitivityClass.FINANCIAL,
            payload=_Sample(taxpayer_nif=_ENVELOPE_CANARY),
        ),
        target,
        master_key_provider=provider,
        hkdf_context=_HKDF_CONTEXT_TX,
    )


def _envelope_loads_under(target: Path, provider: EphemeralMasterKeyProvider) -> bool:
    """Return True if the envelope decrypts under ``provider``'s key."""
    try:
        load_encrypted_envelope(
            target,
            Envelope[_Sample],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=provider,
            hkdf_context=_HKDF_CONTEXT_TX,
            max_supported_version=1,
        )
    except DecryptionError:
        return False
    return True


def _blob_loads_under(root: Path, ref: BlobReference, provider: EphemeralMasterKeyProvider) -> bool:
    """Return True if the blob's wrapped DEK unwraps under ``provider``'s key."""
    try:
        EncryptedBlobStore(root_dir=root, master_key_provider=provider).get(ref)
    except DecryptionError:
        return False
    return True


def _keystore_unwraps_under(path: Path, provider: EphemeralMasterKeyProvider) -> bool:
    """Return True if the persisted wrapped bucket DEK unwraps under ``provider``'s key."""
    try:
        unwrap_dek(
            kek=provider.get_master_key(),
            wrapped=read_wrapped_bucket_dek(path),
            bucket_id=_KEYSTORE_BUCKET_ID,
        )
    except DecryptionError:
        return False
    return True


def _rewrap_keystore_dek_probe_skip(
    path: Path,
    *,
    old_provider: EphemeralMasterKeyProvider,
    new_provider: EphemeralMasterKeyProvider,
) -> str:
    """Re-wrap the persisted bucket DEK from ``old`` to ``new`` with probe-skip.

    Mirrors the per-store probe-skip contract the two ciphertext rotation
    primitives use, applied to the keystore's value-preserving DEK re-wrap:
    unwrap under the new key first (already re-wrapped -> skip), else unwrap
    under the old key and re-wrap under the new key. Uses only the sanctioned
    ``unwrap_dek`` / ``wrap_dek`` primitives; the DEK value is preserved.
    """
    wrapped = read_wrapped_bucket_dek(path)
    new_kek = new_provider.get_master_key()
    try:
        unwrap_dek(kek=new_kek, wrapped=wrapped, bucket_id=_KEYSTORE_BUCKET_ID)
    except DecryptionError:
        pass
    else:
        return "skipped"
    dek = unwrap_dek(kek=old_provider.get_master_key(), wrapped=wrapped, bucket_id=_KEYSTORE_BUCKET_ID)
    rewrapped: WrappedDek = wrap_dek(kek=new_kek, dek=dek, bucket_id=_KEYSTORE_BUCKET_ID)
    write_wrapped_bucket_dek(path, rewrapped)
    return "rotated"


@pytest.fixture
def seeded_three_stores(
    tmp_path: Path,
    old_key: EphemeralMasterKeyProvider,
) -> Iterator[tuple[Path, Path, BlobReference, Path, bytes]]:
    """Seed all three rotation stores under the old key and yield their handles.

    Returns ``(envelope_store_dir, blob_root, blob_ref, keystore_path,
    keystore_dek)`` so a test can drive each store's real rotation primitive
    independently and simulate a crash between them.
    """
    envelope_store = tmp_path / "tx-store"
    envelope_store.mkdir()
    _seed_envelope(envelope_store / "rec-001.envelope.json", provider=old_key)

    blob_root = tmp_path / "blob-store"
    blob_ref = EncryptedBlobStore(root_dir=blob_root, master_key_provider=old_key).put(
        _BLOB_PAYLOAD,
        classification=SensitivityClass.FINANCIAL,
        content_type="application/octet-stream",
    )

    keystore_path = tmp_path / "keystore" / "bucket.dek.json"
    keystore_dek = b"D" * 32
    write_wrapped_bucket_dek(
        keystore_path,
        wrap_dek(kek=old_key.get_master_key(), dek=keystore_dek, bucket_id=_KEYSTORE_BUCKET_ID),
    )
    yield envelope_store, blob_root, blob_ref, keystore_path, keystore_dek


class TestMixedKeyRotationCrashWindow:
    def test_crash_after_envelope_rotation_leaves_recoverable_mixed_state(
        self,
        seeded_three_stores: tuple[Path, Path, BlobReference, Path, bytes],
        old_key: EphemeralMasterKeyProvider,
        new_key: EphemeralMasterKeyProvider,
    ) -> None:
        envelope_store, blob_root, blob_ref, keystore_path, keystore_dek = seeded_three_stores
        envelope_path = envelope_store / "rec-001.envelope.json"

        # --- Simulate the crash: rotate ONLY the envelope store, then stop
        # (the blob-manifest and keystore stores never got their turn). This
        # is the real primitive driven store-by-store, not a patched failure.
        envelope_summary = rotate_master_key(
            (RotationPlanEntry(store_dir=envelope_store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=old_key,
            new_master_key_provider=new_key,
        )
        assert envelope_summary.rotated == 1
        assert envelope_summary.errors == 0

        # --- Anti-tautology: the mixed state genuinely straddles both keys.
        # The envelope reads under the NEW key only; the blob and keystore
        # read under the OLD key only. A new-key-only view of the whole bucket
        # would silently drop the un-rotated stores if recovery were skipped.
        assert _envelope_loads_under(envelope_path, new_key) is True
        assert _envelope_loads_under(envelope_path, old_key) is False
        assert _blob_loads_under(blob_root, blob_ref, old_key) is True
        assert _blob_loads_under(blob_root, blob_ref, new_key) is False
        assert _keystore_unwraps_under(keystore_path, old_key) is True
        assert _keystore_unwraps_under(keystore_path, new_key) is False

        # --- Recovery: re-run the FULL rotation across all three stores. The
        # already-rotated envelope is probe-skipped; the blob and keystore are
        # completed. Every store converges on the new key.
        envelope_rerun = rotate_master_key(
            (RotationPlanEntry(store_dir=envelope_store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=old_key,
            new_master_key_provider=new_key,
        )
        blob_rerun = rotate_blob_stores(
            (blob_root,),
            old_master_key_provider=old_key,
            new_master_key_provider=new_key,
        )
        keystore_outcome = _rewrap_keystore_dek_probe_skip(
            keystore_path,
            old_provider=old_key,
            new_provider=new_key,
        )

        assert envelope_rerun.rotated == 0
        assert envelope_rerun.skipped == 1
        assert blob_rerun.rotated == 1
        assert blob_rerun.errors == 0
        assert keystore_outcome == "rotated"

        # Every store now reads under the new key, and none under the old.
        assert _envelope_loads_under(envelope_path, new_key) is True
        assert _blob_loads_under(blob_root, blob_ref, new_key) is True
        assert _keystore_unwraps_under(keystore_path, new_key) is True
        assert _blob_loads_under(blob_root, blob_ref, old_key) is False
        assert _keystore_unwraps_under(keystore_path, old_key) is False

        # The keystore DEK VALUE is preserved across the re-wrap (only its
        # wrapping master key changed), so downstream ciphertext stays valid.
        assert (
            unwrap_dek(
                kek=new_key.get_master_key(),
                wrapped=read_wrapped_bucket_dek(keystore_path),
                bucket_id=_KEYSTORE_BUCKET_ID,
            )
            == keystore_dek
        )
        # And the blob payload survives the rotation byte-for-byte.
        assert EncryptedBlobStore(root_dir=blob_root, master_key_provider=new_key).get(blob_ref) == _BLOB_PAYLOAD

    def test_full_rerun_after_convergence_is_a_clean_no_op(
        self,
        seeded_three_stores: tuple[Path, Path, BlobReference, Path, bytes],
        old_key: EphemeralMasterKeyProvider,
        new_key: EphemeralMasterKeyProvider,
    ) -> None:
        envelope_store, blob_root, blob_ref, keystore_path, _keystore_dek = seeded_three_stores
        del blob_ref

        # Converge all three stores onto the new key in one full pass.
        rotate_master_key(
            (RotationPlanEntry(store_dir=envelope_store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=old_key,
            new_master_key_provider=new_key,
        )
        rotate_blob_stores((blob_root,), old_master_key_provider=old_key, new_master_key_provider=new_key)
        assert _rewrap_keystore_dek_probe_skip(keystore_path, old_provider=old_key, new_provider=new_key) == "rotated"

        # A second full rotation is a clean no-op: every store already reads
        # under the new key, so every probe-skip fires.
        envelope_noop = rotate_master_key(
            (RotationPlanEntry(store_dir=envelope_store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=old_key,
            new_master_key_provider=new_key,
        )
        blob_noop = rotate_blob_stores((blob_root,), old_master_key_provider=old_key, new_master_key_provider=new_key)
        keystore_noop = _rewrap_keystore_dek_probe_skip(keystore_path, old_provider=old_key, new_provider=new_key)

        assert envelope_noop.rotated == 0
        assert envelope_noop.skipped == 1
        assert blob_noop.rotated == 0
        assert blob_noop.skipped == 1
        assert keystore_noop == "skipped"

    def test_crash_between_blob_and_keystore_recovers_the_keystore_only(
        self,
        seeded_three_stores: tuple[Path, Path, BlobReference, Path, bytes],
        old_key: EphemeralMasterKeyProvider,
        new_key: EphemeralMasterKeyProvider,
    ) -> None:
        envelope_store, blob_root, blob_ref, keystore_path, _keystore_dek = seeded_three_stores

        # Simulate a crash later in the sequence: envelopes and blobs rotated,
        # keystore not yet. Only the keystore is under the old key now.
        rotate_master_key(
            (RotationPlanEntry(store_dir=envelope_store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=old_key,
            new_master_key_provider=new_key,
        )
        rotate_blob_stores((blob_root,), old_master_key_provider=old_key, new_master_key_provider=new_key)

        assert _envelope_loads_under(envelope_store / "rec-001.envelope.json", new_key) is True
        assert _blob_loads_under(blob_root, blob_ref, new_key) is True
        # Anti-tautology: the keystore alone still straddles the old key.
        assert _keystore_unwraps_under(keystore_path, new_key) is False
        assert _keystore_unwraps_under(keystore_path, old_key) is True

        # Recovery re-run: the two already-rotated stores probe-skip, the
        # keystore is completed.
        envelope_rerun = rotate_master_key(
            (RotationPlanEntry(store_dir=envelope_store, hkdf_context=_HKDF_CONTEXT_TX),),
            old_master_key_provider=old_key,
            new_master_key_provider=new_key,
        )
        blob_rerun = rotate_blob_stores((blob_root,), old_master_key_provider=old_key, new_master_key_provider=new_key)
        keystore_outcome = _rewrap_keystore_dek_probe_skip(keystore_path, old_provider=old_key, new_provider=new_key)

        assert envelope_rerun.skipped == 1
        assert blob_rerun.skipped == 1
        assert keystore_outcome == "rotated"
        assert _keystore_unwraps_under(keystore_path, new_key) is True
