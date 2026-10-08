"""A worker target survives session turnover and rejects cross-root/profile custody."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError

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
