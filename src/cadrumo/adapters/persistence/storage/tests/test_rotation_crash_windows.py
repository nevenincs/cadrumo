"""Crash-injection tests for the mixed-key master-key rotation window.

A master-key rotation touches two independent stores: the
``*.envelope.json`` file consumers (rotated by :func:`rotate_master_key`) and
the blob-manifest wrapped DEKs (rotated by :func:`rotate_blob_stores`). No
single orchestrator wires them together, so a crash BETWEEN them leaves a
mixed-key ground state -- some ciphertext under the new key, some still under
the old.

The recovery contract is per-store probe-skip idempotency: each store first
attempts decryption under the NEW key and skips when it succeeds, so re-running
the whole rotation after a crash completes exactly the un-rotated remainder and
is a clean no-op once both stores have converged.

The interruption is real rather than simulated: the tests drive the actual
rotation primitives store by store and stop after the first. No storage
primitive is patched, and each test carries an anti-tautology arm reading both
stores under a single-key view, to confirm the mixed state genuinely straddles
the two keys before the recovery re-run resolves it.

Scope, and what this no longer covers
-------------------------------------
This module previously seeded a THIRD store, the keystore's wrapped bucket DEK,
which was deleted with the master-key keystore route it belonged to. Two
consequences, and only the first is a real loss.

**Genuinely lost: the second crash position.** Three stores have two inter-store
boundaries, so the old module could interrupt after the first store and again
after the second, and prove recovery from each. Two stores have exactly one
boundary. That dimension cannot be reconstructed here -- it needs a third store
to exist, not a third test -- so a future rotation surface joining this sequence
should restore the later-boundary case rather than assume this file covers it.

**Not lost, and worth stating so it is not mourned twice:** the deleted arm's
re-wrap logic lived in this test file, not in production. There was never a
keystore rotation primitive; the test authored its own probe-skip helper and
then asserted that helper behaved. Its removal costs less coverage than its
prominence in the old docstring implied, because the behaviour under test was
the test's own.
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
from ._rotation_key_fixtures import RotationKeys, rotation_keys

__all__ = ["rotation_keys"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_HKDF_CONTEXT_TX = b"cadrumo.domain.transactions.catalogue.v1"
_ENVELOPE_CANARY = "12345678Z"
_BLOB_PAYLOAD = b"per-blob financial payload bytes"
_ENVELOPE_LEAF = "rec-001.envelope.json"


class _Sample(BaseModel):
    """Synthetic envelope payload for the rotation crash-window tests."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    taxpayer_nif: str


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


def _rotate_envelopes(store: Path, keys: RotationKeys):
    return rotate_master_key(
        (RotationPlanEntry(store_dir=store, hkdf_context=_HKDF_CONTEXT_TX),),
        old_master_key_provider=keys.old_key,
        new_master_key_provider=keys.new_key,
    )


def _rotate_blobs(root: Path, keys: RotationKeys):
    return rotate_blob_stores(
        (root,),
        old_master_key_provider=keys.old_key,
        new_master_key_provider=keys.new_key,
    )


@pytest.fixture
def seeded_two_stores(
    tmp_path: Path,
    rotation_keys: RotationKeys,
) -> Iterator[tuple[Path, Path, BlobReference]]:
    """Seed both rotation stores under the OLD key and yield their handles.

    Returns ``(envelope_store_dir, blob_root, blob_ref)`` so a test can drive
    each store's real rotation primitive independently and interrupt between
    them.
    """
    envelope_store = tmp_path / "tx-store"
    envelope_store.mkdir()
    _seed_envelope(envelope_store / _ENVELOPE_LEAF, provider=rotation_keys.old_key)

    blob_root = tmp_path / "blob-store"
    blob_ref = EncryptedBlobStore(root_dir=blob_root, master_key_provider=rotation_keys.old_key).put(
        _BLOB_PAYLOAD,
        classification=SensitivityClass.FINANCIAL,
        content_type="application/octet-stream",
    )
    yield envelope_store, blob_root, blob_ref


