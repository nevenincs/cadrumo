"""End-to-end smoke test for the encrypted-persistence substrate.

Runs the full chain: master-key provider (file backend) -> encrypted
blob store -> secret store put/get/delete -> envelope round-trip ->
redaction -> file-lock contention. Deliberately broader than the
per-module unit tests so a regression in any layer trips this single
test rather than going undetected until a downstream consumer fails.
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from .....core.locks import exclusive_file_lock
from .....core.directory_scan import DirectoryEntryKind, scan_directory
from .....tests.master_key import EphemeralMasterKeyProvider
from .. import (
    EncryptedBlobStore,
    Envelope,
    SecretRecord,
    SecretStore,
    SensitivityClass,
    default_rules_for_class,
    load_envelope,
    redact,
    safe_repository_id,
    save_envelope,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_SECRET_CREATED_AT = datetime(2026, 5, 25, 13, 45, 0, tzinfo=UTC)
_SECRET_EXPIRES_AT = _SECRET_CREATED_AT + timedelta(hours=12)
_ENVELOPE_WRITTEN_AT = datetime(2026, 5, 25, 14, 0, 0, tzinfo=UTC)


def test_full_chain_secret_round_trip(tmp_path: Path) -> None:
    """End-to-end: secret-store record persists through the full crypto stack."""
    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "store-root",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "fallback-store",
        blob_store=blob_store,
        master_key_provider=provider,
    )

    record = SecretRecord(
        key="aeat:smoke:google-oauth-token",
        value=b"refresh-token-abc-xyz",
        classification=SensitivityClass.SECRET,
        metadata={"issued_by": "smoke"},
        created_at=_SECRET_CREATED_AT,
        expires_at=_SECRET_EXPIRES_AT,
    )
    secret_store.put(record)
    loaded = secret_store.get(record.key)
    assert loaded.value == record.value
    assert loaded.metadata == record.metadata

    # The plaintext key and the plaintext value must NOT appear anywhere
    # under the store directory (encrypted-at-rest invariant).
    for path in scan_directory(tmp_path / "store-root", recursive=True, select=DirectoryEntryKind.FILES):
        data = path.read_bytes()
        assert b"refresh-token-abc-xyz" not in data
        assert b"aeat:smoke:google-oauth-token" not in data
    index_path = tmp_path / "fallback-store" / "index.json"
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
        written_at=_ENVELOPE_WRITTEN_AT,
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
    """The substrate's typed id helper refuses a token shaped like a traversal."""
    from .. import PathContainmentError

    with pytest.raises(PathContainmentError, match=r"separator"):
        safe_repository_id("../escape", context="smoke")


def test_file_lock_serializes_writers(tmp_path: Path) -> None:
    """A second non-blocking acquire fails immediately while the lock is held."""
    from .. import LockAcquisitionError

    target = tmp_path / "shared.json"
    with (
        exclusive_file_lock(target),
        pytest.raises(LockAcquisitionError, match=r"lock|timeout|acquire"),
        exclusive_file_lock(target, timeout=0.0),
    ):
        pytest.fail("nested non-blocking acquire should have failed")


_LOCK_HOLDER_SCRIPT = """
import sys
import time
from pathlib import Path

from cadrumo.core import exclusive_file_lock

target = Path(sys.argv[1])
hold_seconds = float(sys.argv[2])
with exclusive_file_lock(target):
    sys.stdout.write("ready\\n")
    sys.stdout.flush()
    time.sleep(hold_seconds)
"""


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=10.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5.0)


def test_cross_process_lock_contention(tmp_path: Path) -> None:
    """A real second process is forced to wait for the lock holder.

    Driven by ``subprocess.Popen`` with a tiny inline worker script
    so the worker has no test-module import dependency. The previous
    ``multiprocessing.spawn`` worker pickled the test module and re-
    imported it in the child process, which on Windows pulled in
    heavy Alembic / registry imports and made child-process startup
    slow enough to race the main thread's readiness wait — the
    project's prior skip cited that as "flaky" on Windows.

    The replacement worker just imports ``cadrumo.core.locks`` (a
    lightweight module with no transitive heavy imports), acquires
    the lock, prints a ``ready`` sentinel to stdout, sleeps, and
    releases. The main thread blocks on ``stdout.readline()`` until
    the sentinel is observed before attempting the contention probe.
    Deterministic on every platform; no opt-in env var required.
    """
    from .. import LockAcquisitionError

    target = tmp_path / "contended.json"
    proc = subprocess.Popen(
        [sys.executable, "-c", _LOCK_HOLDER_SCRIPT, str(target), "30.0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        sentinel_deadline = time.monotonic() + 10.0
        sentinel: str | None = None
        while time.monotonic() < sentinel_deadline:
            line = proc.stdout.readline()
            if not line:
                break
            if line.strip() == "ready":
                sentinel = line.strip()
                break
        assert sentinel == "ready", "lock-holder subprocess did not emit readiness sentinel"

        with (
            pytest.raises(LockAcquisitionError, match=r"lock|timeout|acquire"),
            exclusive_file_lock(target, timeout=0.1, retry_backoff=0.01),
        ):
            pytest.fail("acquired lock while another process held it")
    finally:
        _stop_process(proc)
