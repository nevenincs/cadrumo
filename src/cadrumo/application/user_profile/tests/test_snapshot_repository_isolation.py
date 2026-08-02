"""Real-behavior tests: a snapshot repository holds its own bucket's snapshots.

``UserProfileSnapshotRepository`` keys each row by the BOUND BUCKET plus the
snapshot id, never by the payload's own ``profile_id``, and ``load``
validated the envelope's classification and version without ever checking
whose profile came back. A snapshot for profile B could therefore be written
into, found in, and read out of profile A's repository, filed under a key
that names only A.

Nothing was inconsistent enough to notice: the key was well-formed, the
envelope was valid, and the stored row and its contents simply disagreed
about whose profile it was, with no path comparing them.

The live-profile repository deliberately does NOT carry this guard, and the
last test here pins that asymmetry so it reads as a decision rather than an
oversight.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....domain.user_profile import (
    ProfileBucketMismatchError,
    UserProfileFact,
    UserProfileRecord,
    UserProfileSnapshot,
    new_profile_snapshot_id,
)
from ....tests.secure_sql import isolated_profile_storage_root
from .._orchestration import profile_create_storage_span
from .._repository import UserProfileLifecycleRepository, UserProfileSnapshotRepository

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_A = "c7f3a1b2-9d4e-4a5f-8b6c-1e2d3f4a5b6c"
_PROFILE_B = "a4f1c2e0-1111-4222-8333-444455556666"


def _record(profile_id: str) -> UserProfileRecord:
    return UserProfileRecord(
        profile_id=profile_id,
        display_name="isolation-operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )


def _snapshot(profile_id: str) -> UserProfileSnapshot:
    return UserProfileSnapshot.from_profile(
        _record(profile_id),
        snapshot_id=new_profile_snapshot_id(profile_id),
    )


def test_saving_a_foreign_profile_snapshot_is_refused() -> None:
    repository = UserProfileSnapshotRepository(bucket_id=_BUCKET_A)

    with pytest.raises(ProfileBucketMismatchError):
        repository.save(_snapshot(_PROFILE_B))


def test_a_refused_save_leaves_nothing_readable() -> None:
    foreign = _snapshot(_PROFILE_B)
    repository = UserProfileSnapshotRepository(bucket_id=_BUCKET_A)

    with pytest.raises(ProfileBucketMismatchError):
        repository.save(foreign)

    assert repository.exists(foreign.snapshot_id) is False


def test_a_same_profile_snapshot_round_trips_through_encryption() -> None:
    snapshot = _snapshot(_BUCKET_A)
    repository = UserProfileSnapshotRepository(bucket_id=_BUCKET_A)

    repository.save(snapshot)
    reloaded = repository.load(snapshot.snapshot_id)

    assert reloaded == snapshot
    assert reloaded.profile_id == _BUCKET_A


def test_the_live_profile_repository_is_deliberately_unguarded() -> None:
    """The lifecycle service's duplicate holds one repository for two identities.

    ``duplicate`` reads the source profile and writes the new one through a
    single bucket-bound repository, so a foreign identity is an exercised
    production shape there rather than a leak. Whether that shape should exist
    is a design question about duplication; it is not something a guard can
    settle without simply breaking it. This test exists so the asymmetry with
    the snapshot repository above reads as a decision.
    """
    repository = UserProfileLifecycleRepository(bucket_id=_BUCKET_A)

    repository.save(_record(_PROFILE_B))

    assert repository.load(_PROFILE_B).profile_id == _PROFILE_B


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_A),
    ):
        yield