class TestMixedKeyRotationCrashWindow:
    def test_crash_after_envelope_rotation_leaves_recoverable_mixed_state(
        self,
        seeded_two_stores: tuple[Path, Path, BlobReference],
        rotation_keys: RotationKeys,
    ) -> None:
        envelope_store, blob_root, blob_ref = seeded_two_stores
        envelope_path = envelope_store / _ENVELOPE_LEAF

        # Interrupt at the only inter-store boundary there is: rotate the
        # envelope store and stop before the blob store gets its turn. The real
        # primitive is driven store by store, not a patched failure.
        envelope_summary = _rotate_envelopes(envelope_store, rotation_keys)
        assert envelope_summary.rotated == 1
        assert envelope_summary.errors == 0

        # Anti-tautology: the ground state genuinely straddles both keys, so a
        # single-key view of the whole bucket would drop one store. Each store
        # is asserted under BOTH keys, because "loads under the new key" alone
        # is satisfied by a store that never moved.
        assert _envelope_loads_under(envelope_path, rotation_keys.new_key) is True
        assert _envelope_loads_under(envelope_path, rotation_keys.old_key) is False
        assert _blob_loads_under(blob_root, blob_ref, rotation_keys.old_key) is True
        assert _blob_loads_under(blob_root, blob_ref, rotation_keys.new_key) is False

        # Recovery: re-run the FULL rotation. The already-rotated envelope is
        # probe-skipped; the blob store is completed.
        envelope_rerun = _rotate_envelopes(envelope_store, rotation_keys)
        blob_rerun = _rotate_blobs(blob_root, rotation_keys)

        assert envelope_rerun.rotated == 0
        assert envelope_rerun.skipped == 1
        assert blob_rerun.rotated == 1
        assert blob_rerun.errors == 0

        # Both stores now read under the new key, and neither under the old.
        assert _envelope_loads_under(envelope_path, rotation_keys.new_key) is True
        assert _blob_loads_under(blob_root, blob_ref, rotation_keys.new_key) is True
        assert _envelope_loads_under(envelope_path, rotation_keys.old_key) is False
        assert _blob_loads_under(blob_root, blob_ref, rotation_keys.old_key) is False

        # The payload survives the rotation byte-for-byte: only the wrapping
        # key changed, so a rotation that silently re-encrypted different bytes
        # would be caught here rather than passing as "it decrypts".
        assert (
            EncryptedBlobStore(root_dir=blob_root, master_key_provider=rotation_keys.new_key).get(blob_ref)
            == _BLOB_PAYLOAD
        )

    def test_full_rerun_after_convergence_is_a_clean_no_op(
        self,
        seeded_two_stores: tuple[Path, Path, BlobReference],
        rotation_keys: RotationKeys,
    ) -> None:
        envelope_store, blob_root, _blob_ref = seeded_two_stores

        # Converge both stores onto the new key in one full pass.
        assert _rotate_envelopes(envelope_store, rotation_keys).rotated == 1
        assert _rotate_blobs(blob_root, rotation_keys).rotated == 1

        # A second full rotation is a clean no-op: every store already reads
        # under the new key, so every probe-skip fires. Asserting `rotated == 0`
        # alongside `skipped == 1` is what distinguishes a genuine skip from a
        # re-rotation that happened to converge on the same readable state.
        envelope_noop = _rotate_envelopes(envelope_store, rotation_keys)
        blob_noop = _rotate_blobs(blob_root, rotation_keys)

        assert envelope_noop.rotated == 0
        assert envelope_noop.skipped == 1
        assert blob_noop.rotated == 0
        assert blob_noop.skipped == 1

    def test_recovery_from_the_reverse_interruption_order(
        self,
        seeded_two_stores: tuple[Path, Path, BlobReference],
        rotation_keys: RotationKeys,
    ) -> None:
        """The blob store may be the one that got its turn before the crash.

        The two stores have no declared rotation order, so recovery must hold
        whichever went first. This is the closest surviving analogue of the
        deleted later-boundary case: it varies WHICH store is stranded rather
        than WHERE in a longer sequence the interruption fell, and it does not
        substitute for a genuine second boundary.
        """
        envelope_store, blob_root, blob_ref = seeded_two_stores
        envelope_path = envelope_store / _ENVELOPE_LEAF

        blob_summary = _rotate_blobs(blob_root, rotation_keys)
        assert blob_summary.rotated == 1

        # Anti-tautology, mirrored: the envelope is the stranded store now.
        assert _blob_loads_under(blob_root, blob_ref, rotation_keys.new_key) is True
        assert _blob_loads_under(blob_root, blob_ref, rotation_keys.old_key) is False
        assert _envelope_loads_under(envelope_path, rotation_keys.old_key) is True
        assert _envelope_loads_under(envelope_path, rotation_keys.new_key) is False

        blob_rerun = _rotate_blobs(blob_root, rotation_keys)
        envelope_rerun = _rotate_envelopes(envelope_store, rotation_keys)

        assert blob_rerun.rotated == 0
        assert blob_rerun.skipped == 1
        assert envelope_rerun.rotated == 1
        assert envelope_rerun.errors == 0

        assert _envelope_loads_under(envelope_path, rotation_keys.new_key) is True
        assert _blob_loads_under(blob_root, blob_ref, rotation_keys.new_key) is True
