"""End-to-end smoke test for the encrypted-persistence substrate.

Runs the full chain: master-key provider (file backend) -> encrypted
blob store -> secret store put/get/delete -> envelope round-trip ->
redaction -> file-lock contention. Deliberately broader than the
per-module unit tests so a regression in any layer trips this single
test rather than going undetected until a downstream consumer fails.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from . import (
    EncryptedBlobStore,
    Envelope,
    EphemeralMasterKeyProvider,
    FileFallbackMasterKeyProvider,
    SecretRecord,
    SecretStore,
    SensitivityClass,
    default_rules_for_class,
    exclusive_file_lock,
    load_envelope,
    redact,
    safe_subpath,
    save_envelope,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def test_master_key_persists_across_provider_instances(tmp_path: Path) -> None:
    """The file-backend master key is stable across re-binding the provider."""
    FileFallbackMasterKeyProvider._reset_for_tests()

    first = FileFallbackMasterKeyProvider(
        store_dir=tmp_path / "secrets",
        passphrase_callback=lambda: "smoke-passphrase",
    )
    key_a = first.get_master_key()

    FileFallbackMasterKeyProvider._reset_for_tests()

    second = FileFallbackMasterKeyProvider(
        store_dir=tmp_path / "secrets",
        passphrase_callback=lambda: "smoke-passphrase",
    )
    assert second.get_master_key() == key_a


def test_full_chain_secret_round_trip(tmp_path: Path) -> None:
    """End-to-end: secret-store record persists through the full crypto stack."""
    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )

    record = SecretRecord(
        key="aeat:smoke:google-oauth-token",
        value=b"refresh-token-abc-xyz",
        classification=SensitivityClass.SECRET,
        metadata={"issued_by": "smoke"},
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=12),
    )
    secret_store.put(record)
    loaded = secret_store.get(record.key)
    assert loaded.value == record.value
    assert loaded.metadata == record.metadata

    # The plaintext key and the plaintext value must NOT appear anywhere
    # under the store directory (encrypted-at-rest invariant).
    for path in (tmp_path / "blobs").rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            assert b"refresh-token-abc-xyz" not in data
            assert b"aeat:smoke:google-oauth-token" not in data
    index_path = tmp_path / "secrets" / "index.json"
    contents = index_path.read_text(encoding="utf-8")
    assert "google-oauth-token" not in contents
    assert "refresh-token" not in contents


def test_envelope_round_trip(tmp_path: Path) -> None:
    """Envelope save/load preserves classification + payload through atomic write."""
    from pydantic import BaseModel, ConfigDict

    class _Payload(BaseModel):
        model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
        kind: str
        amount: int

    env = Envelope[_Payload](
        schema_version=1,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.OPERATIONAL,
        payload=_Payload(kind="smoke", amount=42),
    )
    target = tmp_path / "envelope.json"
    save_envelope(env, target)
    loaded = load_envelope(
        target,
        Envelope[_Payload],
        expected_class=SensitivityClass.OPERATIONAL,
        max_supported_version=1,
    )
    assert loaded.payload.kind == "smoke"
    assert loaded.payload.amount == 42


def test_redaction_strips_audit_class_defaults() -> None:
    """The default rule set for AUDIT redacts NIF, URL, and JWT in one pass."""
    text = "filed by 12345678Z fetched from https://sede.example.com/x?y=1"
    rules = default_rules_for_class(SensitivityClass.AUDIT)
    out = redact(text, rules=rules)
    assert "12345678Z" not in out
    assert "?y=1" not in out
    assert "/x" not in out


def test_path_safety_rejects_traversal(tmp_path: Path) -> None:
    """The substrate's typed path helpers refuse traversal attempts."""
    from . import PathContainmentError

    with pytest.raises(PathContainmentError):
        safe_subpath(tmp_path, "../escape", context="smoke")


def test_file_lock_serializes_writers(tmp_path: Path) -> None:
    """A second non-blocking acquire fails immediately while the lock is held."""
    from . import LockAcquisitionError

    target = tmp_path / "shared.json"
    with exclusive_file_lock(target), pytest.raises(LockAcquisitionError), exclusive_file_lock(target, timeout=0.0):
        pytest.fail("nested non-blocking acquire should have failed")


def _holder_proc(target: str, hold_seconds: float, ready_event) -> None:
    """Worker that holds the lock for hold_seconds then releases."""
    with exclusive_file_lock(Path(target)):
        ready_event.set()
        time.sleep(hold_seconds)


@pytest.mark.skipif(
    os.name == "nt" and "AEAT_RUN_LOCK_CONTENTION" not in os.environ,
    reason="Windows mp.spawn flaky; opt-in via AEAT_RUN_LOCK_CONTENTION=1",
)
def test_cross_process_lock_contention(tmp_path: Path) -> None:
    """A real second process is forced to wait for the lock holder."""
    from . import LockAcquisitionError

    target = tmp_path / "contended.json"
    ctx = mp.get_context("spawn")
    ready = ctx.Event()
    holder = ctx.Process(target=_holder_proc, args=(str(target), 0.5, ready))
    holder.start()
    try:
        ready.wait(timeout=10.0)
        with pytest.raises(LockAcquisitionError), exclusive_file_lock(target, timeout=0.1, retry_backoff=0.01):
            pytest.fail("acquired lock while another process held it")
    finally:
        holder.join(timeout=10.0)
