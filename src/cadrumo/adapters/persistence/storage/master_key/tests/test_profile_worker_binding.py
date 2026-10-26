"""A worker target survives session turnover and rejects cross-root/profile custody."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from os import stat_result
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity

from ..bucket_session import BucketSession
from ..profile_worker_binding import ProfileWorkerBindingOwner

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def identity() -> ProfileWorkerIdentity:
    return ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="test-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )


def session(target: ProfileWorkerIdentity, root: Path) -> BucketSession:
    now = datetime.now(UTC)
    return BucketSession.open_resumed(
        bucket_id=str(target.binding.profile_id),
        dek=bytes(range(32)),
        idle_minutes=5,
        opened_at=now,
        idle_deadline=now + timedelta(minutes=5),
        absolute_deadline=now + timedelta(minutes=5),
        storage_root=root,
    )


def test_closed_custody_does_not_permit_worker_retargeting(tmp_path: Path) -> None:
    owner, target, other = ProfileWorkerBindingOwner(), identity(), identity()
    owner.bind(target, storage_root=tmp_path)
    first = session(target, tmp_path)
    try:
        owner.require_session(first)
    finally:
        first.close()
    owner.require_session(None)
    owner.bind(target, storage_root=tmp_path / ".")
    with pytest.raises(AutomationCustodyError):
        owner.bind(other, storage_root=tmp_path)
    unexpected = session(other, tmp_path)
    try:
        with pytest.raises(AutomationCustodyError):
            owner.require_session(unexpected)
    finally:
        unexpected.close()


def test_matching_profile_id_in_another_storage_root_is_refused(tmp_path: Path) -> None:
    owner, target = ProfileWorkerBindingOwner(), identity()
    second = tmp_path / "another-root"
    second.mkdir()
    owner.bind(target, storage_root=tmp_path)
    unexpected = session(target, second)
    try:
        with pytest.raises(AutomationCustodyError):
            owner.require_session(unexpected)
        with pytest.raises(AutomationCustodyError):
            owner.bind(target, storage_root=second)
    finally:
        unexpected.close()


def test_replacement_worker_identity_cannot_reuse_the_existing_process(tmp_path: Path) -> None:
    owner, target = ProfileWorkerBindingOwner(), identity()
    owner.bind(target, storage_root=tmp_path)
    for replacement in (
        ProfileWorkerIdentity(worker_id=uuid4(), runtime_boot_id=target.runtime_boot_id, binding=target.binding),
        ProfileWorkerIdentity(worker_id=target.worker_id, runtime_boot_id=uuid4(), binding=target.binding),
    ):
        with pytest.raises(AutomationCustodyError):
            owner.bind(replacement, storage_root=tmp_path)


def test_replacing_the_root_directory_does_not_preserve_its_identity(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    owner, target = ProfileWorkerBindingOwner(), identity()
    owner.bind(target, storage_root=root)
    active = session(target, root)
    try:
        owner.require_session(active)
        root.rename(tmp_path / "displaced-root")
        root.mkdir()
        with pytest.raises(AutomationCustodyError):
            owner.require_session(active)
    finally:
        active.close()


def test_canonical_session_skips_resolution_but_checks_physical_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve()
    owner, target = ProfileWorkerBindingOwner(), identity()
    owner.bind(target, storage_root=root)
    active = session(target, root)
    original_stat = Path.stat
    checked: list[Path] = []

    def no_resolution(self: Path, *, strict: bool = False) -> Path:
        raise AssertionError("canonical session must not repeat native path traversal")

    def stat(self: Path, *, follow_symlinks: bool = True) -> stat_result:
        checked.append(self)
        return original_stat(self, follow_symlinks=follow_symlinks)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(Path, "resolve", no_resolution)
            patch.setattr(Path, "stat", stat)
            for _ in range(3):
                owner.require_session(active)
            assert checked == [root, root, root]
    finally:
        active.close()


def test_noncanonical_session_still_resolves_its_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    child = root / "child"
    child.mkdir()
    owner, target = ProfileWorkerBindingOwner(), identity()
    owner.bind(target, storage_root=root)
    active = session(target, child / "..")
    try:
        owner.require_session(active)
    finally:
        active.close()
