"""Recovery-wrap KDF parity with the canonical Argon2id parameter window.

The recovery-wrap member rides inside a sealed archive an importer was handed,
so its Argon2 costs are attacker-reachable: they decide how much work an
offline brute force of the operator's passphrase must do. These tests pin the
reader to the canonical
:class:`~adapters.persistence.storage.master_key.KdfParams` window rather than
a local "is it positive" check.

Real behaviour throughout: the real recovery-wrap encoder, the real reader, the
real canonical validator, and the real sealed-archive writer/reader for the
wire path. Nothing is mocked or stubbed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage.bucket import (
    ExportArchiveHeader,
    read_sealed_archive,
    write_sealed_archive,
)
from ....adapters.persistence.storage.master_key import (
    ARGON2_MEMORY_COST_KIB,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
    KdfParams,
)
from ....domain.buckets import BucketImportError
from .._service import _recovery_wrap_bytes, _recovery_wrap_kdf

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SALT = b"s" * 16
_INSTANT = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
_BUCKET_ID = "88888888-8888-4888-8888-888888888888"
_MANIFEST_DIGEST = "e" * 64


def _canonical_accepts(*, memory_cost: int, time_cost: int, parallelism: int, salt: bytes) -> bool:
    """Return whether the canonical KdfParams window admits this parameter set."""
    try:
        KdfParams(
            algorithm="argon2id",
            version=19,
            memory_cost=memory_cost,
            time_cost=time_cost,
            parallelism=parallelism,
            salt=salt,
            output_length=32,
        )
    except Exception:
        return False
    return True


def _reader_accepts(*, memory_cost: int, time_cost: int, parallelism: int, salt: bytes) -> bool:
    """Return whether the recovery-wrap reader admits this parameter set."""
    payload = _recovery_wrap_bytes(
        salt,
        memory_cost=memory_cost,
        time_cost=time_cost,
        parallelism=parallelism,
    )
    try:
        _recovery_wrap_kdf(payload)
    except BucketImportError:
        return False
    return True


def test_audit_probe_weak_parameters_are_refused() -> None:
    """The audit's literal probe: memory=1, time=1, parallelism=1, 1-byte salt.

    Before the canonical routing this returned a usable parameter set, letting a
    tampered archive drive the importer's KDF into a regime the substrate
    rejects everywhere else.
    """
    payload = _recovery_wrap_bytes(b"x", memory_cost=1, time_cost=1, parallelism=1)

    with pytest.raises(BucketImportError):
        _recovery_wrap_kdf(payload)


def test_exporter_minted_parameters_round_trip() -> None:
    """What the export path actually mints must stay readable (no stranding)."""
    payload = _recovery_wrap_bytes(
        _SALT,
        memory_cost=ARGON2_MEMORY_COST_KIB,
        time_cost=ARGON2_TIME_COST,
        parallelism=ARGON2_PARALLELISM,
    )

    params = _recovery_wrap_kdf(payload)

    assert params.salt == _SALT
    assert params.memory_cost == ARGON2_MEMORY_COST_KIB
    assert params.time_cost == ARGON2_TIME_COST
    assert params.parallelism == ARGON2_PARALLELISM
    assert params.algorithm == "argon2id"
    assert params.version == 19
    assert params.output_length == 32


@pytest.mark.parametrize(
    ("label", "memory_cost", "time_cost", "parallelism", "salt"),
    [
        ("baseline", ARGON2_MEMORY_COST_KIB, ARGON2_TIME_COST, ARGON2_PARALLELISM, _SALT),
        ("all-weak", 1, 1, 1, b"x"),
        ("memory below floor", 1024, ARGON2_TIME_COST, ARGON2_PARALLELISM, _SALT),
        ("memory one below floor", ARGON2_MEMORY_COST_KIB - 1, ARGON2_TIME_COST, ARGON2_PARALLELISM, _SALT),
        ("memory above ceiling", 1024 * 1024 + 1, ARGON2_TIME_COST, ARGON2_PARALLELISM, _SALT),
        ("time below floor", ARGON2_MEMORY_COST_KIB, 1, ARGON2_PARALLELISM, _SALT),
        ("time above ceiling", ARGON2_MEMORY_COST_KIB, 17, ARGON2_PARALLELISM, _SALT),
        ("parallelism above ceiling", ARGON2_MEMORY_COST_KIB, ARGON2_TIME_COST, 9, _SALT),
        ("salt too short", ARGON2_MEMORY_COST_KIB, ARGON2_TIME_COST, ARGON2_PARALLELISM, b"s" * 15),
        ("salt too long", ARGON2_MEMORY_COST_KIB, ARGON2_TIME_COST, ARGON2_PARALLELISM, b"s" * 17),
        ("salt empty", ARGON2_MEMORY_COST_KIB, ARGON2_TIME_COST, ARGON2_PARALLELISM, b""),
        ("max memory", 1024 * 1024, ARGON2_TIME_COST, ARGON2_PARALLELISM, _SALT),
        ("max time", ARGON2_MEMORY_COST_KIB, 16, ARGON2_PARALLELISM, _SALT),
        ("max parallelism", ARGON2_MEMORY_COST_KIB, ARGON2_TIME_COST, 8, _SALT),
    ],
)
def test_reader_window_equals_canonical_window(
    label: str,
    memory_cost: int,
    time_cost: int,
    parallelism: int,
    salt: bytes,
) -> None:
    """The reader admits exactly the canonical window -- no wider, no narrower.

    This is the anti-divergence invariant. A future cost-bump to ``KdfParams``
    that the recovery reader does not track fails here, in both directions.
    """
    canonical = _canonical_accepts(
        memory_cost=memory_cost,
        time_cost=time_cost,
        parallelism=parallelism,
        salt=salt,
    )
    reader = _reader_accepts(
        memory_cost=memory_cost,
        time_cost=time_cost,
        parallelism=parallelism,
        salt=salt,
    )

    assert reader == canonical, (
        f"{label}: recovery reader accepts={reader} but canonical KdfParams accepts={canonical}"
    )


def test_weak_parameters_are_refused_off_the_real_archive_wire(tmp_path: Path) -> None:
    """A tampered archive carrying weak costs is refused after a real wire round trip.

    Uses the real sealed-archive writer and reader so the refusal is proven at
    the boundary an attacker actually reaches, not only at the decoder helper.
    """
    archive = tmp_path / "weak.cadrumo-bucket.tar.gz"
    write_sealed_archive(
        archive,
        header=ExportArchiveHeader(
            product="cadrumo",
            bucket_id=_BUCKET_ID,
            manifest_digest=_MANIFEST_DIGEST,
            recovery_wrap_present=True,
            archive_schema_version=3,
            created_at=_INSTANT,
        ),
        payload_envelope_bytes=b"irrelevant-ciphertext",
        recovery_wrap_bytes=_recovery_wrap_bytes(b"x", memory_cost=1, time_cost=1, parallelism=1),
    )

    contents = read_sealed_archive(archive)
    assert contents.recovery_wrap_bytes is not None

    with pytest.raises(BucketImportError):
        _recovery_wrap_kdf(contents.recovery_wrap_bytes)


def test_exporter_parameters_survive_the_real_archive_wire(tmp_path: Path) -> None:
    """The exporter's own parameters survive the same real wire path unchanged."""
    archive = tmp_path / "baseline.cadrumo-bucket.tar.gz"
    write_sealed_archive(
        archive,
        header=ExportArchiveHeader(
            product="cadrumo",
            bucket_id=_BUCKET_ID,
            manifest_digest=_MANIFEST_DIGEST,
            recovery_wrap_present=True,
            archive_schema_version=3,
            created_at=_INSTANT,
        ),
        payload_envelope_bytes=b"irrelevant-ciphertext",
        recovery_wrap_bytes=_recovery_wrap_bytes(
            _SALT,
            memory_cost=ARGON2_MEMORY_COST_KIB,
            time_cost=ARGON2_TIME_COST,
            parallelism=ARGON2_PARALLELISM,
        ),
    )

    contents = read_sealed_archive(archive)
    assert contents.recovery_wrap_bytes is not None
    params = _recovery_wrap_kdf(contents.recovery_wrap_bytes)

    assert params.salt == _SALT
    assert params.memory_cost == ARGON2_MEMORY_COST_KIB
    assert params.time_cost == ARGON2_TIME_COST
    assert params.parallelism == ARGON2_PARALLELISM


def test_non_argon2id_kdf_is_refused() -> None:
    """A recovery wrap naming another KDF is refused before any derivation."""
    payload = _recovery_wrap_bytes(
        _SALT,
        memory_cost=ARGON2_MEMORY_COST_KIB,
        time_cost=ARGON2_TIME_COST,
        parallelism=ARGON2_PARALLELISM,
    ).replace(b"argon2id", b"scrypt\x22\x22")

    with pytest.raises(BucketImportError):
        _recovery_wrap_kdf(payload)
