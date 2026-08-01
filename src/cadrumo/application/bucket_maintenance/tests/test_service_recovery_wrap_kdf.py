"""Recovery-wrap Argon2id parameters: a security floor, not an enrolment window.

The recovery-wrap member rides inside a sealed archive an importer was handed,
so its Argon2 costs are attacker-reachable: they decide how much work an
offline brute force of the operator's passphrase must do. The reader must
therefore refuse weak costs -- but it must NOT refuse an archive merely because
its enrolled parameters differ from what we mint today, because a sealed
archive is the operator's last-resort path to their own encrypted financial
data.

These tests pin both halves: below-floor parameters are refused, and parameters
outside the current new-enrolment window (including stronger ones, and by
extension any set enrolled before a future cost bump) still open.

Real behaviour throughout: the real recovery-wrap encoder, the real reader, the
real parameter records, and the real sealed-archive writer/reader for the wire
path. Nothing is mocked or stubbed.
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
from .._service import (
    _RECOVERY_READ_MIN_MEMORY_COST_KIB,
    _RECOVERY_READ_MIN_PARALLELISM,
    _RECOVERY_READ_MIN_TIME_COST,
    _recovery_wrap_bytes,
    _recovery_wrap_kdf,
)

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

    DISCRIMINATING. Before the fix this returned a usable parameter set, letting
    a tampered archive drive the importer's KDF into a regime an offline brute
    force clears cheaply.
    """
    payload = _recovery_wrap_bytes(b"x", memory_cost=1, time_cost=1, parallelism=1)

    with pytest.raises(BucketImportError):
        _recovery_wrap_kdf(payload)


def test_exporter_minted_parameters_round_trip() -> None:
    """What the export path actually mints must stay readable (no stranding).

    SUPPORTING: passes both before and after the fix, since the exporter mints
    the enrolment baseline either way. It exists to prove the tightening strands
    nothing, not to prove the tightening happened.
    """
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
    ("label", "memory_cost", "time_cost", "parallelism"),
    [
        ("memory above enrolment ceiling", 2 * 1024 * 1024, ARGON2_TIME_COST, ARGON2_PARALLELISM),
        ("time above enrolment ceiling", ARGON2_MEMORY_COST_KIB, 32, ARGON2_PARALLELISM),
        ("parallelism above enrolment ceiling", ARGON2_MEMORY_COST_KIB, ARGON2_TIME_COST, 16),
        ("stronger on every axis", 2 * 1024 * 1024, 32, 16),
    ],
)
def test_archive_enrolled_stronger_than_today_still_imports(
    label: str,
    memory_cost: int,
    time_cost: int,
    parallelism: int,
) -> None:
    """An archive enrolled ABOVE today's enrolment window must still open.

    DISCRIMINATING. This is the whole point of reading through the enrolled
    record plus a floor rather than the new-enrolment window: a stronger KDF is
    not a threat, and refusing it would be the defect. These parameter sets are
    all rejected by the new-enrolment ``KdfParams`` window, so a reader bound to
    that window refuses them.

    It is also the standing proxy for the hazard that has no direct test today:
    the reader and the enrolment window must be free to differ, so raising the
    enrolment floor cannot refuse a previously-written archive.
    """
    assert not _canonical_accepts(
        memory_cost=memory_cost,
        time_cost=time_cost,
        parallelism=parallelism,
        salt=_SALT,
    ), f"{label}: precondition -- this set must be outside the new-enrolment window"

    assert _reader_accepts(
        memory_cost=memory_cost,
        time_cost=time_cost,
        parallelism=parallelism,
        salt=_SALT,
    ), f"{label}: recovery reader refused an archive enrolled with STRONGER parameters"


def test_reader_floor_never_exceeds_the_enrolment_floor() -> None:
    """The reader's floor stays at or below the enrolment floor.

    DISCRIMINATING. This is the structural guard against the failure that costs
    an operator their data: if a future OWASP bump raises the enrolment floor
    and someone raises the reader floor to match, every archive enrolled under
    the old floor becomes unopenable. The reader floor must lag, never lead.
    """
    assert _RECOVERY_READ_MIN_MEMORY_COST_KIB <= ARGON2_MEMORY_COST_KIB
    assert _RECOVERY_READ_MIN_TIME_COST <= ARGON2_TIME_COST
    assert _RECOVERY_READ_MIN_PARALLELISM <= ARGON2_PARALLELISM


@pytest.mark.parametrize(
    ("label", "memory_cost", "time_cost", "parallelism", "salt"),
    [
        ("all-weak", 1, 1, 1, _SALT),
        ("memory far below floor", 1024, ARGON2_TIME_COST, ARGON2_PARALLELISM, _SALT),
        ("memory one below floor", _RECOVERY_READ_MIN_MEMORY_COST_KIB - 1, ARGON2_TIME_COST, ARGON2_PARALLELISM, _SALT),
        ("time below floor", ARGON2_MEMORY_COST_KIB, _RECOVERY_READ_MIN_TIME_COST - 1, ARGON2_PARALLELISM, _SALT),
        ("parallelism below floor", ARGON2_MEMORY_COST_KIB, ARGON2_TIME_COST, 0, _SALT),
        ("salt too short", ARGON2_MEMORY_COST_KIB, ARGON2_TIME_COST, ARGON2_PARALLELISM, b"s" * 15),
        ("salt too long", ARGON2_MEMORY_COST_KIB, ARGON2_TIME_COST, ARGON2_PARALLELISM, b"s" * 17),
        ("salt empty", ARGON2_MEMORY_COST_KIB, ARGON2_TIME_COST, ARGON2_PARALLELISM, b""),
    ],
)
def test_below_floor_parameters_are_refused(
    label: str,
    memory_cost: int,
    time_cost: int,
    parallelism: int,
    salt: bytes,
) -> None:
    """Parameters weaker than the security floor are refused.

    DISCRIMINATING. Preserves the security win: the pre-fix reader accepted any
    positive cost, so a tampered archive could drive the importer's KDF into a
    regime an offline brute force clears cheaply.
    """
    assert not _reader_accepts(
        memory_cost=memory_cost,
        time_cost=time_cost,
        parallelism=parallelism,
        salt=salt,
    ), f"{label}: recovery reader accepted parameters below the security floor"


def test_weak_parameters_are_refused_off_the_real_archive_wire(tmp_path: Path) -> None:
    """A tampered archive carrying weak costs is refused after a real wire round trip.

    DISCRIMINATING. Uses the real sealed-archive writer and reader so the
    refusal is proven at the boundary an attacker actually reaches, not only at
    the decoder helper.
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
    """The exporter's own parameters survive the same real wire path unchanged.

    SUPPORTING: a no-stranding control, green under both implementations.
    """
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
    """A recovery wrap naming another KDF is refused before any derivation.

    SUPPORTING: the algorithm guard predates this change and is unaffected by it.
    """
    payload = _recovery_wrap_bytes(
        _SALT,
        memory_cost=ARGON2_MEMORY_COST_KIB,
        time_cost=ARGON2_TIME_COST,
        parallelism=ARGON2_PARALLELISM,
    ).replace(b"argon2id", b"scrypt\x22\x22")

    with pytest.raises(BucketImportError):
        _recovery_wrap_kdf(payload)
